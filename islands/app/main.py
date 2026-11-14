"""Islands: backup-01 and model-vault, one image, picked by ISLAND=backup|vault.

They sit on trapnet and are only reached through a web node's
/admin/infra/<host>/ and /internal-backup/ proxies (spec 5.5).
Run with:  uvicorn --factory app.main:create_app
"""

import os

from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import backup, vault
from app.common import not_found_page

ISLANDS = {"backup": (backup.router, backup.HOST), "vault": (vault.router, vault.HOST)}


def create_app() -> FastAPI:
    island = os.environ.get("ISLAND", "backup")
    if island not in ISLANDS:
        raise ValueError(f"ISLAND must be backup or vault, got {island!r}")
    router, host = ISLANDS[island]
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)
    app.state.bait_secret = os.environ["BAIT_SECRET"]
    app.include_router(router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        return not_found_page(host, 405 if exc.status_code == 405 else 404)

    return app
