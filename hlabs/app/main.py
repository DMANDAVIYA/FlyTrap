"""App factory. Run with:  uvicorn --factory app.main:create_app

APP_ROLE=real|pod changes only seeding, the /_edge/* endpoints, the stray
file/island routes (pods) and whether the ops-migrate login exists (pods).
Normal pages render the same on both sides.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import islands
from app.config import Settings, load_settings
from app.db import Database
from app.middleware import EdgeContextMiddleware
from app.routes import account, admin, api, bait_files, beacon, edge, infra, public
from app.seed import seed_if_empty
from app.web import error_page

log = logging.getLogger("hlabs")
REAL_SEED = 7


def routers(settings: Settings) -> list[APIRouter]:
    common = [public.router, account.router, api.router, admin.router, beacon.router]
    if settings.is_pod:
        return [*common, edge.pod_router, infra.router, bait_files.router]
    return [*common, edge.real_router]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    db: Database = app.state.db
    if settings.is_pod:
        db.ensure_copy_of(Path(settings.template_db))
        db.create_tables()
        app.state.http = islands.make_client()
    else:
        seed_if_empty(db, "real", REAL_SEED)
        app.state.http = None
    log.info("hlabs ready (role=%s)", settings.role)
    yield
    if app.state.http is not None:
        await app.state.http.aclose()
    db.engine.dispose()


async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    return error_page(request, exc.status_code)


async def bad_input(request: Request, exc: RequestValidationError) -> Response:
    """Malformed query or form values get the normal error pages, never FastAPI's default JSON."""
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "invalid request"}, status_code=422)
    return error_page(request, 404)


async def server_error(request: Request, exc: Exception) -> Response:
    log.exception("unhandled error on %s", request.url.path)
    return error_page(request, 500)


async def admin_login_required(request: Request, exc: admin.AdminLoginRequired) -> Response:
    return RedirectResponse("/admin/", status_code=303)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.add_middleware(EdgeContextMiddleware, bait_secret=settings.bait_secret)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    for router in routers(settings):
        app.include_router(router)
    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(RequestValidationError, bad_input)
    app.add_exception_handler(admin.AdminLoginRequired, admin_login_required)
    app.add_exception_handler(Exception, server_error)
    return app
