"""Normalisation of the raw analytics-prompt disposition payload.

This module is intentionally narrow: it only cleans/coerces fields (trim
strings, cap lengths, normalise dates, coerce sentiment) and does **not**
decide the stage code — that is the sole responsibility of
``app/services/stage_code.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.models.enums import DispositionCategory
from app.models.requests import DispositionPayload

MAX_SUMMARY_LENGTH = 2000
MAX_REASON_LENGTH = 500

_SENTIMENT_ALIASES: dict[str, DispositionCategory] = {
    "positive": DispositionCategory.POSITIVE,
    "pos": DispositionCategory.POSITIVE,
    "happy": DispositionCategory.POSITIVE,
    "neutral": DispositionCategory.NEUTRAL,
    "neu": DispositionCategory.NEUTRAL,
    "negative": DispositionCategory.NEGATIVE,
    "neg": DispositionCategory.NEGATIVE,
    "angry": DispositionCategory.NEGATIVE,
    "frustrated": DispositionCategory.NEGATIVE,
}


@dataclass(frozen=True)
class NormalisedDisposition:
    """Cleaned, type-safe version of the raw disposition payload."""

    stage_code_raw: str | None
    disposition_reason: str | None
    disposition_summary: str | None
    ptp_date: date | None
    ptp_amount: float | None
    callback_datetime: datetime | None
    confidence: float
    customer_verified: bool | None
    sentiment: DispositionCategory
    evidence_quote: str | None


def _clean_text(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None
    return cleaned[:max_length]


def _coerce_sentiment(value: DispositionCategory | str | None) -> DispositionCategory:
    if value is None:
        return DispositionCategory.UNKNOWN
    if isinstance(value, DispositionCategory):
        return value
    key = value.strip().lower()
    return _SENTIMENT_ALIASES.get(key, DispositionCategory.UNKNOWN)


def normalise_disposition(payload: DispositionPayload) -> NormalisedDisposition:
    """Clean and coerce a raw :class:`DispositionPayload` into a safe shape.

    - Trims whitespace on all text fields.
    - Caps ``disposition_summary`` / ``disposition_reason`` lengths.
    - Leaves date/datetime normalisation to pydantic (already ISO-parsed),
      but defends against ``None``.
    - Coerces ``confidence`` into ``[0, 1]`` (defaulting missing to 0.0 so
      the stage-code engine safely downgrades low-confidence dispositions).
    - Coerces sentiment aliases into the :class:`DispositionCategory` enum.
    """
    confidence = payload.confidence
    if confidence is None:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    stage_code_raw = payload.stage_code.strip().upper() if payload.stage_code else None

    return NormalisedDisposition(
        stage_code_raw=stage_code_raw or None,
        disposition_reason=_clean_text(payload.disposition_reason, MAX_REASON_LENGTH),
        disposition_summary=_clean_text(payload.disposition_summary, MAX_SUMMARY_LENGTH),
        ptp_date=payload.ptp_date,
        ptp_amount=payload.ptp_amount,
        callback_datetime=payload.callback_datetime,
        confidence=confidence,
        customer_verified=payload.customer_verified,
        sentiment=_coerce_sentiment(payload.sentiment),
        evidence_quote=_clean_text(payload.evidence_quote, MAX_REASON_LENGTH),
    )
