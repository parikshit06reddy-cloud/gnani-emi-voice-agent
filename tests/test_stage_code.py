"""Tests for the deterministic stage-code resolution engine (app/services/stage_code.py).

This is the highest-value module in the assignment, so it gets the deepest
test coverage: evidence enforcement, consistency rules, disambiguation,
disconnect overrides, and the bilingual keyword fallback.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.models.enums import StageCode, StageCodeSource
from app.models.requests import DispositionPayload, WebhookTranscriptTurn
from app.services.disposition import normalise_disposition
from app.services.stage_code import resolve_stage_code

CALL_DATE = date(2026, 7, 28)


def turn(n: int, speaker: str, text: str, language: str = "en-US") -> WebhookTranscriptTurn:
    return WebhookTranscriptTurn(turn=n, speaker=speaker, text=text, language=language)


def make_disposition(**kwargs) -> "object":
    payload = DispositionPayload(**kwargs)
    return normalise_disposition(payload)


def resolve(*, disposition_kwargs, transcript, call_status="completed", call_date=CALL_DATE, threshold=0.6):
    disposition = make_disposition(**disposition_kwargs)
    return resolve_stage_code(
        disposition=disposition,
        transcript=transcript,
        call_status=call_status,
        call_date=call_date,
        confidence_threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 1. Happy-path commitment codes with valid evidence
# ---------------------------------------------------------------------------


def test_ptp_today_accepted_with_evidence():
    transcript = [
        turn(1, "bot", "Will you be able to pay today?"),
        turn(2, "customer", "Yes, I will pay today."),
    ]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_TODAY",
            ptp_date=CALL_DATE,
            confidence=0.9,
            customer_verified=True,
            evidence_quote="I will pay today",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_TODAY
    assert result.stage_code_source == StageCodeSource.LLM
    assert result.stage_group == "ptp"


def test_ptp_future_accepted_with_evidence():
    transcript = [turn(1, "customer", "I will pay on the 30th of July.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_FUTURE",
            ptp_date=date(2026, 7, 30),
            confidence=0.93,
            customer_verified=True,
            evidence_quote="I will pay on the 30th",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_FUTURE


def test_already_paid_accepted_with_evidence():
    transcript = [turn(1, "customer", "I already paid this EMI last week.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="ALREADY_PAID",
            confidence=0.85,
            customer_verified=True,
            evidence_quote="I already paid this EMI last week",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.ALREADY_PAID
    assert result.stage_group == "already_paid"


def test_callback_scheduled_accepted_with_datetime():
    transcript = [turn(1, "customer", "Please call me back tomorrow at 5pm.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="CALLBACK_SCHEDULED",
            callback_datetime=datetime(2026, 7, 29, 17, 0, tzinfo=timezone.utc),
            confidence=0.8,
            customer_verified=True,
            evidence_quote="call me back tomorrow at 5pm",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.CALLBACK_SCHEDULED
    assert result.stage_group == "callback"


def test_rtp_financial_accepted_with_evidence():
    transcript = [turn(1, "customer", "I lost my job and cannot pay right now.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="RTP_FINANCIAL",
            confidence=0.75,
            customer_verified=True,
            evidence_quote="I lost my job and cannot pay right now",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.RTP_FINANCIAL
    assert result.stage_group == "rtp"


# ---------------------------------------------------------------------------
# 2. Evidence enforcement (missing / not-in-transcript / low confidence)
# ---------------------------------------------------------------------------


def test_missing_evidence_quote_downgrades_to_unclear():
    transcript = [turn(1, "customer", "Maybe I can pay soon.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_TODAY",
            ptp_date=CALL_DATE,
            confidence=0.9,
            customer_verified=True,
            evidence_quote=None,
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert result.stage_code_source == StageCodeSource.DERIVED
    assert "evidence_quote_missing_or_not_in_transcript" in result.applied_rules


def test_evidence_quote_not_in_transcript_downgrades_to_unclear():
    transcript = [turn(1, "customer", "I am not sure yet.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_TODAY",
            ptp_date=CALL_DATE,
            confidence=0.9,
            customer_verified=True,
            evidence_quote="I will definitely pay today for sure",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert "evidence_quote_missing_or_not_in_transcript" in result.applied_rules


def test_low_confidence_downgrades_to_unclear():
    transcript = [turn(1, "customer", "I will pay today.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_TODAY",
            ptp_date=CALL_DATE,
            confidence=0.3,
            customer_verified=True,
            evidence_quote="I will pay today",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert any(r.startswith("confidence_below_threshold") for r in result.applied_rules)


def test_low_confidence_with_disconnect_status_yields_dscn():
    transcript = [turn(1, "customer", "I will pay today.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_TODAY",
            ptp_date=CALL_DATE,
            confidence=0.1,
            customer_verified=True,
            evidence_quote="I will pay today",
        ),
        transcript=transcript,
        call_status="failed",
    )
    assert result.stage_code == StageCode.DSCN


def test_evidence_matching_is_accent_and_case_insensitive():
    transcript = [turn(1, "customer", "Sí, pagaré mañana sin falta.", language="es-ES")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_TOMORROW",
            ptp_date=date(2026, 7, 29),
            confidence=0.88,
            customer_verified=True,
            evidence_quote="SI, PAGARE MANANA",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_TOMORROW


# ---------------------------------------------------------------------------
# 3. Consistency rules
# ---------------------------------------------------------------------------


def test_ptp_code_without_ptp_date_downgrades():
    transcript = [turn(1, "customer", "I will pay soon, I promise.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_FUTURE",
            confidence=0.9,
            customer_verified=True,
            evidence_quote="I will pay soon, I promise",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert "ptp_code_missing_ptp_date" in result.applied_rules


def test_ptp_date_in_past_downgrades_to_unclear():
    transcript = [turn(1, "customer", "I already paid on the 1st, I mean I will pay on the 1st.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_FUTURE",
            ptp_date=date(2026, 7, 1),
            confidence=0.9,
            customer_verified=True,
            evidence_quote="I will pay on the 1st",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert "ptp_date_in_past" in result.applied_rules


def test_mismatched_ptp_code_is_corrected_to_match_date():
    # LLM says PTP_FUTURE but the date is actually today -> correct to PTP_TODAY.
    transcript = [turn(1, "customer", "I will pay today, right now.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_FUTURE",
            ptp_date=CALL_DATE,
            confidence=0.9,
            customer_verified=True,
            evidence_quote="I will pay today, right now",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_TODAY
    assert any(r.startswith("ptp_code_corrected") for r in result.applied_rules)


def test_mismatched_ptp_code_corrected_to_tomorrow():
    transcript = [turn(1, "customer", "I will pay tomorrow morning.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_FUTURE",
            ptp_date=date(2026, 7, 29),
            confidence=0.9,
            customer_verified=True,
            evidence_quote="I will pay tomorrow morning",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_TOMORROW


def test_ptp_partial_not_reclassified_by_temporal_rule():
    transcript = [turn(1, "customer", "I can pay half of it today.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_PARTIAL",
            ptp_date=CALL_DATE,
            confidence=0.9,
            customer_verified=True,
            evidence_quote="I can pay half of it today",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.PTP_PARTIAL


def test_callback_without_datetime_downgrades():
    transcript = [turn(1, "customer", "Can you call me back later?")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="CALLBACK_SCHEDULED",
            confidence=0.9,
            customer_verified=True,
            evidence_quote="Can you call me back later",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert "callback_missing_datetime" in result.applied_rules


def test_unverified_customer_blocks_ptp_commitment():
    transcript = [turn(1, "customer", "Sure, I will pay today.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="PTP_TODAY",
            ptp_date=CALL_DATE,
            confidence=0.95,
            customer_verified=False,
            evidence_quote="I will pay today",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert "customer_not_verified_blocks_commitment" in result.applied_rules


def test_unverified_customer_blocks_already_paid():
    transcript = [turn(1, "customer", "I already paid it.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="ALREADY_PAID",
            confidence=0.9,
            customer_verified=False,
            evidence_quote="I already paid it",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR


def test_already_paid_vs_dispute_paid_reclassification():
    transcript = [
        turn(1, "customer", "I already paid but you charged me the wrong amount, it's incorrect amount."),
    ]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="ALREADY_PAID",
            confidence=0.9,
            customer_verified=True,
            evidence_quote="I already paid but you charged me the wrong amount",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.DISPUTE_PAID
    assert "already_paid_reclassified_as_dispute_paid" in result.applied_rules


def test_dispute_paid_confirmed_when_amount_contested():
    transcript = [turn(1, "customer", "That's the wrong amount, I already paid the correct EMI.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="DISPUTE_PAID",
            confidence=0.85,
            customer_verified=True,
            evidence_quote="That's the wrong amount, I already paid",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.DISPUTE_PAID


def test_third_party_vs_wrong_number_reclassification():
    transcript = [turn(1, "customer", "Sorry, this is the wrong number, he never lived here.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="THIRD_PARTY",
            confidence=0.8,
            customer_verified=None,
            evidence_quote="this is the wrong number",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.WRONG_NUMBER
    assert "third_party_reclassified_as_wrong_number" in result.applied_rules


def test_wrong_number_vs_third_party_reclassification():
    transcript = [turn(1, "customer", "He's not here right now, I'm his brother.")]
    result = resolve(
        disposition_kwargs=dict(
            stage_code="WRONG_NUMBER",
            confidence=0.8,
            customer_verified=None,
            evidence_quote="He's not here right now, I'm his brother",
        ),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.THIRD_PARTY


# ---------------------------------------------------------------------------
# 4. Disconnect overrides / invalid codes
# ---------------------------------------------------------------------------


def test_invalid_stage_code_string_falls_back_to_keyword_or_unclear():
    transcript = [turn(1, "customer", "I don't know what to say.")]
    result = resolve(
        disposition_kwargs=dict(stage_code="NOT_A_REAL_CODE", confidence=0.9),
        transcript=transcript,
    )
    assert result.stage_code == StageCode.UNCLEAR
    assert "proposed_stage_code_invalid_enum" in result.applied_rules


def test_no_stage_code_but_busy_status_yields_busy():
    result = resolve(
        disposition_kwargs=dict(stage_code=None),
        transcript=[],
        call_status="busy",
    )
    assert result.stage_code == StageCode.BUSY


def test_no_stage_code_but_no_answer_status_yields_rnr():
    result = resolve(
        disposition_kwargs=dict(stage_code=None),
        transcript=[],
        call_status="no_answer",
    )
    assert result.stage_code == StageCode.RNR


def test_no_stage_code_and_no_transcript_yields_unclear():
    result = resolve(
        disposition_kwargs=dict(stage_code=None),
        transcript=[],
        call_status="completed",
    )
    assert result.stage_code == StageCode.UNCLEAR


# ---------------------------------------------------------------------------
# 5. Keyword/regex fallback classifier (English + Spanish)
# ---------------------------------------------------------------------------


def test_keyword_fallback_english_already_paid():
    transcript = [turn(1, "customer", "I already paid this EMI last week, please check your records.")]
    result = resolve(disposition_kwargs=dict(stage_code=None), transcript=transcript)
    assert result.stage_code == StageCode.ALREADY_PAID
    assert result.stage_code_source == StageCodeSource.FALLBACK


def test_keyword_fallback_spanish_already_paid():
    transcript = [turn(1, "customer", "Ya pague esa cuota la semana pasada.", language="es-ES")]
    result = resolve(disposition_kwargs=dict(stage_code=None), transcript=transcript)
    assert result.stage_code == StageCode.ALREADY_PAID
    assert result.stage_code_source == StageCodeSource.FALLBACK


def test_keyword_fallback_spanish_financial_hardship():
    transcript = [turn(1, "customer", "Perdi mi trabajo y no tengo dinero para pagar.", language="es-ES")]
    result = resolve(disposition_kwargs=dict(stage_code=None), transcript=transcript)
    assert result.stage_code == StageCode.RTP_FINANCIAL


def test_keyword_fallback_english_wrong_number():
    transcript = [turn(1, "customer", "This is the wrong number, you have reached someone else.")]
    result = resolve(disposition_kwargs=dict(stage_code=None), transcript=transcript)
    assert result.stage_code == StageCode.WRONG_NUMBER


def test_keyword_fallback_refusal_no_reason():
    transcript = [turn(1, "customer", "I will not pay, period.")]
    result = resolve(disposition_kwargs=dict(stage_code=None), transcript=transcript)
    assert result.stage_code == StageCode.RTP_NO_REASON


def test_stage_group_mapping_present_for_all_final_codes():
    from app.models.enums import STAGE_CODE_TO_GROUP, StageCode as SC

    for code in SC:
        assert code in STAGE_CODE_TO_GROUP
