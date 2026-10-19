"""FastAPI application factory and ASGI entrypoint.

Run locally with:  uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.db.migrate import run_migrations
from app.db.session import dispose_engines
from app.services.errors import UpstreamError


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    run_migrations()  # bring the SQLite/Postgres schema up to date before serving
    yield
    dispose_engines()


async def _upstream_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, UpstreamError)
    return JSONResponse(
        status_code=502,
        content={"detail": f"Upstream provider '{exc.provider}' failed: {exc.detail}"},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(UpstreamError, _upstream_error_handler)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
