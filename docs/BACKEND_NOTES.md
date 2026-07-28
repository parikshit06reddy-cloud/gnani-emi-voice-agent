# Backend Notes (Handoff)

Factual notes from the FastAPI backend build for the Gnani Agents Console
EMI-collections outbound voice agent assignment. Scope owned by this agent:
everything under `/home/user/workspace/gnani-emi-voice-agent` **except**
`app/static/`, `prompts/`, `gnani_config/`, `docs/` (other than this file and
`docs/test-results.json`), and `README.md`.

## 1. How to run

```bash
cd /home/user/workspace/gnani-emi-voice-agent
python -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env   # edit as needed; safe defaults exist for local/dev

# Run the API (JSON-file repository by default, no external DB needed)
API_KEY=dev-api-key WEBHOOK_API_KEY=dev-webhook-key \
  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Interactive API docs: `http://localhost:8000/docs` (Swagger) and `/redoc`.
- Health check: `GET /health`.
- To use MongoDB instead of the flat-file store, set `MONGODB_URI` (and
  optionally `MONGODB_DB`) in `.env` — `app/repositories/factory.py` switches
  repositories automatically based on whether `MONGODB_URI` is set.
- Docker: `docker compose up --build` starts the API + a `mongo:7` container
  (see `docker-compose.yml`, `Dockerfile`, `.dockerignore`).
- Postman: import `postman/Gnani-EMI-Voice-Agent.postman_collection.json` and
  `postman/environment.json` — includes a "12 Mandatory Scenarios" folder with
  ready-made initiate+webhook request pairs.
- Sample webhook payloads for manual testing/demo: `samples/webhooks/*.json`
  (16 files, one per stage-code outcome, all validated against the live
  pipeline — see section 4).

## 2. Test results

Run with: `.venv/bin/python -m pytest tests/ -v`

**Result: 90 passed, 0 failed** (11 benign warnings — Starlette's
`HTTP_422_UNPROCESSABLE_ENTITY` deprecation notice from FastAPI internals,
unrelated to application code; safe to ignore).

Coverage spans: request/response model validation, stage-code deterministic
engine rules (`tests/test_stage_code.py`, the bulk of the suite), repository
behavior (JSON + in-memory Mongo-like fakes), call service orchestration,
webhook idempotency, auth dependencies, and API route status codes.

## 3. Seed scenario results (mandatory 12 scenarios)

Run with (server must be running first):

```bash
.venv/bin/python scripts/seed_scenarios.py --base-url http://localhost:8000
```

(Omit `--base-url` to run in-process against an ephemeral ASGI app instead of
a live server.)

**Result: 12/12 PASS.** Machine-readable output written to
`docs/test-results.json` (the only file this agent writes under `docs/`).
Summary of each scenario and the stage code / behavior it exercises:

| # | Scenario | Outcome |
|---|----------|---------|
| 1 | PTP today | `stage_code=PTP_TODAY`, webhook 200 |
| 2 | Future PTP | `stage_code=PTP_FUTURE`, webhook 200 |
| 3 | Already paid | `stage_code=ALREADY_PAID`, webhook 200 |
| 4 | Callback requested | `stage_code=CALLBACK_SCHEDULED`, webhook 200 |
| 5 | RTP financial hardship | `stage_code=RTP_FINANCIAL`, webhook 200 |
| 6 | Dispute EMI amount | `stage_code=DISPUTE_CHARGES`, webhook 200 |
| 7 | Third party answers | `stage_code=THIRD_PARTY`, webhook 200 |
| 8 | Language switch mid-call (bilingual) | `stage_code=PTP_TOMORROW`, `language_switched=true`, `language_captured=mixed` |
| 9 | Disconnect, no clear disposition | `stage_code=DSCN`, webhook 200 |
| 10 | Duplicate webhook replay | first delivery `duplicate=false`, replay `duplicate=true`, no double-processing |
| 11 | Invalid initial request | HTTP 422, `code=VALIDATION_ERROR` |
| 12 | Gnani API failure + timeout (injected via mock) | timeout → HTTP 504, hard failure → HTTP 502 |

## 4. Manual verification performed

- `pip install -r requirements.txt` into the project `.venv` — clean install.
- Full pytest run — 90/90 green.
- Started `uvicorn` and ran `scripts/seed_scenarios.py` against the live
  server — 12/12 PASS, `docs/test-results.json` produced.
- `curl` checks against the running server:
  - `GET /health` → `{"status":"ok","version":"1.0.0","repository":"json","gnani_mode":"mock"}`
  - `GET /docs` → HTTP 200 (Swagger UI)
  - `GET /api/v1/config` → `{"api_key_required": true}` (actual key never
    returned by any endpoint)
  - `GET /api/v1/calls` without `X-API-Key` → HTTP 401
  - `GET /api/v1/calls` with `X-API-Key` → paginated list, phone numbers
    masked (e.g. `*******9999`)
  - `GET /api/v1/calls/{call_id}` → full `CallDetail`, phone masked even in
    nested `call_request.phone_number`
  - `GET /api/v1/stats` → aggregate counts matching seeded calls
- All 16 files in `samples/webhooks/` were validated two ways: (a) schema
  validation via `PostCallWebhookRequest.model_validate()`, and (b) run
  through the live `process_webhook` pipeline to confirm each produces its
  intended `stage_code` (including one file that intentionally demonstrates
  the confidence/evidence downgrade to `UNCLEAR`).
