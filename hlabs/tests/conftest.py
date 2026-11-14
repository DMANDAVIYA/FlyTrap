"""Shared fixtures: a pod app and a real app, each on its own SQLite file.

Run inside the image (the Windows host blocks some native packages):
    docker build -t flytrap-hlabs hlabs
    docker run --rm flytrap-hlabs python -m pytest -q
To also check the islands copy of bait.py, mount it:
    docker run --rm -v "<repo>/islands/app/bait.py:/islands/app/bait.py:ro" flytrap-hlabs python -m pytest -q
"""

import shutil
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import bait
from app.config import Settings
from app.main import create_app
from app.seed import DEMO_EMAIL, build_sqlite

SESSION_SECRET = "test-session-secret"
BAIT_SECRET = "test-bait-secret"
SID = "s_0123456789abcdef"
OTHER_SID = "s_fedcba9876543210"


def settings(role: str, db_file: Path, template: Path | None = None) -> Settings:
    return Settings(
        role=role,
        database_url=f"sqlite:///{db_file.as_posix()}",
        session_secret=SESSION_SECRET,
        bait_secret=BAIT_SECRET,
        pod_name="pod-1" if role == "pod" else "",
        node_name="hl-web-03" if role == "pod" else "web-1",
        template_db=str(template or ""),
    )


@pytest.fixture(scope="session")
def pod_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("templates") / "pod.db"
    build_sqlite(path, "pod", 1001)
    return path


@pytest.fixture(scope="session")
def real_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("real") / "real.db"
    build_sqlite(path, "real", 7)
    return path


class Unreachable(httpx.AsyncBaseTransport):
    """backup-01 and model-vault do not run in unit tests; fail fast instead of waiting on DNS."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("island not running", request=request)


def client_for(app) -> TestClient:
    return TestClient(app, headers={"X-Edge-Session": SID}, raise_server_exceptions=False)


@pytest.fixture
def pod(pod_template: Path, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(settings("pod", tmp_path / "data" / "pod.db", pod_template))
    with client_for(app) as client:
        app.state.http = httpx.AsyncClient(transport=Unreachable())
        yield client


@pytest.fixture
def real(real_template: Path, tmp_path: Path) -> Iterator[TestClient]:
    live = tmp_path / "real.db"
    shutil.copyfile(real_template, live)
    app = create_app(settings("real", live))
    with client_for(app) as client:
        yield client


@pytest.fixture(params=["real", "pod"])
def either(request: pytest.FixtureRequest) -> TestClient:
    return request.getfixturevalue(request.param)


def login_demo(client: TestClient) -> None:
    response = client.post("/login", data={"email": DEMO_EMAIL, "password": bait.demo_password(BAIT_SECRET)},
                           follow_redirects=False)
    assert response.status_code == 303, response.text


def migration_pw(sid: str = SID) -> str:
    return bait.value(BAIT_SECRET, sid, "migration_pw", bait.PLACES["page"])


def login_ops(client: TestClient, sid: str = SID) -> None:
    response = client.post("/admin/login", data={"username": "ops-migrate", "password": migration_pw(sid)},
                           headers={"X-Edge-Session": sid}, follow_redirects=False)
    assert response.status_code == 303, response.text
