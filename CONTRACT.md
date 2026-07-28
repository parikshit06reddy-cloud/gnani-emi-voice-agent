# Shared Contract — Gnani EMI Collections Voice Agent

This file is the single source of truth for the API surface and data shapes.
Backend and dashboard MUST both conform to it. Do not change it without updating both sides.

## Project root
`/home/user/workspace/gnani-emi-voice-agent`

## Layout
```
gnani-emi-voice-agent/
  app/
    main.py                 # FastAPI app factory, router mount, static mount, WS
    core/
      config.py             # pydantic-settings, env based
      logging.py            # structured JSON logging + request_id
      security.py           # API key auth deps (X-API-Key), webhook key
      exceptions.py         # domain exceptions + handlers
    models/
      enums.py              # StageCode, CallStatus, Language, DispositionCategory
      call.py               # Pydantic models: CustomerInfo, EmiDetails, CallRecord, TranscriptTurn
      requests.py           # InitialMessageRequest, PostCallWebhookRequest
      responses.py          # InitialMessageResponse, CallSummaryRow, CallDetail, StatsResponse
    api/
      v1/
        calls.py            # POST /api/Initial_Message ; GET /api/v1/calls ; GET /api/v1/calls/{call_id}
        webhooks.py         # POST /api/v1/webhooks/post-call
        stats.py            # GET /api/v1/stats
        health.py           # GET /health
    services/
      gnani_client.py       # httpx AsyncClient, timeout + tenacity retry, mock mode
      initial_message.py    # dynamic multilingual initial message builder + PII rules
      stage_code.py         # deterministic stage-code resolution + validation
      disposition.py        # analytics-prompt disposition normaliser
      call_service.py       # orchestration, idempotency, persistence
      ws_manager.py         # websocket broadcast
    repositories/
      base.py               # abstract CallRepository
      mongo_repo.py         # motor implementation
      json_repo.py          # JSON file fallback (default when MONGODB_URI unset)
    static/                 # dashboard (index.html, detail.html, css, js)
  prompts/                  # bot prompts (system, per-stage, analytics)
  gnani_config/             # bot config export JSON + flow
  docs/                     # architecture, stage codes, test results
  tests/                    # pytest
  scripts/seed_scenarios.py # runs the 12 mandatory scenarios end-to-end in mock mode
  postman/
  .env.example  Dockerfile  docker-compose.yml  requirements.txt  README.md
```

## Enums

StageCode (string values, exactly these):
PTP_TODAY, PTP_TOMORROW, PTP_FUTURE, PTP_PARTIAL, ALREADY_PAID, CALLBACK_SCHEDULED,
RTP_FINANCIAL, RTP_MEDICAL, RTP_NO_REASON, DISPUTE_PAID, DISPUTE_CHARGES, NO_LOAN,
WRONG_NUMBER, THIRD_PARTY, BUSY, RNR, VM, DSCN, UNCLEAR

CallStatus: queued, initiated, ringing, connected, completed, failed, no_answer, busy, cancelled

Language: en-US, es-ES, mixed, unknown  (aliases accepted on input: "English", "English (US)", "en", "Spanish", "es", "Mixed")

Stage-code groups (used by stats + dashboard colouring):
- ptp: PTP_TODAY, PTP_TOMORROW, PTP_FUTURE, PTP_PARTIAL
- already_paid: ALREADY_PAID
- rtp: RTP_FINANCIAL, RTP_MEDICAL, RTP_NO_REASON
- dispute: DISPUTE_PAID, DISPUTE_CHARGES, NO_LOAN
- callback: CALLBACK_SCHEDULED
- non_connect: RNR, VM, BUSY, WRONG_NUMBER, DSCN
- other: THIRD_PARTY, UNCLEAR

## 1. POST /api/Initial_Message
Auth: header `X-API-Key: <API_KEY>`

Request body:
```json
{
  "customer_id": "CUST001",
  "customer_name": "Rahul Sharma",
  "phone_number": "9876543210",
  "country_code": "+1",
  "loan_account_number": "LAN123456",
  "emi_amount": 1200.0,
  "emi_due_date": "2026-07-25",
  "preferred_language": "English (US)",
  "currency": "USD",
  "initial_message": null,
  "metadata": {}
}
```
Validation: phone_number 7-15 digits; country_code `^\+\d{1,4}$`; emi_amount > 0;
emi_due_date valid ISO date; customer_id / loan_account_number non-empty;
preferred_language must map to en-US or es-ES. 422 on failure with field errors.

