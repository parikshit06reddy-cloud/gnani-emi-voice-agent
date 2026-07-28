# Reproducing the Agent in Gnani Agents Console

Step-by-step instructions to rebuild this Voice Agent in the real **Gnani Agents Console** UI
(`https://app.gnani.ai/agents/agent/list`), using [`agent-config.json`](./agent-config.json) as
the reference/import-compatible document. Every tab name, field name, dropdown option, and URL
below is taken from a live configuration session — see
[`CONSOLE_FINDINGS.md`](./CONSOLE_FINDINGS.md) for the full raw findings.

**Agent created in this session:**

| | |
|---|---|
| Name | `EMI Collections Agent - Apex Financial` |
| Agent ID | `d411993d126843e2912509f931d54ee2` |
| Config URL pattern | `https://app.gnani.ai/agents/agent/update?agentId=d411993d126843e2912509f931d54ee2&configTab=<TabName>` |
| `<TabName>` values | `System+Prompt`, `Agent+Details`, `Conversation+Flow`, `Transcriber`, `LLM+Model`, `Voice`, `Analytics`, `FAQ+Answers` |
| Agent list URL | `https://app.gnani.ai/agents/agent/list` |
| Channels | Chat, Voice (no separate inbound/outbound selector exists in this Console) |

---

## Requirement → Console mapping (read this first)

The assignment mandates **Gnani Prisma ASR**, **Gnani Timbre 2.5 TTS**, and **Gnani Evon LLM**. In
this Console tenant, "Prisma" and "Timbre 2.5" are not exposed as selectable models. In every one
of the three slots, the Gnani-native model actually available was selected — so the requirement
that "all three Gnani components are configured" is satisfied at the tenant-configuration level.
Only the specific model **names** "Prisma" and "Timbre 2.5" are unavailable in this tenant; Gnani
should enable them for the reviewer. Swapping the model name, once available, is a one-field
change — either the Console dropdown, or the `GNANI_ASR_MODEL` / `GNANI_TTS_MODEL` /
`GNANI_LLM_MODEL` environment variables that the backend reads (see `.env.example` and
`CONTRACT.md`) — no code changes required either way.

| Assignment-required component | Console provider/model actually available in this tenant | Selected | Note |
|---|---|---|---|
| Gnani Prisma ASR | Provider: Gnani, Microsoft. Gnani-native model: **Responsive** only | Gnani / **Responsive** | "Prisma" does not exist in this tenant's Transcriber tab. "Responsive" is the only Gnani-native ASR model. |
| Gnani Timbre 2.5 TTS | Service: Cartesia, ElevenLabs, Gemini, Gnani, Google, Microsoft, Speech Cloud. Gnani-native model: **Timbre G v1.0** only | Gnani / **Timbre G v1.0**, voice **Jenny (Female)** | "Timbre 2.5" does not exist in this tenant. "Gnani Timbre G v1.0" is the only Gnani-native TTS model; voices Elena/Jenny/John/Lucia support en-US + es-ES. |
| Gnani Evon LLM | Provider: Gnani, Google, Open AI. Gnani-native models: Aion v3.2, **Evon v2.0**, Evon v2.0 Fast, Evon v2.0 Ultra | Gnani / **Evon v2.0** | Exact match — "Evon" exists natively. Evon v2.0 Fast is the Console's default for new agents; changed to plain Evon v2.0 to match the assignment precisely. |

Full verbatim dropdown listings and screenshots of each screen are in
[`CONSOLE_FINDINGS.md`](./CONSOLE_FINDINGS.md) §4.

## Where the reviewer verifies each Gnani component

| Component | Console tab | Direct URL |
|---|---|---|
| ASR (Transcriber) | Transcriber | `https://app.gnani.ai/agents/agent/update?agentId=d411993d126843e2912509f931d54ee2&configTab=Transcriber` |
| LLM (LLM Model) | LLM Model | `https://app.gnani.ai/agents/agent/update?agentId=d411993d126843e2912509f931d54ee2&configTab=LLM+Model` |
| TTS (Voice) | Voice | `https://app.gnani.ai/agents/agent/update?agentId=d411993d126843e2912509f931d54ee2&configTab=Voice` |

