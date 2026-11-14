"""Tripwires: instant ones flip immediately, scored ones add risk.

Pure functions over a request view and a session, so they are easy to test.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs

from .sessions import Session

SECRET_FILES = ("/.env", "/.git/config", "/backup.zip")
ENUMERABLE = re.compile(r"^/api/v1/(users|invoices)/(\d+)$")
TOOL_AGENTS = re.compile(
    r"sqlmap|nikto|nmap|masscan|zgrab|gobuster|dirbuster|feroxbuster|ffuf|wfuzz|nuclei|"
    r"python-requests|python-httpx|python-urllib|aiohttp|curl/|wget/|go-http-client|libwww-perl",
    re.I,
)
# Generic detection signatures by attack class (OWASP CRS categories): traversal,
# SQL injection markers, script injection, command chaining, cloud metadata access.
SIGNATURES = [
    ("traversal", re.compile(r"\.\./|\.\.\\|%2e%2e(%2f|/)|\.\.%2f", re.I)),
    ("sqli", re.compile(r"union(\s|\+|%20)+select|'\s*or\s+'?\d+'?\s*=\s*'?\d|;\s*drop\s+table|sleep\(\d|benchmark\(", re.I)),
    ("xss", re.compile(r"<script|javascript:|onerror\s*=|onload\s*=", re.I)),
    ("cmd", re.compile(r";\s*(cat|ls|id|whoami|uname)\b|\$\([^)]*\)|`[^`]+`", re.I)),
    ("metadata", re.compile(r"169\.254\.169\.254|metadata\.google\.internal", re.I)),
]


@dataclass
class RequestView:
    method: str
    path: str
    query: str
    user_agent: str
    body: bytes = b""
    headers_blob: str = ""


@dataclass
class Hit:
    tripwire: str
    instant: bool
    score: int = 0
    detail: str = ""


@dataclass
class DynamicRule:
    """A hot-loaded rule approved by Zeus (or session-scoped by Athena)."""
    rule_id: str
    path_prefix: str | None = None
    path_regex: str | None = None
    ua_contains: str | None = None
    action: str = "flip"          # flip | score
    score: int = 30
    session_id: str | None = None  # None = everyone
    expires: float = field(default_factory=lambda: time.time() + 3600)

    def matches(self, req: RequestView, session: Session) -> bool:
        if self.session_id and self.session_id != session.session_id:
            return False
        if self.path_prefix and not req.path.startswith(self.path_prefix):
            return False
        if self.path_regex and not re.search(self.path_regex, req.path):
            return False
        if self.ua_contains and self.ua_contains.lower() not in req.user_agent.lower():
            return False
        return bool(self.path_prefix or self.path_regex or self.ua_contains)


def _form_value(body: bytes, name: str) -> str:
    try:
        values = parse_qs(body.decode("utf-8", "ignore")).get(name, [])
    except ValueError:
        return ""
    return values[0].strip() if values else ""


def instant_hits(req: RequestView) -> list[Hit]:
    path, hits = req.path, []
    if path.startswith("/internal-backup"):
        hits.append(Hit("T1", True, detail="robots.txt disallowed path"))
    if path in SECRET_FILES or path.startswith("/.git/"):
        hits.append(Hit("T2", True, detail="secret file"))
    if req.method == "POST" and b"ops-migrate" in req.body:
        hits.append(Hit("T3", True, detail="migration login from page comment"))
    if path.startswith("/admin-legacy"):
        hits.append(Hit("T4", True, detail="hidden footer link"))
    if req.method == "POST" and path in ("/signup", "/contact") and _form_value(req.body, "company_website"):
        hits.append(Hit("T5", True, detail="hidden form field filled"))
    if path.startswith("/docs/agent-verify"):
        hits.append(Hit("T7", True, detail="followed AI-only note"))
    return hits


def scored_hits(req: RequestView, session: Session, now: float) -> list[Hit]:
    hits: list[Hit] = []
    blob = f"{req.path}?{req.query}\n{req.headers_blob}\n{req.body[:4096].decode('utf-8', 'ignore')}"
    for name, pattern in SIGNATURES:
        if pattern.search(blob):
            hits.append(Hit("T8", False, 40, f"signature: {name}"))
            break
    match = ENUMERABLE.match(req.path)
    if match:
        session.ids_seen.append((now, match.group(0)))
        recent = {i for t, i in session.ids_seen if now - t <= 60}
        if len(recent) >= 5:
            hits.append(Hit("T10", False, 35, f"{len(recent)} record IDs in 60 s"))
    session.hits.append(now)
    if sum(1 for t in session.hits if now - t <= 10) > 50:
        hits.append(Hit("T11", False, 20, "over 5 requests/s for 10 s"))
    if TOOL_AGENTS.search(req.user_agent or ""):
        if not any(h.tripwire == "T12" for h in hits) and session.risk < 30:
            hits.append(Hit("T12", False, 30, "tool user agent"))
    return hits


def not_found_hit(session: Session, status: int, now: float) -> Hit | None:
    if status != 404:
        return None
    session.not_found.append(now)
    recent = sum(1 for t in session.not_found if now - t <= 30)
    if recent == 8:
        return Hit("T9", False, 25, "8 not-found responses in 30 s")
    return None


def dynamic_hits(req: RequestView, session: Session, rules: list[DynamicRule], now: float) -> list[Hit]:
    return [
        Hit(r.rule_id, r.action == "flip", r.score, "approved rule")
        for r in rules
        if r.expires > now and r.matches(req, session)
    ]


def infer_stage(path: str, set_cookie: str) -> str | None:
    """Stage the request suggests (only ever moves a session forward)."""
    if "hl_admin=" in set_cookie:
        return "access"
    if path.startswith(("/admin/infra", "/admin/console")):
        return "discovery"
    if any(k in path for k in ("/export", ".csv", "weights", ".env.production", ".sql.gz", "vault-admin-token")):
        return "collection"
    return None
