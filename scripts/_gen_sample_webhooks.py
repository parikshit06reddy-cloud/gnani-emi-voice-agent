"""One-off generator for samples/webhooks/*.json.

Not part of the runtime application; run manually to regenerate the sample
payloads if the webhook schema changes. Produces one realistic post-call
webhook payload per stage-code family (>=10 files, one per CONTRACT.md
StageCode family) with full multi-turn transcripts.
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "samples" / "webhooks"
RECORDINGS_DIR = PROJECT_ROOT / "samples" / "recordings"


def turn(n, speaker, text, lang="en-US"):
    return {"turn": n, "speaker": speaker, "text": text, "language": lang}


def _recording_url_for(call_id: str, language: str = "en-US") -> str:
    """Point at a real file in samples/recordings/ only on an exact call_id
    match, else fall back to the standard ``/recordings/<call_id>.wav``
    convention. Deliberately does NOT do a loose language-only match here --
    that previously caused unrelated en-US samples to all resolve to the
    same real recording file. Samples with a genuine matching recording set
    ``recording_url`` explicitly via the payload() overrides instead."""
    if not RECORDINGS_DIR.is_dir():
        return f"/recordings/{call_id}.wav"
    exact_names = {f"{call_id}.wav", f"{call_id}.mp3"}
    for candidate in sorted(RECORDINGS_DIR.glob("*")):
        if candidate.name in exact_names:
            return f"/recordings/{candidate.name}"
    return f"/recordings/{call_id}.wav"


def payload(call_id, event_id, disposition, transcript, **overrides):
    language = overrides.get("language_detected", "en-US")
    body = {
        "event_id": event_id,
        "call_id": call_id,
        "gnani_call_reference": f"gnani-{event_id}",
        "call_status": "completed",
        "call_duration_seconds": 92,
        "call_started_at": "2026-07-28T12:00:00+00:00",
        "call_ended_at": "2026-07-28T12:01:32+00:00",
        "recording_url": _recording_url_for(call_id, language=language),
        "language_detected": "en-US",
        "asr_engine": "gnani-prisma",
        "tts_engine": "gnani-timbre-2.5",
        "llm_engine": "gnani-evon",
        "disposition": disposition,
        "transcript": transcript,
    }
    body.update(overrides)
    return body


SAMPLES: dict[str, dict] = {}

# 1. PTP_TODAY
SAMPLES["01_ptp_today.json"] = payload(
    "CALL-20260728-1001", "evt-sample-ptp-today",
    {
        "stage_code": "PTP_TODAY",
        "disposition_reason": "Customer explicitly committed to paying today.",
        "disposition_summary": "Customer confirmed identity, acknowledged the overdue EMI, and promised to pay the full amount today.",
        "ptp_date": "2026-07-28",
        "ptp_amount": 1200.0,
        "confidence": 0.95,
        "customer_verified": True,
        "sentiment": "positive",
        "evidence_quote": "I will pay it today, no problem",
    },
    [
        turn(1, "bot", "Hello, this is Aria calling from Apex Financial Services. May I confirm I'm speaking with Marcus Whitfield regarding your loan ending in 3456?"),
        turn(2, "customer", "Yes, this is Marcus speaking."),
        turn(3, "bot", "Thank you for confirming. Your EMI of 1200.00 USD was due on July 25, 2026 and has not yet been received. Are you able to make this payment?"),
        turn(4, "customer", "Oh, I completely forgot about it. Let me take care of it."),
        turn(5, "bot", "I appreciate that. Just to confirm, will you be paying the full amount of 1200.00 USD today?"),
        turn(6, "customer", "Yes, I will pay it today, no problem. I'll do it online this afternoon."),
        turn(7, "bot", "Wonderful, thank you Marcus. Is there anything else I can help you with regarding your account?"),
        turn(8, "customer", "No, that covers it. Thanks for the reminder."),
        turn(9, "bot", "You're welcome. Have a great day, and thank you for banking with Apex Financial Services."),
    ],
)

# 2. PTP_FUTURE (real recorded call: CALL-SAMPLE-EN-PTP-FUTURE)
SAMPLES["02_ptp_future.json"] = payload(
    "CALL-20260728-1002", "evt-sample-ptp-future",
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
)

# 3. ALREADY_PAID
SAMPLES["03_already_paid.json"] = payload(
    "CALL-20260728-1003", "evt-sample-already-paid",
    {
        "stage_code": "ALREADY_PAID",
        "disposition_reason": "Customer states the EMI was already paid two days ago via online banking.",
        "disposition_summary": "Customer claims payment already made; recommend verification against payment gateway records.",
        "confidence": 0.85,
        "customer_verified": True,
        "sentiment": "neutral",
        "evidence_quote": "I already paid this EMI two days ago online",
    },
    [
        turn(1, "bot", "May I confirm I'm speaking with Priya Raghunathan about the loan ending in 3456?"),
        turn(2, "customer", "Yes, speaking."),
        turn(3, "bot", "Your EMI of 968.00 USD was due on July 23. Have you had a chance to make this payment?"),
        turn(4, "customer", "Yes actually, I already paid this EMI two days ago online through your app."),
        turn(5, "bot", "Thank you for letting me know. Do you happen to have a transaction reference number?"),
        turn(6, "customer", "I don't have it in front of me, but it went through — I checked my bank statement."),
        turn(7, "bot", "No problem, we'll verify this on our end and update your account. Thank you for confirming."),
    ],
)

# 4. CALLBACK_SCHEDULED
SAMPLES["04_callback_scheduled.json"] = payload(
    "CALL-20260728-1004", "evt-sample-callback",
    {
        "stage_code": "CALLBACK_SCHEDULED",
        "disposition_reason": "Customer requested a callback at a specific time tomorrow due to being busy.",
        "disposition_summary": "Customer was in a meeting and requested a callback tomorrow at 5pm.",
        "callback_datetime": "2026-07-29T17:00:00+00:00",
        "confidence": 0.88,
        "customer_verified": True,
        "sentiment": "neutral",
        "evidence_quote": "Please call me back tomorrow at 5pm",
    },
    [
        turn(1, "bot", "Am I speaking with Daniel O'Sullivan about your EMI?"),
        turn(2, "customer", "Yes, but I'm actually in a meeting right now."),
        turn(3, "bot", "I understand, this will only take a moment. Can I proceed briefly?"),
        turn(4, "customer", "No, I really can't talk right now. Can you please call me back tomorrow at 5pm?"),
        turn(5, "bot", "Of course, I will call you back tomorrow, July 29th, at 5pm. Thank you for your time."),
    ],
    call_duration_seconds=35,
)

# 5. RTP_FINANCIAL (real recorded call: CALL-SAMPLE-ES-RTP-FINANCIAL)
SAMPLES["05_rtp_financial.json"] = payload(
    "CALL-20260728-1005", "evt-sample-rtp-financial",
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
)

# 6. RTP_MEDICAL
SAMPLES["06_rtp_medical.json"] = payload(
    "CALL-20260728-1006", "evt-sample-rtp-medical",
    {
        "stage_code": "RTP_MEDICAL",
        "disposition_reason": "Customer cites a medical emergency and hospital expenses preventing payment.",
        "disposition_summary": "Customer's family member is hospitalized; unable to pay EMI this cycle.",
        "confidence": 0.88,
        "customer_verified": True,
        "sentiment": "negative",
        "evidence_quote": "my wife is in the hospital and all our money is going to medical bills",
    },
    [
        turn(1, "bot", "Am I speaking with Tyrone Jackson regarding your loan ending in 3456?"),
        turn(2, "customer", "Yes, this is Tyrone."),
        turn(3, "bot", "Your EMI of 2150.00 USD was due on July 19. Can you make the payment?"),
        turn(4, "customer", "This isn't a good time, my wife is in the hospital and all our money is going to medical bills."),
        turn(5, "bot", "I'm sorry to hear that. We'll note this and have our team reach out about possible relief options."),
    ],
)

# 7. DISPUTE_CHARGES
SAMPLES["07_dispute_charges.json"] = payload(
    "CALL-20260728-1007", "evt-sample-dispute-charges",
    {
        "stage_code": "DISPUTE_CHARGES",
        "disposition_reason": "Customer disputes a penalty charge added to the EMI amount.",
        "disposition_summary": "Customer contests extra penalty/late fee added to this cycle's EMI.",
        "confidence": 0.87,
        "customer_verified": True,
        "sentiment": "negative",
        "evidence_quote": "you've charged me a penalty that shouldn't be there",
    },
    [
        turn(1, "bot", "Am I speaking with Rebecca Lindqvist regarding your EMI ending in 3456?"),
        turn(2, "customer", "Yes, but I have an issue with this bill."),
        turn(3, "bot", "Please tell me more, I'd like to help resolve this."),
        turn(4, "customer", "This is the wrong amount — you've charged me a penalty that shouldn't be there."),
        turn(5, "bot", "I understand. Can you clarify what amount you expected to be billed?"),
        turn(6, "customer", "My EMI should be 350, not 385.50. I dispute the extra charges."),
        turn(7, "bot", "Understood, I've logged your dispute for our billing team to review."),
    ],
)

# 8. DISPUTE_PAID (paid but disputing further collection)
SAMPLES["08_dispute_paid.json"] = payload(
    "CALL-20260728-1008", "evt-sample-dispute-paid",
    {
        "stage_code": "DISPUTE_PAID",
        "disposition_reason": "Customer disputes that this EMI is still outstanding, insisting it was already settled and is being wrongly re-billed.",
        "disposition_summary": "Customer disputes the outstanding balance, claiming it was already paid and incorrectly re-charged.",
        "confidence": 0.86,
        "customer_verified": True,
        "sentiment": "negative",
        "evidence_quote": "I already paid this last month and you are billing me again by mistake",
    },
    [
        turn(1, "bot", "May I confirm I'm speaking with Jonathan Pike about your EMI ending in 3456?"),
        turn(2, "customer", "Yes, but this call shouldn't even be happening."),
        turn(3, "bot", "I'm sorry to hear that, can you explain?"),
        turn(4, "customer", "I already paid this last month and you are billing me again by mistake. I want this corrected, not just noted as unpaid."),
        turn(5, "bot", "I understand your frustration, I'm logging this as a billing dispute for urgent review."),
    ],
)

# 9. THIRD_PARTY
SAMPLES["09_third_party.json"] = payload(
    "CALL-20260728-1009", "evt-sample-third-party",
    {
        "stage_code": "THIRD_PARTY",
        "disposition_reason": "Someone other than the borrower answered; the borrower is reachable later.",
        "disposition_summary": "Borrower's sister answered the call; borrower is reachable this evening.",
        "confidence": 0.82,
        "customer_verified": False,
        "sentiment": "neutral",
        "evidence_quote": "this is her sister. She's not here right now",
    },
    [
        turn(1, "bot", "May I confirm I'm speaking with Aisha Bello?"),
        turn(2, "customer", "No, this is her sister. She's not here right now."),
        turn(3, "bot", "I see, do you know when she'll be available?"),
        turn(4, "customer", "She should be back this evening. I can pass along a message."),
        turn(5, "bot", "Thank you, please ask her to call us back regarding her EMI payment."),
    ],
    call_duration_seconds=28,
)

# 10. WRONG_NUMBER
SAMPLES["10_wrong_number.json"] = payload(
    "CALL-20260728-1010", "evt-sample-wrong-number",
    {
        "stage_code": "WRONG_NUMBER",
        "disposition_reason": "The person who answered has no knowledge of the borrower and states this is not their number.",
        "disposition_summary": "Wrong number reached; no relationship to the borrower.",
        "confidence": 0.9,
        "customer_verified": False,
        "sentiment": "neutral",
        "evidence_quote": "I don't know any Nathan Brooks, you have the wrong number",
    },
    [
        turn(1, "bot", "May I confirm I'm speaking with Nathan Brooks?"),
        turn(2, "customer", "No, I don't know any Nathan Brooks, you have the wrong number."),
        turn(3, "bot", "I apologize for the inconvenience, I'll update our records. Have a good day."),
    ],
    call_duration_seconds=15,
)

# 11. NO_LOAN
SAMPLES["11_no_loan.json"] = payload(
    "CALL-20260728-1011", "evt-sample-no-loan",
    {
        "stage_code": "NO_LOAN",
        "disposition_reason": "Customer confirms identity but denies having any loan or EMI with this organisation.",
        "disposition_summary": "Verified customer states they have no active loan with Apex Financial Services.",
        "confidence": 0.84,
        "customer_verified": True,
        "sentiment": "negative",
        "evidence_quote": "I don't have any loan with your company, I've never borrowed from you",
    },
    [
        turn(1, "bot", "May I confirm I'm speaking with Jonathan Pike?"),
        turn(2, "customer", "Yes, this is Jonathan."),
        turn(3, "bot", "This is regarding your EMI on loan account ending in 3456 with Apex Financial Services."),
        turn(4, "customer", "I don't have any loan with your company, I've never borrowed from you. This must be an error."),
        turn(5, "bot", "I apologize, I'll flag this account for review. Thank you for letting us know."),
    ],
)

# 12. BUSY (call_status == busy, no conversation)
SAMPLES["12_busy.json"] = payload(
    "CALL-20260728-1012", "evt-sample-busy",
    {
        "stage_code": None,
        "disposition_reason": "Line was busy; call could not connect.",
        "disposition_summary": "Customer's line was busy on this attempt.",
        "confidence": 0.0,
        "customer_verified": None,
        "sentiment": "unknown",
        "evidence_quote": None,
    },
    [],
    call_status="busy",
    call_duration_seconds=0,
)

# 13. RNR (ring no response)
SAMPLES["13_rnr.json"] = payload(
    "CALL-20260728-1013", "evt-sample-rnr",
    {
        "stage_code": None,
        "disposition_reason": "Call rang out with no answer.",
        "disposition_summary": "No answer after multiple rings; recommend retry later.",
        "confidence": 0.0,
        "customer_verified": None,
        "sentiment": "unknown",
        "evidence_quote": None,
    },
    [],
    call_status="no_answer",
    call_duration_seconds=0,
)

# 14. VM (voicemail)
SAMPLES["14_voicemail.json"] = payload(
    "CALL-20260728-1014", "evt-sample-voicemail",
    {
        "stage_code": "VM",
        "disposition_reason": "Call was answered by voicemail; bot left a callback message.",
        "disposition_summary": "Voicemail detected, automated message left requesting a callback.",
        "confidence": 0.75,
        "customer_verified": None,
        "sentiment": "unknown",
        "evidence_quote": "you have reached the voicemail of",
    },
    [
        turn(1, "bot", "You have reached the voicemail of Derek Holloway. Please leave a message after the tone."),
        turn(2, "bot", "Hello, this message is for Derek Holloway from Apex Financial Services regarding your EMI. Please call us back at your earliest convenience."),
    ],
    call_status="completed",
    call_duration_seconds=22,
)

# 15. DSCN (disconnect mid-call, no clear disposition)
SAMPLES["15_disconnect_unclear.json"] = payload(
    "CALL-20260728-1015", "evt-sample-disconnect",
    {
        "stage_code": None,
        "disposition_reason": "Call dropped shortly after connecting, before any disposition could be captured.",
        "disposition_summary": "The call was disconnected mid-conversation.",
        "confidence": 0.0,
        "customer_verified": None,
        "sentiment": "unknown",
        "evidence_quote": None,
    },
    [
        turn(1, "bot", "Hello, may I confirm I'm speaking with Miguel Santos?"),
        turn(2, "customer", "Yes, this is\u2014"),
    ],
    call_status="failed",
    call_duration_seconds=8,
)

# 16. UNCLEAR (evidence missing / low confidence, forces downgrade)
SAMPLES["16_unclear_low_confidence.json"] = payload(
    "CALL-20260728-1016", "evt-sample-unclear",
    {
        "stage_code": "PTP_TODAY",
        "disposition_reason": "Analytics proposed PTP_TODAY but no supporting quote was captured and confidence is low.",
        "disposition_summary": "Ambiguous conversation; customer's intent to pay today could not be clearly evidenced.",
        "confidence": 0.35,
        "customer_verified": True,
        "sentiment": "neutral",
        "evidence_quote": "",
    },
    [
        turn(1, "bot", "May I confirm I'm speaking with Lucia Herrera?"),
        turn(2, "customer", "Yes, that's me."),
        turn(3, "bot", "Your EMI of 1050.00 USD was due on July 25. Can we discuss this?"),
        turn(4, "customer", "Umm, maybe, I'm not sure, I'll have to think about it."),
    ],
)
# NOTE: this payload demonstrates the stage-code engine's evidence/confidence
# downgrade rule -- proposed PTP_TODAY has no matching evidence_quote and
# confidence 0.35 < threshold 0.6, so resolve_stage_code() downgrades it to
# UNCLEAR with stage_code_source="derived". See app/services/stage_code.py.


# 17. PTP_TOMORROW via bilingual language switch (real recorded call: CALL-SAMPLE-SWITCH-PTP-TOMORROW)
SAMPLES["17_language_switch_ptp_tomorrow.json"] = payload(
    "CALL-20260728-1017", "evt-sample-language-switch",
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
)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, body in SAMPLES.items():
        (OUT_DIR / filename).write_text(json.dumps(body, indent=2, ensure_ascii=False))
    print(f"Wrote {len(SAMPLES)} sample webhook files to {OUT_DIR}")


if __name__ == "__main__":
    main()
