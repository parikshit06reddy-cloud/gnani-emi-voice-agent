# Live call runbook (GNANI_MODE=live)

Everything in this repo runs end to end in `GNANI_MODE=mock` with no external dependency. This
document covers the switch to `live`, where the backend places a real outbound call through the
Gnani Agents Console and receives a real post-call webhook.

> **Read the "Unverified contract" section first.** The live call-trigger request shape in
> `app/services/gnani_client.py::_trigger_call_live` is an assumption, not a contract confirmed
> against Gnani's outbound-call API documentation.

## 1. Prerequisites

| Item | Where it goes | Notes |
|---|---|---|
| Gnani API key | `GNANI_API_KEY` | From the Gnani console. Never commit it. |
| Gnani API base URL | `GNANI_BASE_URL` | Defaults to `https://console.gnani.ai`. Confirm against Gnani's API docs. |
| Agent ID | `GNANI_AGENT_ID` | **Must be `d411993d126843e2912509f931d54ee2`** — the real configured agent. The `.env.example` default (`agent-emi-collections`) is a placeholder and will not resolve. |
| Caller ID / DID | `GNANI_CALLER_ID` | The outbound number provisioned on the Gnani account. |
| Public HTTPS tunnel | `PUBLIC_WEBHOOK_BASE_URL` | e.g. `https://abc123.ngrok.app`. Gnani must be able to reach your webhook from the internet. |
| Destination phone | request body | Use your own number for the first test. |

## 2. Configure

```bash
# .env
GNANI_MODE=live
GNANI_API_KEY=<your key>
GNANI_BASE_URL=https://console.gnani.ai
GNANI_AGENT_ID=d411993d126843e2912509f931d54ee2
GNANI_CALLER_ID=<your provisioned outbound number>
PUBLIC_WEBHOOK_BASE_URL=https://<your-subdomain>.ngrok.app
WEBHOOK_API_KEY=<a strong random value, not the dev default>
API_KEY=<a strong random value, not the dev default>
```

Start the tunnel **before** the app, so the app logs the correct callback URL:

```bash
ngrok http 8000
# then, in another terminal
docker compose up --build      # or: uvicorn app.main:app --port 8000
```

Confirm the mode actually flipped — the startup log must no longer print the
`GNANI_MODE=mock` warning, and `/health` must report `"gnani_mode":"live"`:

```bash
curl -s http://localhost:8000/health
```

Then confirm Gnani can reach you (run this from outside your network, or just hit the tunnel URL):

```bash
curl -s https://<your-subdomain>.ngrok.app/health
```

If that last call does not return JSON, the post-call webhook will never arrive and the call row
will stay at `call_status=initiated` forever. Fix the tunnel before placing a call.

## 3. Set the webhook URL in the console

The console's **Analytics tab → Post-Call Trigger** must point at the same tunnel:

```
POST https://<your-subdomain>.ngrok.app/api/v1/webhooks/post-call
```

Add the auth header the backend expects, or the webhook will be rejected with 401:

```
X-Webhook-Key: <the same value as WEBHOOK_API_KEY in .env>
```

Note the header is `X-Webhook-Key` (enforced by `require_webhook_key` in `app/core/security.py`),
**not** `X-API-Key` — `X-API-Key` guards the business endpoints and is a different secret.

**Known risk:** if the console's Post-Call Trigger form does not support custom request headers,
Gnani cannot send `X-Webhook-Key` and every webhook will 401. Enable the query-key fallback
instead (HTTPS tunnel required):

```bash
# .env
WEBHOOK_ALLOW_QUERY_KEY=true
WEBHOOK_API_KEY=<strong-random-value>
```

Console Post-Call Trigger URL:

```
POST https://<your-subdomain>.ngrok.app/api/v1/webhooks/post-call?webhook_key=<same-value>
```

This is implemented in `require_webhook_key` (`app/core/security.py`) and covered by tests in
`tests/test_api_webhooks.py`. It is disabled by default so production deployments are not
silently weakened. Do not disable webhook authentication entirely.

