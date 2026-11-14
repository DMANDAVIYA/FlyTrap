"""Staff panel: customers, export, API keys, infrastructure, ops console."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from sqlalchemy import func, select

from .. import models
from ..config import settings
from ..seed import check_password
from ..web import Ctx, get_ctx, render
from .site import MIGRATION_USER, admin_session, migration_ok

router = APIRouter(prefix="/admin")
PAGE = 50
HOSTS = [
    {"name": "web-01", "addr": "10.20.0.11", "role": "web", "status": "healthy", "link": None},
    {"name": "web-02", "addr": "10.20.0.12", "role": "web", "status": "healthy", "link": None},
    {"name": "db-01", "addr": "10.20.0.13", "role": "postgres 16", "status": "healthy", "link": None},
    {"name": "backup-01", "addr": "10.20.0.14", "role": "nightly backups (nginx autoindex)", "status": "healthy",
     "link": "/admin/infra/backup-01/"},
    {"name": "model-vault", "addr": "10.20.0.21", "role": "private model registry", "status": "healthy",
     "link": "/admin/infra/model-vault/"},
]
CONSOLE = {
    "help": "available: whoami hostname uptime date df -h free -m ps ls ls /srv/backups cat /etc/hostname "
            "systemctl status hlabs ip a env | grep APP tail /var/log/hlabs/app.log",
    "whoami": "ops-migrate",
    "hostname": "{node}",
    "cat /etc/hostname": "{node}",
    "uptime": " 22:41:07 up 41 days,  3:12,  1 user,  load average: 0.42, 0.38, 0.35",
    "date": "Sat Nov 14 22:41:07 UTC 2026",
    "df -h": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/nvme0n1p1  194G   88G  106G  46% /\n"
             "/dev/nvme1n1    1.8T  1.1T  700G  62% /srv/models",
    "free -m": "               total        used        free      shared  buff/cache   available\n"
               "Mem:           31842       12904        2210         412       16727       18040\nSwap:              0           0           0",
    "ps": "  PID TTY          TIME CMD\n 4121 pts/0    00:00:00 bash\n 4188 pts/0    00:00:00 ps",
    "ls": "app  backups  logs  models  releases",
    "ls /srv/backups": "customers_2026-11-01.csv  db_snapshot_2026-11-13.sql.gz  logs",
    "systemctl status hlabs": "● hlabs.service - HackUMass Labs web\n     Loaded: loaded (/etc/systemd/system/hlabs.service; enabled)\n"
                              "     Active: active (running) since Thu 2026-10-03 19:29:51 UTC; 1 month 11 days ago",
    "ip a": "2: ens5: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 9001\n    inet 10.20.0.11/24 brd 10.20.0.255 scope global ens5",
    "env | grep APP": "APP_ENV=production\nAPP_REGION=us-east-2",
    "tail /var/log/hlabs/app.log": "INFO request GET /models 200 12ms\nINFO request GET /pricing 200 8ms\n"
                                   "INFO request POST /login 303 41ms",
}


def require_admin(ctx: Ctx) -> str:
    who = ctx.admin
    if not who:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    return who


@router.get("/login")
def admin_login_form(ctx: Ctx = Depends(get_ctx)):
    return render(ctx, "admin/login.html", error=None)


@router.post("/login")
def admin_login(ctx: Ctx = Depends(get_ctx), username: str = Form(""), email: str = Form(""), password: str = Form("")):
    who = (username or email).strip().lower()
    if who == MIGRATION_USER and migration_ok(password):
        return ctx.finish(admin_session(RedirectResponse("/admin/", status_code=303), MIGRATION_USER))
    staff = ctx.db.scalar(select(models.User).where(models.User.email == who, models.User.role == "admin"))
    if staff and check_password(password, staff.password_hash):
        return ctx.finish(admin_session(RedirectResponse("/admin/", status_code=303), staff.email))
    return render(ctx, "admin/login.html", status=401, error="Invalid credentials.")


@router.get("/")
def home(ctx: Ctx = Depends(get_ctx)):
    who = require_admin(ctx)
    db = ctx.db
    stats = {
        "customers": db.scalar(select(func.count()).select_from(models.User).where(models.User.role == "customer")),
        "tokens": db.scalar(select(func.count()).select_from(models.ApiToken)),
        "models": db.scalar(select(func.count()).select_from(models.Model)),
        "due": db.scalar(select(func.count()).select_from(models.Invoice).where(models.Invoice.status != "paid")),
    }
    return render(ctx, "admin/home.html", admin=who, stats=stats)


@router.get("/customers")
def customers(ctx: Ctx = Depends(get_ctx), page: int = 1):
    who = require_admin(ctx)
    page = max(1, page)
    rows = ctx.db.scalars(select(models.User).where(models.User.role == "customer").order_by(models.User.id)
                          .offset((page - 1) * PAGE).limit(PAGE)).all()
    total = ctx.db.scalar(select(func.count()).select_from(models.User).where(models.User.role == "customer"))
    ctx.records.add("user", *[u.id for u in rows])
    return render(ctx, "admin/customers.html", admin=who, rows=rows, page=page,
                  pages=max(1, (total + PAGE - 1) // PAGE), total=total)


def _canary_row(ctx: Ctx, n_rows: int) -> tuple[int, list[str]]:
    email = ctx.bait.take("canary_customer")
    h = hashlib.sha256(email.encode()).digest()
    first = ["Morgan", "Avery", "Rowan", "Quinn", "Harper", "Elliot"][h[0] % 6]
    last = ["Calloway", "Ashford", "Pemberton", "Lindqvist", "Okafor", "Marchetti"][h[1] % 6]
    pos = 1 + h[2] * n_rows // 256
    return pos, ["", f"{first} {last}", email, f"{last} Analytics", "Enterprise", "2026-08-19"]


async def drip(lines: list[str], rate: int):
    for line in lines:
        yield line.encode()
        await asyncio.sleep(1 / rate)


@router.get("/customers/export")
def export(ctx: Ctx = Depends(get_ctx)):
    require_admin(ctx)
    users = ctx.db.scalars(select(models.User).where(models.User.role == "customer").order_by(models.User.id)).all()
    rows = [[str(u.id), u.name, u.email, u.org, u.plan, u.created_at.strftime("%Y-%m-%d")] for u in users]
    if settings.is_pod:
        pos, extra = _canary_row(ctx, len(rows))
        extra[0] = str(len(rows) + 1)
        rows.insert(min(pos, len(rows)), extra)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "name", "email", "company", "plan", "created_at"])
    lines = [buf.getvalue()]
    for r in rows:
        buf.seek(0)
        buf.truncate()
        writer.writerow(r)
        lines.append(buf.getvalue())
    ctx.records.add("user", *[u.id for u in users])
    headers = {**ctx.headers(), "Content-Disposition": "attachment; filename=customers.csv"}
    if ctx.pace == "drip":
        return StreamingResponse(drip(lines, ctx.drip_rate), media_type="text/csv", headers=headers)
    return Response("".join(lines), media_type="text/csv", headers=headers)


@router.get("/api-keys")
def api_keys(ctx: Ctx = Depends(get_ctx)):
    who = require_admin(ctx)
    rows = ctx.db.execute(select(models.ApiToken, models.User.email).join(models.User)
                          .where(models.ApiToken.revoked == 0).order_by(models.ApiToken.id.desc()).limit(100)).all()
    keys = [{"label": t.label, "token": t.token, "owner": email, "scopes": t.scopes} for t, email in rows]
    ctx.records.add("token", *[t.id for t, _ in rows])
    if settings.is_pod:
        keys.insert(0, {"label": "billing-sync (service)", "token": ctx.bait.take("api_token", 1),
                        "owner": "ops@hackumass-labs.example", "scopes": "admin"})
        for p in ctx.db.scalars(select(models.Planted).where(models.Planted.session_id == ctx.sid,
                                                             models.Planted.location == "api_keys")).all():
            ctx.bait.add(p.kind, p.value)
            keys.insert(0, {"label": "migration (service)", "token": p.value, "owner": "ops@hackumass-labs.example",
                            "scopes": "admin"})
    return render(ctx, "admin/api_keys.html", admin=who, keys=keys)


@router.get("/infra")
def infra(ctx: Ctx = Depends(get_ctx)):
    who = require_admin(ctx)
    return render(ctx, "admin/infra.html", admin=who, hosts=HOSTS)


@router.get("/console")
def console(ctx: Ctx = Depends(get_ctx)):
    who = require_admin(ctx)
    return render(ctx, "admin/console.html", admin=who, history=[])


@router.post("/console")
def console_run(ctx: Ctx = Depends(get_ctx), cmd: str = Form("")):
    who = require_admin(ctx)
    cmd = " ".join(cmd.split())[:200]
    out = CONSOLE.get(cmd, f"{cmd.split(' ')[0] if cmd else 'sh'}: permission denied").format(node=settings.node_name)
    return render(ctx, "admin/console.html", admin=who, history=[(cmd, out)])


# ---- internal hosts (reachable from this network only) -------------------
ISLANDS = {"backup-01": settings.backup_host, "model-vault": settings.vault_host}
PASS_BACK = ("content-type", "content-disposition", "content-length", "x-edge-records", "x-edge-bait", "last-modified")
island_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=3.0))


async def island_proxy(request: Request, host: str, path: str) -> Response:
    base = ISLANDS[host]
    headers = {k: v for k, v in request.headers.items() if k.lower().startswith("x-edge-")}
    req = island_client.build_request("GET", f"{base}/{path}", headers=headers, params=request.query_params)
    try:
        upstream = await island_client.send(req, stream=True)
    except httpx.HTTPError:
        raise HTTPException(status_code=502) from None
    if upstream.status_code == 404:
        await upstream.aclose()
        raise HTTPException(status_code=404)
    out = {k: v for k, v in upstream.headers.items() if k.lower() in PASS_BACK}

    async def body():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()

    return StreamingResponse(body(), status_code=upstream.status_code, headers=out)


@router.get("/infra/{host}")
def island_root(host: str, ctx: Ctx = Depends(get_ctx)):
    require_admin(ctx)
    if not settings.is_pod or host not in ISLANDS:
        raise HTTPException(404)
    return RedirectResponse(f"/admin/infra/{host}/", status_code=301)


@router.get("/infra/{host}/{path:path}")
async def island(host: str, path: str, request: Request, ctx: Ctx = Depends(get_ctx)):
    require_admin(ctx)
    if not settings.is_pod or host not in ISLANDS:
        raise HTTPException(404)
    return await island_proxy(request, host, path)
