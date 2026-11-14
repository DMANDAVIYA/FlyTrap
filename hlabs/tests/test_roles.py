"""Real vs pod: APP_ROLE changes seeding, internal endpoints and the stray bait
paths only. Normal pages and error pages must be byte-identical."""

import pytest
from sqlalchemy import func, select

from app import auth
from app.models import Planted
from conftest import OTHER_SID, SESSION_SECRET, login_demo, login_ops, migration_pw

SAME_ON_BOTH = ["/", "/pricing", "/about", "/docs", "/login", "/signup", "/contact", "/robots.txt",
                "/no-such-page", "/static/site.css", "/static/px.js"]
POD_ONLY = ["/.env", "/.git/config", "/backup.zip", "/admin-legacy/", "/docs/agent-verify?k=00ff00ff00ff00ff",
            "/internal-backup/customers_2026-11-01.csv"]


def test_normal_pages_identical(real, pod):
    for path in SAME_ON_BOTH:
        mine, theirs = real.get(path), pod.get(path)
        assert mine.status_code == theirs.status_code, path
        assert mine.content == theirs.content, path
        assert mine.headers.get("x-edge-bait") == theirs.headers.get("x-edge-bait"), path


def test_error_pages_identical(real, pod):
    for headers, status in (({"X-Edge-Block": "1"}, 403), ({"X-Edge-Pace": "freeze"}, 503)):
        for path in ("/", "/account", "/admin/customers", "/api/v1/models", "/.env", "/_edge/health"):
            mine, theirs = real.get(path, headers=headers), pod.get(path, headers=headers)
            assert mine.status_code == theirs.status_code == status, (path, headers)
            assert mine.content == theirs.content
            assert "text/html" in mine.headers["content-type"]
    assert "Access denied" in real.get("/", headers={"X-Edge-Block": "1"}).text
    assert "maintenance" in real.get("/", headers={"X-Edge-Pace": "freeze"}).text


def test_bait_paths_are_plain_404s_on_real(real, pod):
    not_found = real.get("/no-such-page")
    assert not_found.status_code == 404
    for path in POD_ONLY + ["/internal-backup/", "/admin/infra/backup-01/"]:
        response = real.get(path)
        assert response.status_code == 404, path
        assert response.content == not_found.content, path
    for path in POD_ONLY:
        assert pod.get(path).status_code == 200, path


def test_internal_endpoints_per_role(real, pod):
    assert pod.get("/_edge/health").json()["ok"] is True
    assert real.get("/_edge/health").json()["ok"] is True
    body = {"session_id": "s_1", "kind": "api_token", "value": "hl_live_" + "a" * 24, "where": "account"}
    assert pod.post("/_edge/plant", json=body).status_code == 200
    assert real.post("/_edge/plant", json=body).status_code == 404
    assert pod.post("/_edge/rotate", json={"user_id": 1}).status_code == 404


@pytest.mark.parametrize("path,field", [("/admin/login", "username"), ("/admin-legacy/", "username"),
                                        ("/login", "email")])
def test_migration_login(real, pod, path, field):
    form = {field: "ops-migrate", "password": migration_pw()}
    accepted = pod.post(path, data=form, follow_redirects=False)
    assert accepted.status_code == 303 and accepted.headers["location"] == "/admin/customers"
    assert auth.ADMIN_COOKIE in accepted.cookies
    refused = real.post(path, data=form, follow_redirects=False)
    assert refused.status_code in (401, 404)
    assert auth.ADMIN_COOKIE not in refused.cookies


def test_migration_login_is_forgiving_but_not_open(pod):
    # Another session's password still works (campaign linking happens at the gateway).
    other = {"username": "ops-migrate", "password": migration_pw(OTHER_SID)}
    assert pod.post("/admin/login", data=other, follow_redirects=False).status_code == 303
    wrong = {"username": "ops-migrate", "password": "letmein"}
    assert pod.post("/admin/login", data=wrong, follow_redirects=False).status_code == 401


