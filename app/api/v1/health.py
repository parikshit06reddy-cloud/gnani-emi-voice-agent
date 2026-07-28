"""Liveness/health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.api.deps import get_settings_dep
from app.core.config import Settings
from app.models.responses import HealthResponse

router = APIRouter(tags=["health"])


def _wants_html(accept: str | None) -> bool:
    """Browsers send ``text/html``; curl and API clients typically do not."""
    if not accept:
        return False
    return "text/html" in accept.lower()


def _health_html(body: HealthResponse) -> str:
    mongo_ok = body.repository == "mongo"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Health — Gnani EMI Voice Agent</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0f1419; color: #e7ecf3; }}
    .ok {{ color: #3dd68c; }}
    .warn {{ color: #f5a623; }}
    dl {{ display: grid; grid-template-columns: auto 1fr; gap: 0.5rem 1.5rem; max-width: 28rem; }}
    dt {{ opacity: 0.75; }}
    dd {{ margin: 0; font-family: ui-monospace, monospace; }}
    p {{ opacity: 0.8; max-width: 36rem; }}
    a {{ color: #6cb6ff; }}
  </style>
</head>
<body>
  <h1 class="ok">Service healthy</h1>
  <dl>
    <dt>status</dt><dd>{body.status}</dd>
    <dt>version</dt><dd>{body.version}</dd>
    <dt>repository</dt><dd class="{"" if mongo_ok else "warn"}">{body.repository}</dd>
    <dt>gnani_mode</dt><dd>{body.gnani_mode}</dd>
  </dl>
  <p>{"MongoDB connected (Docker Compose stack)." if mongo_ok else "Using JSON file store — expected only for local virtualenv without MongoDB."}</p>
  <p><a href="/">Dashboard</a> · <a href="/docs">API docs</a> · <a href="/health" onclick="location.reload();return false;">JSON</a> (use curl)</p>
</body>
</html>"""


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Unauthenticated liveness probe reporting version, active repository backend, and Gnani mode.",
)
async def health(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
) -> HealthResponse | HTMLResponse:
    """Return basic service health/version/configuration information."""
    body = HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        repository=settings.repository_kind,
        gnani_mode=settings.GNANI_MODE,
    )
    if _wants_html(request.headers.get("accept")):
        return HTMLResponse(_health_html(body))
    return body
