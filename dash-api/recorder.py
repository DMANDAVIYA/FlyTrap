"""Record every outgoing live message to runs/<run_id>.jsonl so any run can be replayed.

One line per message: the envelope exactly as sent (it carries its own ts).
A new run file starts when dash-api starts and again on every
{"type": "swarm", "data": {"state": "released"}} so each "Release the swarm"
is its own replayable run. Run id = UTC start time, e.g. 20261114-224107.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

log = logging.getLogger("dash.recorder")

RUN_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
SKIP_TYPES = {"replay"}


class Recorder:
    def __init__(self, runs_dir: Path, enabled: bool = True) -> None:
        self.dir = runs_dir
        self.enabled = enabled
        self.run_id: str | None = None
        self._fh: IO[str] | None = None
        self._lines = 0
        if enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def start_run(self) -> str:
        self.close()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        n = 1
        while (self.dir / f"{run_id}.jsonl").exists():
            n += 1
            run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{n}"
        self.run_id = run_id
        self._fh = (self.dir / f"{run_id}.jsonl").open("a", encoding="utf-8", buffering=1)
        self._lines = 0
        log.info("recording run %s", run_id)
        return run_id

    def tap(self, msg: dict[str, Any], text: str) -> None:
        if not self.enabled or msg.get("type") in SKIP_TYPES:
            return
        data = msg.get("data") or {}
        if msg.get("type") == "swarm" and data.get("state") == "released" and self._lines:
            self.start_run()
        if self._fh is None:
            self.start_run()
        assert self._fh is not None
        self._fh.write(text + "\n")
        self._lines += 1

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


def _ts_of(line: str) -> str | None:
    try:
        return json.loads(line).get("ts")
    except ValueError:
        return None


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def describe(path: Path) -> dict[str, Any]:
    first = last = None
    with path.open("rb") as fh:
        head = fh.readline().decode("utf-8", "replace")
        first = _ts_of(head)
        size = path.stat().st_size
        fh.seek(max(0, size - 65536))
        tail = fh.read().decode("utf-8", "replace").strip().splitlines()
        if tail:
            last = _ts_of(tail[-1])
    start, end = _parse(first), _parse(last)
    return {
        "run": path.stem,
        "bytes": path.stat().st_size,
        "started": first,
        "ended": last,
        "duration_s": round((end - start).total_seconds(), 1) if start and end else None,
    }


def list_runs(runs_dir: Path) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        return []
    out = []
    for path in sorted(runs_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            out.append(describe(path))
        except OSError:
            continue
    return out


def run_path(runs_dir: Path, run: str) -> Path | None:
    if not RUN_ID.match(run):
        return None
    path = runs_dir / f"{run}.jsonl"
    return path if path.is_file() else None
