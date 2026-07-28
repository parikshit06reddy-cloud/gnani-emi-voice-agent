"""API response models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.call import AuditLogEntry, EngineInfo, TranscriptTurn
from app.models.enums import CallStatus, DispositionCategory, Language, StageCode, StageCodeSource


class ErrorDetail(BaseModel):
    """Nested error object inside the standard error envelope."""

    code: str = Field(..., description="Machine-readable error code.")
    message: str = Field(..., description="Human-readable error message.")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional structured context.")


class ErrorResponse(BaseModel):
    """Standard error envelope returned by every handled error."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": False,
                "error": {"code": "GNANI_TIMEOUT", "message": "Gnani call-trigger API timed out.", "details": {}},
                "request_id": "3d2b6e2e-4f34-4a7a-9b7f-3a9e6c9b0a11",
            }
        }
    }

    success: bool = False
    error: ErrorDetail
    request_id: str


class InitialMessageResponse(BaseModel):
    """Response body for ``POST /api/Initial_Message``."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "call_id": "CALL-20260728-0001",
                "gnani_call_reference": "gnani-9f3c1e2a",
                "customer_id": "CUST001",
                "customer_name": "Rahul Sharma",
                "phone_number": "******3210",
                "country_code": "+1",
                "loan_account_number": "LAN123456",
                "emi_amount": 1200.0,
                "emi_due_date": "2026-07-25",
                "preferred_language": "en-US",
                "initial_message": "Hello, this is Aria calling from Apex Financial Services ...",
                "call_status": "initiated",
                "created_at": "2026-07-28T12:00:00+00:00",
            }
        }
    }

    success: bool = True
    call_id: str
    gnani_call_reference: str | None
    customer_id: str
    customer_name: str
    phone_number: str = Field(..., description="Masked phone number (last 4 digits only).")
    country_code: str
    loan_account_number: str
    emi_amount: float
    emi_due_date: date
    preferred_language: Language
    initial_message: str
    call_status: CallStatus
    created_at: datetime


class WebhookAckResponse(BaseModel):
    """Response body for ``POST /api/v1/webhooks/post-call``."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "duplicate": False,
                "call_id": "CALL-20260728-0001",
                "stage_code": "PTP_FUTURE",
                "ptp_date": "2026-07-30",
            }
        }
    }

    success: bool = True
    duplicate: bool = False
    call_id: str
    stage_code: StageCode | None = None
    ptp_date: date | None = None


_CALL_SUMMARY_ROW_EXAMPLE: dict = {
    "call_id": "CALL-20260728-0001",
    "customer_id": "CUST001",
    "customer_name": "Rahul Sharma",
    "masked_phone_number": "******3210",
    "loan_account_number": "LAN123456",
    "call_initiated_time": "2026-07-28T12:00:00+00:00",
    "call_status": "completed",
    "call_duration_seconds": 96,
    "call_duration_display": "01:36",
    "stage_code": "PTP_FUTURE",
    "stage_group": "ptp",
    "disposition_reason": "Customer promised payment by month end.",
    "ptp_date": "2026-07-30",
    "language": "es-ES",
}


class CallSummaryRow(BaseModel):
    """One row in the ``GET /api/v1/calls`` list response."""

    model_config = {"json_schema_extra": {"example": _CALL_SUMMARY_ROW_EXAMPLE}}

    call_id: str
    customer_id: str
    customer_name: str
    masked_phone_number: str
    loan_account_number: str
    call_initiated_time: datetime | None
    call_status: CallStatus
    call_duration_seconds: int | None
    call_duration_display: str
    stage_code: StageCode | None
    stage_group: str | None
    disposition_reason: str | None
    ptp_date: date | None
    language: Language | None


