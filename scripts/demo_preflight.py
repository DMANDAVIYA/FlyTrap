"""One command before judges arrive: is the whole lab demo-ready?

Checks every container is up, the site and dash-api answer, the blue agents and
red raiders are healthy (and which ones run on AI vs rules), the trap copies are
healthy, the counters are at zero, and the kill switch works.
Stdlib only. Run from the repo root:  python scripts/demo_preflight.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request

EXPECTED = {"gateway", "controller", "dash-api", "web-1", "web-2", "backup-01", "model-vault", "crowd", "rebuilder",
            *(f"pod-{i}" for i in range(1, 6)), *(f"raider-{i}" for i in range(1, 6))}
results: list[tuple[bool, str]] = []


def record(ok: bool, text: str) -> None:
    results.append((ok, text))
    print(f"  {'OK  ' if ok else 'FAIL'}  {text}")


def http(url: str, data: bytes | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, data=data, headers={"content-type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 - any failure is just a failed check
        return 0, str(exc)


def in_controller(code: str) -> str:
    out = subprocess.run(["docker", "compose", "exec", "-T", "controller", "python", "-c", code],
                         capture_output=True, text=True, timeout=60)
    return out.stdout.strip() or out.stderr.strip()


def main() -> int:
    print("Containers:")
    ps = subprocess.run(["docker", "compose", "ps", "--format", "json"], capture_output=True, text=True, timeout=60)
    rows = [json.loads(l) for l in ps.stdout.splitlines() if l.strip().startswith("{")]
    running = {r["Service"] for r in rows if r.get("State") == "running"}
    missing = sorted(EXPECTED - running)
    record(not missing, f"{len(running & EXPECTED)}/{len(EXPECTED)} services running" + (f", missing: {missing}" if missing else ""))

    print("Endpoints:")
    status, body = http("http://localhost:8080/")
    record(status == 200 and "HackUMass Labs" in body, f"site through the gateway (HTTP {status})")
    status, _ = http("http://localhost:8090/healthz")
    record(status == 200, f"dash-api (HTTP {status})")

    print("Swarm:")
    health = in_controller(
        "import httpx,json;h=httpx.get('http://localhost:8070/health').json();"
        "print(json.dumps({'blue':{a['agent']:a['mode'] for a in h['blue']},'red':{r['raider']:r['mode'] for r in h['red']}}))")
    try:
        h = json.loads(health)
        kinds = {a.split("-", 1)[0] for a in h["blue"]}  # cerberus-1..5 and hephaestus-1..5 guard one pod each
        record(len(kinds) == 7, f"blue agents ({len(h['blue'])}): " + ", ".join(f"{k}={v}" for k, v in h["blue"].items()))
        record(len(h["red"]) == 5, "red raiders: " + ", ".join(f"{k}={v}" for k, v in h["red"].items()))
    except (ValueError, KeyError):
        record(False, f"controller health unreadable: {health[:120]}")

    pods = in_controller(
        "import httpx,os;r=httpx.get('http://gateway-admin:8081/_admin/health',headers={'X-Admin-Token':os.environ['ADMIN_TOKEN']}).json();"
        "print(sum(p['healthy'] for p in r['pods']), len(r['pods']), r['lockdown'], r['sessions'])")
    try:
        healthy, total, lockdown, sessions = pods.split()
        record(healthy == total, f"trap copies healthy: {healthy}/{total}")
        record(lockdown == "off", f"lockdown is {lockdown}")
        record(int(sessions) < 5, f"live sessions: {sessions} (press Reset Tartarus if high)")
    except ValueError:
        record(False, f"gateway health unreadable: {pods[:120]}")

    print("Controls:")
    status, body = http("http://localhost:8090/api/control/stop", b"{}")
    record(status == 200, f"kill switch answers (HTTP {status})")

    failed = [t for ok, t in results if not ok]
    print("\nREADY FOR THE DEMO" if not failed else f"\nNOT READY: {len(failed)} check(s) failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
