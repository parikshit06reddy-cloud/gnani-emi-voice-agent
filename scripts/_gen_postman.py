"""One-off generator for postman/Gnani-EMI-Voice-Agent.postman_collection.json.

Not part of the runtime application; run manually to regenerate the
collection if endpoints change. Kept in scripts/ for traceability.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def item(name, method, path, *, headers=None, body=None, description="", query=None):
    headers = headers or []
    req = {
        "method": method,
        "header": headers,
        "url": {
            "raw": "{{base_url}}" + path + (("?" + "&".join(f"{k}={v}" for k, v in query.items())) if query else ""),
            "host": ["{{base_url}}"],
            "path": [p for p in path.lstrip("/").split("/") if p],
        },
        "description": description,
    }
    if query:
        req["url"]["query"] = [{"key": k, "value": str(v)} for k, v in query.items()]
    if body is not None:
        req["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2), "options": {"raw": {"language": "json"}}}
    return {"name": name, "request": req, "response": []}


API_KEY_HEADER = [{"key": "X-API-Key", "value": "{{api_key}}", "type": "text"}]
WEBHOOK_KEY_HEADER = [{"key": "X-Webhook-Key", "value": "{{webhook_key}}", "type": "text"}]
JSON_CONTENT = {"key": "Content-Type", "value": "application/json", "type": "text"}


def initiate_body(customer_id, phone_suffix, *, customer_name="Marcus Whitfield", **overrides):
    body = {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "phone_number": f"98765{phone_suffix}",
        "country_code": "+1",
        "loan_account_number": f"LAN{phone_suffix}",
        "emi_amount": 1200.0,
        "emi_due_date": "2026-07-25",
        "preferred_language": "English (US)",
        "currency": "USD",
    }
    body.update(overrides)
    return body


def webhook_body(call_id, event_id, disposition, transcript, **overrides):
    body = {
        "event_id": event_id,
        "call_id": call_id,
        "gnani_call_reference": f"gnani-{event_id}",
        "call_status": "completed",
        "call_duration_seconds": 95,
        "call_started_at": "2026-07-28T12:00:00+00:00",
        "call_ended_at": "2026-07-28T12:01:35+00:00",
        "recording_url": f"/recordings/{call_id}.wav",
        "language_detected": "en-US",
        "asr_engine": "gnani-prisma",
        "tts_engine": "gnani-timbre-2.5",
        "llm_engine": "gnani-evon",
        "disposition": disposition,
        "transcript": transcript,
    }
    body.update(overrides)
    return body


def turn(n, speaker, text, lang="en-US"):
    return {"turn": n, "speaker": speaker, "text": text, "language": lang}


scenarios_folder_items = []

# 1. PTP today
scenarios_folder_items.append(item(
    "Scenario 1 - Initiate: PTP today",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM01", "100001", customer_name="Marcus Whitfield"),
    description="Initiate a call for a customer who will later promise to pay today.",
))
scenarios_folder_items.append(item(
    "Scenario 1 - Webhook: PTP today",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=webhook_body(
        "CALL-20260728-0001", "evt-pm-01",
        {
            "stage_code": "PTP_TODAY",
            "disposition_reason": "Customer explicitly committed to paying today.",
            "disposition_summary": "Customer confirmed identity and promised full payment today.",
            "ptp_date": "2026-07-28",
            "ptp_amount": 1200.0,
            "confidence": 0.95,
            "customer_verified": True,
            "sentiment": "positive",
            "evidence_quote": "I will pay it today, no problem",
        },
        [
            turn(1, "bot", "Hello, may I confirm I'm speaking with Marcus Whitfield regarding your loan ending in 3456?"),
            turn(2, "customer", "Yes, this is Marcus speaking."),
            turn(3, "bot", "Your EMI of 1200.00 USD was due on July 25, 2026. Are you able to make the payment?"),
            turn(4, "customer", "Oh yes, I forgot. Let me pay it right now."),
            turn(5, "bot", "So you will pay the full amount today?"),
            turn(6, "customer", "Yes, I will pay it today, no problem."),
        ],
    ),
))

# 2. Future PTP (real recorded call: CALL-SAMPLE-EN-PTP-FUTURE)
scenarios_folder_items.append(item(
    "Scenario 2 - Initiate: Future PTP",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM02", "100002", customer_name="Marcus Whitfield", loan_account_number="LAN4417", preferred_language="English (US)", emi_amount=968.0, emi_due_date="2026-07-21"),
))
scenarios_folder_items.append(item(
    "Scenario 2 - Webhook: Future PTP",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=webhook_body(
        "CALL-20260728-0002", "evt-pm-02",
        {
            "stage_code": "PTP_FUTURE",
            "disposition_reason": "Customer committed to a specific future payment date after his next payday.",
            "disposition_summary": "Customer cannot pay today but committed to paying the full EMI on August 8th once he gets paid.",
            "ptp_date": "2026-08-08",
            "ptp_amount": 968.0,
            "confidence": 0.9,
            "customer_verified": True,
            "sentiment": "neutral",
            "evidence_quote": "I could do it on the eighth of August",
        },
        [
            turn(1, "bot", "Hello, this is Aria calling from Apex Financial Services regarding the loan account ending in 4417. May I confirm I am speaking with Marcus Whitfield?"),
            turn(2, "customer", "Yeah, this is Marcus."),
            turn(3, "bot", "Thank you for confirming, Marcus. I'm calling about your monthly installment of nine hundred sixty eight dollars, which was due on July twenty first. Are you able to take care of that today?"),
            turn(4, "customer", "Not today, no. I just moved and things have been tight."),
            turn(5, "bot", "I understand. Is there a date in the next couple of weeks when you would be able to make the payment?"),
            turn(6, "customer", "I get paid on the seventh, so... I could do it on the eighth of August."),
            turn(7, "bot", "August eighth. And would that be the full nine hundred sixty eight dollars?"),
            turn(8, "customer", "Yes, the full amount."),
            turn(9, "bot", "Perfect. So just to confirm, you will pay nine hundred sixty eight dollars on August eighth. Is that correct?"),
            turn(10, "customer", "That's correct."),
            turn(11, "bot", "Thank you, Marcus. I've noted that down. You'll receive a reminder before the date. Have a good day."),
            turn(12, "customer", "Thanks. Bye."),
        ],
        language_detected="en-US",
        recording_url="/recordings/CALL-SAMPLE-EN-PTP-FUTURE.mp3",
    ),
))

# 3. Already paid
scenarios_folder_items.append(item(
    "Scenario 3 - Initiate: Already paid",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM03", "100003", customer_name="Priya Raghunathan", emi_amount=968.0),
))
scenarios_folder_items.append(item(
    "Scenario 3 - Webhook: Already paid",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=webhook_body(
        "CALL-20260728-0003", "evt-pm-03",
        {
            "stage_code": "ALREADY_PAID",
            "disposition_reason": "Customer states the EMI was already paid two days ago.",
            "disposition_summary": "Customer claims payment already made; pending verification.",
            "confidence": 0.85,
            "customer_verified": True,
            "sentiment": "neutral",
            "evidence_quote": "I already paid this EMI two days ago online",
        },
        [
            turn(1, "bot", "May I confirm I'm speaking with Priya Raghunathan about the loan ending in 3456?"),
            turn(2, "customer", "Yes, speaking."),
            turn(3, "bot", "Your EMI of 968.00 USD was due on July 25. Have you made this payment?"),
            turn(4, "customer", "Yes actually, I already paid this EMI two days ago online."),
        ],
    ),
))

# 4. Callback requested
scenarios_folder_items.append(item(
    "Scenario 4 - Initiate: Callback requested",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM04", "100004", customer_name="Daniel O'Sullivan", emi_amount=1875.5),
))
scenarios_folder_items.append(item(
    "Scenario 4 - Webhook: Callback requested",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=webhook_body(
        "CALL-20260728-0004", "evt-pm-04",
        {
            "stage_code": "CALLBACK_SCHEDULED",
            "disposition_reason": "Customer requested a callback at a specific time tomorrow.",
            "disposition_summary": "Customer busy, requested callback tomorrow at 5pm.",
            "callback_datetime": "2026-07-29T17:00:00+00:00",
            "confidence": 0.88,
            "customer_verified": True,
            "sentiment": "neutral",
            "evidence_quote": "Please call me back tomorrow at 5pm",
        },
        [
            turn(1, "bot", "Am I speaking with Daniel O'Sullivan about your EMI?"),
            turn(2, "customer", "Yes, but I'm in a meeting right now."),
            turn(3, "bot", "I understand, this will be quick. Can I proceed?"),
            turn(4, "customer", "No, I really can't talk now. Please call me back tomorrow at 5pm."),
        ],
    ),
))

# 5. RTP financial (real recorded call: CALL-SAMPLE-ES-RTP-FINANCIAL)
scenarios_folder_items.append(item(
    "Scenario 5 - Initiate: RTP financial hardship",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM05", "100005", customer_name="Carmen Delgado", loan_account_number="LAN8302", preferred_language="Spanish", emi_amount=519.99, emi_due_date="2026-07-24"),
))
scenarios_folder_items.append(item(
    "Scenario 5 - Webhook: RTP financial hardship",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=webhook_body(
        "CALL-20260728-0005", "evt-pm-05",
        {
            "stage_code": "RTP_FINANCIAL",
            "disposition_reason": "Customer cites job loss and financial hardship.",
            "disposition_summary": "Customer lost her job last month and cannot commit to a payment date; requested deferral options.",
            "confidence": 0.9,
            "customer_verified": True,
            "sentiment": "negative",
            "evidence_quote": "Perdí mi trabajo el mes pasado y ahora mismo no tengo ese dinero",
        },
        [
            turn(1, "bot", "Buenas tardes, le llama Aria de Apex Financial Services sobre la cuenta de préstamo que termina en 8302. ¿Hablo con Carmen Delgado?", "es-ES"),
            turn(2, "customer", "Sí, soy Carmen.", "es-ES"),
            turn(3, "bot", "Gracias por confirmar, Carmen. Le llamo por su cuota mensual de quinientos diecinueve dólares con noventa y nueve centavos, que venció el veinticuatro de julio. ¿Podría realizar el pago hoy?", "es-ES"),
            turn(4, "customer", "No puedo. Perdí mi trabajo el mes pasado y ahora mismo no tengo ese dinero.", "es-ES"),
            turn(5, "bot", "Lamento escuchar eso. ¿Tiene alguna idea de cuándo podría cambiar su situación?", "es-ES"),
            turn(6, "customer", "Estoy buscando trabajo, pero de verdad no puedo comprometerme a una fecha. No quiero prometer algo que no pueda cumplir.", "es-ES"),
            turn(7, "bot", "Entiendo, y le agradezco su honestidad. Voy a registrar que no puede pagar por dificultades económicas. ¿Le gustaría que le enviemos información sobre nuestras opciones de aplazamiento?", "es-ES"),
            turn(8, "customer", "Sí, por favor. Eso me ayudaría mucho.", "es-ES"),
            turn(9, "bot", "Perfecto. Nuestro equipo de servicio se pondrá en contacto con usted con esas opciones. Gracias por su tiempo, Carmen. Que tenga un buen día.", "es-ES"),
            turn(10, "customer", "Gracias a usted. Adiós.", "es-ES"),
        ],
        language_detected="es-ES",
        recording_url="/recordings/CALL-SAMPLE-ES-RTP-FINANCIAL.mp3",
    ),
))

# 6. Dispute EMI amount
scenarios_folder_items.append(item(
    "Scenario 6 - Initiate: Dispute EMI amount",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM06", "100006", customer_name="Tyrone Jackson", emi_amount=2150.0),
))
scenarios_folder_items.append(item(
    "Scenario 6 - Webhook: Dispute EMI amount",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=webhook_body(
        "CALL-20260728-0006", "evt-pm-06",
        {
            "stage_code": "DISPUTE_CHARGES",
            "disposition_reason": "Customer disputes penalty charges added to the EMI amount.",
            "disposition_summary": "Customer contests extra penalty charges on the EMI.",
            "confidence": 0.87,
            "customer_verified": True,
            "sentiment": "negative",
            "evidence_quote": "you've charged me a penalty that shouldn't be there",
        },
        [
            turn(1, "bot", "Am I speaking with Tyrone Jackson regarding your EMI ending in 3456?"),
            turn(2, "customer", "Yes, but I have an issue with this bill."),
            turn(3, "bot", "Please tell me more, I'd like to help."),
            turn(4, "customer", "This is the wrong amount, you've charged me a penalty that shouldn't be there."),
        ],
    ),
))

# 7. Third party answers
scenarios_folder_items.append(item(
    "Scenario 7 - Initiate: Third party answers",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM07", "100007", customer_name="Rebecca Lindqvist", emi_amount=385.5),
))
scenarios_folder_items.append(item(
    "Scenario 7 - Webhook: Third party answers",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=webhook_body(
        "CALL-20260728-0007", "evt-pm-07",
        {
            "stage_code": "THIRD_PARTY",
            "disposition_reason": "Someone other than the borrower answered; borrower reachable later.",
            "disposition_summary": "Borrower's brother answered, borrower reachable this evening.",
            "confidence": 0.82,
            "customer_verified": False,
            "sentiment": "neutral",
            "evidence_quote": "this is her brother. She's not here right now",
        },
        [
            turn(1, "bot", "May I confirm I'm speaking with Rebecca Lindqvist?"),
            turn(2, "customer", "No, this is her brother. She's not here right now."),
            turn(3, "bot", "I see, do you know when she'll be available?"),
            turn(4, "customer", "She should be back this evening, I can pass a message."),
        ],
    ),
))

# 8. Language switch mid-call (real recorded call: CALL-SAMPLE-SWITCH-PTP-TOMORROW)
scenarios_folder_items.append(item(
    "Scenario 8 - Initiate: Language switch mid-call",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM08", "100008", customer_name="Miguel Santos", loan_account_number="LAN6155", emi_amount=1200.0, emi_due_date="2026-07-25"),
))
scenarios_folder_items.append(item(
    "Scenario 8 - Webhook: Language switch mid-call (bilingual)",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=webhook_body(
        "CALL-20260728-0008", "evt-pm-08",
        {
            "stage_code": "PTP_TOMORROW",
            "disposition_reason": "Customer switched to Spanish and committed to paying the full EMI tomorrow.",
            "disposition_summary": "Customer requested to continue in Spanish and promised full payment on July 29th.",
            "ptp_date": "2026-07-29",
            "ptp_amount": 1200.0,
            "confidence": 0.9,
            "customer_verified": True,
            "sentiment": "positive",
            "evidence_quote": "Voy a pagar mañana sin falta",
        },
        [
            turn(1, "bot", "Hello, this is Aria calling from Apex Financial Services regarding the loan account ending in 6155. May I confirm I am speaking with Miguel Santos?"),
            turn(2, "customer", "Speaking, yes."),
            turn(3, "bot", "Thank you. I'm calling about your installment of one thousand two hundred dollars, which was due on July twenty fifth."),
            turn(4, "customer", "Perdón, ¿podría continuar en español, por favor? Lo entiendo mucho mejor.", "es-ES"),
            turn(5, "bot", "Claro que sí, continuamos en español. Su cuota de mil doscientos dólares venció el veinticinco de julio. ¿Podría realizar el pago hoy?", "es-ES"),
            turn(6, "customer", "Hoy no, pero mañana sí. Voy a pagar mañana sin falta.", "es-ES"),
            turn(7, "bot", "Muy bien. ¿Sería el monto completo de mil doscientos dólares mañana, veintinueve de julio?", "es-ES"),
            turn(8, "customer", "Sí, el monto completo.", "es-ES"),
            turn(9, "bot", "Perfecto, lo anoto. Usted pagará mil doscientos dólares el veintinueve de julio. ¿Es correcto?", "es-ES"),
            turn(10, "customer", "Correcto. ¿Algo más?", "es-ES"),
            turn(11, "bot", "Eso es todo. Gracias por su tiempo, señor Santos. Que tenga un buen día.", "es-ES"),
            turn(12, "customer", "Igualmente, gracias. Adiós.", "es-ES"),
        ],
        language_detected="mixed",
        recording_url="/recordings/CALL-SAMPLE-SWITCH-PTP-TOMORROW.mp3",
    ),
))

# 9. Disconnect / no clear disposition
scenarios_folder_items.append(item(
    "Scenario 9 - Initiate: Disconnect, no clear disposition",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM09", "100009", customer_name="Aisha Bello", emi_amount=630.75),
))
scenarios_folder_items.append(item(
    "Scenario 9 - Webhook: Disconnect, no clear disposition",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=webhook_body(
        "CALL-20260728-0009", "evt-pm-09",
        {
            "stage_code": None,
            "disposition_reason": "Call dropped shortly after connecting.",
            "disposition_summary": "The call was disconnected before any disposition could be captured.",
            "confidence": 0.0,
            "customer_verified": None,
            "sentiment": "unknown",
            "evidence_quote": None,
        },
        [
            turn(1, "bot", "Hello, may I confirm I'm speaking with Aisha Bello?"),
            turn(2, "customer", "Yes, this is\u2014"),
        ],
        call_status="failed",
        call_duration_seconds=8,
    ),
))

# 10. Duplicate webhook replay
dup_payload = webhook_body(
    "CALL-20260728-0010", "evt-pm-10-duplicate",
    {
        "stage_code": "PTP_TODAY",
        "disposition_reason": "Customer committed to paying today.",
        "ptp_date": "2026-07-28",
        "confidence": 0.92,
        "customer_verified": True,
        "sentiment": "positive",
        "evidence_quote": "I will pay today",
    },
    [
        turn(1, "bot", "May I confirm I'm speaking with Jonathan Pike?"),
        turn(2, "customer", "Yes, speaking."),
        turn(3, "bot", "Your EMI of 1440.00 USD was due on July 25. Can you pay today?"),
        turn(4, "customer", "Yes, I will pay today."),
    ],
)
scenarios_folder_items.append(item(
    "Scenario 10 - Initiate: Duplicate webhook setup",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM10", "100010", customer_name="Jonathan Pike", emi_amount=1440.0),
))
scenarios_folder_items.append(item(
    "Scenario 10 - Webhook: First delivery (duplicate=false expected)",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=dup_payload,
    description="First delivery of this event_id. Response should have duplicate=false.",
))
scenarios_folder_items.append(item(
    "Scenario 10 - Webhook: Replay (duplicate=true expected)",
    "POST", "/api/v1/webhooks/post-call",
    headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
    body=dup_payload,
    description="Exact replay with the same event_id. Response should have duplicate=true and cause no state change.",
))

# 11. Invalid initial request (expect 422)
scenarios_folder_items.append(item(
    "Scenario 11 - Initiate: Invalid request (expect 422)",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM11", "100011", customer_name="Lucia Herrera", preferred_language="Spanish", phone_number="123"),
    description="phone_number is too short (must be 7-15 digits). Expect HTTP 422 with VALIDATION_ERROR envelope and field_errors.",
))

# 12. Gnani API failure + timeout (injected via phone suffix)
scenarios_folder_items.append(item(
    "Scenario 12a - Initiate: Injected Gnani timeout (phone ends 0000)",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM12A", "500000", customer_name="Nathan Brooks"),
    description="Mock mode: phone numbers ending in 0000 simulate a Gnani call-trigger timeout. Expect HTTP 504 GNANI_TIMEOUT.",
))
scenarios_folder_items.append(item(
    "Scenario 12b - Initiate: Injected Gnani 5xx failure (phone ends 9999)",
    "POST", "/api/Initial_Message",
    headers=API_KEY_HEADER + [JSON_CONTENT],
    body=initiate_body("CUST-PM12B", "509999", customer_name="Nathan Brooks"),
    description="Mock mode: phone numbers ending in 9999 simulate a persistent Gnani 5xx failure. Expect HTTP 502 GNANI_TRIGGER_FAILED.",
))

# --- Core / infra endpoints ------------------------------------------------
core_items = [
    item("Health check", "GET", "/health", description="Unauthenticated liveness/readiness check."),
    item("Public config", "GET", "/api/v1/config", description="Returns {\"api_key_required\": true}. Never leaks the actual key."),
    item(
        "List calls",
        "GET", "/api/v1/calls",
        headers=API_KEY_HEADER,
        query={"page": 1, "page_size": 25, "sort_by": "created_at", "sort_dir": "desc"},
        description="Paginated call list with optional filters: call_date, date_from, date_to, call_status, stage_code, stage_group, customer_id, loan_account_number, language, ptp_date, q.",
    ),
    item(
        "List calls - filter by stage_code",
        "GET", "/api/v1/calls",
        headers=API_KEY_HEADER,
        query={"stage_code": "PTP_TODAY", "page": 1, "page_size": 25},
    ),
    item(
        "Get call detail",
        "GET", "/api/v1/calls/{{call_id}}",
        headers=API_KEY_HEADER,
        description="Full CallDetail for a single call_id. 404 CALL_NOT_FOUND if missing.",
    ),
    item(
        "Get stats",
        "GET", "/api/v1/stats",
        headers=API_KEY_HEADER,
        description="Aggregate stats. Accepts the same filters as List calls.",
    ),
    item(
        "Initiate call - happy path template",
        "POST", "/api/Initial_Message",
        headers=API_KEY_HEADER + [JSON_CONTENT],
        body=initiate_body("CUST001", "3210", country_code="+1"),
        description="Generic happy-path template for POST /api/Initial_Message.",
    ),
    item(
        "Post-call webhook - happy path template",
        "POST", "/api/v1/webhooks/post-call",
        headers=WEBHOOK_KEY_HEADER + [JSON_CONTENT],
        body=webhook_body(
            "CALL-20260728-0001", "evt-001",
            {
                "stage_code": "PTP_FUTURE",
                "disposition_reason": "Customer said 'I will pay on the 30th'.",
                "disposition_summary": "Customer confirmed identity and promised payment by month end.",
                "ptp_date": "2026-07-30",
                "ptp_amount": 1200.0,
                "confidence": 0.93,
                "customer_verified": True,
                "sentiment": "neutral",
                "evidence_quote": "I will pay on the 30th",
            },
            [turn(1, "bot", "Hello, may I confirm I'm speaking with Marcus Whitfield?"), turn(2, "customer", "Sí, soy yo.", "es-ES")],
        ),
        description="Generic happy-path template for POST /api/v1/webhooks/post-call.",
    ),
]

collection = {
    "info": {
        "_postman_id": str(uuid.uuid4()),
        "name": "Gnani EMI Voice Agent",
        "description": (
            "Full API collection for the Gnani Agents Console EMI-collections outbound voice "
            "agent backend. Covers all endpoints from CONTRACT.md plus example request bodies "
            "for all 12 mandatory demo scenarios. Import postman/environment.json alongside "
            "this collection and set `base_url`, `api_key`, `webhook_key`."
        ),
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "item": [
        {"name": "Core", "item": core_items},
        {"name": "12 Mandatory Scenarios", "item": scenarios_folder_items},
    ],
    "variable": [
        {"key": "base_url", "value": "http://localhost:8000"},
        {"key": "api_key", "value": "dev-api-key"},
        {"key": "webhook_key", "value": "dev-webhook-key"},
        {"key": "call_id", "value": "CALL-20260728-0001"},
    ],
}

out_path = PROJECT_ROOT / "postman" / "Gnani-EMI-Voice-Agent.postman_collection.json"
out_path.write_text(json.dumps(collection, indent=2, ensure_ascii=False))
print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
