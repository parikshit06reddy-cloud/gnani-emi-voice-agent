# Demo & presentation guide (assignment §12)

Step-by-step script for the **5–10 minute live demonstration** expected by the
assignment. Run through this once before the review session.

## Pre-demo checklist (5 minutes before)

```bash
# Option A — one command (Docker)
./scripts/demo_prepare.sh          # macOS/Linux
# or
.\scripts\demo_prepare.ps1         # Windows PowerShell

# Option B — manual
docker compose up --build -d
docker exec gnani-emi-api python scripts/seed_scenarios.py --base-url http://localhost:8000
```

Confirm:

- [ ] `curl -s http://localhost:8000/health` → `"repository":"mongo"`, `"gnani_mode":"mock"`
- [ ] Dashboard at [http://localhost:8000/](http://localhost:8000/) shows **14 calls**
- [ ] Open a call with a recording (e.g. `CALL-SAMPLE-EN-PTP-FUTURE`) — audio plays
- [ ] Swagger at [http://localhost:8000/docs](http://localhost:8000/docs) loads
- [ ] CI badge green on GitHub (pytest + 12/12 scenarios)

---

## Demo script (~8 minutes)

### 1. Architecture (60 s)

Open [`docs/architecture-diagram.png`](./architecture-diagram.png) or
[`docs/architecture.md`](./architecture.md).

**Say:**

> Outbound EMI collections voice agent on Gnani Agents Console. FastAPI
> initiates calls, receives post-call webhooks, runs a deterministic
> stage-code engine that validates LLM output against transcript evidence,
> and exposes everything to an ops dashboard with WebSocket updates.

Key flow: **Initial_Message → Gnani call → multi-turn ASR/LLM/TTS →
Analytics prompt → webhook → stage-code engine → dashboard**.

### 2. Gnani Console configuration (90 s)

Open the Console (or screenshots in `docs/screenshots/`):

| Tab | What to show |
|---|---|
| Agent list | `EMI Collections Agent - Apex Financial` |
| Transcriber | Gnani / **Responsive** (tenant's Gnani-native ASR; Prisma not listed) |
| Voice | Gnani / **Timbre G v1.0**, Jenny (Timbre 2.5 not listed in tenant) |
| LLM Model | Gnani / **Evon v2.0** — exact match |
| System Prompt | Pasted from `prompts/01-system-prompt.md` |
| Languages | en-US + es-ES |
| Analytics | Post-call webhook URL + analytics prompt |
| Pre-call variables | `customer_name`, `emi_amount`, `loan_last4`, etc. |

**Talking point (ASR/TTS naming):**

> The assignment specifies Prisma and Timbre 2.5 by name. This Console tenant
> only exposes Responsive (ASR) and Timbre G v1.0 (TTS) as Gnani-native
> options — documented in `gnani_config/CONSOLE_FINDINGS.md`. Evon v2.0 is an
> exact match. Swapping model names once enabled is a one-field Console change;
> no backend code changes required.

Direct config URL:
`https://app.gnani.ai/agents/agent/update?agentId=d411993d126843e2912509f931d54ee2&configTab=Agent+Details`

### 3. Conversation design (60 s)

Open [`prompts/02-conversation-flow.md`](./prompts/02-conversation-flow.md).

**Highlight:**

- 10-stage state machine (identity → EMI context → reminder → intent → …)
- Slot memory — never re-asks answered questions
- Identity gate — no amount/due date before verification
- Bilingual EN/ES with mid-call language switch
- FDCPA-style guardrails in `prompts/05-guardrails.md`

### 4. Initiate a call via FastAPI (90 s)

**Mock path (no phone needed):**

Swagger → `POST /api/Initial_Message` → Execute with:

```json
{
  "customer_id": "CUST-DEMO",
  "customer_name": "Demo Customer",
  "country_code": "+1",
  "phone_number": "5551234567",
  "loan_account_number": "LAN1234567890",
  "emi_amount": 1250.00,
  "currency": "USD",
  "emi_due_date": "2026-07-25",
  "preferred_language": "en-US"
}
```

Header: `X-API-Key: dev-api-key`

**Show response:** dynamic `initial_message`, masked phone, `call_status=initiated`.

**Live path (optional, impressive):**

Follow [`live-call-runbook.md`](./live-call-runbook.md) — set `GNANI_MODE=live`,
ngrok tunnel, place call to your own phone.

### 5. Stage-code engine (90 s)

Open [`docs/stage-code-logic.md`](./stage-code-logic.md) and briefly show
`app/services/stage_code.py`.

**Say:**

> We never trust the LLM's stage code blindly. Every commitment code requires
> an evidence quote that appears verbatim in a customer transcript turn, plus
> confidence above threshold. Failing checks downgrade to UNCLEAR or DSCN —
> matching the assignment rule: no disposition based on assumptions.

Quick example: show scenario 10 in dashboard — duplicate webhook, `duplicate: true`,
no duplicate row.

### 6. Dashboard walkthrough (90 s)

Open [http://localhost:8000/](http://localhost:8000/).

| Show | Where |
|---|---|
| Summary cards | Total, PTP, Already-paid, RTP, Dispute, Non-connect |
| Filters | Stage code, date, language, PTP date |
| Call list | Masked phone `******3210`, stage chips |
| Detail page | Transcript, disposition, raw webhook payload, audit log |
| Recording | Play `CALL-SAMPLE-EN-PTP-FUTURE.mp3` |
| Language switch | Open language-switch scenario — mixed language tags |
| Real-time | WebSocket indicator (green dot) or 10 s polling fallback |
| Charts | Stage-code bar + language donut |

### 7. Failure handling (60 s)

From seeded data or live curl:

| Scenario | Expected |
|---|---|
| Invalid request (missing phone) | `422 VALIDATION_ERROR` with field details |
| Gnani timeout (`phone …0000`) | `504 GNANI_TIMEOUT`, no orphan row |
| Gnani 5xx (`phone …9999`) | `502 GNANI_TRIGGER_FAILED` |
| Duplicate webhook | `200`, `"duplicate": true`, no state change |

Reference: [`docs/test-scenarios.md`](./test-scenarios.md) — **12/12 pass**.

### 8. Production readiness (30 s)

Open [`docs/production-readiness.md`](./production-readiness.md).

**Mention:** HMAC webhook signing, secrets manager, horizontal scaling, DNC
compliance, CI/CD (now implemented — see `.github/workflows/ci.yml`).

---

## Live call quick reference

See [`live-call-runbook.md`](./live-call-runbook.md) for the full procedure.

If the Gnani Console **cannot send custom webhook headers**, enable query-key
auth (HTTPS tunnel required):

```bash
# .env
WEBHOOK_ALLOW_QUERY_KEY=true
WEBHOOK_API_KEY=<strong-random-value>
```

Console Post-Call Trigger URL:

```
POST https://<ngrok-subdomain>.ngrok.app/api/v1/webhooks/post-call?webhook_key=<same-value>
```

---

## Recording a Loom / screen capture (submission item #15)

Suggested 3-minute structure:

1. **0:00–0:30** — Architecture diagram + repo overview
2. **0:30–1:30** — Dashboard: 14 seeded calls, filters, detail page, audio playback
3. **1:30–2:15** — Swagger: trigger call, show initial message
4. **2:15–2:45** — Console screenshots: ASR/TTS/LLM tabs
5. **2:45–3:00** — Test results: 12/12 scenarios, CI green

Save as `docs/demo-recording.mp4` or link in README — optional but strengthens
submission item #15.

---

## Interviewer Q&A prep

| Likely question | Answer pointer |
|---|---|
| Why Responsive instead of Prisma? | `gnani_config/CONSOLE_FINDINGS.md` — tenant limitation, closest Gnani-native ASR |
| How do you prevent wrong dispositions? | Evidence quote + confidence gate in `stage_code.py` |
| What if LLM hallucinates a PTP date? | Evidence-date consistency check; downgrade to UNCLEAR |
| Duplicate webhooks? | Idempotent on `event_id` (fallback `call_id+call_ended_at`) |
| How to go live? | `GNANI_MODE=live` + runbook; trigger API shape may need one iteration |
| Why mock mode default? | Zero-dependency demo; full lifecycle reproducible without Gnani credentials |
| MongoDB vs JSON? | `MONGODB_URI` presence selects backend; compose bundles Mongo |
