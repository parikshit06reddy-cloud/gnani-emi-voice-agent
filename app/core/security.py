"""API key authentication dependencies.

Two separate secrets are used, per CONTRACT:

- ``X-API-Key`` guards the business endpoints (initial message, calls, stats).
- ``X-Webhook-Key`` guards the Gnani post-call webhook.

Both use a constant-time comparison (``hmac.compare_digest``) to avoid
timing side-channels, and raise :class:`~app.core.exceptions.Unauthorized`
so the response matches the CONTRACT error envelope exactly.
"""

from __future__ import annotations

import hmac

from fastapi import Query, Security
from fastapi.security import APIKeyHeader

from app.core.config import get_settings
from app.core.exceptions import Unauthorized

_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
_webhook_key_scheme = APIKeyHeader(name="X-Webhook-Key", auto_error=False)


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


async def require_api_key(api_key: str | None = Security(_api_key_scheme)) -> str:
    """FastAPI dependency enforcing a valid ``X-API-Key`` header.

    Raises:
        Unauthorized: if the header is missing or does not match the
            configured ``API_KEY``.
    """
    settings = get_settings()
    if not api_key or not _constant_time_eq(api_key, settings.API_KEY):
        raise Unauthorized("Missing or invalid X-API-Key header.")
    return api_key


async def require_webhook_key(
    webhook_key: str | None = Security(_webhook_key_scheme),
    webhook_key_query: str | None = Query(
        default=None,
        alias="webhook_key",
        description="Webhook secret (only when WEBHOOK_ALLOW_QUERY_KEY=true).",
    ),
    key_query: str | None = Query(
        default=None,
        alias="key",
        description="Alternate webhook secret query param (WEBHOOK_ALLOW_QUERY_KEY only).",
    ),
) -> str:
    """FastAPI dependency enforcing a valid ``X-Webhook-Key`` header.

    When ``WEBHOOK_ALLOW_QUERY_KEY=true``, also accepts ``?webhook_key=`` or
    ``?key=`` on the post-call webhook URL — a fallback for Gnani Console
    tenants whose Post-Call Trigger form cannot attach custom headers.

    Raises:
        Unauthorized: if the header is missing or does not match the
            configured ``WEBHOOK_API_KEY``.
    """
    settings = get_settings()
    candidate = webhook_key
    if not candidate and settings.WEBHOOK_ALLOW_QUERY_KEY:
        candidate = webhook_key_query or key_query
    if not candidate or not _constant_time_eq(candidate, settings.WEBHOOK_API_KEY):
        raise Unauthorized("Missing or invalid X-Webhook-Key header.")
    return candidate
