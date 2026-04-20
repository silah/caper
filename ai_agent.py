"""
Agentic browser loop for AI test generation.

Opens a real Playwright browser, decomposes the user's prompt into sub-goals,
then iterates: take accessibility snapshot → ask LLM for next action → execute →
record step → repeat until each goal is complete.
"""
import json
import threading
import uuid

import litellm
from playwright.sync_api import sync_playwright

from ai_client import VALID_ACTIONS

# ── In-memory task store ──────────────────────────────────────────────────────

_tasks: dict = {}

INTERACTIVE_ROLES = {
    'button', 'link', 'textbox', 'checkbox', 'radio', 'combobox',
    'listbox', 'menuitem', 'searchbox', 'spinbutton', 'switch', 'tab',
    'menuitemcheckbox', 'menuitemradio', 'option', 'treeitem',
}


def create_task() -> str:
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        'status': 'running',
        'steps': [],
        'log': [],
        'test_id': None,
        'error': None,
    }
    return task_id


def get_task(task_id: str) -> dict | None:
    return _tasks.get(task_id)


def start_agent(prompt: str, config: dict, task_id: str, save_callback) -> None:
    """Launch the agent loop in a background daemon thread."""
    t = threading.Thread(
        target=_run_agent,
        args=(prompt, config, task_id, save_callback),
        daemon=True,
    )
    t.start()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _log(task_id: str, msg: str) -> None:
    if task_id in _tasks:
        _tasks[task_id]['log'].append(msg)


def _flatten_tree(node: dict, results: list | None = None, depth: int = 0) -> list:
    """Walk the Playwright accessibility tree and collect interactive elements."""
    if results is None:
        results = []
    if depth > 8:
        return results

    role = node.get('role', '')
    name = (node.get('name') or '').strip()

    if role in INTERACTIVE_ROLES and name:
        entry = f'[{role}] "{name}"'
        if node.get('checked') is not None:
            entry += f' checked={node["checked"]}'
        if node.get('disabled'):
            entry += ' (disabled)'
        results.append(entry)

    for child in node.get('children', []):
        _flatten_tree(child, results, depth + 1)

    return results


def _dom_summary(page) -> str:
    """Return a compact text representation of the page's interactive elements."""
    try:
        tree = page.accessibility.snapshot(interesting_only=True)
        if not tree:
            return 'No accessibility tree available.'
        elements = _flatten_tree(tree)
        if not elements:
            return 'No interactive elements found.'
        # Cap to keep LLM context small
        capped = elements[:100]
        suffix = f'\n... ({len(elements) - 100} more elements not shown)' if len(elements) > 100 else ''
        return '\n'.join(capped) + suffix
    except Exception as e:
        return f'DOM snapshot failed: {e}'


def _resolve_locator(page, selector_type: str, selector: str):
    if selector_type == 'role':
        if ':' in selector:
            role, name = selector.split(':', 1)
            return page.get_by_role(role.strip(), name=name.strip())
        return page.get_by_role(selector.strip())
    elif selector_type == 'aria':
        return page.locator(f'[aria-label="{selector}"]')
    elif selector_type == 'placeholder':
        return page.get_by_placeholder(selector)
    elif selector_type == 'label':
        return page.get_by_label(selector)
    elif selector_type == 'text':
        return page.get_by_text(selector)
    elif selector_type == 'partial_link_text':
        return page.locator(f'a:has-text("{selector}")')
    elif selector_type == 'id':
        return page.locator(f'[id="{selector}"]')
    elif selector_type == 'name':
        return page.locator(f'[name="{selector}"]')
    elif selector_type == 'class':
        return page.locator(f'.{selector}')
    elif selector_type == 'xpath':
        return page.locator(f'xpath={selector}')
    else:
        return page.locator(selector)


