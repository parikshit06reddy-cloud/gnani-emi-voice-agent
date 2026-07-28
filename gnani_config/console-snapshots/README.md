# Console snapshots

Point-in-time captures of what the Gnani Agents Console actually held, kept so the repo can be
diffed against the live agent rather than assumed to match it.

Agent: **EMI Collections Agent - Apex Financial** (`d411993d126843e2912509f931d54ee2`)

## `system-prompt-BEFORE-repaste.txt`

The System Prompt as it stood in the console immediately before it was overwritten with the
current `prompts/01-system-prompt.md` (387 words, versus 1732 words now).

It was replaced because it had drifted from the backend and would have broken a live call:

| Variable | Old console prompt | Current backend (`build_bot_variables`) |
|---|---|---|
| `{{loan_account_number}}` | referenced | **no longer sent** — replaced by `{{loan_last4}}` |
| `{{loan_last4}}` | absent | sent (last 4 digits only) |
| `{{current_date}}` | absent | sent (needed for "today"/"tomorrow" date math) |
| `{{payment_link_hint}}` | absent | sent |
| `{{customer_first_name}}` | absent | sent |
| `{{emi_due_date_display}}` | absent | sent (language-localised spoken form) |

The old prompt also lacked the explicit identity-verification gate that forbids disclosing the EMI
amount or due date before the borrower confirms who they are. That gate is the single most
important compliance property of this agent, and it is now asserted in
`tests/test_initial_message.py` so it cannot silently regress.

## Re-paste record

- Replaced with the fenced block from `prompts/01-system-prompt.md`, verbatim.
- Console required clicking **Validate** before **Save** became available; validation passed
  ("✓ Validated", 1732 words).
- Save toast: **"Agent detail(s) updated successfully"**.
- Verified after a page reload: prompt begins `You are {{bot_name}}, an automated collections
  calling assistant for {{org_name}}.`, ends `- Never continue past a clear do-not-call request.`,
  contains `{{loan_last4}}`, and contains no `{{loan_account_number}}`.
- Evidence: [`docs/screenshots/gnani-system-prompt.png`](../../docs/screenshots/gnani-system-prompt.png).

### On the "Draft" label

After saving, the tab shows a status pill reading **Draft** next to a **Save as version** button,
which looks like the prompt might only be an unpublished draft while calls still use an older
published copy. It is not. The pill's dropdown is titled "Saved Prompt Versions" and states
"Saved versions are snapshots. All edits happen in draft." — the only entry is "Current Draft"
(badge: "Editing"), and the Save-as-version dialog describes itself as "Versions are snapshots you
can restore later." There is no separate published/live tier and no older version being served, so
the saved draft *is* the prompt a live call uses. No version snapshot was created.
Evidence: [`docs/screenshots/gnani-system-prompt-version.png`](../../docs/screenshots/gnani-system-prompt-version.png).

Every `{{variable}}` in the current prompt is checked against
`app/services/initial_message.py::build_bot_variables` — there are no placeholders the backend
does not send.

## Analytics prompt — not installed, and why

`prompts/03-analytics-prompt.md` has **no corresponding field in this console tenant**. The
Analytics tab exposes exactly two features and neither accepts a free-text analysis prompt while
in a saveable state:

- **Post-call Data Extraction** — toggle is off and "Add Data Field" is disabled. Enabling it is
  the only way to reach per-field extraction instructions, and saving it fails with
  `Failed to update agent detail(s)` (see [`../CONSOLE_FINDINGS.md`](../CONSOLE_FINDINGS.md)).
- **Post-Call Trigger** — the outbound webhook config. Enabled and left untouched.

Evidence: [`docs/screenshots/gnani-analytics-tab.png`](../../docs/screenshots/gnani-analytics-tab.png).

This is not a gap in the deliverable: disposition extraction runs in this backend
(`app/services/stage_code.py`), deterministically and with evidence validation, rather than being
delegated to the console. `prompts/03-analytics-prompt.md` documents the equivalent LLM-side
contract for a tenant where that feature works.
