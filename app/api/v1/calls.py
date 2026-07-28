"""Endpoints: initial-message trigger, call listing, and call detail."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_call_service
from app.core.security import require_api_key
from app.models.enums import Language
from app.models.requests import InitialMessageRequest
from app.models.responses import CallDetail, CallListResponse, CallSummaryRow, ErrorResponse, InitialMessageResponse
from app.repositories.base import CallFilters
from app.services.call_service import CallService, to_summary_row

router = APIRouter(tags=["calls"])


@router.post(
    "/api/Initial_Message",
    response_model=InitialMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate an outbound EMI-collections call",
    description=(
        "Validates the customer/loan payload, builds the dynamic bilingual "
        "initial message and bot variables, persists a `queued` call "
        "record, then triggers the call via the Gnani Agents Console "
        "call-trigger API (mock or live per `GNANI_MODE`). Retries on "
        "timeout/5xx up to `GNANI_MAX_RETRIES` times with exponential "
        "backoff before failing."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing/invalid X-API-Key."},
        422: {"model": ErrorResponse, "description": "Request validation failed."},
        502: {"model": ErrorResponse, "description": "Gnani call-trigger API rejected the request (GNANI_TRIGGER_FAILED)."},
        504: {"model": ErrorResponse, "description": "Gnani call-trigger API timed out after retries (GNANI_TIMEOUT)."},
    },
    dependencies=[Depends(require_api_key)],
)
async def initiate_call(
    body: InitialMessageRequest,
    call_service: CallService = Depends(get_call_service),
) -> InitialMessageResponse:
    """Trigger a new outbound EMI-collections call for a customer."""
    record = await call_service.create_call(body)
    return InitialMessageResponse(
        call_id=record.call_id,
        gnani_call_reference=record.gnani_call_reference,
        customer_id=record.customer.customer_id,
        customer_name=record.customer.customer_name,
        phone_number=record.customer.masked_phone_number,
        country_code=record.customer.country_code,
        loan_account_number=record.emi_details.loan_account_number,
        emi_amount=record.emi_details.emi_amount,
        emi_due_date=record.emi_details.emi_due_date,
        preferred_language=record.preferred_language,
        initial_message=record.initial_message,
        call_status=record.call_status,
        created_at=record.created_at,
    )


@router.get(
    "/api/v1/calls",
    response_model=CallListResponse,
    summary="List calls with filters, search, and pagination",
    description="Returns a paginated, filterable, sortable list of call summary rows.",
    responses={401: {"model": ErrorResponse, "description": "Missing/invalid X-API-Key."}},
    dependencies=[Depends(require_api_key)],
)
async def list_calls(
    call_service: CallService = Depends(get_call_service),
    call_date: date | None = Query(default=None, description="Filter by call_initiated_at date (YYYY-MM-DD)."),
    date_from: date | None = Query(default=None, description="Filter: created_at >= date_from."),
    date_to: date | None = Query(default=None, description="Filter: created_at <= date_to."),
    call_status: str | None = Query(default=None, description="Filter by exact call_status."),
    stage_code: list[str] | None = Query(default=None, description="Filter by one or more stage codes (repeatable)."),
    stage_group: str | None = Query(default=None, description="Filter by stage code group."),
    customer_id: str | None = Query(default=None, description="Filter by customer_id."),
    loan_account_number: str | None = Query(default=None, description="Filter by loan_account_number."),
    language: str | None = Query(default=None, description="Filter by captured/preferred language."),
    ptp_date: date | None = Query(default=None, description="Filter by exact ptp_date."),
    q: str | None = Query(default=None, description="Full-text search over transcript/summary/reason."),
    page: int = Query(default=1, ge=1, description="1-based page number."),
    page_size: int = Query(default=25, ge=1, le=200, description="Items per page (max 200)."),
    sort_by: str = Query(default="created_at", description="Field to sort by."),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort direction."),
) -> CallListResponse:
    """List call summary rows matching the supplied filters."""
    filters = CallFilters(
        call_date=call_date,
        date_from=date_from,
        date_to=date_to,
        call_status=call_status,
        stage_code=stage_code or [],
        stage_group=stage_group,
        customer_id=customer_id,
        loan_account_number=loan_account_number,
        language=language,
        ptp_date=ptp_date,
        q=q,
    )
    result = await call_service.list_calls(
        filters, page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir
    )
    rows = [to_summary_row(record) for record in result.items]
    return CallListResponse(
        items=rows, page=result.page, page_size=result.page_size, total=result.total, total_pages=result.total_pages
    )


@router.get(
    "/api/v1/calls/{call_id}",
    response_model=CallDetail,
    summary="Get full call detail",
    description="Returns the complete call record, including transcript, audit log, and raw payloads.",
    responses={
        401: {"model": ErrorResponse, "description": "Missing/invalid X-API-Key."},
        404: {"model": ErrorResponse, "description": "No call found with this call_id (CALL_NOT_FOUND)."},
    },
    dependencies=[Depends(require_api_key)],
)
async def get_call_detail(
    call_id: str,
    call_service: CallService = Depends(get_call_service),
) -> CallDetail:
    """Fetch the full detail record for a single call."""
    record = await call_service.get_call(call_id)
    customer = record.customer.model_dump(mode="json")
    return CallDetail(
        call_id=record.call_id,
        customer=customer,
        emi_details=record.emi_details.model_dump(mode="json"),
        call_request=record.call_request,
        gnani_console_response=record.gnani_console_response,
        post_call_payload=record.post_call_payload,
        call_status=record.call_status,
        call_duration_seconds=record.call_duration_seconds,
        stage_code=record.stage_code,
        stage_group=record.stage_group,
        stage_code_source=record.stage_code_source,
        disposition_reason=record.disposition_reason,
        disposition_summary=record.disposition_summary,
        ptp_date=record.ptp_date,
        ptp_amount=record.ptp_amount,
        callback_datetime=record.callback_datetime,
        language_captured=record.language_captured,
        language_switched=record.language_switched,
        sentiment=record.sentiment,
        confidence=record.confidence,
        customer_verified=record.customer_verified,
        evidence_quote=record.evidence_quote,
        recording_url=record.recording_url,
        engines=record.engines,
        conversation_transcript=record.conversation_transcript,
        initial_message=record.initial_message,
        call_initiated_at=record.call_initiated_at,
        call_started_at=record.call_started_at,
        call_completed_at=record.call_completed_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
        audit_log=record.audit_log,
        webhook_event_ids=record.webhook_event_ids,
    )
