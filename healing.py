"""
Self-healing module for Caper.

Diagnoses failed test steps using the configured LLM (same provider/key/model
as the rest of the AI features), then suggests or auto-applies selector fixes.
"""
import base64
import json
import os
import re

import ai_client

# ── Custom step glossary ──────────────────────────────────────────────────────
# Only injected for step types that are actually present in the failing test,
# keeping prompts short and focused.

CUSTOM_STEP_GLOSSARY = {
    "pick_random": """\
pick_random is a Caper-specific step (not a standard Playwright concept) that:
  1. Waits for the first element matching a CSS selector to appear in the DOM.
  2. Fetches ALL elements matching that selector via locator.all().
  3. Optionally filters out elements that also match an exclude selector (e.g. .sold-out).
  4. Picks one element at random using Python's random.choice().
  5. Captures its inner text or a named HTML attribute and stores it in a runtime
     variable (e.g. {{selected_product}}) for use in later steps.
  6. Optionally clicks the picked element.

Common failure reasons for pick_random:
  - No elements matched the selector (page not fully loaded, selector changed, or
    all candidates were filtered out by the exclude rule).
  - The picked element existed but was not interactable (obscured, off-screen).
  - The captured attribute or text was empty after picking.

NOTE: pick_random failures are always surfaced for human review — do not
auto-apply a fix, set requires_human_review=true.""",

    "click_if_exists": """\
click_if_exists is a Caper-specific step (not a standard Playwright concept) that:
  1. Checks if an element matching the selector exists in the DOM AND is visible.
  2. If found and visible: clicks it and records status 'success'.
  3. If not found or not visible: records status 'skipped' and continues — this is
     NOT a failure, it is intentional tolerant behaviour.
  4. Only records status 'error' if the element was found but the click itself threw
     an exception (e.g. element was covered by another element).

This step is designed for elements that appear inconsistently (cookie banners,
modals, promotional overlays). A 'skipped' result is expected correct behaviour.
If this step shows status 'error' (NOT 'skipped'), the element existed but could
not be clicked — that is the actual failure to diagnose.""",
}

# ── Error pattern classification ──────────────────────────────────────────────

# Errors that suggest the selector itself is broken — healable
_HEALABLE_PATTERNS = [
    r'strict mode violation',
    r'no elements',
    r'element.*not found',
    r'locator.*did not match',
    r'timeout.*waiting',
    r'element.*not.*attached',
    r'element.*detached',
]

# Errors that are real test failures — do NOT attempt to heal
_ASSERTION_PATTERNS = [
    r"expected.*got",
    r"AssertionError",
    r"Expected.*to contain",
    r"assert.*failed",
]

# Step types that should never be auto-healed
_NON_HEALABLE_ACTIONS = {
    'navigate', 'wait', 'wait_for_load_state', 'execute_js',
    'pick_random',  # randomness makes retry unreliable
}


def is_healable(step: dict, error_msg: str) -> bool:
    """Return True if this failure looks like a selector drift worth diagnosing."""
    action = step.get('action', '')
    if action in _NON_HEALABLE_ACTIONS:
        return False
    for pat in _ASSERTION_PATTERNS:
        if re.search(pat, error_msg, re.IGNORECASE):
            return False
    for pat in _HEALABLE_PATTERNS:
        if re.search(pat, error_msg, re.IGNORECASE):
            return True
    # Default: still worth diagnosing even if pattern unrecognised
    return True


# ── Screenshot encoding ───────────────────────────────────────────────────────

def _encode_screenshot(path: str) -> str | None:
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception:
        return None


def _screenshot_path_for_step(artefact_dir: str, step_number: int,
                               base_artefacts_dir: str) -> str | None:
    """Return the filesystem path to the screenshot taken at a given step number."""
    if not artefact_dir:
        return None
    path = os.path.join(base_artefacts_dir, artefact_dir,
                        'screenshots', f'{step_number:04d}.png')
    return path if os.path.exists(path) else None


# ── Prompt assembly ───────────────────────────────────────────────────────────

def _build_glossary_section(steps: list) -> str:
    actions = {s.get('action') for s in steps if isinstance(s, dict)}
    relevant = {k: v for k, v in CUSTOM_STEP_GLOSSARY.items() if k in actions}
    if not relevant:
        return ''
    parts = ['The following custom step types are used in this test:\n']
    for action, desc in relevant.items():
        parts.append(f'[{action}]\n{desc}')
    return '\n\n'.join(parts)


def _build_system_prompt(steps: list) -> str:
    parts = [
        "You are a test automation engineer diagnosing a broken UI test. "
        "The test was written against a web application that may have since changed. "
        "Your job is to determine what changed and, where possible, suggest a corrected "
        "CSS selector. Respond ONLY with a valid JSON object — no markdown, no explanation."
    ]
    glossary = _build_glossary_section(steps)
    if glossary:
        parts.append(glossary)
    return '\n\n'.join(parts)


