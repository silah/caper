Self-Healing Tests
==================

Feature specification for intent-aware, AI-driven test healing in Caper.
Written: 2026-04-26


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. OVERVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When a test step fails because the UI has changed — a selector was
renamed, a flow was restructured, a button was moved — the current
behaviour is a hard failure with a raw Playwright error message. The
engineer must manually open the test, find the broken step, inspect
the live site, and update the selector.

Self-healing replaces that with:

  1. An LLM diagnoses the failure using the DOM snapshot, screenshot,
     error message, and the step's stated intent.
  2. If the failure is a simple selector drift, the LLM suggests a
     replacement selector and retries the step automatically.
  3. If the step passes with the new selector, the fix is saved back
     to the test definition and flagged as a healed change.
  4. If the LLM cannot confidently suggest a fix, it produces a plain-
     English diagnosis and surfaces it on the execution detail page for
     human review.

The key design principle throughout: healing is assistive, not silent.
Every healed change is visible, reviewable, and reversible. The system
never modifies a test without a human being able to see what changed
and why.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. THE INTENT FIELD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2.1 What it is
--------------
Every step gains an optional `intent` string — a plain-English
description of what that step is supposed to accomplish from the
user's perspective, not from a technical perspective.

Good intent:
  "Click the checkout button to move from the basket to payment"

Bad intent (too technical, restates the selector):
  "Click element #checkout-btn"

The distinction matters because the intent survives selector changes.
When #checkout-btn becomes data-testid="proceed-to-checkout", the
intent is still valid and gives the LLM the context it needs to find
the right replacement.

2.2 Where it is stored
-----------------------
The `intent` field is stored on each step object in the `steps` JSON
column of the `tests` table. It is part of the step definition, not
the execution record. This means:

  - It persists across all future executions of that test.
  - It is included when the test is exported or duplicated.
  - It is visible in the test builder UI alongside the step.
  - It travels with the test if the test is used in a suite.

Storing it on the step rather than on the execution record is a
deliberate choice. Execution records are immutable history — they
describe what happened. Step definitions describe intent. Mixing them
would couple the test definition to a specific run.

2.3 How it gets populated — two paths
--------------------------------------

PATH A: AI-generated tests

When a test is created via the AI generator (either Quick or Smart
mode), the LLM already produces the full step list. We extend the
generation prompt to also return an `intent` field on every step in
the same JSON response. This costs nothing extra — same API call,
same latency, one more field per step object.

The prompt addition:
  "For each step, include an 'intent' field: a one-sentence plain-
  English description of what this step achieves from the user's
  perspective. Focus on the goal, not the mechanism."

This is the highest-quality path because the LLM that designed the
test also knows exactly why each step exists. It has the full test
goal in context and can write precise, meaningful intents.

PATH B: Manually built tests (lazy capture)

For tests built by hand in the step builder, the intent field is
optional and starts empty. We do not force users to fill it in
upfront — most will not, and empty fields on a form create friction
without adding value until a failure actually occurs.

Instead, intent is captured reactively on first failure:

  - A step fails with no intent stored.
  - The execution detail page shows an inline prompt on that step:
    "What was this step supposed to do? (Used to diagnose failures)"
  - The user types a one-line explanation and submits.
  - The intent is saved back to the step definition immediately via
    a PATCH API call.
  - The AI diagnosis is then (re-)triggered with the newly captured
    intent — without re-running the full test.

Why lazy rather than upfront?

  a) People write better explanations when something is broken and
     they are actively thinking about what it should do. The failure
     context focuses the mind.
  b) Many steps are self-evident (navigate to URL, wait for element).
     Forcing intents on those adds noise.
  c) Reduces the activation energy of creating a test — fewer
     required fields means faster test authoring.
  d) Over time, as tests fail and intents are filled in, the test
     suite builds up a library of intent coverage organically,
     prioritised by which steps actually break.

The intent field IS available in the step builder UI for users who
want to fill it in proactively — it is just not required.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. THE CUSTOM STEP GLOSSARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Caper has custom step types that no LLM knows about natively:
pick_random and click_if_exists. When one of these fails, the LLM
cannot reason about why without understanding what the step does.

The solution is a glossary injected into the system prompt of every
healing or diagnosis request. The glossary is a Python dict in
ai_agent.py (or a new healing module) mapping step action names to
plain-English descriptions:

CUSTOM_STEP_GLOSSARY = {
    "pick_random": """
        pick_random is a Caper-specific step that:
        1. Waits for the first element matching a CSS selector to
           appear in the DOM.
        2. Fetches ALL elements matching that selector.
        3. Optionally filters out elements that also match an exclude
           selector (e.g. .out-of-stock).
        4. Picks one element at random using random.choice().
        5. Captures its inner text or a named HTML attribute and
           stores it in a runtime variable (e.g. {{selected_product}}).
        6. Optionally clicks the picked element.

        Common failure reasons:
        - No elements matched the selector (page not loaded, selector
          changed, or all items were filtered out by the exclude rule).
        - The picked element was present but not interactable (covered
          by another element, outside viewport).
        - The captured attribute or text was empty.
    """,

    "click_if_exists": """
        click_if_exists is a Caper-specific step that:
        1. Checks if an element matching the selector exists in the DOM
           AND is currently visible.
        2. If found: clicks it and records status 'success'.
        3. If not found: records status 'skipped' and continues — this
           is NOT a failure.
        4. Only records status 'error' if the element was found but
           the click itself threw an exception.

        This step is intentionally tolerant of absence. A 'skipped'
        result is expected and correct behaviour. If this step shows
        status 'error' (not 'skipped'), the element existed but could
        not be clicked — that is the failure to diagnose.
    """
}

Why store this in Python rather than in the prompt template?

  - It can be updated independently as custom steps evolve.
  - It can be selectively included — only inject glossary entries for
    step types actually present in the failing test, keeping prompts
    shorter.
  - It is testable in isolation.
  - Future custom steps automatically get a slot in the glossary
    without changing the prompt assembly logic.

Standard step types (click, type, navigate, assert_text, etc.) do not
need glossary entries — the LLM already knows Playwright semantics
from training data. We only describe what is genuinely novel.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. THE HEALING FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4.1 Trigger
-----------
Healing is triggered when a test execution ends with status 'error'
AND at least one step has status 'error' in its step_results. It is
NOT triggered for:

  - Timeout failures (the page may genuinely be down).
  - Assertion failures where the element was found but the value was
    wrong — that is a real test failure, not a selector problem.
  - Steps with status 'skipped' (click_if_exists — expected).

The distinction between "selector broken" and "assertion failed" is
important. If a click step fails with "element not found", the UI
probably changed. If an assert_text step fails with "expected 'In
Stock' but got 'Out of Stock'", the site's data changed — healing
the selector would not help and could mask a genuine regression.

The code distinguishes these by inspecting the error message:
  - "strict mode violation" → selector matches too many elements
  - "element not found" / "no elements" → selector matches nothing
  - "timeout" → element didn't appear in time
  - "Expected ... got ..." → assertion failure — do not attempt heal

4.2 What is sent to the LLM
-----------------------------
For each failed step, the healing prompt contains:

  [SYSTEM]
  You are a test automation engineer diagnosing a broken UI test.
  The test was written against a web application that has since
  changed. Your job is to determine what changed and, where possible,
  suggest a corrected selector.

  {CUSTOM_STEP_GLOSSARY — only entries relevant to this test}

  [USER]
  Test name: {test.name}
  Overall test goal: {test.description}

  Failed step:
    Step number: {i}
    Action: {step.action}
    Original selector: {step.selector} (type: {step.selectorType})
    Intent: {step.intent or "not provided"}
    Error: {step_result.message}

  Screenshot at point of failure: [attached as base64 image]

  Current DOM snapshot (area around expected element):
  {trimmed_dom_fragment}

  All step results up to this point:
  {step_results_so_far}

  Please respond with a JSON object:
  {
    "diagnosis": "one paragraph plain English — what you think changed",
    "confidence": "high | medium | low",
    "suggested_selector": "the new CSS selector, or null if you cannot suggest one",
    "suggested_selector_type": "css | xpath | etc, or null",
    "reasoning": "why you chose this selector",
    "is_assertion_failure": true/false,
    "requires_human_review": true/false
  }

Why include the screenshot?

The DOM alone can be misleading — an element might exist in the DOM
but be hidden behind a modal, or the layout may have changed so what
the test intended to click is no longer in the expected location.
The screenshot grounds the LLM in what the user actually saw at the
moment of failure, not just what was in the HTML.

Why include all step results up to the failure?

Context about what succeeded before the failure is valuable. If steps
1-4 passed and step 5 failed, the LLM knows the page loaded correctly
and the failure is isolated to this specific interaction. If step 1
(navigate) failed, the LLM should flag a connectivity or URL problem,
not a selector problem.

Why trim the DOM rather than send the full page?

