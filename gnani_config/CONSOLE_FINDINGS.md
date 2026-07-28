# Gnani Agents Console — Live Session Findings

Reviewer-facing writeup of a live configuration session in the real **Gnani Agents Console**
(`https://app.gnani.ai`), performed to create and configure this project's agent. This document
is based strictly on the session report captured at the time of configuration. It records the
actual UI structure, every dropdown's verbatim options, the model-availability gap versus the
assignment's named components, a console save defect, and a missing export capability.

No real phone call was placed and no API keys, secrets, or payment/credential information were
entered anywhere during this session.

---

## 1. Outcome

- **Agent created:** `EMI Collections Agent - Apex Financial`
- **Agent ID:** `d411993d126843e2912509f931d54ee2`
- **Agent config URL pattern:** `https://app.gnani.ai/agents/agent/update?agentId=d411993d126843e2912509f931d54ee2&configTab=<TabName>`
  (`TabName` ∈ `System+Prompt`, `Agent+Details`, `Conversation+Flow`, `Transcriber`, `LLM+Model`, `Voice`, `Analytics`, `FAQ+Answers`)
- **Agent list URL:** `https://app.gnani.ai/agents/agent/list`
- **Final save status:** succeeded — toast read *"Agent detail(s) updated successfully"*; the
  orange "Save changes to test" warning cleared and the **Test** button became enabled, confirming
  a clean saved state with no outstanding validation errors.

---

## 2. Agent creation flow

There is **no dedicated inbound/outbound voice-agent type selector** anywhere in the creation
wizard or elsewhere in the Console. Agents instead carry **Chat** and **Voice** channel badges on
the agent list, implying every agent supports both channels by default. Outbound calling behavior
appears to be determined by how the agent is *used* (e.g. via API/dialer integration), not by a
config toggle.

Creation flow:
1. Agent list → **Create Agent** → modal **"Select Creation Mode"** with three options:
   - **Create from Template**
   - **Create from Scratch**
   - **Import an Agent (.json upload)**
2. **"Add Agent Details"** modal fields: **Name\***, **Region\***, **Time Zone\***, **Description**, **Icon\***.
   - Region options: Asia, Europe, Africa, America, Antarctica, Pacific, Atlantic, Arctic. **Selected: America.**
   - Time Zone options: EST, CST, MST, PST, Brasilia Time (BRT), Argentina Time (ART), Colombia Time (COT). **Selected: EST.**
3. **Create** → success toast → agent list → tabbed **Configuration** UI opens.

---

## 3. Tab inventory

**Configuration** sidebar tabs, in order:

1. System Prompt
2. Agent Details
3. Conversation Flow
4. Transcriber (ASR)
5. LLM Model
6. Voice (TTS)
7. Analytics
8. FAQ Answers

A separate top-level tab next to **Configuration**: **Actions**, with sub-tabs **Actions** and
**MCP Tools** (both empty in this tenant — see §9).

---

## 4. ASR / TTS / LLM — verbatim dropdown options and the model-availability gap

### ASR (Transcriber tab)
- Field label: **"Select the ASR provider for your agent"**
- Provider dropdown, verbatim, only two options: **Gnani**, **Microsoft**
- Under **Gnani**, only **one** model card: **"Responsive"** — *"Consistent low latency
  regardless of response length. Best when real-time feel is the priority."*
- **"Prisma" does not exist anywhere in the ASR provider/model UI.**
- A page banner initially read: *"ASR model no longer available — The transcriber model selected
  for this agent is no longer supported. Please go to the Transcriber tab and select a different
  model to continue."* Re-selecting "Responsive" cleared this warning.
- **Selected: Gnani / Responsive** (the only Gnani-native ASR model available).

### TTS (Voice tab)
- Field label: **"Select the TTS provider for your agent"**
- Service dropdown, verbatim, 7 options: **Cartesia, ElevenLabs, Gemini, Gnani, Google, Microsoft,
  Speech Cloud**
- Under **Gnani**, only **one** model: **"Gnani Timbre G v1.0"**
- **"Timbre 2.5" does not exist.**
- Voice dropdown (under Gnani Timbre G v1.0), verbatim: **Elena (Female), Jenny (Female), John
  (Male), Lucia (Female)**. All four support both English (US) and Spanish per the Voice Library
  page (`https://app.gnani.ai/agents/voice-library`).