class CallListResponse(BaseModel):
    """Paginated response body for ``GET /api/v1/calls``."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [_CALL_SUMMARY_ROW_EXAMPLE],
                "page": 1,
                "page_size": 25,
                "total": 1,
                "total_pages": 1,
            }
        }
    }

    items: list[CallSummaryRow]
    page: int
    page_size: int
    total: int
    total_pages: int


class CallDetail(BaseModel):
    """Full call detail response for ``GET /api/v1/calls/{call_id}``."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "call_id": "CALL-20260728-0001",
                "customer": {
                    "customer_id": "CUST001",
                    "customer_name": "Rahul Sharma",
                    "masked_phone_number": "******3210",
                    "country_code": "+1",
                },
                "emi_details": {
                    "loan_account_number": "LAN123456",
                    "emi_amount": 1200.0,
                    "currency": "USD",
                    "emi_due_date": "2026-07-25",
                },
                "call_request": {},
                "gnani_console_response": {},
                "post_call_payload": {},
                "call_status": "completed",
                "call_duration_seconds": 96,
                "stage_code": "PTP_FUTURE",
                "stage_group": "ptp",
                "stage_code_source": "derived",
                "disposition_reason": "Customer promised payment by month end.",
                "disposition_summary": "Customer confirmed identity and promised payment by month end.",
                "ptp_date": "2026-07-30",
                "ptp_amount": 1200.0,
                "callback_datetime": None,
                "language_captured": "es-ES",
                "language_switched": False,
                "sentiment": "neutral",
                "confidence": 0.93,
                "customer_verified": True,
                "evidence_quote": "I will pay on the 30th",
                "recording_url": "/recordings/CALL-20260728-0001.wav",
                "engines": {"asr": "gnani-prisma", "tts": "gnani-timbre-2.5", "llm": "gnani-evon"},
                "conversation_transcript": [],
                "initial_message": "Hello, this is Aria calling from Apex Financial Services ...",
                "call_initiated_at": "2026-07-28T12:00:00+00:00",
                "call_started_at": "2026-07-28T12:00:05+00:00",
                "call_completed_at": "2026-07-28T12:01:41+00:00",
                "created_at": "2026-07-28T12:00:00+00:00",
                "updated_at": "2026-07-28T12:01:41+00:00",
                "audit_log": [
                    {
                        "at": "2026-07-28T12:00:00+00:00",
                        "actor": "system",
                        "action": "call_created",
                        "detail": "Call initiated via /api/Initial_Message.",
                    }
                ],
                "webhook_event_ids": ["evt-001"],
            }
        }
    }

    call_id: str
    customer: dict[str, Any] = Field(..., description="Customer info with masked_phone_number only.")
    emi_details: dict[str, Any]
    call_request: dict[str, Any]
    gnani_console_response: dict[str, Any]
    post_call_payload: dict[str, Any]
    call_status: CallStatus
    call_duration_seconds: int | None
    stage_code: StageCode | None
    stage_group: str | None
    stage_code_source: StageCodeSource | None
    disposition_reason: str | None
    disposition_summary: str | None
    ptp_date: date | None
    ptp_amount: float | None
    callback_datetime: datetime | None
    language_captured: Language | None
    language_switched: bool
    sentiment: DispositionCategory | None
    confidence: float | None
    customer_verified: bool | None
    evidence_quote: str | None
    recording_url: str | None
    engines: EngineInfo
    conversation_transcript: list[TranscriptTurn]
    initial_message: str
    call_initiated_at: datetime | None
    call_started_at: datetime | None
    call_completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    audit_log: list[AuditLogEntry]
    webhook_event_ids: list[str]


class StatsResponse(BaseModel):
    """Response body for ``GET /api/v1/stats``."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_calls": 12,
                "completed_calls": 10,
                "connected_calls": 9,
                "ptp_calls": 4,
                "already_paid_calls": 1,
                "rtp_calls": 1,
                "dispute_calls": 1,
                "non_connect_calls": 2,
                "callback_calls": 1,
                "connect_rate": 0.75,
                "ptp_rate": 0.4,
                "by_stage_code": {"PTP_FUTURE": 2},
                "by_language": {"en-US": 8, "es-ES": 3, "mixed": 1},
                "by_day": [{"date": "2026-07-28", "calls": 12}],
            }
        }
    }

    total_calls: int
    completed_calls: int
    connected_calls: int
    ptp_calls: int
    already_paid_calls: int
    rtp_calls: int
    dispute_calls: int
    non_connect_calls: int
    callback_calls: int
    connect_rate: float
    ptp_rate: float
    by_stage_code: dict[str, int]
    by_language: dict[str, int]
    by_day: list[dict[str, Any]]


class HealthResponse(BaseModel):
    """Response body for ``GET /health``."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "version": "1.0.0",
                "repository": "json",
                "gnani_mode": "mock",
            }
        }
    }

    status: str
    version: str
    repository: str
    gnani_mode: str


class ConfigResponse(BaseModel):
    """Response body for ``GET /api/v1/config``. Never exposes the actual key."""

    model_config = {"json_schema_extra": {"example": {"api_key_required": True}}}

    api_key_required: bool = True