- OpenAPI schema completeness: all 7 operations have both `summary` and
  `description`. Response/request models carry `json_schema_extra` examples
  (`CallSummaryRow`, `CallListResponse`, `CallDetail`, `ConfigResponse`,
  `DispositionPayload`, `ErrorResponse`, `HealthResponse`,
  `InitialMessageRequest`, `InitialMessageResponse`,
  `PostCallWebhookRequest`, `StatsResponse`, `TranscriptTurn`,
  `WebhookAckResponse`). Pure enums (`CallStatus`, `Language`, `Speaker`,
  `StageCode`, `StageCodeSource`, `DispositionCategory`) and FastAPI's
  built-in validation-error schemas (`HTTPValidationError`,
  `ValidationError`) intentionally have no custom example — their values are
  self-explanatory from the enum listing itself.

## 5. Deviations from CONTRACT.md

**None.** The implementation follows `CONTRACT.md` as written: endpoint
paths/methods, request/response field names and casing, masking rules,
error envelope shape, idempotency behavior, and repository abstraction all
match the contract. No fields were renamed, added, or dropped from the
contract's response models.

## 6. Stage-code engine rule list (`app/services/stage_code.py`)

The stage-code resolver is a fully deterministic, rule-based engine — it
never calls an LLM to *decide* a stage code, so every resolution is
auditable via the `applied_rules` list attached to the result. Rules, in the
order they are effectively applied:

1. **Evidence-based assignment** — a proposed `stage_code` from the Gnani
   post-call payload is only accepted if it comes with a non-empty
   `evidence_quote` and a `confidence` score. No blind trust of the
   third-party payload's stage code.
2. **Confidence threshold gating** — proposals with `confidence` below
   `STAGE_CODE_CONFIDENCE_THRESHOLD` (default `0.6`, configurable via env)
   are downgraded to `UNCLEAR` rather than accepted outright.
3. **PTP date consistency/correction** — for PTP-family codes
   (`PTP_TODAY`, `PTP_TOMORROW`, `PTP_FUTURE`), the engine cross-checks the
   claimed `ptp_date` against the call date and reclassifies among the three
   if the date doesn't match the claimed bucket (e.g. a "PTP today" claim
   with a date three days out is corrected to `PTP_FUTURE`).
4. **`customer_verified` gating** — commitments that require identity
   confirmation (PTP commitments, `ALREADY_PAID`) are blocked/downgraded if
   `customer_verified` is not `true`, since an unverified party cannot bind
   the account to a promise or payment claim.
5. **`ALREADY_PAID` vs `DISPUTE_PAID` disambiguation** — if the customer
   claims payment was made but also disputes the amount/charge, the engine
   reclassifies to `DISPUTE_PAID` rather than accepting a plain
   `ALREADY_PAID`, since the underlying claim is contested, not settled.
6. **`THIRD_PARTY` vs `WRONG_NUMBER` disambiguation** — distinguishes "a
   third party who knows the customer answered" from "call reached someone
   with no connection to the account" using transcript evidence, since the
   two require different follow-up actions.
7. **Keyword fallback (English + Spanish)** — when no usable stage-code
   proposal exists (missing/low-confidence/absent), the engine scans the
   transcript for bilingual keyword patterns (e.g. "already paid" / "ya
   pagué", "wrong number" / "número equivocado", financial-hardship phrases)
   before giving up.
8. **Disconnect override** — call-status signals take precedence over a
   weak/missing disposition: a `failed`/no-answer/busy call status routes to
   `DSCN`, `BUSY`, or `RNR` respectively, overriding any low-confidence or
   absent stage-code proposal.
9. **Final fallback — `UNCLEAR`** — if nothing above resolves a code (no
   evidence, no keyword match, no disconnect signal), the call is marked
   `UNCLEAR` rather than guessing.

Each final code also maps to a `stage_group` (e.g. `ptp`, `dispute`,
`non_connect`) used for `/api/v1/stats` aggregation — see
`test_stage_group_mapping_present_for_all_final_codes` in
`tests/test_stage_code.py` for the full mapping coverage.

## 7. Notes for the dashboard agent

- **Field naming is intentional, not a bug**: `CallSummaryRow` (list view)
  exposes `masked_phone_number`; `InitialMessageResponse` (call-creation
  response) exposes `phone_number` (also masked). Both are masked strings —
  use the correct field name per endpoint.
- **WebSocket broadcast payload shape**:
  `{"type": "call.created" | "call.updated", "call_id": "<id>", "row": {<CallSummaryRow-shaped dict>}}`.
  Subscribe via the WS endpoint documented in `app/api/v1/calls.py` /
  `app/services/ws_manager.py`.
- **`GET /api/v1/config`** returns only `{"api_key_required": true}` — the
  actual API key value is never exposed by any endpoint.
- **Phone masking is applied everywhere**, including nested
  `call_request.phone_number` inside `GET /api/v1/calls/{call_id}` — do not
  expect to find an unmasked number anywhere in API responses.
- **`docs/test-results.json`** is the only file this agent wrote into
  `docs/`; all other files in that directory (architecture docs, screenshots,
  stage-code-logic.md, etc.) belong to another agent and were left
  untouched.
- Error responses use a consistent envelope:
  `{"success": false, "error": {"code": "...", "message": "...", "details": ...}, "request_id": "..."}`.
  Relevant codes: `VALIDATION_ERROR` (422), `CALL_NOT_FOUND` (404),
  `GNANI_TIMEOUT` (504), `GNANI_TRIGGER_FAILED` (502), `UNAUTHORIZED` (401).
  `DUPLICATE_WEBHOOK` is informational only and still returns HTTP 200.
