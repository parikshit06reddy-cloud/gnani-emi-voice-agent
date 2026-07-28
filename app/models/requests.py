"""Request body models for the public API endpoints."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import DispositionCategory, Speaker
from app.models.util import normalise_language_strict

_PHONE_RE = re.compile(r"^\d{7,15}$")
_COUNTRY_CODE_RE = re.compile(r"^\+\d{1,4}$")


class InitialMessageRequest(BaseModel):
    """Request body for ``POST /api/Initial_Message``."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "customer_id": "CUST001",
                "customer_name": "Rahul Sharma",
                "phone_number": "9876543210",
                "country_code": "+1",
                "loan_account_number": "LAN123456",
                "emi_amount": 1200.0,
                "emi_due_date": "2026-07-25",
                "preferred_language": "English (US)",
                "currency": "USD",
                "initial_message": None,
                "metadata": {},
            }
        }
    }

    customer_id: str = Field(..., min_length=1, description="Unique customer identifier.")
    customer_name: str = Field(..., min_length=1, description="Full name of the customer.")
    phone_number: str = Field(..., description="Customer phone number, 7-15 digits, no symbols.")
    country_code: str = Field(..., description="Country calling code, e.g. '+1'.")
    loan_account_number: str = Field(..., min_length=1, description="Loan account number.")
    emi_amount: float = Field(..., gt=0, description="EMI amount due, must be > 0.")
    emi_due_date: date = Field(..., description="ISO date the EMI is/was due.")
    preferred_language: str = Field(
        default="en-US", description="Customer's preferred language (aliases accepted)."
    )
    currency: str = Field(default="USD", description="ISO 4217 currency code.")
    initial_message: str | None = Field(
        default=None, description="Pre-authored opening message; auto-generated if omitted."
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary passthrough metadata.")

    @field_validator("phone_number")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        digits = v.strip()
        if not _PHONE_RE.match(digits):
            raise ValueError("phone_number must be 7-15 digits with no symbols.")
        return digits

    @field_validator("country_code")
    @classmethod
    def _validate_country_code(cls, v: str) -> str:
        v = v.strip()
        if not _COUNTRY_CODE_RE.match(v):
            raise ValueError("country_code must match ^\\+\\d{1,4}$, e.g. '+1'.")
        return v

    @field_validator("customer_id", "customer_name", "loan_account_number")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty or whitespace-only.")
        return v.strip()

    @field_validator("preferred_language")
    @classmethod
    def _validate_language(cls, v: str) -> str:
        normalised = normalise_language_strict(v)
        if normalised is None:
            raise ValueError(
                "preferred_language must map to a supported language "
                "(en-US or es-ES); accepted aliases include 'English', "
                "'English (US)', 'en', 'en-US', 'Spanish', 'es', 'es-ES', 'Español'."
            )
        return normalised.value


class DispositionPayload(BaseModel):
    """The ``disposition`` object nested inside a post-call webhook payload."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "stage_code": "PTP_FUTURE",
                "disposition_reason": "Customer said 'I will pay on the 30th'.",
                "disposition_summary": "Customer confirmed identity and promised payment by month end.",
                "ptp_date": "2026-07-30",
                "ptp_amount": 1200.0,
                "callback_datetime": None,
                "confidence": 0.93,
                "customer_verified": True,
                "sentiment": "neutral",
                "evidence_quote": "I will pay on the 30th",
            }
        }
    }

    stage_code: str | None = Field(default=None, description="LLM/analytics-proposed stage code.")
    disposition_reason: str | None = Field(default=None, description="Short reason for the disposition.")
    disposition_summary: str | None = Field(default=None, description="Longer free-text call summary.")
    ptp_date: date | None = Field(default=None, description="Promise-to-pay date, if applicable.")
    ptp_amount: float | None = Field(default=None, description="Promised payment amount, if partial/specified.")
    callback_datetime: datetime | None = Field(default=None, description="Requested callback date/time.")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Model confidence 0-1.")
    customer_verified: bool | None = Field(default=None, description="Whether identity was confirmed.")
    sentiment: DispositionCategory | str | None = Field(default=None, description="Overall call sentiment.")
    evidence_quote: str | None = Field(
        default=None, description="Verbatim customer quote supporting the stage code."
    )

    @field_validator("ptp_date", "callback_datetime", mode="before")
    @classmethod
    def _blank_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class WebhookTranscriptTurn(BaseModel):
    """A transcript turn as received in the raw webhook payload."""

    turn: int = Field(..., ge=1)
    speaker: Speaker
    text: str = Field(..., min_length=1)
    language: str | None = Field(default=None)
    timestamp: datetime | None = None


class PostCallWebhookRequest(BaseModel):
    """Request body for ``POST /api/v1/webhooks/post-call``."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "evt-001",
                "call_id": "CALL-20260728-0001",
                "gnani_call_reference": "gnani-9f3c",
                "call_status": "completed",
                "call_duration_seconds": 96,
                "call_started_at": "2026-07-28T12:00:05+00:00",
                "call_ended_at": "2026-07-28T12:01:41+00:00",
                "recording_url": "https://example.com/recordings/CALL-20260728-0001.wav",
                "language_detected": "es-ES",
                "asr_engine": "gnani-prisma",
                "tts_engine": "gnani-timbre-2.5",
                "llm_engine": "gnani-evon",
                "disposition": {
                    "stage_code": "PTP_FUTURE",
                    "disposition_reason": "Customer said 'I will pay on the 30th'.",
                    "disposition_summary": "...",
                    "ptp_date": "2026-07-30",
                    "ptp_amount": 1200.0,
                    "callback_datetime": None,
                    "confidence": 0.93,
                    "customer_verified": True,
                    "sentiment": "neutral",
                    "evidence_quote": "I will pay on the 30th",
                },
                "transcript": [
                    {
                        "turn": 1,
                        "speaker": "bot",
                        "text": "Hello, may I confirm I'm speaking with Rahul Sharma?",
                        "language": "en-US",
                        "timestamp": "2026-07-28T12:00:10+00:00",
                    },
                    {
                        "turn": 2,
                        "speaker": "customer",
                        "text": "Si, soy yo.",
                        "language": "es-ES",
                        "timestamp": "2026-07-28T12:00:15+00:00",
                    },
                ],
            }
        }
    }

    event_id: str | None = Field(default=None, description="Unique webhook delivery id (idempotency key).")
    call_id: str = Field(..., min_length=1, description="Internal call_id this webhook refers to.")
    gnani_call_reference: str | None = Field(default=None, description="Gnani console call reference.")
    call_status: str = Field(..., description="Terminal (or interim) call status.")
    call_duration_seconds: int | None = Field(default=None, ge=0)
    call_started_at: datetime | None = None
    call_ended_at: datetime | None = None
    recording_url: str | None = None
    language_detected: str | None = None
    asr_engine: str | None = None
    tts_engine: str | None = None
    llm_engine: str | None = None
    disposition: DispositionPayload = Field(default_factory=DispositionPayload)
    transcript: list[WebhookTranscriptTurn] = Field(default_factory=list)

    @field_validator("call_id")
    @classmethod
    def _non_empty_call_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("call_id must not be empty.")
        return v.strip()

    @model_validator(mode="after")
    def _idempotency_fallback_key_available(self) -> PostCallWebhookRequest:
        # No hard requirement, but call_ended_at is used as a fallback
        # idempotency component when event_id is absent — document via model.
        return self

    def idempotency_key(self) -> str:
        """Return the idempotency key: ``event_id`` or a ``call_id``+``call_ended_at`` fallback."""
        if self.event_id:
            return self.event_id
        ended = self.call_ended_at.isoformat() if self.call_ended_at else "no-end-time"
        return f"{self.call_id}:{ended}"
