"""HackUMass Labs web app. One image for every instance; APP_ROLE never changes normal page output."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .routes import admin, api, exposed, internal, site
from .web import TEMPLATES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "static")), name="static")

TITLES = {
    401: ("Sign in required", "You need to sign in to view this page."),
    403: ("Access denied", "You don't have permission to access this resource."),
    404: ("Page not found", "The page you were looking for doesn't exist or has moved."),
    500: ("Something went wrong", "An unexpected error occurred. Our team has been notified."),
    502: ("Service unavailable", "A backend service didn't respond. Please try again shortly."),
    503: ("Down for maintenance", "We're performing scheduled maintenance. Please check back in a few minutes."),
}


def error_page(request: Request, status: int) -> HTMLResponse:
    title, text = TITLES.get(status, TITLES[500])
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": title.lower().replace(" ", "_")}, status_code=status)  # type: ignore[return-value]
    return TEMPLATES.TemplateResponse(request, "error.html", {"code": status, "title": title, "text": text,
                                                              "user": None, "admin": None, "ai_note": ""},
                                      status_code=status)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code in (301, 302, 303, 307) and exc.headers and "Location" in exc.headers:
        return RedirectResponse(exc.headers["Location"], status_code=exc.status_code)
    return error_page(request, exc.status_code)


@app.exception_handler(Exception)
async def crash(request: Request, exc: Exception):
    logging.getLogger("hlabs").exception("unhandled error on %s", request.url.path)
    return error_page(request, 500)


@app.middleware("http")
async def pacing(request: Request, call_next):
    """The front proxy can ask for the normal 403 page (blocked) or maintenance (paused)."""
    if not request.url.path.startswith(("/_edge", "/healthz")):
        if request.headers.get("x-edge-block") == "1":
            return error_page(request, 403)
        if request.headers.get("x-edge-pace") == "freeze":
            return error_page(request, 503)
    return await call_next(request)


for module in (internal, site, api, admin, exposed):
    app.include_router(module.router)


@app.on_event("startup")
def ready() -> None:
    logging.getLogger("hlabs").info("hlabs up: role=%s node=%s", settings.role, settings.node_name)