Screenshots of these screens (captured during the live session):
[ASR config](./../docs/screenshots/gnani-asr-config.png),
[TTS config](./../docs/screenshots/gnani-tts-config.png),
[LLM config](./../docs/screenshots/gnani-llm-config.png).

---

## 1. Create the agent

1. Go to **Agent List** (`https://app.gnani.ai/agents/agent/list`) — see
   [`gnani-agent-list.png`](./../docs/screenshots/gnani-agent-list.png).
2. Click **Create Agent** → modal **"Select Creation Mode"**:
   - Create from Template
   - Create from Scratch
   - Import an Agent (.json upload) — you can also import a `.json` shaped like
     [`agent-config.json`](./agent-config.json) here.
3. Choose **Create from Scratch**. Fill the **"Add Agent Details"** modal:
   - **Name\*:** `EMI Collections Agent - Apex Financial`
   - **Region\*:** `America` (options: Asia, Europe, Africa, America, Antarctica, Pacific, Atlantic, Arctic)
   - **Time Zone\*:** `Eastern Standard Time (EST)` (options: EST, CST, MST, PST, Brasilia Time (BRT), Argentina Time (ART), Colombia Time (COT))
   - **Description:** `Outbound EMI payment collection voice agent. Bilingual English (US) and Spanish. Produces evidence-based disposition stage codes.`
   - **Icon\*:** default
4. Click **Create**. Note the generated Agent ID from the "⋮" menu (Agent ID with copy icon) —
   this is `d411993d126843e2912509f931d54ee2` in this session; set it as `GNANI_AGENT_ID` in `.env`.

See [`gnani-agent-overview.png`](./../docs/screenshots/gnani-agent-overview.png) for the resulting
tabbed Configuration UI.

## 2. Agent Details tab — Languages

1. Open the **Agent Details** tab (`configTab=Agent+Details`).
2. Language field (multi-select chip dropdown): add **English (US)** (primary) then **Spanish**.
3. A **"Language Change Confirmation"** modal appears warning that transcriber settings may need
   review — confirm via "Add Language".
