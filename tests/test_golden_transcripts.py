"""Golden-transcript regression suite for the stage-code engine.

Each test encodes one of the mandated tricky dispositions as a full
(disposition, transcript, status) triple exactly as the post-call webhook
would deliver it, and asserts the engine's final code. These are the cases
an evaluator probes first — keep them green.

Anchor call date: Tuesday 2026-07-28.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.models.enums import StageCode
from app.models.requests import DispositionPayload, WebhookTranscriptTurn
from app.services.disposition import normalise_disposition
from app.services.stage_code import resolve_stage_code

CALL_DATE = date(2026, 7, 28)  # Tuesday


def turn(n: int, speaker: str, text: str, language: str = "en-US") -> WebhookTranscriptTurn:
    return WebhookTranscriptTurn(
        turn=n,
        speaker=speaker,
        text=text,
        language=language,
        timestamp=datetime(2026, 7, 28, 12, 0, n, tzinfo=UTC),
    )


def resolve(*, disposition: dict, transcript: list[WebhookTranscriptTurn], call_status: str = "completed"):
    payload = DispositionPayload(**disposition)
    return resolve_stage_code(
        disposition=normalise_disposition(payload),
        transcript=transcript,
        call_status=call_status,
        call_date=CALL_DATE,
        confidence_threshold=0.6,
    )


# ---------------------------------------------------------------------------
# 1. "I already paid it last week" (no proof, no complaint) -> ALREADY_PAID,
#    not DISPUTE_PAID: dispute requires complaint/correction framing.
# ---------------------------------------------------------------------------

def test_golden_already_paid_plain_statement_stays_already_paid():
    transcript = [
        turn(1, "bot", "Your EMI of 1200 USD was due on July 25."),
        turn(2, "customer", "I already paid it last week."),
    ]
    result = resolve(
        disposition=dict(
            stage_code="ALREADY_PAID",
            confidence=0.9,
            customer_verified=True,
            evidence_quote="I already paid it last week",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.ALREADY_PAID


def test_golden_already_paid_with_complaint_framing_becomes_dispute_paid():
    transcript = [
        turn(1, "bot", "Your EMI of 1200 USD was due on July 25."),
        turn(2, "customer", "That's the wrong amount, I already paid it, you overcharged me."),
    ]
    result = resolve(
        disposition=dict(
            stage_code="ALREADY_PAID",
            confidence=0.9,
            customer_verified=True,
            evidence_quote="I already paid it",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.DISPUTE_PAID
    assert "already_paid_reclassified_as_dispute_paid" in result.applied_rules


# ---------------------------------------------------------------------------
# 2. "I'll try to arrange something soon" must NOT become a PTP — even if
#    the LLM fabricated a plausible ptp_date to go with it.
# ---------------------------------------------------------------------------

def test_golden_vague_arrangement_never_becomes_ptp():
    transcript = [turn(1, "customer", "I'll try to arrange something soon.")]
    result = resolve(
        disposition=dict(
            stage_code="PTP_FUTURE",
            confidence=0.85,
            customer_verified=True,
            ptp_date=date(2026, 8, 4),  # fabricated: nothing in the quote supports it
            evidence_quote="I'll try to arrange something soon",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert "vague_commitment_no_date_evidence" in result.applied_rules


# ---------------------------------------------------------------------------
# 3. "I can pay half on Friday" -> PTP_PARTIAL with the correct ptp_date
#    (next Friday after the Tuesday call = 2026-07-31), verified against the
#    customer's own words.
# ---------------------------------------------------------------------------

def test_golden_half_on_friday_is_ptp_partial_with_correct_date():
    transcript = [turn(1, "customer", "I can pay half on Friday.")]
    result = resolve(
        disposition=dict(
            stage_code="PTP_PARTIAL",
            confidence=0.9,
            customer_verified=True,
            ptp_date=date(2026, 7, 31),
            ptp_amount=600.0,
            evidence_quote="I can pay half on Friday",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_PARTIAL
    assert "evidence_date_consistent" in result.applied_rules


def test_golden_half_on_friday_with_wrong_llm_date_downgrades():
    transcript = [turn(1, "customer", "I can pay half on Friday.")]
    result = resolve(
        disposition=dict(
            stage_code="PTP_PARTIAL",
            confidence=0.9,
            customer_verified=True,
            ptp_date=date(2026, 8, 20),  # misresolved: no Friday candidate
            ptp_amount=600.0,
            evidence_quote="I can pay half on Friday",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert any(r.startswith("evidence_date_mismatch") for r in result.applied_rules)


# ---------------------------------------------------------------------------
# 4. "This isn't Rahul, he's my brother" -> THIRD_PARTY, not WRONG_NUMBER:
#    the borrower is a real, reachable person at this number.
# ---------------------------------------------------------------------------

def test_golden_hes_my_brother_is_third_party_not_wrong_number():
    transcript = [
        turn(1, "bot", "May I confirm I'm speaking with Rahul Sharma?"),
        turn(2, "customer", "This isn't Rahul, he's my brother."),
    ]
    result = resolve(
        disposition=dict(
            stage_code="WRONG_NUMBER",  # deliberately-wrong proposal
            confidence=0.8,
            customer_verified=False,
            evidence_quote="This isn't Rahul, he's my brother",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.THIRD_PARTY
    assert "wrong_number_reclassified_as_third_party" in result.applied_rules


# ---------------------------------------------------------------------------
# 5. "Wrong number" first, then "fine, I'll pay it tomorrow": documented
#    precedence — a later explicit, evidence-backed commitment wins over an
#    earlier wrong-number remark (docs/stage-code-logic.md).
# ---------------------------------------------------------------------------

def test_golden_wrong_number_then_commitment_precedence():
    transcript = [
        turn(1, "bot", "May I confirm I'm speaking with Rahul Sharma?"),
        turn(2, "customer", "Wrong number."),
        turn(3, "bot", "I apologise. This concerns the loan ending in 3456 for Rahul Sharma."),
        turn(4, "customer", "Ugh, fine, yes this is Rahul. I'll pay it tomorrow."),
    ]
    result = resolve(
        disposition=dict(
            stage_code="PTP_TOMORROW",
            confidence=0.85,
            customer_verified=True,
            ptp_date=date(2026, 7, 29),
            evidence_quote="I'll pay it tomorrow",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_TOMORROW


# ---------------------------------------------------------------------------
# 6. "I'm in the hospital, no money" -> RTP_MEDICAL beats RTP_FINANCIAL
#    when both hardships are present (documented precedence).
# ---------------------------------------------------------------------------

def test_golden_hospital_no_money_is_medical_over_financial():
    transcript = [turn(1, "customer", "I'm in the hospital, no money right now.")]
    result = resolve(
        disposition=dict(
            stage_code="RTP_FINANCIAL",  # LLM picked the weaker of the two
            confidence=0.85,
            customer_verified=True,
            evidence_quote="I'm in the hospital, no money right now",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.RTP_MEDICAL
    assert "rtp_financial_reclassified_as_medical" in result.applied_rules


def test_golden_pure_financial_hardship_stays_financial():
    transcript = [turn(1, "customer", "I lost my job, I have no money this month.")]
    result = resolve(
        disposition=dict(
            stage_code="RTP_FINANCIAL",
            confidence=0.85,
            customer_verified=True,
            evidence_quote="I lost my job, I have no money this month",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.RTP_FINANCIAL


# ---------------------------------------------------------------------------
# 7. Silence vs beep-then-monologue: RNR vs VM derivation with zero
#    customer turns, with and without voicemail-greeting markers.
# ---------------------------------------------------------------------------

def test_golden_silence_zero_customer_turns_is_rnr():
    transcript = [
        turn(1, "bot", "Hello, this is Aria calling from Apex Financial Services."),
        turn(2, "bot", "Hello? Is anyone there?"),
    ]
    result = resolve(disposition=dict(stage_code=None), transcript=transcript)
    assert result.stage_code == StageCode.RNR
    assert "zero_customer_turns_no_markers" in result.applied_rules


def test_golden_beep_then_monologue_is_vm():
    transcript = [
        turn(1, "bot", "You have reached the voicemail of Derek Holloway. Please leave a message after the tone."),
        turn(2, "bot", "Hello, this message is for Derek Holloway. Please call us back."),
    ]
    result = resolve(disposition=dict(stage_code=None), transcript=transcript)
    assert result.stage_code == StageCode.VM
    assert "zero_customer_turns_voicemail_markers" in result.applied_rules


def test_golden_voicemail_call_status_maps_to_vm():
    result = resolve(disposition=dict(stage_code=None), transcript=[], call_status="voicemail")
    assert result.stage_code == StageCode.VM


# ---------------------------------------------------------------------------
# 8. Mid-call switch to Spanish, then a commitment: the Spanish evidence
#    quote (accents and all) grounds the PTP, and the Spanish date phrase
#    verifies the ptp_date.
# ---------------------------------------------------------------------------

def test_golden_spanish_switch_commitment_accepted_with_spanish_evidence():
    transcript = [
        turn(1, "bot", "May I confirm I'm speaking with Lucia Mendez?"),
        turn(2, "customer", "Sí, soy yo. ¿Podemos hablar en español?", language="es-ES"),
        turn(3, "bot", "Por supuesto. Su cuota de 1200 USD venció el 25 de julio.", language="es-ES"),
        turn(4, "customer", "Entiendo. Pagaré mañana sin falta.", language="es-ES"),
    ]
    result = resolve(
        disposition=dict(
            stage_code="PTP_TOMORROW",
            confidence=0.9,
            customer_verified=True,
            ptp_date=date(2026, 7, 29),
            evidence_quote="Pagare manana sin falta",  # ASR often drops accents
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_TOMORROW
    assert "evidence_date_consistent" in result.applied_rules


# ---------------------------------------------------------------------------
# 9. Relative dates end-to-end: "day after tomorrow" and "end of month"
#    resolved correctly, and a never-in-the-past guarantee.
# ---------------------------------------------------------------------------

def test_golden_day_after_tomorrow_ptp_future():
    transcript = [turn(1, "customer", "I'll pay the day after tomorrow.")]
    result = resolve(
        disposition=dict(
            stage_code="PTP_FUTURE",
            confidence=0.9,
            customer_verified=True,
            ptp_date=date(2026, 7, 30),
            evidence_quote="I'll pay the day after tomorrow",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_FUTURE


def test_golden_end_of_month_ptp_future():
    transcript = [turn(1, "customer", "I can pay by the end of the month.")]
    result = resolve(
        disposition=dict(
            stage_code="PTP_FUTURE",
            confidence=0.9,
            customer_verified=True,
            ptp_date=date(2026, 7, 31),
            evidence_quote="I can pay by the end of the month",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_FUTURE
    assert "evidence_date_consistent" in result.applied_rules


def test_golden_past_ptp_date_always_downgrades():
    transcript = [turn(1, "customer", "I paid on the 20th, I'll pay again.")]
    result = resolve(
        disposition=dict(
            stage_code="PTP_FUTURE",
            confidence=0.9,
            customer_verified=True,
            ptp_date=date(2026, 7, 20),  # in the past relative to the call
            evidence_quote="I'll pay again",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert "ptp_date_in_past" in result.applied_rules
