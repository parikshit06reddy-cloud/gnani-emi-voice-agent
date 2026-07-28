"""FastAPI application factory for the Gnani EMI Collections Voice Agent backend."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import calls, health, stats, webhooks
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIdMiddleware, configure_logging
from app.models.responses import ConfigResponse
from app.repositories.factory import build_repository
from app.services.call_service import CallService
from app.services.gnani_client import GnaniClient
from app.services.ws_manager import ws_manager as global_ws_manager

logger = logging.getLogger("gnani.main")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Wire up settings, repository, Gnani client, and services at startup."""
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    repository = await build_repository(settings)
    gnani_client = GnaniClient(settings)
    call_service = CallService(
        repository=repository,
        gnani_client=gnani_client,
        settings=settings,
        ws_manager=global_ws_manager,
    )

    app.state.settings = settings
    app.state.repository = repository
    app.state.gnani_client = gnani_client
    app.state.call_service = call_service
    app.state.ws_manager = global_ws_manager

    logger.info(
        "startup_complete",
        extra={
            "extra_fields": {
                "repository": settings.repository_kind,
                "gnani_mode": settings.GNANI_MODE,
            }
        },
    )
    try:
        yield
    finally:
        await gnani_client.aclose()
        close = getattr(repository, "close", None)
        if callable(close):
            await close()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "Backend API for an outbound EMI-collections AI voice agent built on "
            "the Gnani Agents Console (Gnani Prisma ASR, Gnani Timbre 2.5 TTS, "
            "Gnani Evon LLM). Provides the initial-message call-trigger API, the "
            "post-call disposition webhook, call listing/detail, aggregate "
            "statistics, and a live WebSocket feed for the dashboard."
        ),
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(calls.router)
    app.include_router(webhooks.router)
    app.include_router(stats.router)
    app.include_router(health.router)

    @app.get(
        "/api/v1/config",
        response_model=ConfigResponse,
        tags=["health"],
        summary="Public frontend configuration",
        description="Tells the dashboard whether an API key is required. Never returns the actual key.",
    )
    async def get_public_config() -> ConfigResponse:
        return ConfigResponse(api_key_required=True)

    @app.websocket("/ws/calls")
    async def ws_calls(websocket: WebSocket) -> None:
        """Live feed of `call.created` / `call.updated` events for the dashboard."""
        manager = websocket.app.state.ws_manager
        await manager.connect(websocket)
        try:
            while True:
                # We don't expect inbound messages; just keep the connection open.
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    recordings_dir = Path(settings.RECORDINGS_DIR)
    try:
        recordings_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/recordings", StaticFiles(directory=str(recordings_dir)), name="recordings")
    except OSError as exc:
        logger.warning(
            "recordings_mount_skipped",
            extra={"extra_fields": {"recordings_dir": str(recordings_dir), "error": str(exc)}},
        )

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


app = create_app()
