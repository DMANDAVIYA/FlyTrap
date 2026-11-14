"""backup-01: an Apache directory listing of nightly backups (spec 5.5).

customers_2026-11-01.csv is listed here but served by the web node itself, from
its own database, so the rows match its admin panel exactly.
"""

import gzip
import hashlib
import random

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response

from app.common import index_page, not_found_page, visitor

HOST = "backup-01"
SNAPSHOT = "db_snapshot_2026-11-13.sql.gz"
ENV_NAMES = {"api_token": "HL_API_TOKEN", "cloud_key_id": "HL_OBJECT_STORE_KEY_ID",
             "cloud_secret": "HL_OBJECT_STORE_SECRET"}
STAFF = ((2, "Maya Okafor"), (3, "Jonah Reyes"), (4, "Priya Raman"))
LOG_PATHS = ("/", "/pricing", "/models", "/docs", "/login", "/account", "/api/v1/models", "/static/site.css",
             "/static/px.js", "/healthz", "/about", "/contact")
AGENTS = ("hlabs-python/1.8.2", "curl/8.5.0", "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.6 Safari/605.1.15", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36", "Go-http-client/1.1")

router = APIRouter()


def snapshot_sql() -> str:
    staff = "\n".join(
        f"{uid}\t{name.lower().replace(' ', '.')}@hackumass-labs.example\t{name}\tHackUMass Labs\tadmin\t"
        f"pbkdf2_sha256$200000${hashlib.sha256(name.encode()).hexdigest()[:32]}$"
        f"{hashlib.sha256(name[::-1].encode()).hexdigest()}\t2025-05-0{uid} 09:00:00\t2026-11-12 18:2{uid}:00\t0"
        for uid, name in STAFF
    )
    return (
        "--\n-- PostgreSQL database dump\n--\n\n-- Dumped from database version 16.4\n"
        "-- Dumped by pg_dump version 16.4\n-- Started on 2026-11-13 03:00:01 UTC\n\n"
        "SET statement_timeout = 0;\nSET client_encoding = 'UTF8';\nSET standard_conforming_strings = on;\n\n"
        "CREATE TABLE public.users (\n    id integer NOT NULL,\n    email character varying(200) NOT NULL,\n"
        "    name character varying(120) NOT NULL,\n    org character varying(120) NOT NULL,\n"
        "    role character varying(20) NOT NULL,\n    password_hash character varying(200) NOT NULL,\n"
        "    created_at timestamp without time zone NOT NULL,\n    last_login timestamp without time zone,\n"
        "    session_version integer DEFAULT 0 NOT NULL\n);\n\n"
        "CREATE TABLE public.api_tokens (\n    id integer NOT NULL,\n    user_id integer NOT NULL,\n"
        "    token character varying(64) NOT NULL,\n    label character varying(80) NOT NULL,\n"
        "    scopes character varying(120) NOT NULL,\n    created_at timestamp without time zone NOT NULL\n);\n\n"
        "CREATE TABLE public.plans (\n    id integer NOT NULL,\n    name text NOT NULL,\n"
        "    price_cents integer NOT NULL,\n    included_tokens bigint NOT NULL\n);\n\n"
        "COPY public.plans (id, name, price_cents, included_tokens) FROM stdin;\n"
        "1\tStarter\t4900\t5000000\n2\tGrowth\t14900\t50000000\n3\tScale\t49900\t250000000\n\\.\n\n"
        "COPY public.users (id, email, name, org, role, password_hash, created_at, last_login, session_version)"
        f" FROM stdin;\n{staff}\n\\.\n\n"
        "-- Customer rows excluded from nightly snapshots (OPS-1874). Monthly export: customers_2026-11-01.csv\n\n"
        "--\n-- PostgreSQL database dump complete\n--\n"
    )


SNAPSHOT_BYTES = gzip.compress(snapshot_sql().encode(), mtime=0)


def access_log(name: str, day: int, lines: int = 240) -> str:
    rng = random.Random(name)
    out = []
    for index in range(lines):
        seconds = index * 86_000 // lines + rng.randint(0, 300)
        stamp = f"{day:02d}/Nov/2026:{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d} +0000"
        path = rng.choice(LOG_PATHS)
        status = rng.choices((200, 304, 302, 404), weights=(80, 10, 6, 4))[0]
        size = 0 if status == 304 else rng.randint(400, 48_000)
        out.append(f'10.20.1.{rng.randint(13, 15)} - - [{stamp}] "GET {path} HTTP/1.1" {status} {size} "-" '
                   f'"{rng.choice(AGENTS)}"')
    return "\n".join(out) + "\n"


ERROR_LOG = (
    "[Fri Nov 13 00:00:01.402113 2026] [mpm_event:notice] [pid 812:tid 812] AH00489: Apache/2.4.58 (Ubuntu) "
    "configured -- resuming normal operations\n"
    "[Fri Nov 13 03:00:01.009311 2026] [core:notice] [pid 812:tid 812] AH00094: Command line: '/usr/sbin/apache2'\n"
    "[Fri Nov 13 03:04:52.551820 2026] [autoindex:error] [pid 1907:tid 1931] [client 10.20.1.14:51022] AH01276: "
    "Cannot serve directory /srv/backups/tmp/: No matching DirectoryIndex found\n"
    "[Sat Nov 14 00:00:01.118404 2026] [mpm_event:notice] [pid 812:tid 812] AH00493: SIGUSR1 received.  "
    "Doing graceful restart\n"
)
LOGS = {"access.log": access_log("access.log", 14), "access.log.1": access_log("access.log.1", 13),
        "error.log": ERROR_LOG}


@router.get("/")
def root() -> Response:
    return index_page("/", HOST, [
        (".env.production", "2026-11-12 03:14", "1.1K"),
        ("customers_2026-11-01.csv", "2026-11-01 04:00", "57K"),
        (SNAPSHOT, "2026-11-13 03:00", f"{len(SNAPSHOT_BYTES) / 1024:.1f}K"),
        ("logs/", "2026-11-14 00:00", "-"),
    ])


@router.get("/.env.production")
def env_production(request: Request) -> Response:
    who = visitor(request)
    lines = ["# hlabs-web production environment (synced from the deploy host)", "APP_ENV=production",
             "APP_URL=https://hackumass-labs.example",
             "DATABASE_URL=postgresql://hlabs_app:Wq7v2mLr9xTb@db-primary.internal:5432/hlabs",
             "REDIS_URL=redis://cache-01.internal:6379/0", ""]
    lines += [f"{env}={who.show(kind, 'backup')}" for kind, env in ENV_NAMES.items()]
    lines += ["HL_OBJECT_STORE_BUCKET=hlabs-model-artifacts", "HL_OBJECT_STORE_REGION=us-east-2",
              "REGISTRY_URL=http://model-vault", "SMTP_HOST=smtp.internal"]
    for index, (kind, value) in enumerate(who.planted, start=2):
        who.note(kind, value)
        lines.append(f"{ENV_NAMES.get(kind, 'HL_' + kind.upper())}_{index}={value}")
    return PlainTextResponse("\n".join(lines) + "\n", headers=who.headers())


@router.get(f"/{SNAPSHOT}")
def snapshot() -> Response:
    return Response(SNAPSHOT_BYTES, media_type="application/gzip", headers={
        "Content-Disposition": f'attachment; filename="{SNAPSHOT}"', "X-Edge-Records": "user:2-4"})


@router.get("/logs")
def logs_redirect(request: Request) -> Response:
    # Path-only Location under the pod's public prefix, so the redirect survives the proxy.
    return RedirectResponse(f"{request.headers.get('x-forwarded-prefix', '')}/logs/", status_code=301)


@router.get("/logs/")
def logs_index() -> Response:
    return index_page("/logs/", HOST, [
        ("access.log", "2026-11-14 23:59", f"{len(LOGS['access.log']) / 1024:.0f}K"),
        ("access.log.1", "2026-11-13 23:59", f"{len(LOGS['access.log.1']) / 1024:.0f}K"),
        ("error.log", "2026-11-14 00:00", f"{len(ERROR_LOG)}"),
    ])


@router.get("/logs/{name}")
def log_file(name: str) -> Response:
    if name not in LOGS:
        return not_found_page(HOST)
    return PlainTextResponse(LOGS[name])
