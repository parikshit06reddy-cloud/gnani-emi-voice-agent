# API Reference

Base URL in examples: `http://localhost:8000` (override with your deployed host). Full request/
response schemas are the single source of truth in [CONTRACT.md](../CONTRACT.md); this document
adds runnable cURL examples, auth headers, and every documented error response. Interactive
documentation is also available at `/docs` (Swagger UI) and `/redoc` once the app is running.

Auth headers used throughout:
- `X-API-Key: <API_KEY>` — required on `Initial_Message`, `calls`, `stats`.
- `X-Webhook-Key: <WEBHOOK_API_KEY>` — required on the post-call webhook.

---

## 1. `POST /api/Initial_Message`

Initiates an outbound call.

```bash
curl -sS -X POST "http://localhost:8000/api/Initial_Message" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST001",
    "customer_name": "Rahul Sharma",
    "phone_number": "9876543210",
    "country_code": "+1",
    "loan_account_number": "LAN123456",
    "emi_amount": 1200.0,
    "emi_due_date": "2026-07-25",
    "preferred_language": "English (US)",
    "currency": "USD"
  }'
```

**Success — 201:**
```json
{
  "success": true,
  "call_id": "CALL-20260728-0001",
  "gnani_call_reference": "gnani-9f3c...",
  "customer_id": "CUST001",
  "customer_name": "Rahul Sharma",
  "phone_number": "******3210",
  "country_code": "+1",
  "loan_account_number": "LAN123456",
  "emi_amount": 1200.0,
  "emi_due_date": "2026-07-25",
  "preferred_language": "en-US",
  "initial_message": "Hello, this is Aria calling from Apex Financial Services ...",
  "call_status": "initiated",
  "created_at": "2026-07-28T12:00:00+00:00"
}
```

**Error — 401 bad key:**
```bash
curl -sS -X POST "http://localhost:8000/api/Initial_Message" \
  -H "X-API-Key: wrong-key" -H "Content-Type: application/json" -d '{}'
```
```json
{"success": false, "error": {"code": "UNAUTHORIZED", "message": "Invalid API key.", "details": {}}, "request_id": "..."}
```

**Error — 422 validation (invalid initial call request; assignment §9 scenario 11):**
```bash
curl -sS -X POST "http://localhost:8000/api/Initial_Message" \
  -H "X-API-Key: ${API_KEY}" -H "Content-Type: application/json" \
  -d '{
    "customer_id": "",
    "customer_name": "Rahul Sharma",
    "phone_number": "123",
    "country_code": "91",
    "loan_account_number": "LAN123456",
    "emi_amount": -5,
    "emi_due_date": "not-a-date",
    "preferred_language": "Klingon"
  }'
```
```json
{"success": false, "error": {"code": "VALIDATION_ERROR", "message": "Request failed validation.", "details": {
  "customer_id": "must not be empty",
  "phone_number": "must be 7-15 digits",
  "country_code": "must match ^\\+\\d{1,4}$",
  "emi_amount": "must be > 0",
  "emi_due_date": "must be a valid ISO date",
  "preferred_language": "must map to en-US or es-ES"
}}, "request_id": "..."}
```

**Error — 502 trigger failed (assignment §9 scenario 12):**
```json
{"success": false, "error": {"code": "GNANI_TRIGGER_FAILED", "message": "Gnani call-trigger API returned an error after 3 retries.", "details": {"upstream_status": 500}}, "request_id": "..."}
```

**Error — 504 timeout (assignment §9 scenario 12, timeout variant):**
```json
{"success": false, "error": {"code": "GNANI_TIMEOUT", "message": "Gnani call-trigger API timed out after 3 retries.", "details": {}}, "request_id": "..."}
```
See [`test-scenarios.md`](./test-scenarios.md) for the mock-mode phone-number suffixes
(`...0000` / `...9999`) that deterministically trigger these two failure modes without a real
Gnani connection.

---

## 2. `POST /api/v1/webhooks/post-call`

Receives the post-call disposition from Gnani Agents Console.

