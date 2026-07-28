"""Post-call webhook endpoint receiving Gnani Agents Console call outcomes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_call_service
from app.core.security import require_webhook_key
from app.models.requests import PostCallWebhookRequest
from app.models.responses import ErrorResponse, WebhookAckResponse
from app.services.call_service import CallService

router = APIRouter(tags=["webhooks"])


@router.post(
    "/api/v1/webhooks/post-call",
    response_model=WebhookAckResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive the Gnani post-call disposition webhook",
    description=(
        "Ingests the post-call payload from the Gnani Agents Console: "
        "updates call status, resolves the final stage code via the "
        "deterministic stage-code engine, stores the transcript/summary, "
        "and captures PTP/callback details. Idempotent on `event_id` "
        "(fallback: `call_id` + `call_ended_at`) — replays return "
        "`duplicate: true` with no state change."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing/invalid X-Webhook-Key."},
        404: {"model": ErrorResponse, "description": "No call found with this call_id (CALL_NOT_FOUND)."},
        422: {"model": ErrorResponse, "description": "Request validation failed."},
    },
    dependencies=[Depends(require_webhook_key)],
)
async def post_call_webhook(
    body: PostCallWebhookRequest,
    call_service: CallService = Depends(get_call_service),
) -> WebhookAckResponse:
    """Process a post-call webhook delivery from the Gnani Agents Console."""
    record, duplicate = await call_service.process_webhook(body)
    return WebhookAckResponse(
        success=True,
        duplicate=duplicate,
        call_id=record.call_id,
        stage_code=record.stage_code,
        ptp_date=record.ptp_date,
    )