def _build_user_prompt(test: dict, step: dict, step_index: int,
                       step_result: dict, prior_results: list) -> str:
    step_desc = {
        'step_number': step_index + 1,
        'action': step.get('action'),
        'selector': step.get('selector', ''),
        'selectorType': step.get('selectorType', ''),
        'intent': step.get('intent') or 'not provided',
        'error_message': step_result.get('message', ''),
    }
    prior_summary = [
        {
            'step': r.get('step'),
            'action': r.get('action'),
            'status': r.get('status'),
            'message': (r.get('message') or '')[:200],
        }
        for r in prior_results
    ]
    return (
        f"Test name: {test.get('name', '')}\n"
        f"Test goal: {test.get('description') or 'not provided'}\n\n"
        f"Failed step:\n{json.dumps(step_desc, indent=2)}\n\n"
        f"Steps that ran before this failure:\n{json.dumps(prior_summary, indent=2)}\n\n"
        "Respond with this exact JSON shape:\n"
        "{\n"
        '  "diagnosis": "one paragraph plain English explaining what you think changed",\n'
        '  "confidence": "high | medium | low",\n'
        '  "suggested_selector": "new CSS selector string, or null",\n'
        '  "suggested_selector_type": "css | id | xpath | aria | text | null",\n'
        '  "reasoning": "brief explanation of why you chose this selector",\n'
        '  "is_assertion_failure": false,\n'
        '  "requires_human_review": false\n'
        "}"
    )


# ── Main diagnosis function ───────────────────────────────────────────────────

def diagnose_step(test: dict, step: dict, step_index: int, step_result: dict,
                  all_step_results: list, config: dict,
                  base_artefacts_dir: str = '') -> dict:
    """
    Call the configured LLM to diagnose a single failed step.
    Returns a diagnosis dict with keys: diagnosis, confidence, suggested_selector,
    suggested_selector_type, reasoning, is_assertion_failure, requires_human_review.
    """
    raw_steps = test.get('steps', '[]')
    steps = json.loads(raw_steps) if isinstance(raw_steps, str) else raw_steps

    system = _build_system_prompt(steps)
    prior = all_step_results[:step_index]
    user_text = _build_user_prompt(test, step, step_index, step_result, prior)

    # Try to attach the screenshot taken at this step
    artefact_dir = test.get('_artefact_dir', '')  # injected by caller if available
    screenshot_path = _screenshot_path_for_step(
        artefact_dir, step_index + 1, base_artefacts_dir
    )
    img_b64 = _encode_screenshot(screenshot_path) if screenshot_path else None

    if img_b64:
        user_content = [
            {'type': 'text', 'text': user_text},
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64}'}},
        ]
    else:
        user_content = user_text

    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user_content},
    ]

    try:
        raw = ai_client._make_completion(config, messages)
        raw = raw.strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
            raw = raw.rstrip('`').strip()
        result = json.loads(raw)
    except Exception as e:
        result = {
            'diagnosis': f'Diagnosis request failed: {e}',
            'confidence': 'low',
            'suggested_selector': None,
            'suggested_selector_type': None,
            'reasoning': '',
            'is_assertion_failure': False,
            'requires_human_review': True,
        }

    # pick_random always requires human review regardless of LLM response
    if step.get('action') == 'pick_random':
        result['requires_human_review'] = True
        result['suggested_selector'] = None

    return result


# ── Full execution diagnosis ──────────────────────────────────────────────────

def diagnose_execution(test: dict, execution: dict, config: dict,
                       base_artefacts_dir: str = '') -> dict:
    """
    Run diagnosis on all healable failed steps in an execution.
    Returns a healing_data dict suitable for storing on the execution record.
    """
    raw_steps = test.get('steps', '[]')
    steps = json.loads(raw_steps) if isinstance(raw_steps, str) else raw_steps

    raw_results = execution.get('step_results') or '[]'
    try:
        step_results = json.loads(raw_results)
    except Exception:
        step_results = []

    # Attach artefact_dir so diagnose_step can find screenshots
    test = dict(test)
    test['_artefact_dir'] = execution.get('artefact_dir', '')

    healing_data = {
        'triggered': True,
        'steps_diagnosed': [],
        'steps_healed': [],
        'diagnoses': {},
    }

    for result in step_results:
        if result.get('status') != 'error':
            continue
        # step_results are 1-indexed; steps list is 0-indexed
        step_num = result.get('step', 0)
        step_index = step_num - 1
        if step_index < 0 or step_index >= len(steps):
            continue

        step = steps[step_index]
        error_msg = result.get('message', '')

        if not is_healable(step, error_msg):
            continue

        healing_data['steps_diagnosed'].append(step_num)
        diagnosis = diagnose_step(
            test, step, step_index, result, step_results,
            config, base_artefacts_dir,
        )
        healing_data['diagnoses'][str(step_num)] = {
            'original_selector': step.get('selector', ''),
            'original_selector_type': step.get('selectorType', ''),
            'intent': step.get('intent', ''),
            **diagnosis,
            'auto_applied': False,
        }

    return healing_data
