"""Orchestration layer tying together validation, the Gnani client, the
stage-code engine, and persistence for both the initial-message and
post-call-webhook flows.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.core.config import Settings
from app.core.exceptions import CallNotFound, ValidationAppError
from app.models.call import (
    AuditLogEntry,
    CallRecord,
    CustomerInfo,
    EmiDetails,
    EngineInfo,
    TranscriptTurn,
    utcnow,
)
from app.models.enums import PTP_STAGE_CODES, CallStatus, Language, StageCode
from app.models.requests import InitialMessageRequest, PostCallWebhookRequest
from app.models.responses import CallSummaryRow
from app.models.util import mask_phone, normalise_language
from app.repositories.base import CallFilters, CallRepository, Page
from app.services import initial_message as initial_message_service
from app.services.disposition import normalise_disposition
from app.services.gnani_client import GnaniClient
from app.services.stage_code import resolve_stage_code
from app.services.ws_manager import WebSocketManager

logger = logging.getLogger("gnani.call_service")


def _jsonable(value: Any) -> Any:
    """Recursively convert pydantic models/enums/datetimes into plain JSON-safe values."""
    return jsonable_encoder(value)


def to_summary_row(record: CallRecord) -> CallSummaryRow:
    """Project a full :class:`CallRecord` down to a :class:`CallSummaryRow`."""
    language = record.language_captured or record.preferred_language
    return CallSummaryRow(
        call_id=record.call_id,
        customer_id=record.customer.customer_id,
        customer_name=record.customer.customer_name,
        masked_phone_number=record.customer.masked_phone_number,
        loan_account_number=record.emi_details.loan_account_number,
        call_initiated_time=record.call_initiated_at,
        call_status=record.call_status,
        call_duration_seconds=record.call_duration_seconds,
        call_duration_display=record.duration_display(),
        stage_code=record.stage_code,
        stage_group=record.stage_group,
        disposition_reason=record.disposition_reason,
        ptp_date=record.ptp_date,
        language=language,
    )


class CallService:
    """Coordinates the initial-message and post-call-webhook use cases."""

    def __init__(
        self,
        *,
        repository: CallRepository,
        gnani_client: GnaniClient,
        settings: Settings,
        ws_manager: WebSocketManager,
    ) -> None:
        self._repo = repository
        self._gnani = gnani_client
        self._settings = settings
        self._ws = ws_manager

    async def _generate_call_id(self, day: date) -> str:
        seq = await self._repo.next_daily_sequence(day)
        return f"CALL-{day.strftime('%Y%m%d')}-{seq:04d}"

    async def create_call(self, request: InitialMessageRequest) -> CallRecord:
        """Handle the ``POST /api/Initial_Message`` use case end-to-end.

        1. Build the initial message + bot variables.
        2. Persist a ``queued`` record.
        3. Trigger the call via the Gnani client (mock or live).
        4. Update status to ``initiated`` (success) or ``failed`` (the
           caller is expected to let GnaniTimeout/GnaniTriggerFailed
           propagate as HTTP errors — this method does not swallow them,
           but it does still persist the failed state first).
        """
        settings = self._settings
        language = normalise_language(request.preferred_language)
        # Configurable allowed-language gate (see README "Spec inconsistency"):
        # the request validator has already mapped the alias to a concrete
        # Language; here we enforce which concrete languages this deployment
        # actually accepts. Rejecting loudly beats silently coercing to en-US.
        supported = settings.supported_languages_list
        if language.value not in supported:
            raise ValidationAppError(
                f"preferred_language '{language.value}' is recognised but not enabled "
                f"for this deployment. Supported languages: {', '.join(supported)}. "
                "Set SUPPORTED_LANGUAGES to change this.",
                details={"preferred_language": language.value, "supported_languages": supported},
            )

        today = datetime.now(UTC).date()
        call_id = await self._generate_call_id(today)

        initial_message = request.initial_message or initial_message_service.build_initial_message(
            customer_name=request.customer_name,
            loan_account_number=request.loan_account_number,
            emi_amount=request.emi_amount,
            currency=request.currency,
            emi_due_date=request.emi_due_date,
            language=language,
            settings=settings,
        )
        bot_variables = initial_message_service.build_bot_variables(
            customer_id=request.customer_id,
            customer_name=request.customer_name,
            loan_account_number=request.loan_account_number,
            emi_amount=request.emi_amount,
            currency=request.currency,
            emi_due_date=request.emi_due_date,
            language=language,
            settings=settings,
            initial_message=initial_message,
        )

        redacted_request = request.model_dump(mode="json")
        redacted_request["phone_number"] = mask_phone(request.phone_number)

        record = CallRecord(
            call_id=call_id,
            customer=CustomerInfo.from_raw(
                customer_id=request.customer_id,
                customer_name=request.customer_name,
                phone_number=request.phone_number,
                country_code=request.country_code,
            ),
            emi_details=EmiDetails(
                loan_account_number=request.loan_account_number,
                emi_amount=request.emi_amount,
                currency=request.currency,
                emi_due_date=request.emi_due_date,
            ),
            preferred_language=language,
            call_request=redacted_request,
            initial_message=initial_message,
            bot_variables=bot_variables,
            call_status=CallStatus.QUEUED,
            engines=EngineInfo(
                asr=settings.GNANI_ASR_MODEL,
                tts=settings.GNANI_TTS_MODEL,
                llm=settings.GNANI_LLM_MODEL,
            ),
            audit_log=[
                AuditLogEntry(actor="system", action="call_queued", detail="Initial request validated and queued.")
            ],
        )
        await self._repo.create(record)
        await self._ws.broadcast({"type": "call.created", "call_id": record.call_id, "row": to_summary_row(record).model_dump(mode="json")})

        webhook_url = f"{settings.PUBLIC_WEBHOOK_BASE_URL.rstrip('/')}/api/v1/webhooks/post-call"

        try:
            result = await self._gnani.trigger_call(
                caller_id=settings.GNANI_CALLER_ID,
                phone_number=request.phone_number,
                country_code=request.country_code,
                initial_message=initial_message,
                bot_variables=bot_variables,
                webhook_url=webhook_url,
            )
        except Exception:
            failed = record.model_copy(
                update={
                    "call_status": CallStatus.FAILED,
                    "updated_at": utcnow(),
                    "audit_log": record.audit_log
                    + [AuditLogEntry(actor="system", action="call_trigger_failed", detail="Gnani trigger raised an error.")],
                }
            )
            await self._repo.update_from_webhook(call_id, failed.model_dump(mode="json", exclude={"call_id"}))
            await self._ws.broadcast(
                {"type": "call.updated", "call_id": call_id, "row": to_summary_row(failed).model_dump(mode="json")}
            )
            raise

        updated = record.model_copy(
            update={
                "call_status": CallStatus.INITIATED,
                "gnani_call_reference": result.gnani_call_reference,
                "gnani_console_response": result.raw_response,
                "call_initiated_at": utcnow(),
                "updated_at": utcnow(),
                "audit_log": record.audit_log
                + [
                    AuditLogEntry(
                        actor="system",
                        action="call_initiated",
                        detail=f"Gnani accepted the call; reference={result.gnani_call_reference}.",
                    )
                ],
            }
        )
        await self._repo.update_from_webhook(call_id, updated.model_dump(mode="json", exclude={"call_id"}))
        await self._ws.broadcast(
            {"type": "call.updated", "call_id": call_id, "row": to_summary_row(updated).model_dump(mode="json")}
        )
        return updated

    async def process_webhook(
        self, payload: PostCallWebhookRequest
    ) -> tuple[CallRecord, bool]:
        """Handle the ``POST /api/v1/webhooks/post-call`` use case.

        Returns:
            A tuple ``(record, duplicate)``. When ``duplicate`` is True, the
            returned record is the pre-existing, unmodified record.

        Raises:
            CallNotFound: if ``payload.call_id`` does not exist.
        """
        idempotency_key = payload.idempotency_key()
        existing = await self._repo.get(payload.call_id)
        if existing is None:
            raise CallNotFound(f"No call found with call_id={payload.call_id!r}.")

        # Claim-before-process: an atomic claim (unique-index insert on Mongo,
        # lock-guarded list append on the JSON store) closes the
        # check-then-act race, so two concurrent deliveries of the same
        # event_id can never both apply their updates.
        claimed = await self._repo.try_claim_event_id(idempotency_key)
        if not claimed:
            logger.info(
                "webhook_duplicate_ignored",
                extra={"extra_fields": {"call_id": payload.call_id, "idempotency_key": idempotency_key}},
            )
            return existing, True

        try:
            return await self._apply_webhook(payload, existing, idempotency_key), False
        except Exception:
            # Processing failed after the claim succeeded — release it so a
            # redelivery is not swallowed as a duplicate of a webhook that
            # never actually took effect.
            await self._repo.release_event_id(idempotency_key)
            raise

    async def _apply_webhook(
        self,
        payload: PostCallWebhookRequest,
        existing: CallRecord,
        idempotency_key: str,
    ) -> CallRecord:
        normalised_disposition = normalise_disposition(payload.disposition)
        call_date = (payload.call_started_at or existing.call_initiated_at or utcnow()).date()

        resolution = resolve_stage_code(
            disposition=normalised_disposition,
            transcript=payload.transcript,
            call_status=payload.call_status,
            call_date=call_date,
            confidence_threshold=self._settings.STAGE_CODE_CONFIDENCE_THRESHOLD,
        )

        transcript_turns = [
            TranscriptTurn(
                turn=t.turn,
                speaker=t.speaker,
                text=t.text,
                language=normalise_language(t.language),
                timestamp=t.timestamp,
            )
            for t in payload.transcript
        ]
        language_captured, language_switched = _detect_language_mix(transcript_turns)

        try:
            new_status = CallStatus(payload.call_status)
        except ValueError:
            new_status = existing.call_status

        updates = {
            "call_status": new_status,
            "call_duration_seconds": payload.call_duration_seconds,
            "call_started_at": payload.call_started_at,
            "call_completed_at": payload.call_ended_at,
            "recording_url": payload.recording_url,
            "post_call_payload": payload.model_dump(mode="json"),
            "stage_code": resolution.stage_code,
            "stage_group": resolution.stage_group,
            "stage_code_source": resolution.stage_code_source,
            "disposition_reason": resolution.disposition_reason,
            "disposition_summary": normalised_disposition.disposition_summary,
            # A PTP date/amount is only meaningful when the FINAL resolved code
            # is a PTP_* code. If the engine downgraded the proposal (e.g. to
            # UNCLEAR for missing evidence), persisting the LLM's ptp_date
            # would surface a hallucinated promise on the dashboard.
            "ptp_date": (
                normalised_disposition.ptp_date
                if resolution.stage_code in PTP_STAGE_CODES
                else None
            ),
            "ptp_amount": (
                normalised_disposition.ptp_amount
                if resolution.stage_code in PTP_STAGE_CODES
                else None
            ),
            "callback_datetime": (
                normalised_disposition.callback_datetime
                if resolution.stage_code == StageCode.CALLBACK_SCHEDULED
                else None
            ),
            "language_captured": language_captured,
            "language_switched": language_switched,
            "sentiment": normalised_disposition.sentiment,
            "confidence": resolution.confidence,
            "customer_verified": normalised_disposition.customer_verified,
            "evidence_quote": normalised_disposition.evidence_quote,
            "conversation_transcript": transcript_turns,
            "engines": EngineInfo(
                asr=payload.asr_engine or existing.engines.asr,
                tts=payload.tts_engine or existing.engines.tts,
                llm=payload.llm_engine or existing.engines.llm,
            ),
            "gnani_call_reference": payload.gnani_call_reference or existing.gnani_call_reference,
            "webhook_event_ids": existing.webhook_event_ids + [idempotency_key],
            "updated_at": utcnow(),
            "audit_log": existing.audit_log
            + [
                AuditLogEntry(
                    actor="webhook",
                    action="post_call_processed",
                    detail=(
                        f"stage_code={resolution.stage_code.value} "
                        f"source={resolution.stage_code_source.value} "
                        f"rules={','.join(resolution.applied_rules)}"
                    ),
                )
            ],
        }

        safe_updates = _jsonable(updates)
        updated = await self._repo.update_from_webhook(payload.call_id, safe_updates)
        assert updated is not None  # existence already checked above
        await self._ws.broadcast(
            {"type": "call.updated", "call_id": updated.call_id, "row": to_summary_row(updated).model_dump(mode="json")}
        )
        return updated

    async def get_call(self, call_id: str) -> CallRecord:
        """Fetch a call by id or raise :class:`CallNotFound`."""
        record = await self._repo.get(call_id)
        if record is None:
            raise CallNotFound(f"No call found with call_id={call_id!r}.")
        return record

    async def list_calls(
        self,
        filters: CallFilters,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
    ) -> Page:
        """List calls matching ``filters`` with pagination."""
        return await self._repo.list(
            filters, page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir
        )

    async def get_stats(self, filters: CallFilters) -> dict:
        """Compute aggregate stats matching ``filters``."""
        return await self._repo.stats(filters)


def _detect_language_mix(turns: list[TranscriptTurn]) -> tuple[Language | None, bool]:
    """Determine ``language_captured`` and ``language_switched`` from a transcript.

    If customer turns span more than one concrete language (en-US/es-ES),
    the call is marked ``language_captured="mixed"`` and
    ``language_switched=True``.
    """
    customer_langs = {
        t.language
        for t in turns
        if t.speaker.value == "customer" and t.language in (Language.EN_US, Language.ES_ES, Language.HI_IN)
    }
    if len(customer_langs) > 1:
        return Language.MIXED, True
    if len(customer_langs) == 1:
        return next(iter(customer_langs)), False
    return None, False