def _execute_step(page, step: dict) -> None:
    action = step.get('action')
    sel_type = step.get('selectorType', 'css')
    sel = step.get('selector', '')

    if action == 'navigate':
        page.goto(step['value'], timeout=30000)
        page.wait_for_load_state('domcontentloaded', timeout=30000)
    elif action == 'click':
        _resolve_locator(page, sel_type, sel).click(timeout=10000)
    elif action == 'type':
        _resolve_locator(page, sel_type, sel).fill(step.get('value', ''), timeout=10000)
    elif action == 'wait':
        page.wait_for_timeout(int(float(step.get('value', '1')) * 1000))
    elif action == 'wait_for_load_state':
        page.wait_for_load_state(step.get('value', 'networkidle'), timeout=30000)
    elif action == 'key_press':
        key = step.get('key', 'Enter')
        if sel:
            _resolve_locator(page, sel_type, sel).press(key, timeout=10000)
        else:
            page.keyboard.press(key)
    elif action == 'select':
        el = _resolve_locator(page, sel_type, sel)
        by = step.get('selectBy', 'text')
        val = step.get('value', '')
        if by == 'value':
            el.select_option(value=val, timeout=10000)
        elif by == 'index':
            el.select_option(index=int(val), timeout=10000)
        else:
            el.select_option(label=val, timeout=10000)
    elif action == 'assert_visible':
        _resolve_locator(page, sel_type, sel).wait_for(state='visible', timeout=10000)
    elif action == 'assert_hidden':
        _resolve_locator(page, sel_type, sel).wait_for(state='hidden', timeout=10000)
    elif action == 'assert_url':
        url = page.url
        assert step['value'] in url, f'URL {url!r} does not contain {step["value"]!r}'
    elif action == 'assert_title':
        title = page.title()
        assert step['value'] in title, f'Title {title!r} does not contain {step["value"]!r}'
    elif action == 'assert_text':
        actual = _resolve_locator(page, sel_type, sel).text_content() or ''
        assert step['value'] in actual, f'Text {actual!r} does not contain {step["value"]!r}'
    elif action == 'scroll_to':
        _resolve_locator(page, sel_type, sel).scroll_into_view_if_needed(timeout=10000)
    elif action == 'hover':
        _resolve_locator(page, sel_type, sel).hover(timeout=10000)
    elif action == 'double_click':
        _resolve_locator(page, sel_type, sel).dblclick(timeout=10000)
    elif action == 'check':
        _resolve_locator(page, sel_type, sel).check(timeout=10000)
    elif action == 'uncheck':
        _resolve_locator(page, sel_type, sel).uncheck(timeout=10000)
    elif action == 'clear':
        _resolve_locator(page, sel_type, sel).clear(timeout=10000)
    elif action == 'screenshot':
        pass  # screenshots handled separately if needed


# ── LLM helpers ───────────────────────────────────────────────────────────────

def _llm_call(config: dict, system: str, user: str) -> str:
    provider = config.get('provider', '').lower()
    kwargs = {
        'model': config['model'],
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user',   'content': user},
        ],
    }
    if provider == 'ollama':
        kwargs['api_base'] = config.get('endpoint') or 'http://localhost:11434'
        kwargs['api_key'] = 'ollama'
    else:
        kwargs['api_key'] = config.get('api_key', '')
    resp = litellm.completion(**kwargs)
    return resp.choices[0].message.content.strip()


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
        if raw.endswith('```'):
            raw = raw[:-3].strip()
    return raw


def _decompose_goals(prompt: str, config: dict) -> list[str]:
    system = (
        'You are a browser test planner. Break the user\'s test description into '
        '2-6 sequential sub-goals. Each sub-goal should be a short, specific action phrase. '
        'If a goal involves searching for something, always include a follow-up goal to click '
        'the correct result and land on the destination page. '
        'Return ONLY a JSON array of strings, no other text. '
        'Example: ["Navigate to the login page", "Submit the login form", "Verify the dashboard loaded"]'
    )
    raw = _llm_call(config, system, f'Test description: {prompt}')
    try:
        goals = json.loads(_strip_fences(raw))
        if isinstance(goals, list) and goals:
            return [str(g) for g in goals]
    except Exception:
        pass
    return [prompt]


_ACTION_REFERENCE = """
Return ONE action as a JSON object. Available actions:
  navigate            {"action":"navigate","value":"URL"}
  click               {"action":"click","selectorType":"...","selector":"..."}
  type                {"action":"type","selectorType":"...","selector":"...","value":"text"}
  wait                {"action":"wait","value":"2"}
  wait_for_load_state {"action":"wait_for_load_state","value":"networkidle"}
  key_press           {"action":"key_press","key":"Enter"}
  select              {"action":"select","selectorType":"...","selector":"...","selectBy":"text","value":"option"}
  assert_visible      {"action":"assert_visible","selectorType":"...","selector":"..."}
  assert_url          {"action":"assert_url","value":"fragment"}
  assert_title        {"action":"assert_title","value":"fragment"}
  assert_text         {"action":"assert_text","selectorType":"...","selector":"...","value":"text"}
  goal_complete       {"action":"goal_complete"}

selectorType preference (use what you can SEE in the DOM summary):
  role > aria > id > placeholder > label > css > partial_link_text > text

For role: use format "role:accessible-name" exactly as it appears in the DOM summary.
IMPORTANT: Only use selector values you can see in the DOM summary. Do not guess.
"""


