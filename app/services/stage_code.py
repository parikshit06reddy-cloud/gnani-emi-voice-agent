"""Deterministic stage-code resolution engine.

This is the highest-value component of the assignment: it turns the raw
LLM/analytics disposition (plus the full transcript) into a *trustworthy*
final stage code, never trusting the model's say-so blindly.

Resolution pipeline (see :func:`resolve_stage_code`):

1. If the payload proposes a usable stage code, validate it is a known
   :class:`StageCode`.
2. For "commitment" codes (PTP_*, ALREADY_PAID, CALLBACK_SCHEDULED,
   RTP_*, DISPUTE_*, NO_LOAN, WRONG_NUMBER) require a non-empty
   ``evidence_quote`` that actually appears (case/accent-insensitive
   substring) in a customer transcript turn, AND a confidence >= threshold.
   Failing either check downgrades to UNCLEAR/DSCN.
3. Apply consistency rules (PTP date required/not-in-past, callback
   datetime required, ALREADY_PAID vs DISPUTE_PAID disambiguation,
   THIRD_PARTY vs WRONG_NUMBER, unverified customer blocks commitments).
4. If the payload provides no usable stage code at all, fall back to a
   keyword/regex classifier over the transcript (English + Spanish).
5. Always return an auditable :class:`StageCodeResolution` recording the
   source, confidence, reason, and every rule that fired.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.models.enums import COMMITMENT_STAGE_CODES, PTP_STAGE_CODES, STAGE_CODE_TO_GROUP, StageCode, StageCodeSource
from app.models.requests import WebhookTranscriptTurn
from app.models.util import normalise_text_for_match
from app.services.date_rules import resolve_evidence_dates
from app.services.disposition import NormalisedDisposition

_STATUS_TO_STAGE_CODE = {
    "busy": StageCode.BUSY,
    "no_answer": StageCode.RNR,
    "voicemail": StageCode.VM,
}

# Voicemail-greeting markers (folded text): a transcript with ZERO customer
# turns whose bot/system turns contain one of these is a voicemail pickup
# (beep-then-monologue), not a ring-no-response.
_VOICEMAIL_MARKERS_RE = re.compile(
    r"(voicemail|voice mail|leave a message|after the tone|after the beep|"
    r"buzon de voz|deje su mensaje|despues del tono|mensaje despues)"
)

# Vague, non-committal phrasing that must NEVER ground a PTP on its own
# ("I'll try to arrange something soon" is not a promise to pay).
_VAGUE_COMMITMENT_RE = re.compile(
    r"\b(try to|i.ll try|arrange something|work something out|see what i can do|"
    r"as soon as (i can|possible)|soon|sometime|eventually|when i can|maybe|"
    r"tratare|intentare|ver que puedo hacer|lo antes posible|pronto|"
    r"en algun momento|cuando pueda|tal vez|quizas)\b"
)

_MEDICAL_MARKERS_RE = re.compile(
    r"\b(hospital|hospitalizado|hospitalizada|surgery|operacion|cirugia|"
    r"medical|medica|medico|sick|enfermo|enferma|accident|accidente|"
    r"emergencia medica|doctor|treatment|tratamiento)\b"
)


@dataclass
class StageCodeResolution:
    """Auditable result of the stage-code resolution engine."""

    stage_code: StageCode
    stage_group: str
    stage_code_source: StageCodeSource
    disposition_reason: str
    confidence: float
    applied_rules: list[str] = field(default_factory=list)


def _customer_text_blob(transcript: list[WebhookTranscriptTurn]) -> str:
    return " \n ".join(
        turn.text for turn in transcript if turn.speaker.value == "customer"
    )


def _evidence_found(evidence_quote: str | None, transcript: list[WebhookTranscriptTurn]) -> bool:
    """Check whether ``evidence_quote`` appears in any customer turn.

    Comparison is case- and accent-insensitive substring matching, applied
    in both directions (quote-in-turn or turn-in-quote) to tolerate minor
    transcription/summarisation differences.
    """
    if not evidence_quote or not evidence_quote.strip():
        return False
    needle = normalise_text_for_match(evidence_quote)
    if not needle:
        return False
    for turn in transcript:
        if turn.speaker.value != "customer":
            continue
        haystack = normalise_text_for_match(turn.text)
        if needle in haystack:
            return True
        # Reverse containment tolerates the LLM quoting slightly MORE than
        # one turn (e.g. merging two adjacent turns) — but only when the
        # real customer turn is itself substantial (>= 12 chars), so a long
        # fabricated "quote" cannot be validated by swallowing a trivially
        # short real turn like "yes" or "ok".
        if len(haystack) >= 12 and haystack in needle:
            return True
    return False


def _classify_ptp_temporal(ptp_date: date, call_date: date) -> StageCode:
    """Map a ptp_date relative to call_date onto PTP_TODAY/TOMORROW/FUTURE."""
    delta_days = (ptp_date - call_date).days
    if delta_days <= 0:
        return StageCode.PTP_TODAY
    if delta_days == 1:
        return StageCode.PTP_TOMORROW
    return StageCode.PTP_FUTURE


def _has_customer_turns(transcript: list[WebhookTranscriptTurn]) -> bool:
    return any(turn.speaker.value == "customer" for turn in transcript)


def _non_conversational_code(
    transcript: list[WebhookTranscriptTurn], call_status: str
) -> StageCode | None:
    """VM/RNR derivation for calls where the customer never spoke.

    Precedence (documented in docs/stage-code-logic.md):
    - zero customer turns + voicemail-greeting markers anywhere in the
      transcript  -> VM (beep-then-monologue: the bot spoke into a machine)
    - zero customer turns, no markers                     -> RNR
    - any customer turn at all                            -> None (not ours)
    """
    if _has_customer_turns(transcript):
        return None
    blob = normalise_text_for_match(" \n ".join(turn.text for turn in transcript))
    if blob and _VOICEMAIL_MARKERS_RE.search(blob):
        return StageCode.VM
    return StageCode.RNR


def _disconnect_stage_code(call_status: str) -> StageCode | None:
    status = call_status.strip().lower()
    if status in _STATUS_TO_STAGE_CODE:
        return _STATUS_TO_STAGE_CODE[status]
    if status in ("failed", "cancelled"):
        return StageCode.DSCN
    return None


# --- Keyword fallback classifier -----------------------------------------
# Applied ONLY when the payload gives no usable stage code at all. Order
# matters: more specific patterns are checked first.
_KEYWORD_RULES: list[tuple[StageCode, re.Pattern[str]]] = [
    (
        StageCode.ALREADY_PAID,
        re.compile(
            r"\b(already paid|i (have |already )?paid|payment (is )?complete|"
            r"ya pague|ya he pagado|ya pagu[eé]|pago (ya )?realizado)\b"
        ),
    ),
    (
        StageCode.WRONG_NUMBER,
        re.compile(
            r"\b(wrong number|not (his|her|my) number|number (does not|doesn.t) belong|"
            r"numero equivocado|no es su numero|numero incorrecto)\b"
        ),
    ),
    (
        StageCode.THIRD_PARTY,
        re.compile(
            r"\b(he.s not (here|available)|she.s not (here|available)|not available right now|"
            r"i.m his (wife|brother|son|daughter|colleague)|i.m her (wife|brother|son|daughter)|"
            r"(he|she).s my (brother|sister|husband|wife|son|daughter|father|mother)|"
            r"this is (his|her) (wife|brother|sister|husband|number, i.m)|"
            r"no est[aá] (aqui|disponible)|soy su (esposa|hermano|hijo|hija|colega)|"
            r"es mi (hermano|hermana|esposo|esposa|hijo|hija|padre|madre))\b"
        ),
    ),
    (
        StageCode.NO_LOAN,
        re.compile(
            r"\b(no such loan|i (do not|don.t) have (a|any) loan|never took (a|this) loan|"
            r"no tengo (ese |ningun )?prestamo|no existe (ese|tal) prestamo)\b"
        ),
    ),
    (
        StageCode.DISPUTE_CHARGES,
        re.compile(
            r"\b(wrong (amount|charge)|dispute the (charge|amount|emi)|overcharged|"
            r"cargo incorrecto|monto incorrecto|disputo (el cargo|el monto))\b"
        ),
    ),
    (
        StageCode.CALLBACK_SCHEDULED,
        re.compile(
            r"\b(call me back|callback|call again (later|tomorrow)|"
            r"llam[ae]me (mas tarde|despues)|vuelva a llamar)\b"
        ),
    ),
    (
        StageCode.RTP_MEDICAL,
        re.compile(
            r"\b(hospital|surgery|medical (emergency|bills?|reason)|i.m sick|"
            r"hospitalizado|emergencia medica|estoy enfermo)\b"
        ),
    ),
    (
        StageCode.RTP_FINANCIAL,
        re.compile(
            r"\b(lost my job|no money|can.t afford|financial (difficulty|trouble|hardship)|"
            r"perdi mi trabajo|no tengo dinero|dificultad financiera|sin dinero)\b"
        ),
    ),
    (
        StageCode.RTP_NO_REASON,
        re.compile(
            r"\b(i (will not|won.t|refuse to) pay|not going to pay|"
            r"no voy a pagar|me niego a pagar)\b"
        ),
    ),
    (
        StageCode.PTP_TODAY,
        re.compile(
            r"\b(pay (it )?today|will pay today|pago hoy|pagare hoy|voy a pagar hoy)\b"
        ),
    ),
    (
        StageCode.PTP_TOMORROW,
        re.compile(
            r"\b(pay tomorrow|will pay tomorrow|pagare manana|pago manana)\b"
        ),
    ),
    (
        StageCode.PTP_PARTIAL,
        re.compile(
            r"\b(pay (part|half|some)|partial payment|pago parcial|pagare parte)\b"
        ),
    ),
]


def _keyword_fallback(transcript: list[WebhookTranscriptTurn]) -> tuple[StageCode, str] | None:
    """Best-effort keyword/regex classifier over customer turns.

    Used ONLY when the payload provides no usable stage code. Returns
    ``(stage_code, matched_snippet)`` or ``None`` if nothing matched.
    """
    for turn in transcript:
        if turn.speaker.value != "customer":
            continue
        folded = normalise_text_for_match(turn.text)
        for stage_code, pattern in _KEYWORD_RULES:
            if pattern.search(folded):
                return stage_code, turn.text
    return None


def resolve_stage_code(
    *,
    disposition: NormalisedDisposition,
    transcript: list[WebhookTranscriptTurn],
    call_status: str,
    call_date: date,
    confidence_threshold: float = 0.6,
) -> StageCodeResolution:
    """Resolve the final, trustworthy stage code for a completed call.

    Args:
        disposition: The cleaned analytics disposition (see disposition.py).
        transcript: Full call transcript.
        call_status: The webhook-reported call status (e.g. "completed",
            "no_answer", "busy").
        call_date: The calendar date the call took place, used to classify
            PTP_TODAY/TOMORROW/FUTURE relative to ``ptp_date``.
        confidence_threshold: Minimum confidence required to trust a
            commitment stage code (default from settings: 0.6).

    Returns:
        A fully auditable :class:`StageCodeResolution`.
    """
    rules: list[str] = []

    disconnect_override = _disconnect_stage_code(call_status)

    proposed: StageCode | None = None
    if disposition.stage_code_raw:
        try:
            proposed = StageCode(disposition.stage_code_raw)
            rules.append("proposed_stage_code_valid_enum")
        except ValueError:
            rules.append("proposed_stage_code_invalid_enum")
            proposed = None

    # --- No usable proposal: disconnect override, then VM/RNR derivation for
    #     zero-customer-turn calls, then keyword fallback.
    if proposed is None:
        if disconnect_override is not None:
            rules.append(f"call_status_disconnect_override:{call_status}")
            return _finalise(
                disconnect_override,
                StageCodeSource.DERIVED,
                f"Call status '{call_status}' indicates no conclusive conversation occurred.",
                disposition.confidence,
                rules,
            )
        non_conversational = _non_conversational_code(transcript, call_status)
        if non_conversational is not None:
            rules.append(
                "zero_customer_turns_voicemail_markers"
                if non_conversational == StageCode.VM
                else "zero_customer_turns_no_markers"
            )
            reason = (
                "No customer turns; transcript contains a voicemail greeting — call answered by voicemail."
                if non_conversational == StageCode.VM
                else "Line connected but the customer never spoke; treated as ring-no-response."
            )
            return _finalise(
                non_conversational, StageCodeSource.DERIVED, reason, disposition.confidence, rules
            )
        fallback = _keyword_fallback(transcript)
        if fallback is not None:
            stage_code, snippet = fallback
            rules.append("keyword_fallback_matched")
            # Fallback-derived commitment codes still require the same
            # evidence to exist verbatim, which it does by construction.
            return _finalise(
                stage_code,
                StageCodeSource.FALLBACK,
                f"Derived from keyword match in transcript: '{snippet.strip()}'.",
                max(disposition.confidence, 0.5),
                rules,
            )
        rules.append("no_proposal_no_fallback_match")
        target = disconnect_override or StageCode.UNCLEAR
        return _finalise(
            target,
            StageCodeSource.DERIVED,
            "No stage code proposed and no keyword evidence found in transcript.",
            disposition.confidence,
            rules,
        )

    # --- customer_verified gate: blocks commitment codes outright.
    if disposition.customer_verified is False and proposed in (
        PTP_STAGE_CODES | {StageCode.ALREADY_PAID}
    ):
        rules.append("customer_not_verified_blocks_commitment")
        return _finalise(
            StageCode.UNCLEAR,
            StageCodeSource.DERIVED,
            "Customer identity was not verified; cannot honour a payment "
            "commitment or paid-claim without verification.",
            disposition.confidence,
            rules,
        )

    # --- Evidence + confidence gate for all commitment codes.
    if proposed in COMMITMENT_STAGE_CODES:
        has_evidence = _evidence_found(disposition.evidence_quote, transcript)
        meets_confidence = disposition.confidence >= confidence_threshold
        if not has_evidence:
            rules.append("evidence_quote_missing_or_not_in_transcript")
        if not meets_confidence:
            rules.append(f"confidence_below_threshold:{disposition.confidence}<{confidence_threshold}")
        if not has_evidence or not meets_confidence:
            target = (
                disconnect_override
                or _non_conversational_code(transcript, call_status)
                or StageCode.UNCLEAR
            )
            reason = (
                "Proposed stage code lacked verifiable evidence in the transcript "
                "or confidence was below threshold; downgraded for safety."
                if target == StageCode.UNCLEAR
                else f"Insufficient evidence/confidence; call-level signals indicate '{target.value}'."
            )
            return _finalise(target, StageCodeSource.DERIVED, reason, disposition.confidence, rules)
        rules.append("evidence_and_confidence_ok")

        # --- Vague-commitment gate (PTP only): an evidence quote made up of
        # non-committal phrasing with no recognisable date expression cannot
        # ground a promise-to-pay, whatever ptp_date the LLM attached to it.
        if proposed in PTP_STAGE_CODES and disposition.evidence_quote:
            folded_quote = normalise_text_for_match(disposition.evidence_quote)
            quote_dates = resolve_evidence_dates(disposition.evidence_quote, call_date)
            if _VAGUE_COMMITMENT_RE.search(folded_quote) and not quote_dates:
                rules.append("vague_commitment_no_date_evidence")
                return _finalise(
                    StageCode.UNCLEAR,
                    StageCodeSource.DERIVED,
                    "Customer's statement was a vague intention "
                    f"({disposition.evidence_quote!r}) with no concrete date; "
                    "not recorded as a promise to pay.",
                    disposition.confidence,
                    rules,
                )

    # --- Consistency rules -------------------------------------------------
    if proposed in PTP_STAGE_CODES:
        if disposition.ptp_date is None:
            rules.append("ptp_code_missing_ptp_date")
            return _finalise(
                StageCode.UNCLEAR,
                StageCodeSource.DERIVED,
                "A PTP_* stage code requires a ptp_date; none was provided.",
                disposition.confidence,
                rules,
            )
        if disposition.ptp_date < call_date:
            rules.append("ptp_date_in_past")
            return _finalise(
                StageCode.UNCLEAR,
                StageCodeSource.DERIVED,
                f"Proposed ptp_date {disposition.ptp_date.isoformat()} is before the "
                f"call date {call_date.isoformat()}; cannot honour a past promise.",
                disposition.confidence,
                rules,
            )
        # --- Evidence-date consistency: if the quote itself contains a
        # recognisable date phrase, the LLM's ptp_date must match one of the
        # phrase's candidate resolutions; otherwise the date was fabricated
        # or misresolved and the PTP cannot be honoured as stated.
        if disposition.evidence_quote:
            quote_dates = resolve_evidence_dates(disposition.evidence_quote, call_date)
            if quote_dates and disposition.ptp_date not in quote_dates:
                rules.append(
                    "evidence_date_mismatch:"
                    f"{disposition.ptp_date.isoformat()}!in{sorted(d.isoformat() for d in quote_dates)}"
                )
                return _finalise(
                    StageCode.UNCLEAR,
                    StageCodeSource.DERIVED,
                    f"ptp_date {disposition.ptp_date.isoformat()} does not match the date "
                    f"phrase in the customer's own words ({disposition.evidence_quote!r}); "
                    "downgraded rather than recording an unverified promise.",
                    disposition.confidence,
                    rules,
                )
            if quote_dates:
                rules.append("evidence_date_consistent")

        if proposed != StageCode.PTP_PARTIAL:
            corrected = _classify_ptp_temporal(disposition.ptp_date, call_date)
            if corrected != proposed:
                rules.append(f"ptp_code_corrected:{proposed.value}->{corrected.value}")
                proposed = corrected
            else:
                rules.append("ptp_code_matches_date")

    if proposed == StageCode.CALLBACK_SCHEDULED and disposition.callback_datetime is None:
        rules.append("callback_missing_datetime")
        return _finalise(
            StageCode.UNCLEAR,
            StageCodeSource.DERIVED,
            "CALLBACK_SCHEDULED requires a callback_datetime; none was provided.",
            disposition.confidence,
            rules,
        )

    if proposed in (StageCode.RTP_FINANCIAL, StageCode.RTP_MEDICAL):
        proposed = _disambiguate_rtp(proposed, transcript, rules)

    if proposed in (StageCode.ALREADY_PAID, StageCode.DISPUTE_PAID):
        proposed = _disambiguate_paid_vs_dispute(proposed, disposition, transcript, rules)

    if proposed in (StageCode.THIRD_PARTY, StageCode.WRONG_NUMBER):
        proposed = _disambiguate_third_party_vs_wrong_number(proposed, disposition, transcript, rules)

    reason = disposition.disposition_reason or f"LLM-assigned stage code {proposed.value} accepted as-is."
    return _finalise(proposed, StageCodeSource.LLM, reason, disposition.confidence, rules)


def _disambiguate_rtp(
    proposed: StageCode,
    transcript: list[WebhookTranscriptTurn],
    rules: list[str],
) -> StageCode:
    """RTP_MEDICAL takes precedence over RTP_FINANCIAL when both apply.

    "I'm in the hospital, no money" is a medical hardship whose financial
    consequence is secondary — the documented precedence (see
    docs/stage-code-logic.md) is MEDICAL > FINANCIAL because it changes both
    the compliance posture and the correct follow-up cadence.
    """
    blob = normalise_text_for_match(_customer_text_blob(transcript))
    if proposed == StageCode.RTP_FINANCIAL and _MEDICAL_MARKERS_RE.search(blob):
        rules.append("rtp_financial_reclassified_as_medical")
        return StageCode.RTP_MEDICAL
    return proposed


def _disambiguate_paid_vs_dispute(
    proposed: StageCode,
    disposition: NormalisedDisposition,
    transcript: list[WebhookTranscriptTurn],
    rules: list[str],
) -> StageCode:
    """ALREADY_PAID vs DISPUTE_PAID: dispute only if the customer contests the amount."""
    blob = normalise_text_for_match(_customer_text_blob(transcript))
    contests_amount = bool(
        re.search(r"\b(wrong amount|too much|overcharg|incorrect amount|monto incorrecto|cobro de mas)\b", blob)
    )
    if proposed == StageCode.ALREADY_PAID and contests_amount:
        rules.append("already_paid_reclassified_as_dispute_paid")
        return StageCode.DISPUTE_PAID
    if proposed == StageCode.DISPUTE_PAID and not contests_amount:
        rules.append("dispute_paid_confirmed_no_contest_language")
    return proposed


def _disambiguate_third_party_vs_wrong_number(
    proposed: StageCode,
    disposition: NormalisedDisposition,
    transcript: list[WebhookTranscriptTurn],
    rules: list[str],
) -> StageCode:
    """THIRD_PARTY (borrower reachable via someone else) vs WRONG_NUMBER (not their number)."""
    blob = normalise_text_for_match(_customer_text_blob(transcript))
    is_wrong_number = bool(
        re.search(r"\b(wrong number|not (his|her) number|numero equivocado|numero incorrecto)\b", blob)
    )
    is_third_party = bool(
        re.search(
            r"\b(not (here|available)|i.m (his|her)|"
            r"(he|she).s my (brother|sister|husband|wife|son|daughter|father|mother)|"
            r"soy su|es mi (hermano|hermana|esposo|esposa|hijo|hija|padre|madre)|"
            r"no esta (aqui|disponible))\b",
            blob,
        )
    )
    if proposed == StageCode.THIRD_PARTY and is_wrong_number and not is_third_party:
        rules.append("third_party_reclassified_as_wrong_number")
        return StageCode.WRONG_NUMBER
    if proposed == StageCode.WRONG_NUMBER and is_third_party and not is_wrong_number:
        rules.append("wrong_number_reclassified_as_third_party")
        return StageCode.THIRD_PARTY
    return proposed


def _finalise(
    stage_code: StageCode,
    source: StageCodeSource,
    reason: str,
    confidence: float,
    rules: list[str],
) -> StageCodeResolution:
    return StageCodeResolution(
        stage_code=stage_code,
        stage_group=STAGE_CODE_TO_GROUP[stage_code].value,
        stage_code_source=source,
        disposition_reason=reason,
        confidence=confidence,
        applied_rules=rules,
    )
