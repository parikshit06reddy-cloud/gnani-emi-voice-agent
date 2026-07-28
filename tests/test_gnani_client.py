"""Tests for the Gnani client: mock-mode failure injection and live-mode retry/timeout."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import GnaniTimeout, GnaniTriggerFailed
from app.services.gnani_client import GnaniClient


def _settings(**overrides) -> Settings:
    defaults = dict(
        GNANI_MODE="mock",
        GNANI_MAX_RETRIES=3,
        GNANI_RETRY_BACKOFF_SECONDS=0.001,
        GNANI_TIMEOUT_SECONDS=1.0,
    )
    defaults.update(overrides)
    return Settings(**defaults)


# --- Mock mode -------------------------------------------------------------


async def test_mock_mode_returns_accepted_response():
    client = GnaniClient(_settings())
    try:
        result = await client.trigger_call(
            caller_id="+10000000000",
            phone_number="9876543210",
            country_code="+1",
            initial_message="Hello",
            bot_variables={"a": 1},
            webhook_url="http://localhost/webhook",
        )
    finally:
        await client.aclose()
    assert result.accepted is True
    assert result.gnani_call_reference.startswith("gnani-")
    assert result.raw_response["engines"]["asr"] == "gnani-prisma"


async def test_mock_mode_injects_timeout_on_0000_suffix():
    client = GnaniClient(_settings())
    try:
        with pytest.raises(GnaniTimeout):
            await client.trigger_call(
                caller_id="+10000000000",
                phone_number="5550000000",
                country_code="+1",
                initial_message="Hello",
                bot_variables={},
                webhook_url="http://localhost/webhook",
            )
    finally:
        await client.aclose()


async def test_mock_mode_injects_5xx_failure_on_9999_suffix():
    client = GnaniClient(_settings())
    try:
        with pytest.raises(GnaniTriggerFailed):
            await client.trigger_call(
                caller_id="+10000000000",
                phone_number="5559999999",
                country_code="+1",
                initial_message="Hello",
                bot_variables={},
                webhook_url="http://localhost/webhook",
            )
    finally:
        await client.aclose()


# --- Live mode: retry/timeout behaviour with a mocked transport -----------


class _CountingTransport(httpx.AsyncBaseTransport):
    """A fake transport that returns a scripted sequence of responses/errors."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.call_count = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.call_count += 1
        action = self._script.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


async def test_live_mode_retries_on_5xx_then_succeeds():
    settings = _settings(GNANI_MODE="live", GNANI_API_KEY="k", GNANI_MAX_RETRIES=3)
    client = GnaniClient(settings)
    transport = _CountingTransport(
        [
            httpx.Response(503, json={"error": "unavailable"}),
            httpx.Response(200, json={"call_reference": "gnani-abc123"}),
        ]
    )
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.GNANI_BASE_URL)
    try:
        result = await client.trigger_call(
            caller_id="+1",
            phone_number="5551234567",
            country_code="+1",
            initial_message="hi",
            bot_variables={},
            webhook_url="http://localhost/webhook",
        )
    finally:
        await client.aclose()
    assert result.gnani_call_reference == "gnani-abc123"
    assert transport.call_count == 2


async def test_live_mode_exhausts_retries_and_raises_trigger_failed():
    settings = _settings(GNANI_MODE="live", GNANI_API_KEY="k", GNANI_MAX_RETRIES=2)
    client = GnaniClient(settings)
    transport = _CountingTransport(
        [
            httpx.Response(500, json={"error": "boom"}),
            httpx.Response(500, json={"error": "boom"}),
        ]
    )
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.GNANI_BASE_URL)
    try:
        with pytest.raises(GnaniTriggerFailed):
            await client.trigger_call(
                caller_id="+1",
                phone_number="5551234567",
                country_code="+1",
                initial_message="hi",
                bot_variables={},
                webhook_url="http://localhost/webhook",
            )
    finally:
        await client.aclose()
    assert transport.call_count == 2


async def test_live_mode_never_retries_on_4xx():
    settings = _settings(GNANI_MODE="live", GNANI_API_KEY="k", GNANI_MAX_RETRIES=3)
    client = GnaniClient(settings)
    transport = _CountingTransport([httpx.Response(400, json={"error": "bad request"})])
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.GNANI_BASE_URL)
    try:
        with pytest.raises(GnaniTriggerFailed):
            await client.trigger_call(
                caller_id="+1",
                phone_number="5551234567",
                country_code="+1",
                initial_message="hi",
                bot_variables={},
                webhook_url="http://localhost/webhook",
            )
    finally:
        await client.aclose()
    assert transport.call_count == 1  # no retries on 4xx


async def test_live_mode_raises_timeout_on_exhausted_timeouts():
    settings = _settings(GNANI_MODE="live", GNANI_API_KEY="k", GNANI_MAX_RETRIES=2)
    client = GnaniClient(settings)
    transport = _CountingTransport(
        [httpx.TimeoutException("timed out"), httpx.TimeoutException("timed out")]
    )
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.GNANI_BASE_URL)
    try:
        with pytest.raises(GnaniTimeout):
            await client.trigger_call(
                caller_id="+1",
                phone_number="5551234567",
                country_code="+1",
                initial_message="hi",
                bot_variables={},
                webhook_url="http://localhost/webhook",
            )
    finally:
        await client.aclose()
    assert transport.call_count == 2
