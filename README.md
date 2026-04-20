# Caper

Caper is a self-hosted synthetic browser testing platform. Write tests once through a web UI, schedule them to run on a cadence, and get instant visibility into whether your web application is behaving correctly — without managing test infrastructure or writing boilerplate code.

Tests run in headless Firefox or Chrome via Playwright. Every execution produces a video recording, per-step screenshots, step-by-step results, and a full HAR of network activity.

---

## Features

### Test Authoring
- **Visual step builder** — compose tests from a library of 25 actions: navigate, click, type, assert, scroll, drag-and-drop, file upload, and more
- **Inline step editing** — edit any step in the table without leaving the page; drag to reorder
- **Import from Splunk Synthetics** — paste a Splunk Synthetics JSON export and Caper maps the steps automatically; native Caper step JSON is also accepted directly
- **Variables** — parameterise tests with `{{BASE_URL}}`, `{{PASSWORD}}` etc., stored per team and substituted at run time
- **Tags** — label tests by status, environment, application, or suite for filtering and grouping

### Execution
- **Multi-browser** — choose Firefox or Chrome per test; both run headless via Playwright's managed browser installs
- **Video recording** — every run produces an MP4 via Playwright's native `record_video_dir`; no ffmpeg screen capture required for recording, only for final .webm → .mp4 conversion
- **HAR capture** — full network trace recorded natively by Playwright (`record_har_path`); captures real status codes, headers, and timings without a proxy
- **Per-step screenshots** — `page.screenshot()` called in the `finally` block of every step
- **Retry on failure** — configure N automatic retries before a run is marked as failed
- **SLA tracking** — flag runs that exceed a configured duration threshold

### Scheduling
- **Automatic runs** — enable a schedule on any test and set an interval in minutes
- **Scheduler heartbeat** — background thread logs a heartbeat every 10 ticks so you can confirm it's alive

### Test Suites
- **Suites** — group tests into an ordered collection and run them as a unit
- **Stop on failure** — optionally halt a suite run when a test fails
- **Suite execution history** — per-run view showing per-test pass/fail, duration, and error detail

### Observability
- **Health dashboard** — one page showing the current pass/fail state of every test, with last run time, duration, SLA status, and next scheduled run; auto-refreshes every 30 seconds
- **Execution overview** — visual timeline of runs per test as coloured squares (green = pass, red = fail, orange border = SLA violated); click any square for details
- **Compare executions** — select two runs and view them side by side: video, step results, duration, errors
- **Flakiness detection** — tests with inconsistent results across recent runs are automatically flagged
- **Application log** — structured event log for scheduler activity, test results, webhook calls, and errors; paginated, last 5 hours

### Notifications
- **Webhooks** — send a configurable HTTP GET or POST to any endpoint on test success or failure; self-signed certificates accepted

