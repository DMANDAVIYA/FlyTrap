"""backup-01 and model-vault: listings, bait reporting, drip, and no giveaway words.

    docker build -t flytrap-islands islands
    docker run --rm flytrap-islands python -m pytest -q
"""

import gzip
import json
import re
import struct

import pytest
from fastapi.testclient import TestClient

from app import bait
from app.main import create_app

SECRET = "test-bait-secret"
SID = "s_0123456789abcdef"
FORBIDDEN = ("pod", "trap", "honeypot", "fake", "flytrap", "edge", "canary")
HEADERS = {"X-Edge-Session": SID, "X-Forwarded-Prefix": "/admin/infra/backup-01"}


def island(monkeypatch, name: str) -> TestClient:
    monkeypatch.setenv("ISLAND", name)
    monkeypatch.setenv("BAIT_SECRET", SECRET)
    return TestClient(create_app(), headers=HEADERS)


def assert_clean(text: str, where: str) -> None:
    found = [word for word in FORBIDDEN if word in text.lower()]
    assert not found, f"{where} contains {found}"


def bait_header(response) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for part in response.headers.get("x-edge-bait", "").split(";"):
        kind, _, value = part.partition("=")
        if value:
            found.setdefault(kind, []).append(value)
    return found


def test_backup_listing_and_files(monkeypatch):
    client = island(monkeypatch, "backup")
    listing = client.get("/")
    assert listing.status_code == 200 and "<title>Index of /</title>" in listing.text
    hrefs = re.findall(r'<a href="([^"?]+)">', listing.text)
    assert hrefs == [".env.production", "customers_2026-11-01.csv", "db_snapshot_2026-11-13.sql.gz", "logs/"]
    logs = client.get("/logs/")
    assert 'href="../"' in logs.text and "access.log" in logs.text
    for name in ("access.log", "access.log.1", "error.log"):
        assert client.get(f"/logs/{name}").status_code == 200
    moved = client.get("/logs", follow_redirects=False)
    assert moved.status_code == 301 and moved.headers["location"] == "/admin/infra/backup-01/logs/"
    snapshot = client.get("/db_snapshot_2026-11-13.sql.gz")
    sql = gzip.decompress(snapshot.content).decode()
    assert "COPY public.users" in sql and snapshot.headers["x-edge-records"] == "user:2-4"
    missing = client.get("/nothing-here")
    assert missing.status_code == 404 and "Apache" in missing.text


def test_backup_env_production(monkeypatch):
    client = island(monkeypatch, "backup")
    planted = "hl_live_" + "Ab3" * 8
    response = client.get("/.env.production", headers={"X-Edge-Planted": f"api_token={planted}"})
    expected = {kind: bait.value(SECRET, SID, kind, bait.PLACES["backup"])
                for kind in ("api_token", "cloud_key_id", "cloud_secret")}
    reported = bait_header(response)
    for kind, value in expected.items():
        assert value in response.text and value in reported[kind]
    assert planted in response.text and planted in reported["api_token"]
    other = client.get("/.env.production", headers={"X-Edge-Session": "s_fedcba9876543210"})
    assert expected["api_token"] not in other.text


def test_vault_registry_and_api(monkeypatch):
    client = island(monkeypatch, "vault")
    page = client.get("/")
    assert page.status_code == 200 and page.headers["x-edge-records"] == "vault_model:1-12"
    assert page.text.count("weights.safetensors") == 12
    models = client.get("/api/models").json()
    assert models["count"] == 12 and all(m["visibility"] == "private" for m in models["models"])
    config = client.get("/models/halcyon-70b-reason/config.json")
    assert config.json()["model_type"] == "llama" and config.headers["x-edge-records"] == "vault_model:1"
    assert client.get("/models/unknown/weights.safetensors").status_code == 404


def test_vault_token(monkeypatch):
    client = island(monkeypatch, "vault")
    response = client.get("/vault-admin-token.txt")
    token = bait.value(SECRET, SID, "api_token", bait.PLACES["vault"])
    assert token in response.text and bait_header(response) == {"api_token": [token]}


def test_vault_weights_are_cut_and_dripped(monkeypatch):
    client = island(monkeypatch, "vault")
    response = client.get("/models/nimbus-1b-draft/weights.safetensors",
                          headers={"X-Edge-Pace": "drip", "X-Edge-Drip-Rate": "1000"})
    body = response.content
    assert len(body) == 5 * 1024 * 1024
    size = struct.unpack("<Q", body[:8])[0]
    header = json.loads(body[8:8 + size])
    assert header["__metadata__"]["format"] == "pt" and "model.embed_tokens.weight" in header
    noise = body[8 + size:]
    assert not re.search(rb"[A-Za-z]", noise)


@pytest.mark.parametrize("name,paths", [
    ("backup", ["/", "/logs/", "/logs/access.log", "/logs/access.log.1", "/logs/error.log", "/.env.production",
                "/missing", "/healthz"]),
    ("vault", ["/", "/api/models", "/vault-admin-token.txt", "/models/halcyon-70b-reason/config.json",
               "/missing", "/healthz"]),
])
def test_no_giveaway_words(monkeypatch, name, paths):
    client = island(monkeypatch, name)
    for path in paths:
        assert_clean(client.get(path).text, f"{name} {path}")
    if name == "backup":
        assert_clean(gzip.decompress(client.get("/db_snapshot_2026-11-13.sql.gz").content).decode(), "snapshot")
    else:
        response = client.get("/models/basalt-70b-base/weights.safetensors",
                              headers={"X-Edge-Pace": "drip", "X-Edge-Drip-Rate": "1000"})
        assert_clean(response.content.decode("latin-1"), "weights")