Behaviour: build initial_message (if not supplied), build bot_variables, persist record with
status `queued`, call Gnani call-trigger API (retry 3x w/ exponential backoff on 5xx/timeout),
then status `initiated` (or `failed` + 502 on exhausted retries).

Response 201:
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
Errors: 401 bad key, 422 validation, 502 `GNANI_TRIGGER_FAILED`, 504 `GNANI_TIMEOUT`.
Error envelope for all handled errors:
```json
{"success": false, "error": {"code": "GNANI_TIMEOUT", "message": "...", "details": {}}, "request_id": "..."}
```

## 2. POST /api/v1/webhooks/post-call
Auth: header `X-Webhook-Key: <WEBHOOK_API_KEY>`. When `WEBHOOK_ALLOW_QUERY_KEY=true`, also
accepts `?webhook_key=` or `?key=` on the URL (HTTPS only; for Console tenants without custom
header support).

Request body (accepts Gnani-style payload):
```json
{
  "event_id": "evt-001",
  "call_id": "CALL-20260728-0001",
  "gnani_call_reference": "gnani-9f3c",
  "call_status": "completed",
  "call_duration_seconds": 96,
  "call_started_at": "2026-07-28T12:00:05+00:00",
  "call_ended_at": "2026-07-28T12:01:41+00:00",
  "recording_url": "https://.../CALL-....mp3",
  "language_detected": "es-ES",
  "asr_engine": "gnani-prisma",
  "tts_engine": "gnani-timbre-2.5",
  "llm_engine": "gnani-evon",
  "disposition": {
    "stage_code": "PTP_FUTURE",
    "disposition_reason": "Customer said 'I will pay on the 30th'.",
    "disposition_summary": "...",
    "ptp_date": "2026-07-30",
    "ptp_amount": 1200.0,
    "callback_datetime": null,
    "confidence": 0.93,
    "customer_verified": true,
    "sentiment": "neutral",
    "evidence_quote": "I will pay on the 30th"
  },
  "transcript": [
    {"turn": 1, "speaker": "bot", "text": "...", "language": "en-US", "timestamp": "..."},
    {"turn": 2, "speaker": "customer", "text": "...", "language": "es-ES", "timestamp": "..."}
  ]
}
```
Idempotency: unique key = `event_id` (fallback `call_id + call_ended_at`). Duplicate ->
200 with `{"success": true, "duplicate": true, "call_id": ...}` and NO state change.
Unknown call_id -> 404 `CALL_NOT_FOUND`.
Stage code missing/invalid or not evidence-backed -> resolved by stage_code service to UNCLEAR/DSCN
with `stage_code_source: "derived"`.

Response 200:
```json
{"success": true, "duplicate": false, "call_id": "...", "stage_code": "PTP_FUTURE", "ptp_date": "2026-07-30"}
```

## 3. GET /api/v1/calls
Auth: X-API-Key. Query params (all optional):
`call_date` (YYYY-MM-DD), `date_from`, `date_to`, `call_status`, `stage_code` (repeatable),
`stage_group`, `customer_id`, `loan_account_number`, `language`, `ptp_date`,
`q` (transcript/summary full-text search), `page` (1), `page_size` (25, max 200),
`sort_by` (created_at), `sort_dir` (desc).

Response 200:
```json
{
  "items": [
    {
      "call_id": "CALL-20260728-0001",
      "customer_id": "CUST001",
      "customer_name": "Rahul Sharma",
      "masked_phone_number": "******3210",
      "loan_account_number": "LAN123456",
      "call_initiated_time": "2026-07-28T12:00:00+00:00",
      "call_status": "completed",
      "call_duration_seconds": 96,
      "call_duration_display": "01:36",
      "stage_code": "PTP_FUTURE",
      "stage_group": "ptp",
      "disposition_reason": "...",
      "ptp_date": "2026-07-30",
      "language": "es-ES"
    }
  ],
  "page": 1, "page_size": 25, "total": 12, "total_pages": 1
}
```

