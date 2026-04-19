import json
import litellm

_AI_PROVIDER_KEY  = 'CAPER_AI_PROVIDER'
_AI_API_KEY_KEY   = 'CAPER_AI_API_KEY'
_AI_MODEL_KEY     = 'CAPER_AI_MODEL'
_AI_ENDPOINT_KEY  = 'CAPER_AI_ENDPOINT'

RESERVED_AI_KEYS = {_AI_PROVIDER_KEY, _AI_API_KEY_KEY, _AI_MODEL_KEY, _AI_ENDPOINT_KEY}

VALID_ACTIONS = {
    'navigate', 'click', 'double_click', 'right_click', 'type', 'clear',
    'check', 'uncheck', 'select', 'key_press', 'hover', 'scroll_to',
    'upload_file', 'drag_and_drop', 'wait', 'wait_for_element',
    'wait_for_load_state', 'execute_js', 'screenshot', 'assert_title',
    'assert_text', 'assert_value', 'assert_visible', 'assert_hidden', 'assert_url',
}

_STEP_REFERENCE = """
CRITICAL: Every step object MUST have an "action" field. Use ONLY the exact action
names listed below — do not invent alternatives (e.g. use "type" not "fill", "input",
or "enter_text"; use "navigate" not "goto" or "open_url").

Available actions and their exact JSON shapes:
  navigate            {"action":"navigate","value":"URL"}
  click               {"action":"click","selectorType":"...","selector":"..."}
  double_click        {"action":"double_click","selectorType":"...","selector":"..."}
  right_click         {"action":"right_click","selectorType":"...","selector":"..."}
  type                {"action":"type","selectorType":"...","selector":"...","value":"text"}
  clear               {"action":"clear","selectorType":"...","selector":"..."}
  check               {"action":"check","selectorType":"...","selector":"..."}
  uncheck             {"action":"uncheck","selectorType":"...","selector":"..."}
  select              {"action":"select","selectorType":"...","selector":"...","selectBy":"text","value":"option text"}
  key_press           {"action":"key_press","selectorType":"...","selector":"...","key":"Enter"}
  hover               {"action":"hover","selectorType":"...","selector":"..."}
  scroll_to           {"action":"scroll_to","selectorType":"...","selector":"..."}
  upload_file         {"action":"upload_file","selectorType":"...","selector":"...","value":"/path/to/file"}
  drag_and_drop       {"action":"drag_and_drop","selectorType":"...","selector":"...","targetSelectorType":"...","targetSelector":"..."}
  wait                {"action":"wait","value":"2"}
  wait_for_element    {"action":"wait_for_element","selectorType":"...","selector":"...","value":"5"}
  wait_for_load_state {"action":"wait_for_load_state","value":"networkidle"}
  execute_js          {"action":"execute_js","value":"document.title"}
  screenshot          {"action":"screenshot"}
  assert_title        {"action":"assert_title","value":"expected title fragment"}
  assert_text         {"action":"assert_text","selectorType":"...","selector":"...","value":"expected text"}
  assert_value        {"action":"assert_value","selectorType":"...","selector":"...","value":"expected value"}
  assert_visible      {"action":"assert_visible","selectorType":"...","selector":"..."}
  assert_hidden       {"action":"assert_hidden","selectorType":"...","selector":"..."}
  assert_url          {"action":"assert_url","value":"expected URL fragment"}

Available selectorType values (prefer semantic ones):
  role        — get_by_role, selector format "role:accessible-name" e.g. "button:Sign in"
  aria        — aria-label attribute value
  placeholder — placeholder attribute value
  label       — visible label text
  text        — visible text content
  id          — element id attribute
  css         — CSS selector
  name        — name attribute
  class       — CSS class name
  xpath       — XPath expression
  tag         — HTML tag name
  link_text   — exact anchor text
  partial_link_text — partial anchor text

Prefer selector types in this order: role, aria, placeholder, label, text, id, css.
Use {{VARIABLE_NAME}} for credentials and environment-specific values (e.g. {{BASE_URL}}, {{PASSWORD}}).

Real-world page considerations:
  - After every navigate step, add {"action":"wait","value":"2"} to allow the page to
    fully load and for any cookie consent or GDPR dialogs to appear.
  - If a cookie/consent banner is likely (news sites, weather, e-commerce), add steps
    to dismiss it (e.g. click "Accept all", "Accept cookies", etc.) before interacting
    with page content. Use role or text selectors for consent buttons.
  - Keep the total number of steps reasonable (typically 5-20 for a focused scenario).
"""

