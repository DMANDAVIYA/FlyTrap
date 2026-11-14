"""Bait values: formats (spec 5.4 / 10.4), where they are rendered, and how they are reported."""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app import bait, ledger
from conftest import BAIT_SECRET, OTHER_SID, SID, login_ops, migration_pw

FORMATS = {
    "api_token": r"hl_live_[0-9A-Za-z]{24}",
    "cloud_key_id": r"HLK[0-9A-Z]{17}",
    "cloud_secret": r"hlsk_[0-9A-Za-z]{32}",
    "migration_pw": r"hlm-[0-9A-Za-z]{10}",
    "ai_note": r"[0-9a-f]{16}",
    "canary_customer": r"c[0-9a-f]{8}@[a-z]+-[a-z]+\.example",
}
# The gateway's canary scanner (gateway/app/canaries.py) must find every value we render.
GATEWAY_PATTERN = re.compile(
    r"hl_live_[A-Za-z0-9]{24}|HLK[A-Z0-9]{17}|hlsk_[A-Za-z0-9]{32}|c[0-9a-f]{8}@[a-z]+-[a-z]+\.example"
)
ISLANDS_COPIES = [
    Path(__file__).resolve().parents[2] / "islands" / "app" / "bait.py",  # repo checkout
    Path("/islands/app/bait.py"),  # mounted into the container
]


def page_value(kind: str, place: str = "page", sid: str = SID) -> str:
    return bait.value(BAIT_SECRET, sid, kind, bait.PLACES[place])


def reported(response) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for kind, value in ledger.parse_bait(response.headers.get("x-edge-bait", "")):
        found.setdefault(kind, []).append(value)
    return found


def test_islands_copy_is_identical():
    copy = next((path for path in ISLANDS_COPIES if path.is_file()), None)
    if copy is None:
        pytest.skip("islands/app/bait.py not available (mount it to run this check)")
    ours = Path(bait.__file__).read_bytes()
    assert copy.read_bytes() == ours, f"{copy} differs from hlabs/app/bait.py"


@pytest.mark.parametrize("kind", bait.KINDS)
def test_formats(kind):
    for sid in (SID, OTHER_SID, "s_anon"):
        for place in bait.PLACES:
            value = page_value(kind, place, sid)
            assert re.fullmatch(FORMATS[kind], value), value
            if kind not in ("migration_pw", "ai_note"):
                assert GATEWAY_PATTERN.fullmatch(value), value


def test_values_are_per_session_and_per_place():
    for kind in bait.KINDS:
        assert page_value(kind, sid=SID) == page_value(kind, sid=SID)
        assert page_value(kind, sid=SID) != page_value(kind, sid=OTHER_SID)
        assert len({page_value(kind, place) for place in bait.PLACES}) == len(bait.PLACES)


def test_demo_password_format():
    assert re.fullmatch(r"[0-9A-Za-z]{16}", bait.demo_password(BAIT_SECRET))


def test_login_comment(either):
    response = either.get("/login")
    password = migration_pw()
    comment = re.search(r"<!--(.*?)-->", response.text, re.S)
    assert comment and "ops-migrate" in comment.group(1) and password in comment.group(1)
    assert reported(response) == {"migration_pw": [password]}
    other = either.get("/login", headers={"X-Edge-Session": OTHER_SID})
    assert migration_pw(OTHER_SID) in other.text and password not in other.text


def test_ai_note_on_landing(either):
    response = either.get("/")
    note = page_value("ai_note")
    assert f'href="/docs/agent-verify?k={note}"' in response.text
    assert reported(response) == {"ai_note": [note]}


class HiddenBaitCheck(HTMLParser):
    """Every visually hidden element is aria-hidden; every control inside one has tabindex=-1."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
    CONTROLS = {"a", "input", "button", "select", "textarea"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[bool] = []
        self.hidden = 0
        self.problems: list[str] = []
        self.controls: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        values = dict(attrs)
        clipped = "u-clip" in (values.get("class") or "").split()
        inside = clipped or any(self.stack)
        if clipped:
            self.hidden += 1
            if values.get("aria-hidden") != "true":
                self.problems.append(f"<{tag}> hidden without aria-hidden")
        if inside and tag in self.CONTROLS:
            self.controls.append(values)
            if values.get("tabindex") != "-1":
                self.problems.append(f"<{tag}> reachable by keyboard: {values}")
        if tag not in self.VOID:
            self.stack.append(inside)

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.VOID and self.stack:
            self.stack.pop()


@pytest.mark.parametrize("path", ["/", "/signup", "/contact", "/pricing"])
def test_hidden_bait_is_inaccessible(pod, path):
    check = HiddenBaitCheck()
    check.feed(pod.get(path).text)
    assert check.hidden >= 1
    assert not check.problems
    hrefs = {control.get("href") for control in check.controls}
    assert "/admin-legacy/" in hrefs  # hidden footer link on every page
    if path in ("/signup", "/contact"):
        assert any(control.get("name") == "company_website" for control in check.controls)


def test_dotenv(pod):
    response = pod.get("/.env")
    expected = {kind: page_value(kind, "dotenv") for kind in ("api_token", "cloud_key_id", "cloud_secret")}
    for kind, value in expected.items():
        assert value in response.text
        assert value in reported(response)[kind]
    assert response.headers["content-type"].startswith("text/plain")


def test_git_config_and_zip(pod):
    git = pod.get("/.git/config")
    assert page_value("api_token", "git") in git.text
    assert reported(git) == {"api_token": [page_value("api_token", "git")]}
    archive = pod.get("/backup.zip")
    assert archive.headers["content-type"] == "application/zip"
    assert page_value("cloud_secret", "zip") in reported(archive)["cloud_secret"]


def test_admin_keys_page(pod):
    login_ops(pod)
    response = pod.get("/admin/keys")
    for kind in ("api_token", "cloud_key_id", "cloud_secret"):
        assert page_value(kind) in response.text
        assert page_value(kind) in reported(response)[kind]
    assert response.headers["x-edge-records"].startswith("token:")


def test_exports_carry_the_visitor_customer(pod):
    login_ops(pod)
    export = pod.get("/admin/customers/export")
    email = page_value("canary_customer")
    assert email in export.text
    assert reported(export) == {"canary_customer": [email]}
    nightly = pod.get("/internal-backup/customers_2026-11-01.csv")
    assert page_value("canary_customer", "backup") in nightly.text
    assert nightly.headers["content-disposition"].endswith('"customers_2026-11-01.csv"')


def test_planted_values_show_only_for_their_session(pod):
    token = "hl_live_P7k2Wq9Zr4Tn6Yb1Mc8Xd3Lf"
    planted = pod.post("/_edge/plant", json={"session_id": SID, "kind": "api_token", "value": token,
                                            "where": "admin/keys"})
    assert planted.json() == {"ok": True, "id": 1, "place": "api_keys"}
    login_ops(pod)
    login_ops(pod, OTHER_SID)
    mine = pod.get("/admin/keys")
    assert token in mine.text and token in reported(mine)["api_token"]
    theirs = pod.get("/admin/keys", headers={"X-Edge-Session": OTHER_SID})
    assert token not in theirs.text
    env_value = "hlsk_" + "A1b2C3d4" * 4
    pod.post("/_edge/plant", json={"session_id": SID, "kind": "cloud_secret", "value": env_value, "where": "/.env"})
    assert env_value in pod.get("/.env").text
