# Production Readiness

This assignment submission runs single-process, JSON-store-by-default, mock-mode-by-default for
reviewer convenience. This document lists the concrete changes required to operate it in
production, mapped to assignment §12.10 ("explain how the solution can be made production-ready").

## Horizontal scaling

- Run the FastAPI app as multiple stateless replicas behind a load balancer (e.g. Kubernetes
  Deployment + Service, or an ECS/Cloud Run service). Statelessness already holds today because
  all call state lives in the repository layer, not in process memory — the one exception is the
  in-memory WebSocket connection set in `app/services/ws_manager.py`, which must move to a shared
  pub/sub backend (Redis pub/sub or a message broker) so a `call.updated` event broadcast by one
  replica reaches dashboard clients connected to a different replica.
- Terminate TLS at the load balancer; the app itself should only bind to a private network
  interface behind it.

## Queueing for bulk dialling

- The bonus "bulk call initiation through CSV upload" and any real dialling program at scale
  needs a queue (SQS, RabbitMQ, or Redis-backed Celery/RQ) between `POST /api/Initial_Message`
  validation and the Gnani call-trigger call, so:
  - Bulk uploads enqueue thousands of call jobs without blocking the HTTP request.
  - A worker pool consumes the queue at a controlled concurrency (respecting Gnani account
    concurrent-call limits and telecom carrier rate limits).
  - Failed triggers requeue with backoff instead of failing the original HTTP request.
- Automatic call retry scheduling (assignment bonus) becomes a queue consumer that re-enqueues
  `RNR`/`BUSY`/`VM` outcomes after a cool-down window, respecting calling-window rules below.

## MongoDB replica set

- Move from a single `MONGODB_URI` standalone instance to a 3-node replica set (e.g. MongoDB
  Atlas or self-hosted) for automatic failover and read scaling.
- Use write concern `majority` for call writes to avoid losing a disposition update on primary
  failover; use read preference `primaryPreferred` for the dashboard's read endpoints.
- Add a nightly `mongodump` (or Atlas continuous backup) with point-in-time recovery matching the
  DR objective below.

## Secrets management

- Replace `.env` file secrets with a secret manager (AWS Secrets Manager, GCP Secret Manager,
  HashiCorp Vault, or Kubernetes Secrets mounted as files) — the app already reads all secrets
  via `pydantic-settings` environment variables (`app/core/config.py`), so this is a deployment
  change, not a code change.
- Rotate `API_KEY`, `WEBHOOK_API_KEY`, and `GNANI_API_KEY` on a schedule; support dual-active keys
  during rotation windows (accept old + new key for a grace period) to avoid downtime.
- Never log secret values; `app/core/logging.py` should redact any field named `*_key`, `*_token`,
  or `Authorization`/`X-API-Key`/`X-Webhook-Key` headers in structured logs.

## Observability

- **Metrics:** export Prometheus-format metrics (`/metrics`) for request rate/latency/error rate
  per endpoint, Gnani call-trigger success/retry/failure counts, webhook processing latency,
  stage-code distribution, and `stage_code_source` breakdown (llm vs derived vs fallback — a
  rising "derived/fallback" rate is a leading indicator of analytics-prompt drift).
- **Traces:** propagate a `request_id` (already generated per request in
  `app/core/logging.py`) as a trace ID via OpenTelemetry, spanning the FastAPI handler → Gnani
  client call → repository write, so a single call's full lifecycle is traceable end-to-end
  including the eventual webhook callback (correlate by `call_id`).
- **Log sampling:** structured JSON logs (already implemented) at `INFO` in production with
  100% sampling for `ERROR`/`WARNING` and statistical sampling (e.g. 10%) for high-volume `INFO`
  request logs to control log-ingestion cost at scale.
- **Alerting:** alert on webhook error rate, Gnani trigger failure rate exceeding threshold,
  and `stage_code=UNCLEAR` rate exceeding a baseline (signals conversation or prompt regressions).

## Webhook signature verification (HMAC upgrade)

- The current design (`X-Webhook-Key: <static value>`) is a shared-secret header check — simple
  but not cryptographically bound to the payload; a leaked key allows payload forgery.
