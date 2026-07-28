# Database Schema — `calls` Collection

MongoDB is the preferred store (assignment §7); the JSON-file fallback
(`app/repositories/json_repo.py`, active automatically when `MONGODB_URI` is unset) mirrors the
same document shape so both repository implementations satisfy the abstract
`app/repositories/base.py::CallRepository` interface identically.

## Collection: `calls` (database `${MONGODB_DB}`, default `gnani_emi`)

One document per call, keyed by `call_id`.

> **Engine identifier naming:** the `engines.asr` / `engines.tts` / `engines.llm` example values
> below (`gnani-prisma`, `gnani-timbre-2.5`, `gnani-evon`) match the assignment's required
> component names and this project's `GNANI_ASR_MODEL` / `GNANI_TTS_MODEL` / `GNANI_LLM_MODEL` env
> var defaults (see `.env.example`). They are environment-configurable, not hardcoded — point them
> at your Gnani Agents Console tenant's real model identifiers (in the tenant used to configure
> this project's own agent, that is `Responsive` for ASR and `Timbre G v1.0` for TTS — see
> [`gnani_config/CONSOLE_FINDINGS.md`](../gnani_config/CONSOLE_FINDINGS.md)) with no code changes.

| Field | Type | Required | Description | Example |
|---|---|---|---|---|
| `call_id` | string | yes | Primary business key, format `CALL-YYYYMMDD-NNNN` | `"CALL-20260728-0001"` |
| `customer.customer_id` | string | yes | Internal customer identifier | `"CUST001"` |
| `customer.customer_name` | string | yes | Full name of borrower | `"Rahul Sharma"` |
| `customer.phone_number` | string | yes | Raw phone number, **never returned** by any read endpoint | `"9876543210"` |
| `customer.masked_phone_number` | string | yes (derived) | Masked form shown on dashboard/API | `"******3210"` |
| `customer.country_code` | string | yes | E.164 country code | `"+1"` |
| `customer.loan_account_number` | string | yes | Full loan account number | `"LAN123456"` |
| `emi_details.emi_amount` | double | yes | EMI amount due | `1200.0` |
| `emi_details.emi_due_date` | string (ISO date) | yes | EMI due date | `"2026-07-25"` |
| `emi_details.currency` | string | yes | ISO currency code | `"USD"` |
| `call_request` | object | yes | Raw `InitialMessageRequest` payload as received | `{...}` |
| `gnani_console_response` | object | no | Raw response from the Gnani call-trigger API (or mock) | `{...}` |
| `post_call_payload` | object | no | Raw post-call webhook payload as received | `{...}` |
| `call_status` | enum string | yes | One of `queued, initiated, ringing, connected, completed, failed, no_answer, busy, cancelled` | `"completed"` |
| `call_duration_seconds` | int | no | Duration once completed | `96` |
| `stage_code` | enum string | no (set post-call) | One of the 19 stage codes | `"PTP_FUTURE"` |
| `stage_group` | enum string | no (derived) | Group per `gnani_config/stage-codes.json` | `"ptp"` |
| `stage_code_source` | enum string | no (set post-call) | `llm` \| `derived` \| `fallback` — see [`stage-code-logic.md`](./stage-code-logic.md) | `"llm"` |
| `disposition_reason` | string | no | One-sentence reason from analytics prompt | `"Customer committed to paying on 30 July 2026."` |
| `disposition_summary` | string | no | 2-4 sentence summary | `"..."` |
| `ptp_date` | string (ISO date) or null | no | Promise-to-pay date if applicable | `"2026-07-30"` |
| `ptp_amount` | double or null | no | Promised amount if partial | `null` |
| `callback_datetime` | string (ISO datetime) or null | no | Scheduled callback if applicable | `null` |
| `language_captured` | enum string | no | `en-US` \| `es-ES` \| `mixed` \| `unknown` | `"es-ES"` |
| `language_switched` | bool | no | True if the call changed language mid-call | `true` |
| `sentiment` | enum string | no | `positive` \| `neutral` \| `negative` | `"neutral"` |
| `confidence` | double | no | Analytics-prompt confidence, 0.0-1.0 | `0.93` |
| `customer_verified` | bool | no | Identity confirmed per transcript | `true` |
| `evidence_quote` | string or null | no | Verbatim customer quote backing the stage code | `"I will pay on the 30th"` |
| `recording_url` | string (URL) or null | no | Call recording location | `"https://.../CALL-....mp3"` |
| `engines.asr` | string | no | ASR engine identifier | `"gnani-prisma"` |
| `engines.tts` | string | no | TTS engine identifier | `"gnani-timbre-2.5"` |
| `engines.llm` | string | no | LLM engine identifier | `"gnani-evon"` |
| `conversation_transcript` | array of TranscriptTurn | no | `{turn, speaker, text, language, timestamp}` | `[...]` |
| `initial_message` | string | yes | Rendered initial message sent to Gnani | `"Hello Rahul, ..."` |
| `webhook_event_ids` | array of string | yes (default `[]`) | All `event_id` values applied, for idempotency | `["evt-001"]` |
| `audit_log` | array of object | yes (default `[]`) | `{at, actor, action, detail}` | `[...]` |
| `call_initiated_at` | string (ISO datetime) | no | When the trigger call was sent | `"2026-07-28T12:00:00+00:00"` |
| `call_started_at` | string (ISO datetime) | no | From post-call payload | `"2026-07-28T12:00:05+00:00"` |
| `call_completed_at` | string (ISO datetime) | no | From post-call payload | `"2026-07-28T12:01:41+00:00"` |
| `created_at` | string (ISO datetime) | yes | Record creation timestamp | `"2026-07-28T12:00:00+00:00"` |
| `updated_at` | string (ISO datetime) | yes | Last mutation timestamp | `"2026-07-28T12:01:45+00:00"` |

