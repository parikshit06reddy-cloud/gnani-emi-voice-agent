"""Shared pytest fixtures: isolated settings, JSON repo in tmp_path, ASGI app/client."""

from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.main import create_app
from app.repositories.json_repo import JsonCallRepository
from app.services.call_service import CallService
from app.services.gnani_client import GnaniClient
from app.services.ws_manager import WebSocketManager


@pytest.fixture
def test_settings(tmp_path, monkeypatch):
    """Build an isolated Settings instance pointing at a tmp_path JSON store."""
    get_settings.cache_clear()
    json_path = tmp_path / "calls.json"
    monkeypatch.setenv("JSON_STORE_PATH", str(json_path))
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setenv("GNANI_MODE", "mock")
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("WEBHOOK_API_KEY", "test-webhook-key")
    monkeypatch.setenv("GNANI_RETRY_BACKOFF_SECONDS", "0.01")
    settings = get_settings()
    yield settings
    get_settings.cache_clear()


@pytest.fixture
async def app(test_settings):
    """Build a fully wired FastAPI app instance for testing."""
    application = create_app()
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app):
    """An httpx.AsyncClient bound to the app via ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def api_headers():
    return {"X-API-Key": "test-api-key"}


@pytest.fixture
def webhook_headers():
    return {"X-Webhook-Key": "test-webhook-key"}


@pytest.fixture
async def call_service(tmp_path, test_settings):
    """A standalone CallService wired to a fresh JSON repo, for unit-level tests."""
    repo = JsonCallRepository(str(tmp_path / "unit_calls.json"))
    gnani_client = GnaniClient(test_settings)
    ws = WebSocketManager()
    service = CallService(repository=repo, gnani_client=gnani_client, settings=test_settings, ws_manager=ws)
    yield service
    await gnani_client.aclose()
