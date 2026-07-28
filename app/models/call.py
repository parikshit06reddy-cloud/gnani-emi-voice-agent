"""Core domain models: customer info, EMI details, transcript turns, and the
persisted call record.

``CallRecord`` is the canonical, storage-level representation used by both
repository implementations (Mongo and JSON). API-facing shapes
(``CallSummaryRow``, ``CallDetail``, etc.) live in ``responses.py`` and are
derived from ``CallRecord``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CallStatus, DispositionCategory, Language, Speaker, StageCode, StageCodeSource
from app.models.util import mask_phone


def utcnow() -> datetime:
    """Return a timezone-aware UTC ``datetime`` (helper for default factories)."""
    return datetime.now(UTC)


class CustomerInfo(BaseModel):
    """Identifying information about the customer being called."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "customer_id": "CUST001",
                "customer_name": "Rahul Sharma",
                "masked_phone_number": "******3210",
                "country_code": "+1",
            }
        }
    }

    customer_id: str = Field(..., description="Client-supplied unique customer identifier.")
    customer_name: str = Field(..., description="Full name of the customer.")
    masked_phone_number: str = Field(
        ..., description="Phone number with all but the last 4 digits masked."
    )
    country_code: str = Field(..., description="E.164-style country calling code, e.g. '+1'.")

    @classmethod
    def from_raw(
        cls, customer_id: str, customer_name: str, phone_number: str, country_code: str
    ) -> CustomerInfo:
        """Build a :class:`CustomerInfo` from raw (unmasked) input data."""
        return cls(
            customer_id=customer_id,
            customer_name=customer_name,
            masked_phone_number=mask_phone(phone_number),
            country_code=country_code,
        )


class EmiDetails(BaseModel):
    """EMI / loan context for the call."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "loan_account_number": "LAN123456",
                "emi_amount": 1200.0,
                "currency": "USD",
                "emi_due_date": "2026-07-25",
            }
        }
    }

    loan_account_number: str = Field(..., description="Loan account number.")
    emi_amount: float = Field(..., gt=0, description="EMI amount due.")
    currency: str = Field(default="USD", description="ISO 4217 currency code.")
    emi_due_date: date = Field(..., description="Date the EMI is/was due.")


class TranscriptTurn(BaseModel):
    """A single turn in the call transcript."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "turn": 1,
                "speaker": "bot",
                "text": "Hello, may I confirm I'm speaking with Rahul Sharma?",
                "language": "en-US",
                "timestamp": "2026-07-28T12:00:10+00:00",
            }
        }
    }

    turn: int = Field(..., ge=1, description="1-based sequential turn number.")
    speaker: Speaker = Field(..., description="Who spoke this turn.")
    text: str = Field(..., min_length=1, description="Transcribed text of the turn.")
    language: Language = Field(default=Language.UNKNOWN, description="Detected language of the turn.")
    timestamp: datetime | None = Field(default=None, description="Wall-clock time of the turn.")

    @field_validator("language", mode="before")
    @classmethod
    def _coerce_language(cls, v: Any) -> Any:
        if v is None:
            return Language.UNKNOWN
        return v


class AuditLogEntry(BaseModel):
    """A single append-only audit trail entry attached to a call record."""

    at: datetime = Field(default_factory=utcnow)
    actor: str = Field(..., description="Who/what performed the action, e.g. 'system', 'webhook'.")
    action: str = Field(..., description="Short action code, e.g. 'call_created'.")
    detail: str = Field(default="", description="Human-readable detail about the action.")


class EngineInfo(BaseModel):
    """Gnani AI stack engines used for the call."""

    asr: str = Field(default="gnani-prisma", description="ASR engine identifier.")
    tts: str = Field(default="gnani-timbre-2.5", description="TTS engine identifier.")
    llm: str = Field(default="gnani-evon", description="LLM engine identifier.")


class CallRecord(BaseModel):
    """Canonical persisted representation of a single outbound call.

    This is the source of truth stored by the repository layer. All API
    response shapes are projections of this model.
    """

    call_id: str = Field(..., description="Internal call identifier, e.g. CALL-20260728-0001.")
    customer: CustomerInfo
    emi_details: EmiDetails
    preferred_language: Language = Language.EN_US

    call_request: dict[str, Any] = Field(
        default_factory=dict, description="Raw initial-message request payload (redacted)."
    )
    gnani_console_response: dict[str, Any] = Field(
        default_factory=dict, description="Raw response from the Gnani call-trigger API."
    )
    post_call_payload: dict[str, Any] = Field(
        default_factory=dict, description="Raw most-recent post-call webhook payload."
    )

    gnani_call_reference: str | None = None
    initial_message: str = ""
    bot_variables: dict[str, Any] = Field(default_factory=dict)

    call_status: CallStatus = CallStatus.QUEUED
    call_duration_seconds: int | None = None

    stage_code: StageCode | None = None
    stage_group: str | None = None
    stage_code_source: StageCodeSource | None = None
    disposition_reason: str | None = None
    disposition_summary: str | None = None
    ptp_date: date | None = None
    ptp_amount: float | None = None
    callback_datetime: datetime | None = None
    language_captured: Language | None = None
    language_switched: bool = False
    sentiment: DispositionCategory | None = None
    confidence: float | None = None
    customer_verified: bool | None = None
    evidence_quote: str | None = None
    recording_url: str | None = None

    engines: EngineInfo = Field(default_factory=EngineInfo)
    conversation_transcript: list[TranscriptTurn] = Field(default_factory=list)

    call_initiated_at: datetime | None = None
    call_started_at: datetime | None = None
    call_completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    audit_log: list[AuditLogEntry] = Field(default_factory=list)
    webhook_event_ids: list[str] = Field(default_factory=list)

    def duration_display(self) -> str:
        """Return ``call_duration_seconds`` formatted as ``MM:SS``."""
        if self.call_duration_seconds is None:
            return "--:--"
        minutes, seconds = divmod(int(self.call_duration_seconds), 60)
        return f"{minutes:02d}:{seconds:02d}"
