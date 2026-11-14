"""JSON API: customers read only their own records (spec 5.2), on both sides."""

from sqlalchemy import select

from app.models import ApiToken, Invoice
from conftest import login_demo

DEMO_ID = 1
UNKNOWN_TOKEN = "hl_live_Zz9Yy8Xx7Ww6Vv5Uu4Tt3Ss2"


def demo_rows(client):
    with client.app.state.db.session() as session:
        own = session.scalar(select(Invoice.id).where(Invoice.user_id == DEMO_ID).order_by(Invoice.id))
        other = session.scalar(select(Invoice.id).where(Invoice.user_id != DEMO_ID).order_by(Invoice.id))
        token = session.scalar(select(ApiToken.token).where(ApiToken.user_id == DEMO_ID).order_by(ApiToken.id))
    return own, other, token


def test_requires_authentication(either):
    for path in ("/api/v1/users/1", "/api/v1/invoices/9001"):
        response = either.get(path)
        assert response.status_code == 401
        assert response.json() == {"error": "authentication required"}


def test_catalog_is_public(either):
    response = either.get("/api/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(body["data"]) > 0
    assert response.headers["x-edge-records"].startswith("model:")


def test_own_records_only_with_cookie(either):
    login_demo(either)
    me = either.get(f"/api/v1/users/{DEMO_ID}")
    assert me.status_code == 200
    assert me.json()["email"] == "demo@valley-robotics.example"
    assert me.headers["x-edge-records"] == f"user:{DEMO_ID}"
    for other in (2, 5, 40, 150):
        response = either.get(f"/api/v1/users/{other}")
        assert response.status_code == 403
        assert response.json() == {"error": "forbidden"}
        assert "x-edge-records" not in response.headers
    assert either.get("/api/v1/users/999999").status_code == 404

    own, other, _ = demo_rows(either)
    mine = either.get(f"/api/v1/invoices/{own}")
    assert mine.status_code == 200 and mine.json()["user_id"] == DEMO_ID
    assert mine.headers["x-edge-records"] == f"invoice:{own}"
    assert either.get(f"/api/v1/invoices/{other}").status_code == 403


def test_own_records_only_with_bearer_token(either):
    own, other, token = demo_rows(either)
    auth = {"Authorization": f"Bearer {token}"}
    assert either.get(f"/api/v1/users/{DEMO_ID}", headers=auth).status_code == 200
    assert either.get("/api/v1/users/3", headers=auth).status_code == 403
    assert either.get(f"/api/v1/invoices/{own}", headers=auth).status_code == 200
    assert either.get(f"/api/v1/invoices/{other}", headers=auth).status_code == 403
    bad = either.get("/api/v1/models", headers={"Authorization": "Bearer not-a-key"})
    assert bad.status_code == 401 and bad.json() == {"error": "invalid API token"}


def test_unknown_well_formed_key(real, pod):
    auth = {"Authorization": f"Bearer {UNKNOWN_TOKEN}"}
    assert real.get("/api/v1/models", headers=auth).status_code == 401
    # Pods accept any well-formed key (planted keys are not in the template) but
    # still only show that account's own records.
    assert pod.get("/api/v1/models", headers=auth).status_code == 200
    me = pod.get("/api/v1/users/2", headers=auth)
    assert me.status_code == 200 and me.json()["role"] == "admin"
    assert pod.get("/api/v1/users/10", headers=auth).status_code == 403


def test_account_page_reports_own_records(either):
    login_demo(either)
    response = either.get("/account")
    assert response.status_code == 200
    records = response.headers["x-edge-records"]
    assert f"user:{DEMO_ID}" in records.split(",") and "invoice:" in records and "token:" in records
    assert "Dana Whitfield" in response.text and "<svg" in response.text


def test_bad_query_values_get_html_or_json_errors(pod):
    assert pod.get("/admin/customers?page=abc").headers["content-type"].startswith("text/html")
    response = pod.get("/api/v1/users/abc")
    assert response.status_code == 422 and response.json() == {"error": "invalid request"}