Full page HTML for a real eCommerce site can be 500KB+. That exhausts
context, increases cost, and buries the relevant fragment in noise.
The trimmed fragment strategy:

  1. Try to find any element that partially matches the broken selector
     (e.g. if `.checkout-btn` is gone, look for any element with
     "checkout" in its class, id, or aria-label).
  2. If found, extract that element plus its 3 levels of ancestors and
     2 levels of siblings — enough structural context to understand
     the surrounding layout.
  3. If nothing partial matches, send the innerText + tag structure of
     the nearest landmark region (main, section, form, etc.).
  4. Hard cap at 8000 characters.

4.3 Confidence thresholds and actions
--------------------------------------
The LLM returns a confidence level. The action taken depends on it:

HIGH confidence + suggested_selector present:
  - Retry the step immediately with the suggested selector.
  - If the retry passes: save the new selector to the test definition,
    mark the execution as 'healed', add a healing record to the DB.
  - If the retry fails: downgrade to MEDIUM path.

MEDIUM confidence + suggested_selector present:
  - Do NOT retry automatically.
  - Show the suggestion on the execution detail page with a
    one-click "Apply and re-test" button.
  - Human decides whether to apply it.

LOW confidence OR no suggested_selector:
  - Show the diagnosis text only.
  - Prompt the user for intent if not already captured.
  - No selector suggestion is shown.

is_assertion_failure = true:
  - Show the diagnosis only. Never suggest a selector fix.
  - The failure message makes clear this is a data/logic issue,
    not a structural one.

requires_human_review = true:
  - Always surface for review regardless of confidence.
  - Used when the LLM detects the flow itself may have changed
    (e.g. a checkout button that no longer exists at all because
    the checkout flow was restructured).

Why not always auto-apply high-confidence suggestions?

Auto-applying even high-confidence suggestions carries risk: the LLM
might find a selector that makes the step pass but targets the wrong
element. For example, if the "Add to basket" button was removed and
replaced with "Add to wishlist", a naive healer might find the
wishlist button and report the test as passing when the intended
functionality is broken.

The retry-and-pass check mitigates but does not eliminate this risk.
The healing record in the DB gives humans a way to audit and revert.
For a first implementation, auto-applying only on HIGH confidence with
a visible audit trail is the right balance.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. DATABASE CHANGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5.1 tests table — step intent
------------------------------
No schema change needed. The `steps` column already stores a JSON
array of step objects. The `intent` field is simply added to each
step object. Old steps without an intent field behave as if
intent = null.

5.2 executions table — healing metadata
-----------------------------------------
Add column: `healing_data TEXT`

Stores a JSON object on executions that were diagnosed or healed:
{
  "triggered": true,
  "steps_diagnosed": [2, 5],
  "steps_healed": [2],
  "diagnoses": {
    "2": {
      "original_selector": "#checkout-btn",
      "suggested_selector": "[data-testid='proceed-to-checkout']",
      "confidence": "high",
      "diagnosis": "The checkout button selector changed...",
      "auto_applied": true
    }
  }
}

This is stored on the execution record (immutable history) so you can
always see what the test looked like at the time of the failure and
what was suggested, even if the test has been updated since.

5.3 New table: healing_log
---------------------------
CREATE TABLE healing_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  test_id INTEGER NOT NULL,
  execution_id INTEGER NOT NULL,
  step_index INTEGER NOT NULL,
  original_selector TEXT,
  original_selector_type TEXT,
  new_selector TEXT,
  new_selector_type TEXT,
  confidence TEXT,
  diagnosis TEXT,
  applied_at TIMESTAMP,
  applied_by TEXT,       -- 'auto' or username
  reverted_at TIMESTAMP,
  reverted_by TEXT,
  FOREIGN KEY (test_id) REFERENCES tests (id),
  FOREIGN KEY (execution_id) REFERENCES executions (id)
)

Why a separate table rather than just the executions column?

