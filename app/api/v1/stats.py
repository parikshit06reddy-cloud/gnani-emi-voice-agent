"""Aggregate call statistics endpoint."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_call_service
from app.core.security import require_api_key
from app.models.responses import ErrorResponse, StatsResponse
from app.repositories.base import CallFilters
from app.services.call_service import CallService

router = APIRouter(tags=["stats"])


@router.get(
    "/api/v1/stats",
    response_model=StatsResponse,
    summary="Get aggregate call statistics",
    description="Computes call/PTP/dispute/etc. counts and rates, using the same filter params as /api/v1/calls.",
    responses={401: {"model": ErrorResponse, "description": "Missing/invalid X-API-Key."}},
    dependencies=[Depends(require_api_key)],
)
async def get_stats(
    call_service: CallService = Depends(get_call_service),
    call_date: date | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    call_status: str | None = Query(default=None),
    stage_code: list[str] | None = Query(default=None),
    stage_group: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    loan_account_number: str | None = Query(default=None),
    language: str | None = Query(default=None),
    ptp_date: date | None = Query(default=None),
    q: str | None = Query(default=None),
) -> StatsResponse:
    """Compute aggregate statistics over calls matching the supplied filters."""
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
    stats = await call_service.get_stats(filters)
    return StatsResponse(**stats)