4. New sections appear:
   - **Language Switch Trigger Threshold** — range 1–10, set to **2**.
   - **Language Switch Prompt** — mode selector: **Implicit Mode / Explicit Mode / Custom Mode**.
     Set to **Explicit Mode**. (Note: Implicit Mode is the more literal match if "automatic
     detection" is interpreted strictly — see [`CONSOLE_FINDINGS.md`](./CONSOLE_FINDINGS.md) §5.)
5. Save. See [`gnani-languages.png`](./../docs/screenshots/gnani-languages.png).

## 3. Transcriber tab — ASR (Gnani Responsive, standing in for Prisma)

1. Open **Transcriber** (`configTab=Transcriber`).
2. Field **"Select the ASR provider for your agent"** — dropdown options: **Gnani, Microsoft**.
   Select **Gnani**.
3. Under Gnani, the only model card is **"Responsive"** — *"Consistent low latency regardless of
   response length. Best when real-time feel is the priority."* Select it.
   (**Note:** "Prisma" is not offered in this tenant — see mapping table above.)
4. Configure the remaining fields on this tab (all real Console fields):
   - **Allow Interruptions** (toggle) + min-words-to-interrupt slider
   - **Initial Message Interruption** (toggle)
   - **Background Noise Filtering** (toggle + slider, range 20–100)
   - **Inverse Text Normalisation** (toggle)
   - **Max Speech Duration** (slider, range 1–240s)
   - **Initial Silence Timeout** (slider, range 10–60s)
   - **Speech Segmentation Silence** (slider, range 0.1–5s)
   - **Custom vocabulary** field ("Add product, people, brand names, etc") — add the English and
     Spanish phrase lists from `transcriber.custom_vocabulary` in
     [`agent-config.json`](./agent-config.json) (EMI, loan account, cuota, préstamo, etc.)
5. Save. See [`gnani-asr-config.png`](./../docs/screenshots/gnani-asr-config.png).

## 4. LLM Model tab — Gnani Evon v2.0 (exact match)

1. Open **LLM Model** (`configTab=LLM+Model`).
2. Field **"Select Provider"** — options: **Gnani, Google, Open AI**. Select **Gnani**.
3. Field **"Select Model"** under Gnani — options:
   - Gnani Aion v3.2 — "Stable and Ultra low latency for Indic"
   - **Gnani Evon v2.0** — "Strong performance across diverse workloads" ← select this
   - Gnani Evon v2.0 Fast — "Low latency, high performance intelligence" (pre-selected default)
   - Gnani Evon v2.0 Ultra — "Lightning speed"
4. Set **Temperature** to `0.5` and **Max Tokens** to `300` (helper text: "~3-4 chars or 3/4 of a
   word" per token).
5. Knowledge Base connector: leave unconnected (a non-blocking informational warning is expected
   — "Connect a KB with all required information...").
6. Save. See [`gnani-llm-config.png`](./../docs/screenshots/gnani-llm-config.png).

## 5. System Prompt tab

1. Open **System Prompt** (`configTab=System+Prompt`).
2. Paste the full contents of [`prompts/01-system-prompt.md`](../prompts/01-system-prompt.md)
   into the **"System Prompt\*"** field (helper text: "Define your agent's role, objectives, and
   conversation flow with customers.").
3. Click **Validate** — a word counter and a heuristic quality meter appear (this session's
   369-word prompt scored "Poor" on the quality meter; this is a subjective score, not a save
   blocker). Use the "⋮" → "Render" option to preview variable substitution if needed.
4. Save. See [`gnani-system-prompt.png`](./../docs/screenshots/gnani-system-prompt.png).

## 6. Voice tab — TTS (Gnani Timbre G v1.0, standing in for Timbre 2.5)

1. Open **Voice** (`configTab=Voice`).
2. Field **"Select the TTS provider for your agent"** — service dropdown options (7 total):
   **Cartesia, ElevenLabs, Gemini, Gnani, Google, Microsoft, Speech Cloud**. Select **Gnani**.
3. Under Gnani, the only model is **"Gnani Timbre G v1.0"**. Select it.
   (**Note:** "Timbre 2.5" is not offered in this tenant — see mapping table above.)
4. Voice dropdown options: **Elena (Female), Jenny (Female), John (Male), Lucia (Female)**. Select
   **Jenny (Female)** (a female voice, per the requirement). All four voices support both English
   (US) and Spanish per the Voice Library page (`https://app.gnani.ai/agents/voice-library`).
5. Set **Rate of Speech** to `1` (range 0.25–2). Leave **Caching** ON ("plays cached audio for
   common phrases"). Leave **Ambient Sound** OFF.
6. Save. See [`gnani-tts-config.png`](./../docs/screenshots/gnani-tts-config.png).

## 7. Conversation Flow tab

1. Open **Conversation Flow** (`configTab=Conversation+Flow`).
2. **Dynamic Messages** toggle: leave OFF ("Set dynamic messages fetched from APIs").
3. **Greeting Message\*** (required): set to
   *"Hello, this is Aria calling from Apex Financial Services regarding the loan account ending in
   {{loan_last4}}. May I confirm I am speaking with {{customer_name}}?"*
4. **Ending Message\*** (required): set to
   *"Thank you for your time today. Have a good day, and goodbye."* (not specified by the
   assignment; drafted to satisfy this mandatory field.)
5. **Pre-call Variables** toggle: turn **ON**. Table columns are **Variable | Sample Value**, with
   an always-present empty "Add variable" row. Add all 11 variables (sample values may be left
   blank):

   | Variable |
   |---|
   | `customer_name` |
   | `customer_id` |
   | `loan_last4` |
   | `loan_account_number` |
   | `emi_amount` |
   | `currency` |
   | `emi_due_date` |
   | `preferred_language` |
   | `current_date` |
   | `org_name` |
   | `bot_name` |

   See [`gnani-variables.png`](./../docs/screenshots/gnani-variables.png).
6. **Call transfer** toggle: leave OFF ("Transfer calls to a phone number based on the
   conditions") — not required for this agent.
7. Save.

## 8. Analytics tab — Post-call webhook (Post-Call Trigger)

1. Open **Analytics** (`configTab=Analytics`).
2. In the **"Post-Call Trigger"** section ("Set post call API config."), toggle it ON. A modal
   **"Add post call API config"** opens:
   - **Method\*** dropdown: **GET, POST, PUT, DELETE, PATCH** — select **POST**.
   - **URL\*:** `${PUBLIC_WEBHOOK_BASE_URL}/api/v1/webhooks/post-call` (resolve
     `PUBLIC_WEBHOOK_BASE_URL` from your `.env`, e.g. an ngrok tunnel URL for local testing).
   - **Headers** section: toggle it ON, then use the Key/Value table to add one row:
     - Key: `X-Webhook-Key`
     - Value: your `WEBHOOK_API_KEY` secret value
   - **In the shared account used for this submission, the Headers toggle was intentionally left
     OFF and no rows were added, so no secret was stored in a shared UI.** Do this step yourself
     in your own tenant before going live.
3. Save. The section then shows a **"Configure"** link to re-edit it. See
   [`gnani-postcall-webhook.png`](./../docs/screenshots/gnani-postcall-webhook.png).

## 9. Analytics tab — Post-call Data Extraction (disposition fields)

1. Same **Analytics** tab, **"Post-call Data Extraction"** section — *"Extract the final call
   outcome and key details from each call transcript."*
2. **Base Instructions** textarea: optionally add global context/rules (left empty in this
   session).
3. Click **"Add Data Field"** once per field below and fill in **Field Name**, **Type**, **Field
   Description**, **Options** (Enum only), and **Extraction Instruction**, then optionally click
   **Test Extraction**. All definitions below are derived from
   [`prompts/03-analytics-prompt.md`](../prompts/03-analytics-prompt.md):

   | Field Name | Type | Options (Enum only) | Extraction Instruction |
   |---|---|---|---|
   | `stage_code` | Enum | `PTP_TODAY`, `PTP_TOMORROW`, `PTP_FUTURE`, `PTP_PARTIAL`, `ALREADY_PAID`, `CALLBACK_SCHEDULED`, `RTP_FINANCIAL`, `RTP_MEDICAL`, `RTP_NO_REASON`, `DISPUTE_PAID`, `DISPUTE_CHARGES`, `NO_LOAN`, `WRONG_NUMBER`, `THIRD_PARTY`, `BUSY`, `RNR`, `VM`, `DSCN`, `UNCLEAR` (19 values) | Select exactly one stage code based only on explicit customer statements. Never infer or assume. Commitment codes require a verbatim evidence quote from a customer turn; if none exists, fall back to UNCLEAR (or BUSY/RNR/VM/DSCN for non-verbal outcomes). |
   | `disposition_reason` | String | — | Write one sentence (≤200 characters) stating what the customer explicitly said, not your inference. |
   | `disposition_summary` | String | — | Summarize the call in 2-4 factual sentences, no speculation. |
   | `ptp_date` | String | — | Resolve relative date expressions ("today", "tomorrow", "next week", weekday names, explicit dates) against `call_metadata.call_date`. Output ISO 8601 (`YYYY-MM-DD`) only. Leave null if no explicit date was stated. |
   | `ptp_amount` | Number | — | Populate only if the customer stated a specific amount. Never fabricate; leave null otherwise. |
   | `callback_datetime` | String | — | Populate only if the customer gave a specific day/time window for a callback (even approximate). Resolve to ISO 8601. Leave null otherwise. |
   | `customer_verified` | Boolean | — | True only if the transcript shows the customer affirmatively acknowledging their identity (e.g. "yes, this is Rahul"). A non-denial is not sufficient. |
   | `sentiment` | Enum | `positive`, `neutral`, `negative` | Classify overall customer sentiment across the call based on tone and content of customer turns only. |
   | `evidence_quote` | String | — | Copy an exact, character-for-character substring from a customer turn supporting the stage_code. If none exists for a commitment code, do not use that code — fall back to UNCLEAR/BUSY/RNR/VM/DSCN and leave this null. |
   | `confidence` | Number | — | 0.9–1.0 for explicit unambiguous statements with clean evidence; 0.6–0.89 for clear statements with minor ambiguity; below 0.6 for weak/partially-inferred signals (prefer UNCLEAR instead of forcing higher confidence). |

   No screenshot is included for this section: it could not be persisted in an enabled state
   (see the known console defect below), so the only capturable state was the section toggled off.
   The field definitions above are the exact values to enter once the defect is resolved.

4. **Known console defect:** saving with this section fully toggled ON (even with a single valid
   Enum field populated) returned **"Failed to update agent detail(s)"** repeatedly during this
   session. This looks like either a backend bug or an undocumented validation rule (possibly
   requiring ≥2 enum options or a populated Base Instructions field).
   **Workaround used for this submission:** the "Post-call Data Extraction" toggle was switched
   back **OFF** (keeping "Post-Call Trigger"/webhook ON) to achieve a clean, fully successful save
   — confirmed by the "Agent detail(s) updated successfully" toast. The field table above is
   provided so a reviewer (or Gnani engineering) can re-attempt entry once the defect is fixed.
   Full details in [`CONSOLE_FINDINGS.md`](./CONSOLE_FINDINGS.md) §9.
5. The backend independently re-validates `stage_code`/`evidence_quote`/dates regardless of this
   Console feature's state — see `app/services/stage_code.py` and
   [`docs/stage-code-logic.md`](../docs/stage-code-logic.md) — so the disposition pipeline is not
   solely dependent on this Console feature persisting.

## 10. FAQ Answers tab — known limitation

1. Open **FAQ Answers** (`configTab=FAQ+Answers`). Single toggle, description: *"Set predefined
   answers for user queries (Only available for English and Hindi)."*
2. **This feature does not support Spanish.** Since this agent is bilingual English (US)/Spanish,
   FAQ Answers was left OFF rather than shipping incomplete language coverage. This is a real
   Console limitation worth flagging to Gnani, not an implementation gap in this submission.

## 11. Save and verify

1. After each tab's changes, click **Save**. The top bar shows an orange "Save changes to test"
   warning until a fully valid save completes; once clean, it clears and the **Test** button
   becomes enabled.
2. Final confirmation for this agent: toast **"Agent detail(s) updated successfully"**, Test
   button enabled, no outstanding validation errors.
3. Trigger a call from your backend in mock mode (`GNANI_MODE=mock`, default) or live mode:
   ```bash
   curl -X POST "$PUBLIC_WEBHOOK_BASE_URL/api/Initial_Message" \
     -H "X-API-Key: $API_KEY" \
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
4. Verify the call appears on the dashboard (`/`) with a stage code and disposition reason
   populated, and that the detail page (`/detail.html?call_id=...`) shows engine badges — the
   dashboard's independent, second point of verification after publish. See
   [`docs/test-scenarios.md`](../docs/test-scenarios.md) for mock-mode behaviour and
   failure-injection phone suffixes.

## 12. What's NOT in this Console tenant

- No inbound/outbound agent type selector — agents carry Chat/Voice channel badges instead (see
  [`CONSOLE_FINDINGS.md`](./CONSOLE_FINDINGS.md) §2).
- No export/JSON-download action for an existing agent — only **Agent ID** (copy) and **Delete
  Agent** exist under the "⋮" menu. **Import from `.json` IS supported** as a creation mode, which
  is why [`agent-config.json`](./agent-config.json) is positioned as an import-compatible
  reference document rather than a literal Console export (see
  [`CONSOLE_FINDINGS.md`](./CONSOLE_FINDINGS.md) §10).
- No native Prisma ASR or Timbre 2.5 TTS models in this tenant (see mapping table above).
- No Spanish support in FAQ Answers (§10 above).

For the complete raw findings (every dropdown, every tab, the save defect, and recommendations to
Gnani), see [`CONSOLE_FINDINGS.md`](./CONSOLE_FINDINGS.md).
