"""Run Charon: the public proxy on :8080 and the admin API on the control address :8081."""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from fastapi import FastAPI, Request

from .admin import build_admin
from .config import settings
from .core import Gateway
from .public import handle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


def build_public(gw: Gateway) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.api_route("/{full_path:path}", methods=METHODS)
    async def catch_all(request: Request, full_path: str):
        return await handle(gw, request)

    return app


async def serve() -> None:
    gw = Gateway(settings)
    await gw.start()
    public = uvicorn.Server(uvicorn.Config(build_public(gw), host="0.0.0.0", port=settings.public_port,
                                           server_header=False, access_log=False, proxy_headers=False))
    admin = uvicorn.Server(uvicorn.Config(build_admin(gw), host=settings.admin_bind, port=settings.admin_port,
                                          server_header=False, access_log=False))
    await asyncio.gather(public.serve(), admin.serve())


if __name__ == "__main__":
    asyncio.run(serve())
