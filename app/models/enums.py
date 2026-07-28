"""Enumerations shared across the API, services, and repositories.

These values are the exact contract-mandated strings — do not rename without
updating ``CONTRACT.md`` and the dashboard.
"""

from __future__ import annotations

from enum import Enum


class StageCode(str, Enum):
    """Final disposition / stage code assigned to a completed call."""

    PTP_TODAY = "PTP_TODAY"
    PTP_TOMORROW = "PTP_TOMORROW"
    PTP_FUTURE = "PTP_FUTURE"
    PTP_PARTIAL = "PTP_PARTIAL"
    ALREADY_PAID = "ALREADY_PAID"
    CALLBACK_SCHEDULED = "CALLBACK_SCHEDULED"
    RTP_FINANCIAL = "RTP_FINANCIAL"
    RTP_MEDICAL = "RTP_MEDICAL"
    RTP_NO_REASON = "RTP_NO_REASON"
    DISPUTE_PAID = "DISPUTE_PAID"
    DISPUTE_CHARGES = "DISPUTE_CHARGES"
    NO_LOAN = "NO_LOAN"
    WRONG_NUMBER = "WRONG_NUMBER"
    THIRD_PARTY = "THIRD_PARTY"
    BUSY = "BUSY"
    RNR = "RNR"
    VM = "VM"
    DSCN = "DSCN"
    UNCLEAR = "UNCLEAR"


class StageGroup(str, Enum):
    """Grouping of stage codes used by stats aggregation and dashboard colours."""

    PTP = "ptp"
    ALREADY_PAID = "already_paid"
    RTP = "rtp"
    DISPUTE = "dispute"
    CALLBACK = "callback"
    NON_CONNECT = "non_connect"
    OTHER = "other"


STAGE_CODE_TO_GROUP: dict[StageCode, StageGroup] = {
    StageCode.PTP_TODAY: StageGroup.PTP,
    StageCode.PTP_TOMORROW: StageGroup.PTP,
    StageCode.PTP_FUTURE: StageGroup.PTP,
    StageCode.PTP_PARTIAL: StageGroup.PTP,
    StageCode.ALREADY_PAID: StageGroup.ALREADY_PAID,
    StageCode.RTP_FINANCIAL: StageGroup.RTP,
    StageCode.RTP_MEDICAL: StageGroup.RTP,
    StageCode.RTP_NO_REASON: StageGroup.RTP,
    StageCode.DISPUTE_PAID: StageGroup.DISPUTE,
    StageCode.DISPUTE_CHARGES: StageGroup.DISPUTE,
    StageCode.NO_LOAN: StageGroup.DISPUTE,
    StageCode.CALLBACK_SCHEDULED: StageGroup.CALLBACK,
    StageCode.RNR: StageGroup.NON_CONNECT,
    StageCode.VM: StageGroup.NON_CONNECT,
    StageCode.BUSY: StageGroup.NON_CONNECT,
    StageCode.WRONG_NUMBER: StageGroup.NON_CONNECT,
    StageCode.DSCN: StageGroup.NON_CONNECT,
    StageCode.THIRD_PARTY: StageGroup.OTHER,
    StageCode.UNCLEAR: StageGroup.OTHER,
}

# Stage codes that MUST be backed by an explicit, evidence-quoted commitment
# from the customer. See app/services/stage_code.py for enforcement.
COMMITMENT_STAGE_CODES: frozenset[StageCode] = frozenset(
    {
        StageCode.PTP_TODAY,
        StageCode.PTP_TOMORROW,
        StageCode.PTP_FUTURE,
        StageCode.PTP_PARTIAL,
        StageCode.ALREADY_PAID,
        StageCode.CALLBACK_SCHEDULED,
        StageCode.RTP_FINANCIAL,
        StageCode.RTP_MEDICAL,
        StageCode.RTP_NO_REASON,
        StageCode.DISPUTE_PAID,
        StageCode.DISPUTE_CHARGES,
        StageCode.NO_LOAN,
        StageCode.WRONG_NUMBER,
    }
)

PTP_STAGE_CODES: frozenset[StageCode] = frozenset(
    {
        StageCode.PTP_TODAY,
        StageCode.PTP_TOMORROW,
        StageCode.PTP_FUTURE,
        StageCode.PTP_PARTIAL,
    }
)


class CallStatus(str, Enum):
    """Lifecycle status of a call record."""

    QUEUED = "queued"
    INITIATED = "initiated"
    RINGING = "ringing"
    CONNECTED = "connected"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    CANCELLED = "cancelled"


class Language(str, Enum):
    """Normalised language codes used throughout the system."""

    EN_US = "en-US"
    ES_ES = "es-ES"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DispositionCategory(str, Enum):
    """High-level sentiment bucket reported by the analytics prompt."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class Speaker(str, Enum):
    """Speaker role for a single transcript turn."""

    BOT = "bot"
    CUSTOMER = "customer"


class StageCodeSource(str, Enum):
    """Provenance of the final stage_code assignment."""

    LLM = "llm"
    DERIVED = "derived"
    FALLBACK = "fallback"