The healing_log is a ledger of changes to test definitions. It needs
to be queryable across tests ("show me all auto-healed changes in the
last 7 days"), reversible ("revert step 3 of test X to its state
before healing"), and auditable by user. The executions column is for
per-run context — the log is for the history of the test definition
itself. Keeping them separate honours the distinction between
"what happened in this run" and "how this test has changed over time".


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. API CHANGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

POST /api/executions/<id>/diagnose
  Triggers AI diagnosis on a completed failed execution.
  Returns the diagnosis JSON.
  Can be called manually from the execution detail page.
  Also called automatically by _run_test_subprocess on failure.

POST /api/executions/<id>/apply-heal
  Body: { step_index: 2, selector: "...", selector_type: "css" }
  Applies a suggested selector to the test definition.
  Writes a healing_log record.
  Returns the updated test.

PATCH /api/tests/<id>/steps/<step_index>/intent
  Body: { intent: "Click the checkout button to proceed to payment" }
  Saves the intent field on a specific step without requiring a full
  test save. Used by the lazy intent capture flow on the execution
  detail page.
  After saving, optionally re-triggers diagnosis if execution_id
  is provided in the body.

GET /api/tests/<id>/healing-log
  Returns the healing history for a test — all past healed changes,
  who applied them, and whether any were reverted.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7. UI CHANGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

7.1 Step builder (create and edit)
------------------------------------
Each step gets an optional `intent` input below the selector fields.
It is visually secondary — smaller font, muted label ("What should
this step achieve?") — so it doesn't clutter the step builder for
users who don't use it.

For AI-generated tests, the intent field is pre-populated and shown
in a read-only style with an "AI-generated" badge. Users can edit it.

7.2 Execution detail page — failed step
-----------------------------------------
When a step has status 'error', the step entry in the compact step
list shows:

  [!] CLICK — error
      "element not found: #checkout-btn"

      [AI Diagnosis]  ← button, triggers POST /diagnose if not yet run

If diagnosis has already run:

  [!] CLICK — error
      "element not found: #checkout-btn"

      Diagnosis: The checkout button was refactored. The old selector
      #checkout-btn no longer exists. A new button with the selector
      [data-testid="proceed-to-checkout"] appears to serve the same
      purpose based on its aria-label "Proceed to checkout".

      Suggested fix: [data-testid="proceed-to-checkout"]  (high confidence)
      [Apply fix]  [Ignore]

      Intent: "not set"
      [What was this step supposed to do?]  ← textarea, inline
      [Save intent]  ← saves via PATCH and re-runs diagnosis

7.3 Test detail page — healing history
----------------------------------------
A new collapsible section "Healing History" shows the healing_log
for that test. Each entry shows: date, step, original selector, new
selector, confidence, applied by (auto or username), and a Revert
button.

This gives teams visibility into how much a test has silently drifted
and been healed — which is itself a useful signal about how stable
that part of the UI is.

7.4 Execution list (view_executions squares)
---------------------------------------------
Healed executions get a visual indicator on their square — a small
wrench icon or a distinct colour (e.g. amber rather than green) — so
at a glance you can see that a run "passed" only after auto-healing.
This is important: a healed pass and a clean pass are not the same
thing, and the UI should reflect that.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8. IMPLEMENTATION ORDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phase 1 — Foundation (no healing yet, just intent capture)
  - Add intent field to step schema
  - Update AI generation prompt to populate intent
  - Show intent in step builder UI (optional field)
  - Show intent on execution detail next to failed steps
  - Add PATCH /api/tests/<id>/steps/<step_index>/intent
  - Add lazy capture textarea on execution detail for steps with
    no intent

Phase 2 — Diagnosis (LLM tells you what broke, no auto-fix yet)
  - Write DOM trimming logic
  - Write healing prompt assembly (includes glossary injection)
  - Add POST /api/executions/<id>/diagnose
  - Show diagnosis card on execution detail
  - Add healing_data column to executions table

Phase 3 — Healing (auto-apply on high confidence)
  - Add healing_log table
  - Add POST /api/executions/<id>/apply-heal
  - Implement retry-with-suggested-selector logic in subprocess runner
  - Mark healed executions visually in execution list
  - Add healing history section to test detail page

Why phase it this way?

Phase 1 has no LLM dependency beyond what already exists — it is
purely a data model and UI change. Shipping it first means intent
data starts accumulating in production immediately, so by the time
Phase 2 launches there is already real intent data to work with.

Phase 2 gives value (diagnosis) without the risk of auto-modification.
Teams can evaluate the quality of the LLM's suggestions before
trusting it to write back to tests.

Phase 3 is the highest-risk phase and benefits most from the learnings
of Phase 2 — particularly around where the LLM's confidence
calibration is reliable and where it is not.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
9. WHAT THIS DOES NOT DO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- It does not heal assertion failures. If the expected value is wrong,
  that is a real test failure. Changing the assertion to match new
  values would defeat the purpose of the assertion.

- It does not heal navigate steps. If a URL changes, that is almost
  always intentional and should be reviewed by a human.

- It does not re-run the full test automatically after healing. It
  retries only the failed step in isolation using a lightweight
  check, then flags the result. A full re-run is initiated manually.

- It does not heal pick_random steps automatically. The randomness
  means a retry might succeed by luck even with a wrong selector.
  pick_random failures are always surfaced for human review.

- It does not learn across tests or teams. Each healing decision is
  made fresh from the current DOM and intent. There is no shared
  selector database or cross-test pattern learning in this spec.
  That is a meaningful future extension but adds significant
  complexity and is out of scope here.
