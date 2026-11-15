"""Crawl the trap copies through the gateway and fail on anything that gives the trap away.

Gets itself flipped into Tartarus on purpose (requests /.env), logs into the decoy admin
panel with the migration login from the page comment, then visits every page and checks:
  - no giveaway words in bodies (pod, trap, honeypot, fake, flytrap, dolos, edge, canary)
  - no internal headers reach the visitor (X-Edge-*, X-Raider)
Stdlib only. Run with the stack up:  python scripts/leakcheck.py [--base http://localhost:8080]
Run "Reset Tartarus" afterwards; this crawl leaves one trapped session behind.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

WORDS = re.compile(r"\b(pods?|traps?|trapped|honeypots?|fake|flytrap|dolos|edge|canar(?:y|ies))\b", re.I)
INTERNAL = ("x-edge-", "x-raider")
PUBLIC = ["/", "/pricing", "/about", "/models", "/login", "/signup", "/contact", "/docs", "/robots.txt",
          "/api/v1/models", "/this-page-does-not-exist"]
TRAP = ["/.env", "/.git/config", "/internal-backup/", "/admin-legacy/", "/docs/agent-verify?k=0"]
ADMIN = ["/admin/", "/admin/customers", "/admin/keys", "/admin/infra", "/admin/console",
         "/admin/infra/backup-01/", "/admin/infra/model-vault/"]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def make_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect)
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (leak-check)")]
    return opener


def fetch(opener, base: str, path: str, data: bytes | None = None) -> tuple[int, dict, str]:
    req = urllib.request.Request(base + path, data=data)
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, dict(r.headers.items()), r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers.items()), e.read(200_000).decode("utf-8", "replace")


def check(path: str, status: int, headers: dict, body: str, problems: list[str]) -> None:
    leaked = [h for h in headers if h.lower().startswith(INTERNAL)]
    if leaked:
        problems.append(f"{path}: internal headers leaked: {leaked}")
    words = sorted({m.group(0).lower() for m in WORDS.finditer(body)})
    if words:
        problems.append(f"{path}: giveaway words in body: {words}")
    print(f"  {status}  {path}{'  <-- problem' if leaked or words else ''}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8080")
    base = parser.parse_args().base.rstrip("/")
    opener, problems = make_opener(), []

    print("Real side (before the flip):")
    for path in PUBLIC:
        check(path, *fetch(opener, base, path), problems)
    login_page = fetch(opener, base, "/login")[2]

    print("Trap side (this session is now flipped):")
    for path in TRAP:
        check(path, *fetch(opener, base, path), problems)

    match = re.search(r"hlm-[A-Za-z0-9]{10}", login_page)
    if match:
        form = urllib.parse.urlencode({"username": "ops-migrate", "password": match.group(0)}).encode()
        fetch(opener, base, "/admin/login", form)
        for path in ADMIN:
            check(path, *fetch(opener, base, path), problems)
    else:
        problems.append("/login: migration login comment not found, admin pages not checked")

    print()
    if problems:
        print(f"LEAK CHECK FAILED: {len(problems)} problem(s)")
        for p in problems:
            print("  - " + p)
        return 1
    print("LEAK CHECK PASSED: no giveaway words, no internal headers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
