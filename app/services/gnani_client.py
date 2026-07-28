"""Client wrapper for the Gnani Agents Console call-trigger API.

Supports two modes controlled by ``settings.GNANI_MODE``:

- ``live``: issues real HTTP calls via ``httpx.AsyncClient`` with an explicit
  timeout and a ``tenacity`` retry policy (exponential backoff, retrying only
  on timeouts/connection errors/5xx — never on 4xx).
- ``mock``: simulates a realistic Gnani console response after a short
  sleep, with **deterministic failure injection** for demo/test purposes
  (see ``_maybe_inject_mock_failure`` below).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import Settings
from app.core.exceptions import GnaniTimeout, GnaniTriggerFailed

logger = logging.getLogger("gnani.client")


class _RetryableGnaniError(Exception):
    """Internal marker exception used to trigger a tenacity retry on 5xx."""

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"Gnani API returned {response.status_code}")
        self.response = response


@dataclass
class GnaniTriggerResult:
    """Normalised result of a call-trigger request, mock or live."""

    gnani_call_reference: str
    accepted: bool
    raw_response: dict[str, Any] = field(default_factory=dict)


class GnaniClient:
    """Thin async client for the Gnani Agents Console call-trigger API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.GNANI_BASE_URL,
            timeout=settings.GNANI_TIMEOUT_SECONDS,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    async def trigger_call(
        self,
        *,
        caller_id: str,
        phone_number: str,
        country_code: str,
        initial_message: str,
        bot_variables: dict[str, Any],
        webhook_url: str,
    ) -> GnaniTriggerResult:
        """Trigger an outbound call via the Gnani Agents Console.

        Args:
            caller_id: The originating caller id configured for the agent.
            phone_number: Destination phone number (unmasked, digits only).
            country_code: E.164 country calling code, e.g. ``+1``.
            initial_message: The dynamically built opening message.
            bot_variables: Variables injected into the bot prompt.
            webhook_url: URL Gnani should call back with the post-call payload.

        Returns:
            A :class:`GnaniTriggerResult` describing the accepted call.

        Raises:
            GnaniTimeout: if the request times out after all retries.
            GnaniTriggerFailed: if the request fails for any other reason
                (4xx, exhausted 5xx retries, connection errors exhausted).
        """
        if self._settings.GNANI_MODE == "mock":
            return await self._trigger_call_mock(phone_number=phone_number, bot_variables=bot_variables)
        return await self._trigger_call_live(
            caller_id=caller_id,
            phone_number=phone_number,
            country_code=country_code,
            initial_message=initial_message,
            bot_variables=bot_variables,
            webhook_url=webhook_url,
        )

    async def _trigger_call_live(
        self,
        *,
        caller_id: str,
        phone_number: str,
        country_code: str,
        initial_message: str,
        bot_variables: dict[str, Any],
        webhook_url: str,
    ) -> GnaniTriggerResult:
        settings = self._settings
        payload = {
            "agent_id": settings.GNANI_AGENT_ID,
            "caller_id": caller_id,
            "phone": f"{country_code}{phone_number}",
            "initial_message": initial_message,
            "bot_variables": bot_variables,
            "asr_model": settings.GNANI_ASR_MODEL,
            "tts_model": settings.GNANI_TTS_MODEL,
            "llm_model": settings.GNANI_LLM_MODEL,
            "webhook_url": webhook_url,
        }
        headers = {"Authorization": f"Bearer {settings.GNANI_API_KEY}"}

        retrying = retry(
            reraise=True,
            stop=stop_after_attempt(max(1, settings.GNANI_MAX_RETRIES)),
            wait=wait_exponential(multiplier=settings.GNANI_RETRY_BACKOFF_SECONDS, min=0, max=30),
            retry=retry_if_exception_type(
                (httpx.TimeoutException, httpx.ConnectError, _RetryableGnaniError)
            ),
        )

        @retrying
        async def _do_request() -> httpx.Response:
            response = await self._client.post(
                "/v1/calls/trigger", json=payload, headers=headers
            )
            if response.status_code >= 500:
                raise _RetryableGnaniError(response)
            return response

        try:
            response = await _do_request()
        except httpx.TimeoutException as exc:
            logger.warning("gnani_trigger_timeout", extra={"extra_fields": {"error": str(exc)}})
            raise GnaniTimeout("Gnani call-trigger API timed out after retries.") from exc
        except httpx.ConnectError as exc:
            logger.warning("gnani_trigger_connect_error", extra={"extra_fields": {"error": str(exc)}})
            raise GnaniTimeout("Could not connect to Gnani call-trigger API.") from exc
        except _RetryableGnaniError as exc:
            logger.error(
                "gnani_trigger_failed_5xx",
                extra={"extra_fields": {"status_code": exc.response.status_code}},
            )
            raise GnaniTriggerFailed(
                "Gnani call-trigger API failed after retries.",
                details={"status_code": exc.response.status_code},
            ) from exc

        if response.status_code >= 400:
            logger.error(
                "gnani_trigger_failed_4xx",
                extra={"extra_fields": {"status_code": response.status_code}},
            )
            raise GnaniTriggerFailed(
                "Gnani call-trigger API rejected the request.",
                details={"status_code": response.status_code, "body": _safe_json(response)},
            )

        body = _safe_json(response)
        return GnaniTriggerResult(
            gnani_call_reference=body.get("call_reference", f"gnani-{uuid.uuid4().hex[:12]}"),
            accepted=True,
            raw_response=body,
        )

    async def _trigger_call_mock(
        self, *, phone_number: str, bot_variables: dict[str, Any]
    ) -> GnaniTriggerResult:
        """Simulate the Gnani console call-trigger API for local/demo use.

        Deterministic failure injection (documented per CONTRACT/task
        requirements so the mandatory failure-mode scenarios are
        demonstrable without a live Gnani account):

        - phone numbers ending in ``0000`` simulate a request timeout,
          raising :class:`GnaniTimeout` (mirrors the retry-exhausted path).
        - phone numbers ending in ``9999`` simulate a persistent 5xx from
          the console, raising :class:`GnaniTriggerFailed`.

        Any other phone number returns a normal simulated "accepted"
        response after a small artificial delay.
        """
        await asyncio.sleep(0.05)

        if phone_number.endswith("0000"):
            logger.warning(
                "gnani_mock_injected_timeout",
                extra={"extra_fields": {"phone_suffix": phone_number[-4:]}},
            )
            raise GnaniTimeout(
                "Gnani call-trigger API timed out after retries (mock-injected via "
                "phone number ending in 0000)."
            )
        if phone_number.endswith("9999"):
            logger.warning(
                "gnani_mock_injected_5xx",
                extra={"extra_fields": {"phone_suffix": phone_number[-4:]}},
            )
            raise GnaniTriggerFailed(
                "Gnani call-trigger API failed after retries (mock-injected via "
                "phone number ending in 9999).",
                details={"status_code": 503},
            )

        settings = self._settings
        reference = f"gnani-{uuid.uuid4().hex[:12]}"
        raw_response = {
            "call_reference": reference,
            "status": "accepted",
            "agent_id": settings.GNANI_AGENT_ID,
            "engines": {
                "asr": settings.GNANI_ASR_MODEL,
                "tts": settings.GNANI_TTS_MODEL,
                "llm": settings.GNANI_LLM_MODEL,
            },
            "bot_variables_echo": bot_variables,
            "mode": "mock",
        }
        return GnaniTriggerResult(
            gnani_call_reference=reference, accepted=True, raw_response=raw_response
        )


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError:
        return {"raw_text": response.text}
