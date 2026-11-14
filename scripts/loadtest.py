"""Load test: how Charon behaves with a crowd, drones, the red swarm and extra traffic at once.

Releases the swarm with --crowd customers and --drones scanners, adds --workers threads of
normal browsing from this machine for --seconds, samples dash-api's live stats, then stops
the swarm and prints only measured numbers. Stdlib only.

    python scripts/loadtest.py --crowd 40 --drones 10 --workers 16 --seconds 60
Press Reset Tartarus afterwards.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import threading
import time
import urllib.error
import urllib.request

SITE, DASH = "http://localhost:8080", "http://localhost:8090"
PAGES = ["/", "/pricing", "/models", "/about", "/login", "/docs", "/api/v1/models", "/static/site.css"]


def post(url: str, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def stats() -> dict:
    with urllib.request.urlopen(f"{DASH}/api/state", timeout=15) as r:
        return json.loads(r.read()).get("stats", {})


def browse(worker: int, until: float, latencies: list, errors: list) -> None:
    ua = f"Mozilla/5.0 (loadtest browser {worker})"
    while time.time() < until:
        req = urllib.request.Request(SITE + random.choice(PAGES), headers={"User-Agent": ua})
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                r.read()
            latencies.append((time.perf_counter() - started) * 1000)
        except (urllib.error.URLError, TimeoutError) as exc:
            errors.append(str(exc)[:60])


def pct(values: list[float], p: float) -> float:
    return round(sorted(values)[min(len(values) - 1, int(len(values) * p))], 1) if values else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crowd", type=int, default=40)
    ap.add_argument("--drones", type=int, default=10)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--seconds", type=int, default=60)
    a = ap.parse_args()

    post(f"{DASH}/api/control/reset", {})
    time.sleep(3)
    released = post(f"{DASH}/api/control/release", {"crowd": a.crowd, "drones": a.drones})
    raiders = len(released.get("started", []))
    until = time.time() + a.seconds
    latencies: list[float] = []
    errors: list[str] = []
    threads = [threading.Thread(target=browse, args=(i, until, latencies, errors), daemon=True) for i in range(a.workers)]
    for t in threads:
        t.start()
    samples = []
    while time.time() < until:
        time.sleep(5)
        try:
            samples.append(stats())
        except (urllib.error.URLError, TimeoutError):
            pass
    for t in threads:
        t.join(timeout=20)
    final = stats()
    post(f"{DASH}/api/control/stop", {})

    rps = [s.get("rps_real", 0) + s.get("rps_trap", 0) for s in samples]
    p50s = [s.get("p50_gw_ms", 0) for s in samples if s.get("p50_gw_ms")]
    p95s = [s.get("p95_gw_ms", 0) for s in samples if s.get("p95_gw_ms")]
    print(f"Load: {a.crowd} customers, {a.drones} drones, {raiders} raiders, {a.workers} extra browsers, {a.seconds}s")
    print(f"  extra browsers: {len(latencies)} requests, {len(latencies) / a.seconds:.0f} req/s, "
          f"latency p50 {pct(latencies, 0.5)} ms, p95 {pct(latencies, 0.95)} ms, p99 {pct(latencies, 0.99)} ms, "
          f"errors {len(errors)}")
    print(f"  gateway total (dash-api): peak {max(rps, default=0):.0f} req/s, mean {statistics.mean(rps) if rps else 0:.0f} req/s")
    print(f"  gateway decision time: p50 {max(p50s, default=0):.3f} ms, p95 {max(p95s, default=0):.3f} ms (worst sample)")
    print(f"  trapped sessions: {final.get('trapped')}, flip time avg {final.get('avg_flip_ms')} ms")
    print(f"  real records exposed: {final.get('real_records_exposed')}")


if __name__ == "__main__":
    main()