## 4. GET /api/v1/calls/{call_id}
Response 200 = full CallDetail: `call_id`, `customer` (with `masked_phone_number` only — raw
phone NEVER returned by any read endpoint), `emi_details`, `call_request`,
`gnani_console_response`, `post_call_payload`, `call_status`, `call_duration_seconds`,
`stage_code`, `stage_group`, `stage_code_source`, `disposition_reason`, `disposition_summary`,
`ptp_date`, `ptp_amount`, `callback_datetime`, `language_captured`, `language_switched` (bool),
`sentiment`, `confidence`, `customer_verified`, `evidence_quote`, `recording_url`,
`engines` `{asr, tts, llm}`, `conversation_transcript[]`, `initial_message`,
`call_initiated_at`, `call_started_at`, `call_completed_at`, `created_at`, `updated_at`,
`audit_log[]` (`{at, actor, action, detail}`), `webhook_event_ids[]`.
404 `CALL_NOT_FOUND` if missing.

## 5. GET /api/v1/stats
Same filter params as /calls. Response:
```json
{
  "total_calls": 12, "completed_calls": 10, "connected_calls": 9,
  "ptp_calls": 4, "already_paid_calls": 1, "rtp_calls": 1,
  "dispute_calls": 1, "non_connect_calls": 2, "callback_calls": 1,
  "connect_rate": 0.75, "ptp_rate": 0.4,
  "by_stage_code": {"PTP_FUTURE": 2},
  "by_language": {"en-US": 8, "es-ES": 3, "mixed": 1},
  "by_day": [{"date": "2026-07-28", "calls": 12}]
}
```

## 6. WS /ws/calls
Server pushes on create/update:
`{"type": "call.created"|"call.updated", "call_id": "...", "row": <CallSummaryRow>}`
Dashboard falls back to 10s polling if the socket closes.

## 7. GET /health -> `{"status":"ok","version":"1.0.0","repository":"json|mongo","gnani_mode":"mock|live"}`

## Dashboard (served at `/` from app/static, no build step, vanilla HTML/CSS/JS)
- `index.html`: 8 summary cards (Total, Completed, Connected, PTP, Already Paid, RTP, Dispute,
  Non-connect), filter bar (call date, call status, stage code multi, customer id,
  loan account number, language, PTP date, transcript search, reset), calls table with all
  contract fields + "View Details" link, pagination, live-update badge via WS, CSV export button,
  analytics charts (stage-code bar + language donut, pure canvas/SVG, no CDN).
- `detail.html?call_id=...`: customer details, call metadata, engine badges (Prisma ASR /
  Timbre 2.5 TTS / Evon LLM), stage code chip, disposition reason + summary, PTP date,
  callback datetime, sentiment/confidence, audio player for recording_url, full transcript
  (bot/customer bubbles w/ per-turn language tag), collapsible raw JSON panels for
  call_request / gnani_console_response / post_call_payload, audit log, timestamps.
- Phone numbers masked everywhere. Dark theme, no external network requests (offline-safe).
- Uses `X-API-Key` from a value injected at `/api/v1/config` or a localStorage-set key input.

## Env vars (.env.example)
APP_NAME, APP_VERSION, ENV, LOG_LEVEL, HOST, PORT,
API_KEY, WEBHOOK_API_KEY, WEBHOOK_ALLOW_QUERY_KEY=false,
GNANI_MODE (mock|live), GNANI_BASE_URL, GNANI_API_KEY, GNANI_AGENT_ID, GNANI_CALLER_ID,
GNANI_ASR_MODEL=gnani-prisma, GNANI_TTS_MODEL=gnani-timbre-2.5, GNANI_LLM_MODEL=gnani-evon,
GNANI_TIMEOUT_SECONDS=10, GNANI_MAX_RETRIES=3, GNANI_RETRY_BACKOFF_SECONDS=0.5,
MONGODB_URI, MONGODB_DB=gnani_emi, JSON_STORE_PATH=./data/calls.json,
PUBLIC_WEBHOOK_BASE_URL, DEFAULT_CURRENCY=USD, ORG_NAME, BOT_NAME, CORS_ORIGINS

Never hardcode secrets. Defaults must let `docker compose up` work with JSON store + mock mode.