> **Engine identifier naming:** the example payload below uses `gnani-prisma` / `gnani-timbre-2.5`
> / `gnani-evon` as `asr_engine` / `tts_engine` / `llm_engine` values, matching the assignment's
> required component names and this project's `GNANI_ASR_MODEL` / `GNANI_TTS_MODEL` /
> `GNANI_LLM_MODEL` env var defaults (see `.env.example`). These are intentionally
> environment-configurable, not hardcoded: point them at whatever model identifiers your Gnani
> Agents Console tenant actually exposes (in the tenant used to configure this project's own
> agent, that is `Responsive` for ASR and `Timbre G v1.0` for TTS — see
> [`gnani_config/CONSOLE_FINDINGS.md`](../gnani_config/CONSOLE_FINDINGS.md)) with no code changes.

```bash
curl -sS -X POST "http://localhost:8000/api/v1/webhooks/post-call" \
  -H "X-Webhook-Key: ${WEBHOOK_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt-001",
    "call_id": "CALL-20260728-0001",
    "gnani_call_reference": "gnani-9f3c",
    "call_status": "completed",
    "call_duration_seconds": 96,
    "call_started_at": "2026-07-28T12:00:05+00:00",
    "call_ended_at": "2026-07-28T12:01:41+00:00",
    "recording_url": "https://example.com/recordings/CALL-20260728-0001.mp3",
    "language_detected": "en-US",
    "asr_engine": "gnani-prisma",
    "tts_engine": "gnani-timbre-2.5",
    "llm_engine": "gnani-evon",
    "disposition": {
      "stage_code": "PTP_FUTURE",
      "disposition_reason": "Customer said '\''I will pay on the 30th'\''.",
      "disposition_summary": "Customer acknowledged the EMI and committed to a future date.",
      "ptp_date": "2026-07-30",
      "ptp_amount": 1200.0,
      "callback_datetime": null,
      "confidence": 0.93,
      "customer_verified": true,
      "sentiment": "neutral",
      "evidence_quote": "I will pay on the 30th"
    },
    "transcript": [
      {"turn": 1, "speaker": "bot", "text": "Hello, this is Aria...", "language": "en-US", "timestamp": "2026-07-28T12:00:05+00:00"},
      {"turn": 2, "speaker": "customer", "text": "Yes this is Rahul. I will pay on the 30th.", "language": "en-US", "timestamp": "2026-07-28T12:00:20+00:00"}
    ]
  }'
```

**Success — 200:**
```json
{"success": true, "duplicate": false, "call_id": "CALL-20260728-0001", "stage_code": "PTP_FUTURE", "ptp_date": "2026-07-30"}
```

**Duplicate delivery — 200 (assignment §9 scenario 10, same `event_id` re-sent):**
```bash
# same request body/headers as above, sent a second time
```
```json
{"success": true, "duplicate": true, "call_id": "CALL-20260728-0001"}
```
No fields are mutated and no WebSocket broadcast fires on this path.

**Error — 401 bad webhook key:**
```json
{"success": false, "error": {"code": "UNAUTHORIZED", "message": "Invalid webhook key.", "details": {}}, "request_id": "..."}
```

**Error — 404 unknown call_id:**
```bash
curl -sS -X POST "http://localhost:8000/api/v1/webhooks/post-call" \
  -H "X-Webhook-Key: ${WEBHOOK_API_KEY}" -H "Content-Type: application/json" \
  -d '{"event_id": "evt-999", "call_id": "CALL-DOES-NOT-EXIST", "call_status": "completed"}'
```
```json
{"success": false, "error": {"code": "CALL_NOT_FOUND", "message": "No call found for call_id CALL-DOES-NOT-EXIST.", "details": {}}, "request_id": "..."}
```

**Error — 422 invalid payload:**
```json
{"success": false, "error": {"code": "VALIDATION_ERROR", "message": "Request failed validation.", "details": {"call_status": "must be one of the documented CallStatus values"}}, "request_id": "..."}
```

