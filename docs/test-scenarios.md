# Mandatory Test Scenarios (Assignment §9)

All 12 scenarios run end-to-end in `GNANI_MODE=mock` via `scripts/seed_scenarios.py`, which is
owned by the backend team; this document specifies how each scenario is triggered, what stage
code and dashboard result is expected, and how to read the results file it produces. Actual
results are written to [`test-results.json`](./test-results.json) by that script and are not
authored by this document — this table is the durable cross-reference between the assignment's
required scenario list and that generated evidence file.

## Mock-mode failure-injection convention

Per `CONTRACT.md` and the backend notes (`docs/BACKEND_NOTES.md`, owned by the backend agent),
mock mode (`GNANI_MODE=mock`, the default) simulates the Gnani call-trigger API and the
conversational loop deterministically based on the last 4 digits of `phone_number`, so scenarios
are reproducible without a live Gnani connection or a real phone call:

| Phone number suffix | Simulated behavior | Used for scenario |
|---|---|---|
| `...0000` | Gnani call-trigger API call times out on every attempt | 12 (timeout variant) |
| `...9999` | Gnani call-trigger API returns HTTP 5xx on every attempt | 12 (5xx variant) |
| any other suffix | Trigger succeeds; mock conversation script keyed by scenario metadata produces a canned transcript + disposition | 1-9 |

## Scenario table

| # | Scenario | Trigger | Expected stage code | Expected dashboard result | Result |
|---|---|---|---|---|---|
| 1 | Customer commits to paying today | `POST /api/Initial_Message` (normal phone suffix) followed by mock post-call webhook with customer turn "I'll pay it today" | `PTP_TODAY` | Row shows stage chip `PTP_TODAY`, PTP calls summary card increments, `ptp_date` = call date | See [`test-results.json`](./test-results.json) → `scenario_01` |
| 2 | Customer provides a future PTP date | Same, transcript turn "I can pay on the 30th" | `PTP_FUTURE` | Stage chip `PTP_FUTURE`, `ptp_date` = resolved future date, PTP card increments | See [`test-results.json`](./test-results.json) → `scenario_02` |
| 3 | Customer states payment already complete | Same, transcript turn "I already paid this" (no dispute framing) | `ALREADY_PAID` | Stage chip `ALREADY_PAID`, Already-Paid card increments | See [`test-results.json`](./test-results.json) → `scenario_03` |
| 4 | Customer requests a callback | Same, transcript turn "call me tomorrow evening" | `CALLBACK_SCHEDULED` | Stage chip `CALLBACK_SCHEDULED`, `callback_datetime` populated, Callback card increments | See [`test-results.json`](./test-results.json) → `scenario_04` |
| 5 | Customer refuses to pay, financial difficulty | Same, transcript turn "I lost my job, can't pay" | `RTP_FINANCIAL` | Stage chip `RTP_FINANCIAL`, RTP card increments | See [`test-results.json`](./test-results.json) → `scenario_05` |
| 6 | Customer disputes the EMI amount | Same, transcript turn "this amount is wrong, I was overcharged" | `DISPUTE_CHARGES` | Stage chip `DISPUTE_CHARGES`, Dispute card increments | See [`test-results.json`](./test-results.json) → `scenario_06` |
| 7 | A third party answers the call | Same, mock transcript has non-borrower speaker confirming borrower is reachable | `THIRD_PARTY` | Stage chip `THIRD_PARTY`, `customer_verified=false` | See [`test-results.json`](./test-results.json) → `scenario_07` |
| 8 | Customer changes language mid-call | Same, transcript starts `en-US`, second half `es-ES` | Any resolvable code (e.g. `PTP_TOMORROW`) with `language_captured=mixed` | Detail page shows `language_switched=true`, per-turn language tags alternate | See [`test-results.json`](./test-results.json) → `scenario_08` |
| 9 | Call disconnects, no clear outcome | Same, transcript has 1-2 customer turns then call_status=failed | `DSCN` | Stage chip `DSCN`, Non-connect card increments | See [`test-results.json`](./test-results.json) → `scenario_09` |
| 10 | Duplicate post-call webhook | Send the same webhook payload (same `event_id`) twice via `curl` | Unchanged (whatever scenario 1-9's webhook set) | Dashboard row unchanged after 2nd delivery, no duplicate row created, response `duplicate: true` | See [`test-results.json`](./test-results.json) → `scenario_10` |
| 11 | Invalid initial call request | `POST /api/Initial_Message` with malformed body (see [`api.md`](./api.md) §1 422 example) | n/a (request rejected before any call) | No row created; 422 response with field-level `details` | See [`test-results.json`](./test-results.json) → `scenario_11` |
| 12 | Gnani API fails or times out | `POST /api/Initial_Message` with `phone_number` ending `...0000` (timeout) and `...9999` (5xx) | n/a (call never initiated) | No row created, or row created with `call_status=failed`; 504/502 response respectively | See [`test-results.json`](./test-results.json) → `scenario_12_timeout`, `scenario_12_5xx` |

## Running the scenarios

```bash
# from the project root, with the app running locally (see README.md Quickstart)
python scripts/seed_scenarios.py
```

This populates [`test-results.json`](./test-results.json) with the request sent, the response
received, the resulting stage code, and a pass/fail flag per scenario, and leaves the
corresponding call records visible on the dashboard (`http://localhost:8000/`) for manual visual
confirmation — satisfying assignment §9's requirement that "the resulting stage code and
disposition reason should be visible on the dashboard for every completed test call."

## Cross-references

- Backend implementation notes and any additional mock-mode conventions:
  [`BACKEND_NOTES.md`](./BACKEND_NOTES.md) (owned by the backend agent).
- Stage-code validation pipeline applied to every scenario's webhook:
  [`stage-code-logic.md`](./stage-code-logic.md).
- Full endpoint/error reference used by each cURL trigger above: [`api.md`](./api.md).
- Dashboard visual evidence: [`screenshots/dashboard-list.png`](./screenshots/dashboard-detail.png)
  and [`screenshots/dashboard-detail.png`](./screenshots/dashboard-detail.png) (owned by the
  dashboard agent).

## Scenarios with playable sample recordings

Three of the seeded scenarios ship with real, playable audio so the dashboard's audio player,
transcript alignment, and language-switch rendering can be reviewed without placing live calls.
The audio is served from `/recordings/<filename>` (a `StaticFiles` mount over
`samples/recordings/`, configurable via `RECORDINGS_DIR`).

| Scenario | Recording | Language | Stage code |
|---|---|---|---|
| 2 — PTP on a specific future date | `CALL-SAMPLE-EN-PTP-FUTURE.mp3` | English (US) | `PTP_FUTURE` |
| 5 — Refusal to pay, financial hardship | `CALL-SAMPLE-ES-RTP-FINANCIAL.mp3` | Spanish | `RTP_FINANCIAL` |
| 8 — Language switch mid-call | `CALL-SAMPLE-SWITCH-PTP-TOMORROW.mp3` | English → Spanish | `PTP_TOMORROW` |

The on-screen transcript for these three is generated from the same scripts used to produce the
audio, so it matches the recording turn for turn (including per-turn language tags). Every other
seeded call intentionally has `recording_url = null` and renders "Recording unavailable" — the same
graceful-degradation path used when Gnani has not yet published a recording for a call. See
[`samples/recordings/README.md`](../samples/recordings/README.md) for full details.