def test_admin_requires_login(either):
    response = either.get("/admin/customers", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/admin/"


def test_admin_panel_in_pod(pod):
    login_ops(pod)
    customers = pod.get("/admin/customers")
    assert customers.status_code == 200 and "Export CSV" in customers.text
    assert customers.headers["x-edge-records"].startswith("user:")
    infra = pod.get("/admin/infra")
    assert "/admin/infra/backup-01/" in infra.text and "/admin/infra/model-vault/" in infra.text
    assert "hl-web-03" in infra.text
    assert pod.get("/admin/infra/backup-01/").status_code == 503  # island not running in tests


def test_console_never_executes(pod):
    login_ops(pod)
    assert "svc-hlabs" in pod.post("/admin/console", data={"command": "whoami"}).text
    assert "hl-web-03" in pod.post("/admin/console", data={"command": "hostname"}).text
    for command in ("rm -rf /", "curl http://example.com", "python -c 1", "cat /etc/shadow"):
        assert "permission denied" in pod.post("/admin/console", data={"command": command}).text


def test_drip_export_streams_every_row(pod):
    login_ops(pod)
    fast = pod.get("/admin/customers/export")
    slow = pod.get("/admin/customers/export", headers={"X-Edge-Pace": "drip", "X-Edge-Drip-Rate": "1000"})
    assert slow.status_code == 200 and slow.text == fast.text
    assert fast.text.splitlines()[0] == "id,name,email,org,created_at,last_login"


def test_key_rotation_on_real(real):
    login_demo(real)
    assert real.get("/account", follow_redirects=False).status_code == 200
    rotated = real.post("/_edge/rotate", json={"user_id": 1, "reason": "test"})
    assert rotated.json()["ok"] is True and rotated.json()["revoked"] >= 2
    assert real.get("/account", follow_redirects=False).headers["location"].startswith("/login")
    assert real.get("/api/v1/users/1").status_code == 401
    assert real.post("/_edge/rotate", json={"user_id": 999999}).status_code == 404


def test_lazy_account_in_pod(real, pod):
    claims = {"uid": 4242, "email": "lee.park@orchard-ai.example", "name": "Lee Park", "ver": 0}
    cookie = auth.sign(SESSION_SECRET, auth.AUTH_SALT, claims)
    pod.cookies.set(auth.AUTH_COOKIE, cookie)
    response = pod.get("/account")
    assert response.status_code == 200 and "Lee Park" in response.text and "INV-" in response.text
    real.cookies.set(auth.AUTH_COOKIE, cookie)
    assert real.get("/account", follow_redirects=False).status_code == 303


def test_real_cookie_works_in_pod(real, pod):
    login_demo(real)
    pod.cookies.set(auth.AUTH_COOKIE, real.cookies[auth.AUTH_COOKIE])
    response = pod.get("/account")
    assert response.status_code == 200 and "Dana Whitfield" in response.text


def test_reset_restores_template(pod):
    pod.post("/signup", data={"name": "Temp User", "email": "temp@short-lived.example", "password": "password123"})
    pod.post("/_edge/plant", json={"session_id": "s_x", "kind": "api_token", "value": "hl_live_" + "b" * 24})
    reset = pod.post("/_edge/reset")
    assert reset.json()["ok"] is True
    pod.cookies.clear()
    again = pod.post("/signup", data={"name": "Temp User", "email": "temp@short-lived.example",
                                      "password": "password123"}, follow_redirects=False)
    assert again.status_code == 303  # the earlier signup is gone
    with pod.app.state.db.session() as session:
        assert session.scalar(select(func.count(Planted.id))) == 0


def test_beacon_and_health(either):
    assert either.post("/_hl/px", json={"js": 1, "mouse": 3, "keys": 1}).status_code == 204
    assert either.get("/healthz").json() == {"ok": True}