This directly matches the `CallDetail` response model referenced in
[CONTRACT.md §4](../CONTRACT.md#4-get-apiv1callscall_id) and the suggested record structure in
the assignment §7, extended with the fields required by CONTRACT (masking, idempotency,
audit log, engine identifiers).

## Indexes

| Index | Fields | Rationale |
|---|---|---|
| `idx_call_id_unique` | `{call_id: 1}` unique | Primary lookup key for `GET /api/v1/calls/{call_id}` and all writes; enforces one document per call. |
| `idx_customer_id` | `{customer.customer_id: 1}` | Dashboard filter by Customer ID (assignment §6.2); supports customer-level history lookups. |
| `idx_loan_account_number` | `{customer.loan_account_number: 1}` | Dashboard filter by Loan Account Number (assignment §6.2). |
| `idx_call_status_created_at` | `{call_status: 1, created_at: -1}` | Stats aggregation and dashboard status filter combined with default recency sort. |
| `idx_stage_code` | `{stage_code: 1}` | Dashboard multi-select stage-code filter and `by_stage_code` stats aggregation. |
| `idx_stage_group` | `{stage_group: 1}` | `stage_group` query param and summary card counts. |
| `idx_ptp_date` | `{ptp_date: 1}` | Dashboard PTP-date filter; supports "calls due to pay on/around date X" ops queries. |
| `idx_language_captured` | `{language_captured: 1}` | Dashboard language filter and `by_language` stats aggregation. |
| `idx_created_at` | `{created_at: -1}` | Default sort for `GET /api/v1/calls` (`sort_by=created_at, sort_dir=desc`) and `call_date`/`date_from`/`date_to` range filters. |
| `idx_webhook_event_ids` | `{webhook_event_ids: 1}` (multikey) | Fast idempotency check on webhook delivery — `db.calls.find({webhook_event_ids: event_id})` before any write. |
| `idx_text_search` | text index on `{disposition_summary: "text", disposition_reason: "text", "conversation_transcript.text": "text"}` | Backs the `q` full-text transcript/summary search query param. |

All indexes are created idempotently at application startup by `app/repositories/mongo_repo.py`
(`create_index` calls are no-ops if the index already exists with the same spec).

## JSON-file fallback shape

When `MONGODB_URI` is unset, `app/repositories/json_repo.py` persists to
`${JSON_STORE_PATH}` (default `./data/calls.json`) as a single JSON document:

```json
{
  "schema_version": 1,
  "calls": {
    "CALL-20260728-0001": { "...": "same document shape as the MongoDB collection above" },
    "CALL-20260728-0002": { "...": "..." }
  }
}
```

- Keyed by `call_id` for O(1) lookup, mirroring the Mongo unique index.
- Filtering, sorting, and pagination for `GET /api/v1/calls` and `GET /api/v1/stats` are done
  in-memory over `calls.values()` after loading the file, so query semantics are identical
  between backends — no endpoint behavior differs based on `repository_kind`.
- Writes are atomic via write-to-temp-file-then-rename to avoid partial-write corruption under
  concurrent access; acceptable for the assignment's single-process dev/demo scope, called out in
  [`production-readiness.md`](./production-readiness.md) as a Mongo replica set migration path
  for production.
- `GET /health` reports `repository: "json"` vs `"mongo"` (per [CONTRACT.md](../CONTRACT.md) §7)
  so it is always visible which backend is active.

## Retention and PII masking

- **Raw phone number** (`customer.phone_number`) is stored but is **never returned** by any read
  endpoint — every response path (list, detail, dashboard) uses `masked_phone_number`
  (`******3210` format: keep last 4 digits, mask the rest) computed at write time and stored
  alongside the raw value for masking to be a pure lookup, not a runtime transform that could be
  bypassed.
- **Recordings** (`recording_url`) point to Gnani-managed storage with a 90-day retention policy
  set in `gnani_config/agent-config.json` → `recording.retention_days`; this application stores
  only the URL reference, not the audio binary, keeping raw voice data out of this database's
  blast radius.
- **Transcripts** may contain incidental PII spoken by the customer (e.g., if they volunteer an
  address). No automatic redaction is applied to transcript text in this assignment scope;
  `docs/production-readiness.md` documents PII-at-rest encryption and field-level redaction as a
  hardening step.
- **Suggested retention policy** (documented here, enforced operationally, not by code in this
  assignment): full call records retained 90 days matching recording retention; after 90 days,
  `conversation_transcript`, `recording_url`, and `customer.phone_number` are purged/nulled while
  `stage_code`, `disposition_reason`, and aggregate stats fields are retained indefinitely for
  reporting, since they contain no raw PII.
- No database credentials, connection strings with embedded passwords, or API keys are ever
  written into any document field — all such secrets stay in environment/secret-manager
  configuration per `.env.example`, never in `calls`.
