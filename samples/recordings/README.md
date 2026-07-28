# Sample call recordings

Three end-to-end sample call recordings for the EMI collections agent. Each is a two-party
conversation (bot "Aria" from Apex Financial Services + borrower) covering a different disposition
path and a different language configuration.

| File | Language | Borrower | Loan | EMI / due date | Stage code | Duration |
|---|---|---|---|---|---|---|
| `CALL-SAMPLE-EN-PTP-FUTURE.mp3` | English (US) | Marcus Whitfield | `LAN4417` | 968.00 USD / 2026-07-21 | `PTP_FUTURE` (promise for 2026-08-08) | 1:03 |
| `CALL-SAMPLE-ES-RTP-FINANCIAL.mp3` | Spanish | Carmen Delgado | `LAN8302` | 519.99 USD / 2026-07-24 | `RTP_FINANCIAL` (job loss) | 1:07 |
| `CALL-SAMPLE-SWITCH-PTP-TOMORROW.mp3` | English → Spanish mid-call | Miguel Santos | `LAN6155` | 1200.00 USD / 2026-07-25 | `PTP_TOMORROW` (promise for 2026-07-29) | 1:00 |

## What each recording demonstrates

- **`CALL-SAMPLE-EN-PTP-FUTURE`** — identity verification before any account disclosure, EMI amount
  and due date read back, borrower proposes a specific future date, agent confirms date *and*
  amount, closing recap. Yields `stage_code=PTP_FUTURE` with a verbatim `evidence_quote`
  ("I could do it on the eighth of August") and `ptp_date` / `ptp_amount` populated.
- **`CALL-SAMPLE-ES-RTP-FINANCIAL`** — the entire call runs in Spanish from the greeting onward
  (pre-call `preferred_language` = Spanish). The borrower states a hardship reason, the agent
  acknowledges it without pressuring or threatening, and does not extract a promise it cannot
  substantiate. Yields `stage_code=RTP_FINANCIAL`, `sentiment=negative`, no `ptp_date`.
- **`CALL-SAMPLE-SWITCH-PTP-TOMORROW`** — starts in English (US); at turn 4 the borrower asks to
  continue in Spanish, and the agent switches for the remainder of the call. This exercises the
  Console's **Language Switch Trigger Threshold** and **Explicit Mode** switch prompt. Yields
  `language_captured=mixed`, `language_switched=true`, `stage_code=PTP_TOMORROW`.

## How they map into the demo

Each recording is attached to a seeded scenario and is served by the backend at
`/recordings/<filename>`, which is a `StaticFiles` mount over this directory (`RECORDINGS_DIR`).
Open the corresponding call on the dashboard detail page and the **Call recording** audio player
will stream the file; the on-screen **Conversation transcript** matches the audio turn for turn,
including per-turn language tags.

| Recording | Seed scenario | Stage code asserted |
|---|---|---|
| `CALL-SAMPLE-EN-PTP-FUTURE.mp3` | Scenario 2 — PTP on a specific future date | `PTP_FUTURE` |
| `CALL-SAMPLE-ES-RTP-FINANCIAL.mp3` | Scenario 5 — refusal to pay, financial hardship | `RTP_FINANCIAL` |
| `CALL-SAMPLE-SWITCH-PTP-TOMORROW.mp3` | Scenario 8 — language switch mid-call | `PTP_TOMORROW` |

Calls that are not one of these three intentionally have no `recording_url` and the detail page
renders "Recording unavailable" — this is the same graceful-degradation path used when the Gnani
platform has not yet published a recording for a call.

## Provenance

These are synthesized reference recordings produced from the scripted conversations in
`samples/recordings/transcripts/`, generated so that the dashboard audio player, transcript
alignment, and language-switch rendering can be demonstrated without placing real calls to real
borrowers. In production, `recording_url` is populated from the `recording_url` field of the Gnani
post-call webhook and points at Gnani-managed storage (90-day retention, see
[`docs/database-schema.md`](../../docs/database-schema.md)); no application change is required.
