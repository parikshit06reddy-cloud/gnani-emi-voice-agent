"""Liveness/health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_settings_dep
from app.core.config import Settings
from app.models.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Unauthenticated liveness probe reporting version, active repository backend, and Gnani mode.",
)
async def health(settings: Settings = Depends(get_settings_dep)) -> HealthResponse:
    """Return basic service health/version/configuration information."""
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        repository=settings.repository_kind,
        gnani_mode=settings.GNANI_MODE,
    )