**Missing/invalid stage code:** not an HTTP error — silently resolved by the stage-code engine to
`UNCLEAR`/`DSCN` with `stage_code_source: "derived"` per [CONTRACT.md](../CONTRACT.md) and
[`stage-code-logic.md`](./stage-code-logic.md); the webhook still returns `200`.

---

## 3. `GET /api/v1/calls`

```bash
curl -sS "http://localhost:8000/api/v1/calls?stage_code=PTP_FUTURE&stage_code=PTP_TODAY&page=1&page_size=25" \
  -H "X-API-Key: ${API_KEY}"
```
```bash
curl -sS "http://localhost:8000/api/v1/calls?customer_id=CUST001&language=en-US" \
  -H "X-API-Key: ${API_KEY}"
```
```bash
curl -sS "http://localhost:8000/api/v1/calls?q=hospital" -H "X-API-Key: ${API_KEY}"
```

**Success — 200:** see [CONTRACT.md §3](../CONTRACT.md#3-get-apiv1calls) for the full shape.

**Error — 401:** same envelope as above with `code: "UNAUTHORIZED"`.

**Error — 422 (bad query param, e.g. `page_size=9999`):**
```json
{"success": false, "error": {"code": "VALIDATION_ERROR", "message": "Request failed validation.", "details": {"page_size": "must be <= 200"}}, "request_id": "..."}
```

---

## 4. `GET /api/v1/calls/{call_id}`

```bash
curl -sS "http://localhost:8000/api/v1/calls/CALL-20260728-0001" -H "X-API-Key: ${API_KEY}"
```

**Error — 404:**
```json
{"success": false, "error": {"code": "CALL_NOT_FOUND", "message": "No call found for call_id CALL-DOES-NOT-EXIST.", "details": {}}, "request_id": "..."}
```

---

## 5. `GET /api/v1/stats`

```bash
curl -sS "http://localhost:8000/api/v1/stats?date_from=2026-07-01&date_to=2026-07-28" \
  -H "X-API-Key: ${API_KEY}"
```
Response shape: see [CONTRACT.md §5](../CONTRACT.md#5-get-apiv1stats).

---

## 6. `WS /ws/calls`

```bash
# using websocat or similar
websocat "ws://localhost:8000/ws/calls"
```
Server pushes `{"type": "call.created"|"call.updated", "call_id": "...", "row": {...}}` on every
create/update. No request body; auth is via the same-origin dashboard session in this assignment
scope (see [`production-readiness.md`](./production-readiness.md) for hardening this to a signed
token). Dashboard falls back to 10s polling if the socket closes.

---

## 7. `GET /health`

```bash
curl -sS "http://localhost:8000/health"
```
```json
{"status": "ok", "version": "1.0.0", "repository": "json", "gnani_mode": "mock"}
```
No authentication required — used for container/orchestrator liveness checks.

---

## Error code reference

| HTTP status | `error.code` | Where it occurs |
|---|---|---|
| 401 | `UNAUTHORIZED` | Any endpoint, missing/invalid `X-API-Key` or `X-Webhook-Key` |
| 404 | `CALL_NOT_FOUND` | `GET /api/v1/calls/{call_id}`, `POST /api/v1/webhooks/post-call` with unknown `call_id` |
| 422 | `VALIDATION_ERROR` | Any endpoint, malformed body/query params |
| 502 | `GNANI_TRIGGER_FAILED` | `POST /api/Initial_Message`, Gnani call-trigger API returned non-2xx after retries |
| 504 | `GNANI_TIMEOUT` | `POST /api/Initial_Message`, Gnani call-trigger API timed out after retries |
| 500 | `INTERNAL_ERROR` | Unhandled exception (logged with `request_id`, generic message returned to client) |

Every handled error uses the envelope from [CONTRACT.md](../CONTRACT.md):
```json
{"success": false, "error": {"code": "...", "message": "...", "details": {}}, "request_id": "..."}
```

See [`test-scenarios.md`](./test-scenarios.md) for how each of the 12 mandatory scenarios maps to
one or more of the calls above, and the Postman collection / additional cURL commands referenced
there for the full mandatory-scenario walkthrough.
