# Feature Suggestions

## Alerting & Notifications
- [ ] Email alerts on test failure (in addition to webhooks)
- [ ] Slack/Teams integration as a first-class notification target
- [ ] Alert suppression — don't re-notify until a failing test recovers

## Test Reliability
- [ ] Retry on failure (configurable N retries before marking failed)
- [ ] Flakiness tracking — flag tests that pass/fail inconsistently
- [ ] Step-level timeout configuration (currently global)

## Results & Reporting
- [ ] Test history chart — pass/fail rate over time per test
- [ ] SLA tracking — mark a test as violating SLA if it takes longer than X seconds
- [ ] Export results as PDF or CSV
- [ ] Compare two executions side-by-side

## Test Authoring
- [ ] Record mode — launch a browser, capture clicks/types as steps automatically
- [ ] Variables/secrets — parameterise tests (e.g. `{{BASE_URL}}`, `{{PASSWORD}}`) stored per-team
- [ ] Test chaining — run one test, then another, passing output between them

## Organisation
- [ ] Tags/labels on tests for grouping and filtering
- [ ] Test suites — run a collection of tests as one unit
- [ ] Per-test environment overrides (staging vs. prod URL)

## Operations
- [ ] Health dashboard — single page showing current pass/fail state of all scheduled tests
- [ ] On-call rotation integration — route alerts to whoever is on call
- [ ] Audit log — track who changed what test and when
