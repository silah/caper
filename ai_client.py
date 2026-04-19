import json
import litellm

_AI_PROVIDER_KEY  = 'CAPER_AI_PROVIDER'
_AI_API_KEY_KEY   = 'CAPER_AI_API_KEY'
_AI_MODEL_KEY     = 'CAPER_AI_MODEL'
_AI_ENDPOINT_KEY  = 'CAPER_AI_ENDPOINT'

RESERVED_AI_KEYS = {_AI_PROVIDER_KEY, _AI_API_KEY_KEY, _AI_MODEL_KEY, _AI_ENDPOINT_KEY}

_STEP_REFERENCE = """
Available actions (use exactly these action names):
  navigate          {"action":"navigate","value":"URL"}
  click             {"action":"click","selectorType":"...","selector":"..."}
  double_click      {"action":"double_click","selectorType":"...","selector":"..."}
  right_click       {"action":"right_click","selectorType":"...","selector":"..."}
  type              {"action":"type","selectorType":"...","selector":"...","value":"text"}
  clear             {"action":"clear","selectorType":"...","selector":"..."}
  check             {"action":"check","selectorType":"...","selector":"..."}
  uncheck           {"action":"uncheck","selectorType":"...","selector":"..."}
  select            {"action":"select","selectorType":"...","selector":"...","selectBy":"text","value":"option text"}
  key_press         {"action":"key_press","selectorType":"...","selector":"...","key":"Enter"}
  hover             {"action":"hover","selectorType":"...","selector":"..."}
  scroll_to         {"action":"scroll_to","selectorType":"...","selector":"..."}
  upload_file       {"action":"upload_file","selectorType":"...","selector":"...","value":"/path/to/file"}
  drag_and_drop     {"action":"drag_and_drop","selectorType":"...","selector":"...","targetSelectorType":"...","targetSelector":"..."}
  wait              {"action":"wait","value":"1"}
  wait_for_element  {"action":"wait_for_element","selectorType":"...","selector":"...","value":"5"}
  wait_for_load_state {"action":"wait_for_load_state","value":"networkidle"}
  execute_js        {"action":"execute_js","value":"document.title"}
  screenshot        {"action":"screenshot"}
  assert_title      {"action":"assert_title","value":"expected title fragment"}
  assert_text       {"action":"assert_text","selectorType":"...","selector":"...","value":"expected text"}
  assert_value      {"action":"assert_value","selectorType":"...","selector":"...","value":"expected value"}
  assert_visible    {"action":"assert_visible","selectorType":"...","selector":"..."}
  assert_hidden     {"action":"assert_hidden","selectorType":"...","selector":"..."}
  assert_url        {"action":"assert_url","value":"expected URL fragment"}

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
"""

_GENERATE_SYSTEM = (
    "You are a test step generator for Caper, a Playwright-based synthetic browser testing platform. "
    "Given a plain-English description of a test scenario, generate a JSON array of Caper test steps. "
    "Return ONLY a valid JSON array — no markdown fences, no explanation, no other text."
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
    elif provider == 'gemini':
        kwargs['api_key'] = api_key
    elif provider == 'groq':
        kwargs['api_key'] = api_key
    elif provider in ('openai', 'anthropic'):
        kwargs['api_key'] = api_key
    else:
        kwargs['api_key'] = api_key

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content.strip()


def generate_test_steps(prompt: str, config: dict) -> list:
    """Call the LLM and return a list of step dicts."""
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
            raw = raw[:-3]

    steps = json.loads(raw)
    if not isinstance(steps, list):
        raise ValueError('LLM returned non-array response')
    return steps


def describe_test(steps: list, config: dict) -> str:
    """Call the LLM and return a plain-English description string."""
    if not config.get('model'):
        raise ValueError('AI model not configured')

    user_content = f"Test steps:\n{json.dumps(steps, indent=2)}"

    return _make_completion(config, [
        {'role': 'system', 'content': _DESCRIBE_SYSTEM},
        {'role': 'user',   'content': user_content},
    ])
