from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes import demo, health
from app.core.config import Config, get_config
from app.core.errors import register_error_handlers
from app.core.security import build_token_verifier
from app.services.demo_service import DemoActions, prepare
from app.services.resource_service import ResourceProbes

API_PREFIX = "/api/v1"
# Any port on a local host, development only.
LOCAL_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"


def create_app(config: Config | None = None) -> FastAPI:
    """Application factory: ``config`` is injectable so tests control everything."""
    config = config or get_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # The demo table is created once here, not on each request (blocking: a thread).
        if not config.is_production:
            await run_in_threadpool(prepare, app.state.demo_actions)
        yield

    app = FastAPI(
        lifespan=lifespan,
        title="Up Mini-App Demo API",
        version="0.1.0",
        description="Demo API for an Up mini-app.",
        # Interactive docs are a development tool, not a production surface.
        docs_url=None if config.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if config.is_production else "/openapi.json",
    )
    app.state.token_verifier = build_token_verifier(config)
    app.state.resource_probes = ResourceProbes.from_config(config)
    app.state.demo_actions = DemoActions.from_config(config)

    _add_cors(app, config)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router, prefix=API_PREFIX)
    if not config.is_production:
        # An example to delete before shipping: never served in production.
        app.include_router(demo.router, prefix=API_PREFIX)
    return app


def _add_cors(app: FastAPI, config: Config) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors.allowed_origins,
        allow_origin_regex=LOCAL_ORIGIN_REGEX if config.is_development else None,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