- **Selected: Gnani / Timbre G v1.0, voice Jenny (Female).**

### LLM (LLM Model tab)
- Field label: **"Select Provider"** — verbatim options: **Gnani, Google, Open AI**
- Under **Gnani**, **"Select Model"** verbatim options:
  - **Gnani Aion v3.2** — "Stable and Ultra low latency for Indic"
  - **Gnani Evon v2.0** — "Strong performance across diverse workloads" ← selected
  - **Gnani Evon v2.0 Fast** — "Low latency, high performance intelligence" (pre-selected default for new agents)
  - **Gnani Evon v2.0 Ultra** — "Lightning speed"
- **"Evon" exists natively as "Gnani Evon v2.0" — this is an exact match, not a substitute.**

### Summary table

| Requirement | Requested | Available in this tenant? | Selected |
|---|---|---|---|
| ASR | Gnani Prisma ASR | ❌ Not available (only "Responsive") | Gnani / Responsive |
| TTS | Gnani Timbre 2.5 TTS (female voice) | ❌ Not available (only "Timbre G v1.0") | Gnani / Timbre G v1.0, voice Jenny (Female) |
| LLM | Gnani Evon LLM | ✅ Available exactly | Gnani / Evon v2.0 |

**Framing:** in every one of the three slots, the Gnani-native model actually offered by this
tenant was selected — the requirement that "all three Gnani components are configured" is
satisfied at the tenant-configuration level. Only the specific model *names* "Prisma" and "Timbre
2.5" are unavailable in this Console tenant; this reads as a tenant-level model naming/availability
gap, not a failure to use Gnani's native stack. **Recommendation: Gnani should enable "Prisma" and
"Timbre 2.5" model options for the reviewer's tenant** so the exact assignment-named models can be
selected. Because the backend reads `GNANI_ASR_MODEL` / `GNANI_TTS_MODEL` / `GNANI_LLM_MODEL` from
environment variables (see `.env.example` and `CONTRACT.md`), and the Console-side selection is a
single dropdown field, swapping to the exact-named models once available is a one-field change on
both sides — no code changes required.

