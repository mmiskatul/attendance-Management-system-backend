"""Application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.frontend import router as frontend_router
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.container import build_container
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.db.client import DatabaseManager
from app.db.migrations import run_migrations
from app.middleware.metrics import MetricsMiddleware, metrics_response
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


def create_app(*, settings: Settings | None = None, startup_enabled: bool = True) -> FastAPI:
    """Application factory."""

    runtime_settings = settings or get_settings()
    setup_logging("DEBUG" if runtime_settings.debug else "INFO")
    frontend_assets_dir = Path(__file__).resolve().parent.parent / "frontend" / "assets"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db_manager = DatabaseManager(runtime_settings)
        database = await db_manager.connect()
        await run_migrations(database)
        container = await build_container(database, runtime_settings)
        await container.auth_service.ensure_bootstrap_admin()

        app.state.settings = runtime_settings
        app.state.db_manager = db_manager
        app.state.container = container
        try:
            yield
        finally:
            await container.close()
            await db_manager.disconnect()

    app = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        docs_url=runtime_settings.docs_url,
        redoc_url=runtime_settings.redoc_url,
        openapi_url=runtime_settings.openapi_url,
        lifespan=lifespan if startup_enabled else None,
    )
    app.state.settings = runtime_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware, request_id_header=runtime_settings.request_id_header)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MetricsMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=runtime_settings.api_v1_prefix)
    app.include_router(frontend_router)
    app.mount("/static", StaticFiles(directory=frontend_assets_dir), name="static")
    app.add_api_route("/metrics", metrics_response, methods=["GET"], include_in_schema=False)
    return app


app = create_app()
