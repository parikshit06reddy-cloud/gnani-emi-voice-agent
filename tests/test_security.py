"""Unit tests for app/core/security.py authentication dependencies."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import require_webhook_key


@pytest.fixture
def webhook_app(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("WEBHOOK_API_KEY", "test-webhook-key")
    monkeypatch.setenv("WEBHOOK_ALLOW_QUERY_KEY", "false")
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setenv("GNANI_MODE", "mock")

    app = FastAPI()

    @app.get("/hook")
    async def hook_route(_: str = Depends(require_webhook_key)):
        return {"ok": True}

    yield app
    get_settings.cache_clear()


def test_webhook_query_key_disabled(webhook_app):
    client = TestClient(webhook_app)
    assert client.get("/hook?webhook_key=test-webhook-key").status_code == 401
    assert client.get("/hook", headers={"X-Webhook-Key": "test-webhook-key"}).status_code == 200


def test_webhook_query_key_enabled(webhook_app, monkeypatch):
    monkeypatch.setenv("WEBHOOK_ALLOW_QUERY_KEY", "true")
    get_settings.cache_clear()
    client = TestClient(webhook_app)
    assert client.get("/hook?webhook_key=test-webhook-key").status_code == 200
    assert client.get("/hook?key=test-webhook-key").status_code == 200
    get_settings.cache_clear()
