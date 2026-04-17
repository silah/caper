# Caper

Caper is a self-hosted synthetic browser testing platform. Write tests once through a web UI, schedule them to run on a cadence, and get instant visibility into whether your web application is behaving correctly — without managing test infrastructure or writing boilerplate code.

Tests run in headless Firefox via Selenium. Every execution produces a video recording, screenshots, step-by-step results, and a HAR of network activity.

---

## Features

### Test Authoring
- **Visual step builder** — compose tests from a library of actions: navigate, click, type, wait, assert title, assert text, scroll, execute JavaScript, screenshot
- **Inline step editing** — edit any step in the table without leaving the page; drag to reorder
- **Import from Splunk Synthetics** — paste a Splunk Synthetics JSON export and Caper maps the steps automatically
- **Variables** — parameterise tests with `{{BASE_URL}}`, `{{PASSWORD}}` etc., stored per team and substituted at run time

### Execution
- **Headless Firefox** — tests run in an isolated Firefox process via GeckoDriver
- **Video recording** — every run produces an MP4 assembled from screenshots captured at 4fps
- **HAR capture** — network activity per step recorded using `window.performance`, no proxy required
- **Retry on failure** — configure N automatic retries before a run is marked as failed
- **SLA tracking** — flag runs that exceed a configured duration threshold

### Scheduling
- **Automatic runs** — enable a schedule on any test and set an interval in minutes
- **Scheduler heartbeat** — background thread logs a heartbeat every 5 minutes so you can confirm it's alive

### Observability
- **Health dashboard** — one page showing the current pass/fail state of every test, with last run time, duration, SLA status, and next scheduled run; auto-refreshes every 30 seconds
- **Execution overview** — visual timeline of runs per test as coloured squares (green = pass, red = fail, orange border = SLA violated); click any square for details
- **Compare executions** — select two runs and view them side by side: video, step results, duration, errors
- **Flakiness detection** — tests with inconsistent results across recent runs are automatically flagged
- **Application log** — structured event log for scheduler activity, test results, webhook calls, and errors; paginated, last 5 hours

### Notifications
- **Webhooks** — send a configurable HTTP GET or POST to any endpoint on test success or failure; self-signed certificates accepted

### Teams
- **Multi-user teams** — register and create or join a team; all tests, executions, and variables are scoped to a team
- **Shared variables** — team-level key/value store for secrets and environment config

---

## Running with Docker (recommended)

```bash
docker compose up --build
```

The app listens on port `5098`. Artefacts (videos, screenshots, HARs) and the SQLite database are persisted via volumes.

## Running locally

```bash
pip install -r requirements.txt
python app.py
```

Requires Firefox and GeckoDriver on your `PATH`, and `ffmpeg` for video assembly.

---

## Project Structure

```
caper/
├── app.py                  # Flask routes, scheduler, subprocess runner
├── database.py             # SQLite schema, migrations, all DB methods
├── test_generator.py       # Generates Python/Selenium scripts from step JSON
├── models.py               # Flask-Login user model
├── requirements.txt
├── Dockerfile
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
│   ├── log.html
│   ├── login.html
│   └── register.html
└── static/
    ├── css/style.css
    └── js/
        ├── app.js          # Step builder, create/edit form logic
        └── har-viewer.js   # Screenshot gallery, HAR renderer, modal
```

---

## Supported Step Actions

| Action | Description |
|---|---|
| `navigate` | Load a URL |
| `click` | Click an element |
| `type` | Type text into an input |
| `wait` | Pause for N seconds |
| `execute_js` | Run arbitrary JavaScript |
| `screenshot` | Mark a screenshot point (continuous capture always active) |
| `assert_title` | Assert the page title contains a string |
| `assert_text` | Assert an element's text contains a string |
| `scroll_to` | Scroll an element into view |

Selectors support: CSS, ID, XPath, Name, Class, Tag, Link Text, Partial Link Text.

---

## Roadmap

See [feature-suggestions.md](feature-suggestions.md) for the full backlog. Key items on the horizon:

- **Email / Slack alerts** on test failure
- **Record mode** — capture a real browser session as test steps automatically
- **Test suites** — group tests and run them as a unit
- **Test history charts** — pass/fail rate over time per test
- **Tags and filtering** — organise tests with labels
- **Audit log** — track who changed what and when
- **Per-test environment overrides** — run the same test against staging and production