- **Upgrade:** have Gnani sign each webhook body with HMAC-SHA256 using a shared signing secret,
  delivered as `X-Gnani-Signature: sha256=<hex>`. The backend recomputes the HMAC over the raw
  request body and does a constant-time comparison before parsing JSON, rejecting on mismatch
  with `401 INVALID_SIGNATURE`. This also protects against replay if combined with a timestamp
  header (`X-Gnani-Timestamp`) and a small allowed clock-skew window, rejecting requests older
  than e.g. 5 minutes even if the signature is valid (defense against a captured-and-replayed
  webhook).
- Keep the existing `X-Webhook-Key` as a secondary check during migration, then deprecate it once
  HMAC verification is confirmed working in production.

## Rate limiting

- Apply per-API-key rate limits on `POST /api/Initial_Message` (e.g. token bucket, 100 req/min)
  to bound accidental or malicious bulk-dial storms; return `429` with `Retry-After`.
- Apply a stricter, source-IP-based rate limit on the webhook endpoint separate from the
  API-key-based limit, since the webhook caller (Gnani) is a fixed, known set of egress IPs that
  can be allow-listed at the network layer (security group / WAF rule) in addition to app-level
  limiting.

## PII encryption at rest

- Encrypt `customer.phone_number` and any transcript fields containing incidental PII using
  field-level encryption (MongoDB Client-Side Field Level Encryption, or application-level
  envelope encryption with a KMS-managed data key) so a database dump or backup alone does not
  expose raw PII.
- Keep `masked_phone_number` unencrypted (it is already a one-way-masked derived value with no
  raw PII) so dashboard reads remain fast without decryption on every list request; only decrypt
  the raw phone number in the rare path that needs it (e.g. an authorized ops tool, not this
  dashboard).

## Compliance

- **Calling-window rules:** enforce local-time calling windows (e.g. no calls before 8am or after
  9pm customer local time, derived from the phone number's area code / country code) at the
  queue-consumer level before triggering a call — reject or reschedule jobs outside the window.
- **DNC list:** maintain a persistent do-not-call list (`phone_number` + `loan_account_number`
  pairs) populated automatically whenever the bot detects a DNC request
  (see [`prompts/05-guardrails.md`](../prompts/05-guardrails.md) §4); check this list before
  every dial attempt, including retries and bulk uploads.
- **Consent and recording notice:** the opening state (S1 in
  [`prompts/02-conversation-flow.md`](../prompts/02-conversation-flow.md)) already includes a
  recording-notice line requirement; in production, log an explicit `consent_acknowledged`
  timestamp per call as a compliance audit artifact, and make the recording notice
  jurisdiction-aware (some jurisdictions require two-party consent before the notice, not after).
- **FDCPA-style tone enforcement:** the guardrails in
  [`prompts/05-guardrails.md`](../prompts/05-guardrails.md) are prompt-level; production should
  add a post-call automated compliance scan (a second, narrow LLM pass or rule-based keyword
  scan over the transcript) that flags any turn resembling a threat, legal claim, or disclosed
  amount pre-verification for human QA review, independent of the disposition analytics pass.

## Disaster recovery (DR)

- **RPO/RTO targets:** define acceptable data loss (e.g. 15 minutes) and recovery time (e.g. 1
  hour) and size the MongoDB replica set + backup cadence to meet them.
- **Multi-region:** for a regulated financial workload, consider an active-passive deployment
  across two regions with async replication of the database and a documented failover runbook;
  the stateless FastAPI layer fails over trivially once DNS/load-balancer routing points at the
  standby region's database.
- **Runbook:** document manual reconciliation steps for calls left in `initiated`/`connected`
  state if the post-call webhook never arrives (Gnani-side outage) — a scheduled job that queries
  Gnani's call-status API for any call older than N minutes still not `completed`/`failed` in our
  store, and reconciles or flags it.

## CI/CD

- Pipeline stages: lint (ruff/flake8) → type-check (mypy) → unit tests (`pytest`, already in
  `tests/`) → build Docker image (`Dockerfile`) → integration test against the image with
  `docker-compose.yml` (mock mode) running `scripts/seed_scenarios.py` and asserting all 12
  scenarios pass → push image to registry → deploy to staging → smoke test `GET /health` →
  manual/automated promotion to production.
- Run `scripts/seed_scenarios.py` as a required CI gate on every pull request — a stage-code or
  webhook regression fails the build before merge, directly operationalizing the assignment's
  "Automated tests integrated with a CI/CD pipeline" bonus requirement.
- Store the `gnani_config/agent-config.json` export under version control (already true in this
  repo) and diff it in CI against the live Console configuration (via a Console export API, if
  available) to catch configuration drift between what is documented and what is actually
  published.