`PUBLIC_WEBHOOK_BASE_URL` is what the backend *tells Gnani per call*; the Post-Call Trigger field
is the *agent-level* fallback. Keep both in sync — a stale value in either place is the most common
cause of a missing webhook.

## 4. Place the call

Swagger UI is at `http://localhost:8000/docs` → `POST /api/Initial_Message`. Body:

```json
{
  "customer_id": "CUST-LIVE01",
  "customer_name": "<your name>",
  "country_code": "+1",
  "phone_number": "<your 10-digit number, digits only, no symbols>",
  "loan_account_number": "LAN9988774417",
  "emi_amount": 968.00,
  "currency": "USD",
  "emi_due_date": "2026-07-21",
  "preferred_language": "en-US"
}
```

`phone_number` must be 7–15 digits with no symbols and `country_code` is required — otherwise you
get a `422 VALIDATION_ERROR` with `field_errors` naming the offending field.

## 5. What to listen for

The opener is built by `build_initial_message()` and is **identity-gated**: it may name the bot,
the org, and the loan's last 4 digits, but must not disclose the EMI amount, the due date, the
balance, or the full account number until the person confirms who they are.

Expected, verbatim (en-US):

```
Hello, this is Aria calling from Apex Financial Services regarding the loan
account ending in 4417. May I confirm whether I am speaking with <name>?
```

Note the exact phrasing is "May I confirm **whether I am** speaking with" — not "May I confirm I'm
speaking with". If you hear the amount ("nine hundred sixty-eight dollars") or the due date
("July twenty-first") *before* you say "yes, speaking", that is a compliance failure and it means
the console's System Prompt is out of sync with `prompts/01-system-prompt.md` — re-paste it.

The same gate is asserted programmatically in `tests/test_initial_message.py`, so a regression
fails CI rather than only being caught by ear.

## 6. Confirm the webhook landed

```bash
# the call row should move off "initiated" and gain a stage code
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/calls/CALL-<id> | python -m json.tool
```

Watch the app log for `post_call_processed`. The row's `stage_code`, `disposition_reason`,
`ptp_date`, `customer_verified`, and `evidence_quote` are then visible on the dashboard detail page.
Raw inbound JSON is preserved verbatim on the record as `post_call_payload`, so you can always
diff what Gnani actually sent against what the model expected.

## 7. Unverified contract — expect to iterate here

Two shapes in this repo were built against the assignment brief and mock fixtures, not against
Gnani's live API:

**Outbound trigger** (`_trigger_call_live`) currently posts:

```
POST {GNANI_BASE_URL}/v1/calls/trigger
Authorization: Bearer {GNANI_API_KEY}

{ "agent_id", "caller_id", "phone", "initial_message", "bot_variables",
  "asr_model", "tts_model", "llm_model", "webhook_url" }
```

The path, the auth scheme, and the field names are all assumptions. A `404` or `401` on the first
live attempt is the expected outcome, not a bug in the rest of the system — check Gnani's API
reference and correct that one method. Nothing else in the codebase depends on its internals; it
returns a `GnaniTriggerResult` and that is the only coupling.

**Inbound webhook** (`PostCallWebhookRequest` in `app/models/requests.py`) is the model to
reconcile once a real payload arrives. Capture the raw body first:

```bash
# ngrok's inspector replays the exact bytes Gnani sent
open http://127.0.0.1:4040
```

If a field name differs, add an alias rather than renaming the internal field, so the mock
fixtures in `samples/webhooks/` and the 136 tests keep passing:

```python
stage_code: StageCode | None = Field(default=None, validation_alias=AliasChoices("stage_code", "<gnani_name>"))
```

## 8. Rollback

Set `GNANI_MODE=mock` and restart. No data migration is needed — live and mock calls share the
same schema, and mock mode keeps its deterministic failure injection (phone suffix `0000` → 504,
`9999` → 502) for regression testing.
