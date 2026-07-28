"""FastAPI dependency providers wiring request-scoped services from app.state."""

from __future__ import annotations

from fastapi import Request

from app.core.config import Settings
from app.repositories.base import CallRepository
from app.services.call_service import CallService
from app.services.ws_manager import WebSocketManager


def get_settings_dep(request: Request) -> Settings:
    """Return the application's :class:`Settings` singleton."""
    return request.app.state.settings


def get_repository(request: Request) -> CallRepository:
    """Return the active :class:`CallRepository` implementation."""
    return request.app.state.repository


def get_call_service(request: Request) -> CallService:
    """Return the shared :class:`CallService` orchestrator."""
    return request.app.state.call_service


def get_ws_manager(request: Request) -> WebSocketManager:
    """Return the shared :class:`WebSocketManager`."""
    return request.app.state.ws_manager