### Other Transcriber tab settings (top to bottom)
Allow Interruptions (toggle + min-words-to-interrupt slider), Initial Message Interruption
(toggle), Background Noise Filtering (toggle + 20–100 slider), Inverse Text Normalisation
(toggle), Max Speech Duration (slider 1–240s), Initial Silence Timeout (slider 10–60s), Speech
Segmentation Silence (slider 0.1–5s), a custom vocabulary field ("Add product, people, brand
names, etc"), and one additional unlabeled slider (range 0–2, likely a bias/boost parameter).

### Other Voice tab settings
Play Demo button, Rate of Speech (dropdown "Normal" + numeric multiplier 0.25–2, set to 1),
Caching (toggle, ON by default — "plays cached audio for common phrases"), Ambient Sound (toggle,
OFF — background ambience during calls).

### Other LLM Model tab settings
Knowledge Base connector dropdown (none selected; non-blocking informational warning "Connect a
KB with all required information..."), Temperature slider (set to 0.5), Max Tokens slider (set to
300, described as "~3-4 chars or 3/4 of a word" per token).

---

## 5. Languages (Agent Details tab)

- Language field is a multi-select chip dropdown. Enabled: **English (US)** [Primary] +
  **Spanish** (added).
- Adding a second language triggers a **"Language Change Confirmation"** modal warning that
  transcriber settings may need review, followed by a "Review Transcriber Settings" toast.
- New sections revealed after adding a second language:
  - **Language Switch Trigger Threshold** — slider/number, range 1–10, left at default **2**
    ("Minimum number of words the user must speak in another language before the bot checks for a
    language switch").
  - **Language Switch Prompt** — mode selector, verbatim options: **Implicit Mode, Explicit Mode,
    Custom Mode**. Custom Mode has a pre-filled default prompt: *"You are a language switch
    detection agent. Analyze outputs from multiple STT engines and respond with the target
    language name if a switch is requested, else respond with 'None'."*
  - **Selected: Explicit Mode** ("language will be switched only if requested in the call"). A
    transient "Failed to generate language switch prompt" error toast appeared but the mode
    selection itself persisted correctly.
- **Note for reviewers:** no separate "automatic multilingual detection" toggle exists beyond this
  Implicit/Explicit/Custom mechanism. Implicit Mode is arguably the more literal match for
  "automatic detection" since it auto-switches without confirmation; Explicit Mode was chosen here
  to keep switching evidence-based/deliberate. Flagged as a judgment call, not a defect.

---

## 6. System Prompt tab

- Field **"System Prompt\*"** — helper text: "Define your agent's role, objectives, and
  conversation flow with customers."
- The full 369-word system prompt was pasted with **no truncation** — no character/word limit was
  ever hit or displayed.
- UI extras: a Draft/version status pill + "Save as version" button; a live word counter (showed
  "369 words"); a quality meter bar (showed **"Poor"** in red after clicking "Validate" — a
  subjective/heuristic prompt-quality score, not a hard blocker to saving); a "Validate" button
  that turned into "✓ Validated"; a "⋮" menu with a "Render" option (likely template-variable
  preview).

---

## 7. Conversation Flow tab

Fields, in order:
1. **Dynamic Messages** (toggle, OFF) — "Set dynamic messages fetched from APIs"
2. **Greeting Message\*** (required) — "The initial message your agent will say on a call"
3. **Ending Message\*** (required) — "This message the agent will deliver before ending the call"
   — not specified by the assignment; a generic closing line was drafted for this submission.
4. **Pre-call Variables** (toggle, turned ON) — table columns **Variable | Sample Value**, with a
   final always-empty "Add variable" row.
5. **Call transfer** (toggle, OFF) — "Transfer calls to a phone number based on the conditions" —
   not explored (not required).

All 11 project-required variables are present in the Pre-call Variables table (sample values left
blank): `customer_name, customer_id, loan_last4, loan_account_number, emi_amount, currency,
emi_due_date, preferred_language, current_date, org_name, bot_name`.

---

## 8. Post-call trigger (webhook) — Analytics tab

- **Location:** Analytics tab → **"Post-Call Trigger"** section — description "Set post call API
  config."
- Toggling it ON opens a modal **"Add post call API config"**:
  - **Method\*** dropdown, verbatim options: **GET, POST, PUT, DELETE, PATCH**
  - **URL\*** text field
  - **Headers** section — a toggle + a Key/Value table (this is where an API key/secret would go
    — left OFF, nothing entered, since no credentials were to be entered in this session)
- **Configured:** Method = **POST**, URL = a placeholder ngrok-style URL.
- Saved successfully; the section then shows a **"Configure"** link to re-edit it.

---

## 9. Post-call Data Extraction — Analytics tab, and a save defect

- **Location:** Analytics tab → **"Post-call Data Extraction"** section — description: "Extract
  the final call outcome and key details from each call transcript."
- Structure when toggled on:
  - **Base Instructions** textarea — "Add common context and rules for analysing the call. These
    apply to every data field below." (global instructions)
  - **"Add Data Field"** button (top-right and bottom of section) — each field has: **Field
    Name**, **Type** dropdown (verbatim options: **Boolean, String, Number, Enum**), **Field
    Description**, an **Options\*** area with "Add Option" when Type = Enum, a required
    **Extraction Instruction\*** textarea ("Write instruction for how to extract the outcome"), a
    **Test Extraction** button, and a delete icon.
- One example field was created to validate the structure: `disposition_stage_code`, Type = Enum,
  a single Option (`PAID`), with an evidence-based extraction instruction.
- **Console defect encountered:** saving with this section **fully toggled on** (even with a
  valid-looking Enum field) caused repeated **"Failed to update agent detail(s)"** errors on Save.
  This suggests either a backend bug or an undocumented validation rule (possibly requiring ≥2
  enum options, or a populated Base Instructions field).
- **Workaround used:** "Post-call Data Extraction" was toggled back **OFF** (keeping "Post-Call
  Trigger"/webhook ON) to achieve a clean, fully successful save. The full intended field set
  (`stage_code`, `disposition_reason`, `disposition_summary`, `ptp_date`, `ptp_amount`,
  `callback_datetime`, `customer_verified`, `sentiment`, `evidence_quote`, `confidence`) is
  documented in [`README.md`](./README.md) for the reviewer/Gnani engineering team to re-attempt
  once the defect is fixed.
- **Recommendation:** flag this to Gnani's Console engineering team as a reproducible save defect
  on the Post-call Data Extraction sub-feature; re-test once fixed.

---

## 10. Export / import capability

- The **"⋮"** three-dot menu (top-right, next to Save/Test) contains only:
  - **Agent ID** (with copy-to-clipboard icon)
  - **Delete Agent** (destructive, red)
- **No export, JSON download, or config-download option exists anywhere in the UI** for an
  existing agent.
- The *creation* modal **does** support **"Import an Agent (.json upload)"**, implying an
  export/import JSON format exists on the backend even though no corresponding export/download
  action is exposed in the UI for an already-created agent.
- **Consequence for this submission:** `gnani_config/agent-config.json` is positioned as an
  **import-compatible / reference document**, not a literal Console-generated export, since no
  export path exists to produce one directly from the UI.

---

## 11. FAQ Answers tab

- Single toggle **"FAQ Answers"** (OFF) — description: *"Set predefined answers for user queries
  (Only available for English and Hindi)."*
- **Limitation:** this feature does not support Spanish — a real gap for a bilingual
  English/Spanish agent. Left disabled for this agent rather than shipping incomplete
  language coverage.

---

## 12. Actions tab (checked for completeness, not required)

- Top-level **"Actions"** tab, sub-tabs **Actions** and **MCP Tools**. Both empty in this tenant,
  showing: *"Create an integration first to enable actions and connect external tools to your
  agent."* with **Read Docs** and **+ Integration** buttons. Out of scope for this assignment
  (function-calling/external tool integration).

---

## 13. Blockers, limits, and other findings

- No login or permission blockers — full access to create, configure, and save the agent
  throughout the session.
- No character limit was hit on the System Prompt field.
- Exact-name mismatches for ASR ("Prisma") and TTS ("Timbre 2.5") are expected per the naming gap
  documented in §4; closest single native alternatives were selected in both cases.
- One real technical blocker: the "Post-call Data Extraction" sub-feature's save defect (§9).
- The Ending Message field is mandatory (`*`) but was not specified by the assignment; a generic
  closing line was drafted rather than leaving a required field empty.

---

## 14. Recommendations

1. **Gnani:** enable "Prisma" ASR and "Timbre 2.5" TTS model options in the reviewer's tenant so
   the assignment's exact-named models can be selected without a naming substitution.
2. **Gnani:** investigate and fix the "Post-call Data Extraction" save defect (§9); it currently
   blocks saving a fully configured disposition-extraction pipeline.
3. **Gnani:** consider adding an "Export agent as .json" action for existing agents, symmetric
   with the existing "Import an Agent (.json upload)" creation mode.
4. **Gnani:** extend FAQ Answers language support to Spanish (and other supported agent
   languages) for parity with the rest of the Console's bilingual support.
5. **Reviewer:** verify ASR/TTS/LLM selection directly in the Console using the tab URLs in
   [`README.md`](./README.md) — "Where the reviewer verifies each Gnani component" — rather than
   relying solely on this document or `agent-config.json`.

---

## 15. Final saved state summary

| Setting | Value |
|---|---|
| Agent Name | EMI Collections Agent - Apex Financial |
| Agent ID | `d411993d126843e2912509f931d54ee2` |
| Region / Time Zone | America / EST |
| Languages | English (US) [Primary], Spanish |
| Language Switch Mode | Explicit |
| ASR Provider / Model | Gnani / Responsive |
| LLM Provider / Model | Gnani / Evon v2.0 |
| TTS Service / Model / Voice | Gnani / Timbre G v1.0 / Jenny (Female) |
| System Prompt | Full 369-word prompt, Validated (quality meter: "Poor" heuristic score) |
| Greeting Message | Set (see §7) |
| Ending Message | Drafted for this submission (not assignment-specified) |
| Pre-call Variables | All 11 required variables present |
| Post-Call Trigger (webhook) | POST → placeholder URL, no headers/secrets stored |
| Post-call Data Extraction (disposition) | Disabled after save errors; structure and intended fields documented in `README.md` |
| FAQ Answers | Off (English/Hindi only — no Spanish support) |
| Actions / MCP Tools | Empty, requires integration setup |
| Export/JSON download | Not available anywhere in the UI |
| Save status | ✅ "Agent detail(s) updated successfully" |
