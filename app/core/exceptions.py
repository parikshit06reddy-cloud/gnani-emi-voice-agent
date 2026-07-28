"""Domain exception hierarchy and FastAPI exception handlers.

All handled errors are rendered using the exact error envelope mandated by
``CONTRACT.md``::

    {"success": false, "error": {"code": ..., "message": ..., "details": {}},
     "request_id": "..."}
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_request_id


class AppError(Exception):
    """Base class for all handled application errors.

    Attributes:
        code: Machine-readable error code returned in the error envelope.
        message: Human-readable message.
        status_code: HTTP status code to respond with.
        details: Optional extra structured context about the error.
    """

    code: str = "APP_ERROR"
    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class ValidationAppError(AppError):
    """Raised for domain-level validation failures outside pydantic."""

    code = "VALIDATION_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class CallNotFound(AppError):
    """Raised when a requested call_id does not exist."""

    code = "CALL_NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND


class GnaniTimeout(AppError):
    """Raised when the Gnani call-trigger API times out after all retries."""

    code = "GNANI_TIMEOUT"
    status_code = status.HTTP_504_GATEWAY_TIMEOUT


class GnaniTriggerFailed(AppError):
    """Raised when the Gnani call-trigger API fails (non-timeout)."""

    code = "GNANI_TRIGGER_FAILED"
    status_code = status.HTTP_502_BAD_GATEWAY


class DuplicateWebhook(AppError):
    """Raised internally to signal an already-processed webhook event.

    Note: the webhook route treats this as a *successful* no-op (HTTP 200
    with ``duplicate: true``) rather than an error response — it is modelled
    as an exception purely so the service layer can short-circuit cleanly.
    """

    code = "DUPLICATE_WEBHOOK"
    status_code = status.HTTP_200_OK


class Unauthorized(AppError):
    """Raised when API key / webhook key authentication fails."""

    code = "UNAUTHORIZED"
    status_code = status.HTTP_401_UNAUTHORIZED


def _error_envelope(code: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
        "request_id": get_request_id(),
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI application."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors = [
            {
                "field": ".".join(str(loc) for loc in err["loc"] if loc != "body"),
                "message": err["msg"],
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_envelope(
                "VALIDATION_ERROR",
                "Request validation failed.",
                {"field_errors": jsonable_encoder(field_errors)},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(code, detail, {}),
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_envelope(
                "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", {}
            ),
        )