_GENERATE_SYSTEM = (
    "You are a test step generator for Caper, a Playwright-based synthetic browser testing platform. "
    "Given a plain-English description of a test scenario, generate a JSON array of Caper test steps. "
    "Return ONLY a valid JSON array — no markdown fences, no explanation, no other text. "
    "Every element of the array must be an object with an 'action' field using one of the exact "
    "action names from the reference. Do not wrap the array in any outer object."
)

_DESCRIBE_SYSTEM = (
    "You are a technical writer reviewing automated browser test steps. "
    "Given a JSON array of Caper test steps, write a concise 1-3 sentence plain-English description "
    "of what the test does. Focus on the user journey and what is being verified. "
    "Do not mention selectors, Playwright, or JSON. Return only the description text."
)


def get_ai_config(team_variables: list) -> dict:
    """Extract AI config from a list of team variable dicts."""
    by_key = {v['key']: v['value'] for v in team_variables}
    return {
        'provider': by_key.get(_AI_PROVIDER_KEY, ''),
        'api_key':  by_key.get(_AI_API_KEY_KEY, ''),
        'model':    by_key.get(_AI_MODEL_KEY, ''),
        'endpoint': by_key.get(_AI_ENDPOINT_KEY, ''),
    }


def _make_completion(config: dict, messages: list) -> str:
    provider = config['provider'].lower()
    model    = config['model']
    api_key  = config['api_key']
    endpoint = config['endpoint']

    kwargs = {'model': model, 'messages': messages}

    if provider == 'ollama':
        kwargs['api_base'] = endpoint or 'http://localhost:11434'
        kwargs['api_key'] = 'ollama'
    else:
        kwargs['api_key'] = api_key

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content.strip()


def _validate_and_clean_steps(steps: list) -> tuple[list, list]:
    """
    Return (valid_steps, dropped_actions).
    Filters out any step missing an 'action' field or with an unrecognised action name.
    """
    valid, dropped = [], []
    for step in steps:
        if not isinstance(step, dict):
            dropped.append(str(step))
            continue
        action = step.get('action', '')
        if action in VALID_ACTIONS:
            valid.append(step)
        else:
            dropped.append(action or '<missing action>')
    return valid, dropped


def generate_test_steps(prompt: str, config: dict) -> tuple[list, list]:
    """
    Call the LLM and return (steps, dropped_actions).
    dropped_actions is a list of action names that were filtered out as unrecognised.
    """
    if not config.get('model'):
        raise ValueError('AI model not configured')

    user_content = (
        f"Test description: {prompt}\n\n"
        f"Step reference:\n{_STEP_REFERENCE}\n\n"
        "Generate the steps array now."
    )

    raw = _make_completion(config, [
        {'role': 'system', 'content': _GENERATE_SYSTEM},
        {'role': 'user',   'content': user_content},
    ])

    # Strip markdown fences if the model wrapped the output anyway
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
        if raw.endswith('```'):
            raw = raw[:-3].strip()

    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError('LLM returned non-array response')

    return _validate_and_clean_steps(parsed)


def describe_test(steps: list, config: dict) -> str:
    """Call the LLM and return a plain-English description string."""
    if not config.get('model'):
        raise ValueError('AI model not configured')

    user_content = f"Test steps:\n{json.dumps(steps, indent=2)}"

    return _make_completion(config, [
        {'role': 'system', 'content': _DESCRIBE_SYSTEM},
        {'role': 'user',   'content': user_content},
    ])