def _next_step(
    current_goal: str,
    completed_goals: list,
    recorded_steps: list,
    current_url: str,
    dom: str,
    failed_selectors: list,
    config: dict,
) -> dict:
    system = (
        'You are a Playwright browser automation agent. '
        'You are shown the current page state and must return the single next action '
        'to make progress toward the current goal. '
        'Use ONLY selector values you can see in the DOM summary — never invent text or names. '
        'IMPORTANT: Before taking any other action, always check the DOM summary for any modal, '
        'banner, or overlay that asks the user to consent to cookies, tracking, or data processing — '
        'regardless of the language the page is in. If such a prompt is present, dismiss it by '
        'clicking the most permissive acceptance option available before doing anything else. '
        'If the current goal is already achieved, return {"action":"goal_complete"}. '
        'IMPORTANT: If you performed a search and results or autocomplete suggestions appeared, '
        'do NOT mark the goal complete — click the most relevant result to navigate to the '
        'destination page first. Goal complete means the page you intended to reach is loaded. '
        'Return ONLY the JSON object, no explanation, no markdown.'
    )

    recent = recorded_steps[-5:] if len(recorded_steps) > 5 else recorded_steps
    clean_recent = [{k: v for k, v in s.items() if k != '_error'} for s in recent]

    user_parts = [
        f'Current URL: {current_url}',
        f'Current goal: {current_goal}',
    ]
    if completed_goals:
        user_parts.append(f'Already completed: {", ".join(completed_goals)}')
    user_parts.append(f'\nPage interactive elements:\n{dom}')
    if clean_recent:
        user_parts.append(f'\nRecent steps:\n{json.dumps(clean_recent, indent=2)}')
    if failed_selectors:
        user_parts.append(f'\nFailed selectors (try something different): {failed_selectors}')
    user_parts.append(f'\n{_ACTION_REFERENCE}')

    raw = _llm_call(config, system, '\n'.join(user_parts))
    return json.loads(_strip_fences(raw))


# ── Main agent loop ───────────────────────────────────────────────────────────

def _run_agent(prompt: str, config: dict, task_id: str, save_callback) -> None:
    task = _tasks[task_id]
    recorded_steps: list = []

    try:
        _log(task_id, 'Decomposing prompt into sub-goals...')
        goals = _decompose_goals(prompt, config)
        _log(task_id, 'Goals: ' + ' → '.join(goals))

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            completed_goals: list[str] = []

            for goal in goals:
                _log(task_id, f'▶ {goal}')
                failed_selectors: list[str] = []
                max_actions = 15

                for _ in range(max_actions):
                    current_url = page.url
                    dom = _dom_summary(page)

                    try:
                        step = _next_step(
                            goal, completed_goals, recorded_steps,
                            current_url, dom, failed_selectors, config,
                        )
                    except Exception as e:
                        _log(task_id, f'  LLM error: {e}')
                        break

                    action = step.get('action')

                    if action == 'goal_complete':
                        _log(task_id, f'  ✓ complete')
                        completed_goals.append(goal)
                        break

                    if action not in VALID_ACTIONS:
                        _log(task_id, f'  Skipped unknown action: {action}')
                        continue

                    selector_desc = step.get('selector') or step.get('value', '')
                    try:
                        _execute_step(page, step)
                        recorded_steps.append(step)
                        task['steps'] = list(recorded_steps)
                        _log(task_id, f'  ✓ {action} {selector_desc}')
                        page.wait_for_timeout(600)
                    except Exception as e:
                        _log(task_id, f'  ✗ {action} "{selector_desc}": {e}')
                        if selector_desc:
                            failed_selectors.append(selector_desc)
                        # Give LLM a chance to try a different selector
                        recorded_steps.append({**step, '_error': str(e)})
                        task['steps'] = [s for s in recorded_steps if '_error' not in s]
                else:
                    _log(task_id, f'  Max actions reached for goal')

            context.close()
            browser.close()

        clean = [s for s in recorded_steps if '_error' not in s]

        if not clean:
            task['status'] = 'error'
            task['error'] = 'No steps were successfully recorded. Try rephrasing your prompt.'
            return

        _log(task_id, f'Saving test with {len(clean)} steps...')
        test_id = save_callback(clean)
        task['test_id'] = test_id
        task['steps'] = clean
        task['status'] = 'complete'
        _log(task_id, f'Done — {len(clean)} steps recorded.')

    except Exception as e:
        task['status'] = 'error'
        task['error'] = str(e)
        _log(task_id, f'Error: {e}')
