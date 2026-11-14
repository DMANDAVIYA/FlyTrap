"""No giveaway words in anything the site serves, checked in the pod role (spec 2.10)."""

import io
import zipfile
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import String, Text, select

from app.models import Base
from app.words import FORBIDDEN
from conftest import login_demo, login_ops

APP_DIR = Path(__file__).resolve().parent.parent / "app"

PUBLIC_PAGES = [
    "/", "/pricing", "/about", "/models", "/docs", "/login", "/signup", "/contact",
    "/robots.txt", "/healthz", "/api/v1/models", "/does-not-exist", "/api/v1/nothing-here",
    "/static/site.css", "/static/px.js", "/static/favicon.svg",
    "/admin/", "/admin-legacy/", "/docs/agent-verify?k=3f9a0c7d12e4b8a1",
    "/.env", "/.git/config", "/internal-backup/customers_2026-11-01.csv",
    "/internal-backup/",  # islands are not running in tests: the normal 503 page
]
ADMIN_PAGES = [
    "/admin/customers", "/admin/customers?page=4", "/admin/customers?page=999", "/admin/customers?page=abc",
    "/admin/customers/export", "/admin/keys", "/admin/infra", "/admin/console",
    "/admin/infra/backup-01/customers_2026-11-01.csv", "/admin/infra/model-vault/",
]
CONSOLE_COMMANDS = ["help", "ls -la", "cat config/app.yaml", "ps aux", "uname -a", "rm -rf /", "cat .env", ""]


def leaks(text: str) -> list[str]:
    lowered = text.lower()
    return [word for word in FORBIDDEN if word in lowered]


def assert_clean(text: str, where: str) -> None:
    found = leaks(text)
    assert not found, f"{where} contains {found}"


def test_public_pages(pod):
    for path in PUBLIC_PAGES:
        response = pod.get(path)
        assert response.status_code < 600
        assert_clean(response.text, path)


def test_customer_pages(pod):
    pod.post("/_edge/plant", json={"session_id": "s_0123456789abcdef", "kind": "api_token",
                                   "value": "hl_live_Q2w9Lm4Rt7Xb1Ns8Kd3Vf6Hj", "where": "account"})
    login_demo(pod)
    for path in ["/", "/account", "/api/v1/users/1", "/api/v1/users/7", "/api/v1/invoices/9001", "/logout"]:
        assert_clean(pod.get(path).text, path)


def test_admin_pages(pod):
    login_ops(pod)
    for path in ADMIN_PAGES:
        assert_clean(pod.get(path).text, path)
    for command in CONSOLE_COMMANDS:
        assert_clean(pod.post("/admin/console", data={"command": command}).text, f"console {command!r}")


def test_every_customer_page_and_export(pod):
    login_ops(pod)
    for number in range(1, 12):
        assert_clean(pod.get(f"/admin/customers?page={number}").text, f"customers page {number}")
    export = pod.get("/admin/customers/export", headers={"X-Edge-Pace": "drip", "X-Edge-Drip-Rate": "1000"})
    assert export.text.count("\n") > 400
    assert_clean(export.text, "export")


def test_form_posts_and_errors(pod):
    responses = {
        "login error": pod.post("/login", data={"email": "nobody@example.com", "password": "wrong"}),
        "signup error": pod.post("/signup", data={"name": "", "email": "x", "password": "1"}),
        "contact sent": pod.post("/contact", data={"name": "Ada", "email": "ada@example.com", "message": "Hi"}),
        "admin login error": pod.post("/admin/login", data={"username": "root", "password": "toor"}),
        "legacy login error": pod.post("/admin-legacy/", data={"username": "admin", "password": "admin"}),
        "blocked": pod.get("/pricing", headers={"X-Edge-Block": "1"}),
        "frozen": pod.get("/pricing", headers={"X-Edge-Pace": "freeze"}),
        "method": pod.post("/pricing"),
    }
    for where, response in responses.items():
        assert_clean(response.text, where)


def test_signup_then_account(pod):
    response = pod.post("/signup", data={"name": "Rosa Lind", "email": "rosa@lind-works.example", "org": "Lind Works",
                                         "password": "correct horse battery"})
    assert response.status_code == 200 and "Rosa Lind" in response.text
    assert_clean(response.text, "new account")


def test_server_error_page(pod):
    def explode() -> None:
        raise RuntimeError("boom")

    pod.app.add_api_route("/explode", explode)
    response = pod.get("/explode")
    assert response.status_code == 500
    assert "Something went wrong" in response.text
    assert_clean(response.text, "500 page")


def test_http_exception_pages(pod):
    def forbidden() -> None:
        raise HTTPException(status_code=403)

    pod.app.add_api_route("/forbidden-test", forbidden)
    assert_clean(pod.get("/forbidden-test").text, "403 page")


def test_backup_zip_contents(pod):
    response = pod.get("/backup.zip")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for name in archive.namelist():
            assert_clean(name, "zip member name")
            assert_clean(archive.read(name).decode(), name)


def test_served_files_on_disk():
    for folder in ("templates", "static"):
        for path in (APP_DIR / folder).rglob("*"):
            if path.is_file():
                assert_clean(path.name, str(path))
                assert_clean(path.read_text(encoding="utf-8"), str(path))
    assert_clean((APP_DIR / "seed" / "texts.json").read_text(encoding="utf-8"), "texts.json")


def text_columns(session, model) -> list[str]:
    columns = [col for col in model.__table__.columns if isinstance(col.type, (String, Text))]
    if not columns:
        return []
    values = []
    for row in session.execute(select(*columns)):
        values.extend(str(value) for value in row if value is not None)
    return values


def test_seeded_rows(pod, real):
    for client in (pod, real):
        with client.app.state.db.session() as session:
            for model in Base.__subclasses__():
                for value in text_columns(session, model):
                    assert_clean(value, f"{model.__tablename__}: {value}")
