"""Application-specific exceptions and handlers."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


@dataclass
class AppError(Exception):
    """Base application error."""

    detail: str
    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "application_error"


class AuthenticationAppError(AppError):
    def __init__(self, detail: str = "Authentication failed.") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED, error_code="auth_failed")


class AuthorizationAppError(AppError):
    def __init__(self, detail: str = "You are not allowed to perform this action.") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN, error_code="forbidden")


class NotFoundAppError(AppError):
    def __init__(self, detail: str = "Resource not found.") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND, error_code="not_found")


class ConflictAppError(AppError):
    def __init__(self, detail: str = "Resource already exists.") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT, error_code="conflict")


class ValidationAppError(AppError):
    def __init__(self, detail: str = "Request validation failed.") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, error_code="validation_error")


class RateLimitAppError(AppError):
    def __init__(self, detail: str = "Rate limit exceeded.") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_429_TOO_MANY_REQUESTS, error_code="rate_limited")


def register_exception_handlers(app: FastAPI) -> None:
    """Attach exception handlers to the FastAPI application."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.error_code, "message": exc.detail}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "request_validation_error",
                    "message": "Request validation failed.",
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": exc.detail}},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        _ = exc
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected internal error occurred.",
                }
            },
        )