### AI Test Generation
- **Quick generation** — describe a test in plain English and an LLM generates the step sequence in a single call; supports `{{VARIABLE_NAME}}` substitution in prompts
- **Smart generation (agentic)** — opens a real headless browser, decomposes the prompt into sub-goals, then iterates: take accessibility snapshot → ask LLM for the next action → execute → repeat; the LLM only uses selector values it can actually see in the DOM, eliminating hallucinated text
- **Cookie consent handling** — the agent automatically detects and dismisses cookie/GDPR banners in any language before proceeding with each goal
- **Describe existing test** — send any test's steps to the LLM and receive a plain-English summary of what it does
- **Bring your own LLM** — configure any provider supported by [LiteLLM](https://github.com/BerriAI/litellm): OpenAI, Anthropic, Google Gemini, Groq, Ollama (local), and more; API key and model are stored as reserved team variables (`CAPER_AI_*`)
- **Live model picker** — the Variables page fetches available models directly from each provider's API so you always see a current list

### Teams
- **Multi-user teams** — register and create or join a team; all tests, executions, and variables are scoped to a team
- **Shared variables** — team-level key/value store for secrets and environment config

---

## Running with Docker (recommended)

```bash
docker compose up --build
```

The app listens on port `5098`. Artefacts (videos, screenshots, HARs) and the SQLite database are persisted via volumes.

Playwright browsers (Firefox and Chromium) are installed inside the image at build time via `playwright install --with-deps`. No separate browser or driver installation is needed.

## Running locally

```bash
pip install -r requirements.txt
playwright install --with-deps chromium firefox
python app.py
```

Requires `ffmpeg` on your `PATH` for .webm → .mp4 video conversion.

---

## Project Structure

```
caper/
├── app.py                      # Flask routes, scheduler, subprocess runner
├── database.py                 # SQLite schema, migrations, all DB methods
├── test_generator.py           # Generates Playwright scripts from step JSON
├── ai_client.py                # LiteLLM wrapper: quick generation and test description
├── ai_agent.py                 # Agentic browser loop: goal decomposition, DOM snapshot, step execution
├── models.py                   # Flask-Login user model
├── requirements.txt
├── Dockerfile
├── internal_test_seed.json     # Importable test covering all actions and selectors
├── templates/
│   ├── index.html
│   ├── create_test.html
│   ├── edit_test.html
│   ├── view_tests.html
│   ├── view_executions.html
│   ├── test_detail.html
│   ├── health.html
│   ├── compare.html
│   ├── variables.html
│   ├── tags.html
│   ├── suites.html
│   ├── suite_detail.html
│   ├── suite_executions.html
│   ├── suite_execution_detail.html
│   ├── internal_testing.html   # /internal-testing test-bed page
│   ├── internal_testing_p2.html
│   ├── log.html
│   ├── login.html
│   └── register.html
└── static/
    ├── css/style.css
    └── js/
        ├── app.js              # Step builder, create/edit form logic
        └── har-viewer.js       # Screenshot gallery, HAR renderer, modal
```

---

## Supported Step Actions

| Action | Description |
|---|---|
| `navigate` | Load a URL |
| `click` | Click an element |
| `double_click` | Double-click an element |
| `right_click` | Right-click an element |
| `type` | Fill an input (replaces existing value atomically) |
| `clear` | Clear an input field |
| `check` | Check a checkbox or radio button |
| `uncheck` | Uncheck a checkbox |
| `select` | Choose an option from a `<select>` dropdown (by text, value, or index) |
| `key_press` | Send a key (Enter, Tab, Escape, Arrow keys, etc.) to an element or focused element |
| `hover` | Move the mouse over an element |
| `drag_and_drop` | Drag a source element onto a target element |
| `upload_file` | Set a file on a file input (`<input type="file">`) |
| `wait` | Pause for N seconds |
| `wait_for_element` | Wait up to N seconds for an element to become visible |
| `wait_for_load_state` | Wait for the page to reach `load`, `domcontentloaded`, or `networkidle` |
| `execute_js` | Run arbitrary JavaScript via `page.evaluate()` |
| `screenshot` | Capture an explicit screenshot at this point in the test |
| `scroll_to` | Scroll an element into view |
| `assert_title` | Assert the page title contains a string |
| `assert_text` | Assert an element's text content contains a string |
| `assert_value` | Assert an input's current value contains a string |
| `assert_visible` | Assert an element is present and visible |
| `assert_hidden` | Assert an element is not visible (hidden or removed from DOM) |
| `assert_url` | Assert the current URL contains a string |

---

## Supported Selector Types

| Type | Resolved via | Example value |
|---|---|---|
| `css` | `page.locator(value)` | `#submit-btn`, `.card:first-child` |
| `id` | `page.locator('[id="value"]')` | `submit-btn` |
| `xpath` | `page.locator('xpath=value')` | `//button[@type='submit']` |
| `name` | `page.locator('[name="value"]')` | `email` |
| `class` | `page.locator('.value')` | `btn-primary` |
| `tag` | `page.locator('value')` | `button`, `meter` |
| `link_text` | `page.locator('a:text-is("value")')` | `Sign in` |
| `partial_link_text` | `page.locator('a:has-text("value")')` | `Sign` |
| `aria` | `page.locator('[aria-label="value"]')` | `close-modal` |
| `text` | `page.get_by_text(value)` | `Submit` |
| `label` | `page.get_by_label(value)` | `Email address` |
| `placeholder` | `page.get_by_placeholder(value)` | `Enter your email` |
| `role` | `page.get_by_role(role, name=name)` | `button:Submit` |
| `jspath` | `page.evaluate_handle('() => (value)')` | `document.querySelector('.btn')` |

Selectors are strict by default — if a locator resolves to more than one element the step fails, which catches ambiguous selectors early.

**role** format: `role:accessible-name`, e.g. `button:Submit` or `textbox:Email`.

---

## Internal Test Bed

`/internal-testing` is a built-in page designed to validate every step action and every selector type. Import `internal_test_seed.json` via the Tests → Import button to create a ready-made test that exercises all 25 actions and all 14 selector types in a single run. Set `INT_TEST_USER` and `INT_TEST_PW` as team variables before running.

---

## AI Configuration

AI features are configured via the **Variables** page. Set the following reserved team variables:

| Variable | Description |
|---|---|
| `CAPER_AI_PROVIDER` | Provider name: `openai`, `anthropic`, `gemini`, `groq`, or `ollama` |
| `CAPER_AI_MODEL` | Model identifier, e.g. `gemini/gemini-2.5-flash`, `claude-sonnet-4-6`, `gpt-4o` |
| `CAPER_AI_API_KEY` | Your provider API key (not required for Ollama) |
| `CAPER_AI_ENDPOINT` | Custom base URL — required for Ollama (e.g. `http://localhost:11434`), optional otherwise |

These keys are hidden from the main variables table and cannot be used as test step variables.

---

## Roadmap

See [feature-suggestions.md](feature-suggestions.md) for the full backlog. Key items on the horizon:

- **Email / Slack alerts** on test failure
- **Record mode** — capture a real browser session as test steps automatically
- **Test history charts** — pass/fail rate over time per test
- **Audit log** — track who changed what and when
- **Per-test environment overrides** — run the same test against staging and production
