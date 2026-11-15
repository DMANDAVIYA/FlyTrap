"""Turn a db-backup (the zip or its unpacked folder) into runs the mock can replay.

    python backup_runs.py "~/Downloads/db-backup.zip"               # list the runs inside
    python backup_runs.py "~/Downloads/db-backup.zip" --runs 16 15  # write mock_runs/<start>.jsonl.gz

A run is everything from one "Release the swarm" to the next stop or reset, sorted by
event id (the CSV is not) and passed through mapper.row_to_message exactly as the live
backend would. The backup keeps only the final row of each session and no stats history,
so `session` and `stats` messages are rebuilt from the same rows: a session is sent when it
first appears, when Argus labels it, when it is flipped or blocked, and at its last event;
stats are recomputed every 2 s with the live formulas (stats.classify_exposure included).
"""

from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from mapper import count_records, envelope, iso, row_to_message, session_data
from stats import LABELS, classify_exposure

HERE = Path(__file__).resolve().parent
TICK = timedelta(seconds=2)
IDLE = timedelta(seconds=10)  # no stats line while nothing happened for this long, so the player can skip the silence
INT_COLS = ("id", "status", "req_bytes", "resp_bytes")
FLOAT_COLS = ("latency_ms", "gw_ms")

csv.field_size_limit(sys.maxsize)


# ---- reading the backup -------------------------------------------------------------------------
@contextmanager
def table(src: Path, name: str) -> Iterator[csv.DictReader]:
    """Open flytrap/<name>.csv from the zip or the folder."""
    if src.suffix == ".zip":
        with zipfile.ZipFile(src) as zf:
            member = next(m for m in zf.namelist() if m.endswith(f"flytrap/{name}.csv"))
            with zf.open(member) as raw:
                yield csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
    else:
        path = next(src.rglob(f"flytrap/{name}.csv"))
        with path.open(encoding="utf-8", newline="") as fh:
            yield csv.DictReader(fh)


def pg_array(text: str) -> list[str]:
    """Postgres text[] literal ({a,"b c"}) -> list. Empty or NULL -> []."""
    text = text.strip()
    if len(text) < 2 or text == "{}":
        return []
    return next(csv.reader([text[1:-1]], skipinitialspace=True))


def ts_of(text: str) -> datetime:
    return datetime.fromisoformat(text)


def event_row(raw: dict[str, str]) -> dict[str, Any]:
    """A CSV row typed the way asyncpg hands it to mapper.row_to_message (empty string = NULL)."""
    row: dict[str, Any] = {k: (v if v != "" else None) for k, v in raw.items()}
    row["ts"] = ts_of(raw["ts"])
    for col in INT_COLS:
        row[col] = int(row[col]) if row[col] is not None else None
    for col in FLOAT_COLS:
        row[col] = float(row[col]) if row[col] is not None else None
    row["records"] = pg_array(raw["records"]) or None
    row.pop("src_ip", None)  # never sent to the dashboard
    return row


def final_sessions(src: Path) -> dict[str, dict[str, Any]]:
    out = {}
    with table(src, "sessions") as rows:
        for r in rows:
            out[r["session_id"]] = {
                "raider": r["raider"] or None, "user_agent": r["user_agent"] or None, "side": r["side"] or "real",
                "pod": r["pod"] or None, "flipped_by": r["flipped_by"] or None, "flip_kind": r["flip_kind"] or None,
                "risk": int(r["risk"] or 0), "pace": r["pace"] or "normal", "label": r["label"] or "unknown",
                "confidence": float(r["confidence"]) if r["confidence"] else None,
                "reasons": json.loads(r["reasons"]) if r["reasons"] else None,
                "stage": r["stage"] or "done", "ladder": r["ladder"] or "watch",
            }
    return out


def find_runs(src: Path) -> list[dict[str, Any]]:
    """One pass over events: where each run starts and ends (by id), and what it holds."""
    marks: list[tuple[int, datetime, str, str]] = []
    with table(src, "events") as rows:
        for r in rows:
            k = r["kind"]
            if k in ("swarm", "flip", "thought", "action", "report", "canary", "lockdown", "request"):
                state = json.loads(r["payload"]).get("state", "") if k == "swarm" else ""
                marks.append((int(r["id"]), ts_of(r["ts"]), k, state))
    marks.sort()
    runs: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for eid, ts, kind, state in marks:
        if kind == "swarm" and state == "released":
            cur = {"first": eid, "last": eid, "start": ts, "end": ts, "open": True, "counts": Counter()}
            runs.append(cur)
            continue
        if cur is None or not cur["open"]:
            continue
        cur["last"], cur["end"] = eid, max(cur["end"], ts)
        cur["counts"][kind] += 1
        if kind == "swarm" and state in ("stopped", "reset"):
            cur["open"] = False  # the run ends at the kill switch or reset
    for i, run in enumerate(runs):
        run["index"] = i
        run["id"] = run["start"].strftime("%Y%m%d-%H%M%S")
    return runs


# ---- rebuilding sessions and stats ----------------------------------------------------------------
def pct(values: list[float], q: float) -> float | None:
    """percentile_cont over a sorted list."""
    if not values:
        return None
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


class Rebuild:
    """Replays one run's rows and yields the envelopes the live dash-api would have sent."""

    def __init__(self, rows: list[dict[str, Any]], finals: dict[str, dict[str, Any]]) -> None:
        self.rows = rows
        self.finals = finals
        self.start = rows[0]["ts"]
        self.last_row = {}
        for r in rows:
            if r["session_id"] and r["session_id"] != "-":
                self.last_row[r["session_id"]] = r["id"]
        self.sessions: dict[str, dict[str, Any]] = {}
        self.sent_at: dict[str, datetime] = {}
        self.fake_total = 0
        self.by_raider: Counter[str] = Counter()
        self.real_ledger: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.canaries = 0
        self.flip_ms: list[float] = []
        self.tripwires: Counter[str] = Counter()
        self.requests = 0
        self.req_times: list[tuple[datetime, str, float | None]] = []

    def _session(self, sid: str, ts: datetime, **change: Any) -> dict[str, Any]:
        s = self.sessions.get(sid)
        if s is None:
            f = self.finals.get(sid, {})
            s = {
                "session_id": sid, "first_seen": ts, "raider": f.get("raider"), "user_agent": f.get("user_agent"),
                "side": "real", "pod": None, "flipped_by": None, "flip_kind": None, "risk": 0, "pace": "normal",
                "label": "unknown", "confidence": None, "reasons": None, "stage": "recon", "ladder": "watch", "ended": False,
            }
            self.sessions[sid] = s
        s.update(change)
        s["last_seen"] = ts
        return s

    def _send(self, sid: str, ts: datetime) -> dict[str, Any]:
        self.sent_at[sid] = ts
        return envelope("session", session_data(self.sessions[sid]), iso(ts))

    def stats(self, at: datetime) -> dict[str, Any]:
        trapped = {sid for sid, s in self.sessions.items() if s["side"] in ("trap", "blocked")}
        other, own = classify_exposure([r for sid in trapped for r in self.real_ledger.get(sid, [])])
        recent = [x for x in self.req_times if x[0] > at - timedelta(seconds=5)]
        gw = sorted(x[2] for x in self.req_times if x[0] > at - timedelta(seconds=60) and x[2] is not None)
        labels = {label: 0 for label in LABELS}
        for s in self.sessions.values():
            labels[s["label"] if s["label"] in labels else "unknown"] += 1
        p50, p95 = pct(gw, 0.5), pct(gw, 0.95)
        return {
            "real_records_exposed": other,
            "real_own_records": own,
            "fake_records_taken": self.fake_total,
            "trapped": len(trapped),
            "canaries_fired": self.canaries,
            "avg_flip_ms": round(sum(self.flip_ms) / len(self.flip_ms), 3) if self.flip_ms else None,
            "rps_real": round(sum(1 for x in recent if x[1] == "real") / 5, 2),
            "rps_trap": round(sum(1 for x in recent if x[1] in ("trap", "blocked")) / 5, 2),
            "p50_gw_ms": round(p50, 3) if p50 is not None else None,
            "p95_gw_ms": round(p95, 3) if p95 is not None else None,
            "sessions_by_label": labels,
            "active_sessions": sum(1 for s in self.sessions.values() if s["last_seen"] > at - timedelta(seconds=60)),
            "records_by_raider": dict(self.by_raider),
            "tripwire_counts": dict(self.tripwires),
            "requests_total": self.requests,
            "since": iso(self.start),
        }

    def messages(self) -> Iterator[dict[str, Any]]:
        tick = self.start + TICK
        last_activity = self.start
        for row in self.rows:
            ts = row["ts"]
            while tick <= ts:
                if tick - last_activity <= IDLE:
                    yield envelope("stats", self.stats(tick), iso(tick))
                tick += TICK
            last_activity = ts
            sid = row["session_id"] if row["session_id"] not in (None, "-") else None
            kind = row["kind"]
            p = json.loads(row["payload"]) if row.get("payload") else {}

            if sid and sid not in self.sessions:
                self._session(sid, ts)
                yield self._send(sid, ts)
            yield row_to_message(row)

            # counters for the stats line
            records = row.get("records") or []
            if kind == "request":
                self.requests += 1
                self.req_times.append((ts, row.get("side") or "real", row.get("gw_ms")))
            if records and row.get("side") == "trap":
                n = count_records(records)
                self.fake_total += n
                self.by_raider[(self.finals.get(sid or "", {}).get("raider")) or p.get("raider") or "unknown"] += n
            if records and row.get("side") == "real" and sid:
                self.real_ledger[sid].append({"session_id": sid, "path": row.get("path"), "status": row.get("status"), "records": records})
            if kind == "canary":
                self.canaries += 1
            if kind == "tripwire" and row.get("tripwire"):
                self.tripwires[row["tripwire"]] += 1
            if kind == "flip":
                ms = p.get("gw_ms", row.get("gw_ms"))
                if ms is not None:
                    self.flip_ms.append(float(ms))

            # session changes, as the sessions table would have shown them
            changed: dict[str, Any] | None = None
            target = sid
            if kind == "flip" and sid:
                f = self.finals.get(sid, {})
                changed = {"side": "trap", "pod": p.get("pod") or row.get("pod"), "flip_kind": p.get("flip_kind") or f.get("flip_kind"),
                           "flipped_by": f.get("flipped_by") or p.get("flip_kind"), "stage": "bait", "ladder": f.get("ladder") or "engage"}
            elif kind == "request" and row.get("side") == "blocked" and sid and self.sessions[sid]["side"] != "blocked":
                changed = {"side": "blocked"}
            elif kind == "tripwire" and sid and p.get("risk") is not None:
                changed = {"risk": max(self.sessions[sid]["risk"], int(p.get("risk") or 0))}
            elif kind == "action" and p.get("status", "done") == "done":
                args = p.get("args") or {}
                target = args.get("session") or sid
                if target and target in self.sessions:
                    if p.get("tool") == "label_session":
                        changed = {"label": args.get("label") or "unknown", "confidence": args.get("confidence"), "reasons": args.get("reasons")}
                    elif p.get("tool") == "set_pace":
                        changed = {"pace": args.get("mode") or args.get("pace") or "slow"}
                    elif p.get("tool") == "block":
                        changed = {"side": "blocked"}
            if changed and target:
                self._session(target, ts, **changed)
                yield self._send(target, ts)
            elif sid and ts - self.sent_at.get(sid, ts) > timedelta(seconds=15):
                self._session(sid, ts)
                yield self._send(sid, ts)  # last_seen refresh, like the live 15 s rule

            if sid and self.last_row.get(sid) == row["id"]:
                # the session's last event in this run: settle on its final row where the run agrees with it
                f = self.finals.get(sid, {})
                s = self.sessions[sid]
                settle = {"stage": f.get("stage", "done"), "ended": True, "label": f.get("label", s["label"]),
                          "confidence": f.get("confidence", s["confidence"]), "reasons": f.get("reasons", s["reasons"])}
                if s["side"] == f.get("side"):
                    settle.update(risk=max(s["risk"], f.get("risk", 0)), pace=f.get("pace", s["pace"]), ladder=f.get("ladder", s["ladder"]))
                self._session(sid, ts, **settle)
                yield self._send(sid, ts)
        yield envelope("stats", self.stats(self.rows[-1]["ts"]), iso(self.rows[-1]["ts"]))


def load_rows(src: Path, first: int, last: int) -> list[dict[str, Any]]:
    rows = []
    with table(src, "events") as reader:
        for r in reader:
            if first <= int(r["id"]) <= last:
                rows.append(event_row(r))
    rows.sort(key=lambda r: r["id"])
    return rows


def write_run(src: Path, run: dict[str, Any], finals: dict[str, dict[str, Any]], out_dir: Path) -> Path:
    rows = load_rows(src, run["first"], run["last"])
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{run['id']}.jsonl.gz"
    kinds: Counter[str] = Counter()
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for msg in Rebuild(rows, finals).messages():
            kinds[msg["type"]] += 1
            fh.write(json.dumps(msg, separators=(",", ":"), default=str) + "\n")
    print(f"wrote {path.name}: {sum(kinds.values())} messages {dict(kinds.most_common())}, {path.stat().st_size // 1024} KB")
    return path


def _self_check() -> None:
    assert pg_array("") == [] and pg_array("{}") == []
    assert pg_array('{user:41,"invoice:9001-9020"}') == ["user:41", "invoice:9001-9020"]
    assert count_records(pg_array("{model:1,model:5-7}")) == 4
    assert pct([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5 and pct([], 0.5) is None


def main() -> None:
    parser = argparse.ArgumentParser(description="Turn a db-backup into replayable mock runs")
    parser.add_argument("backup", type=Path, help="db-backup .zip, or the folder it unpacks to")
    parser.add_argument("--runs", type=int, nargs="*", help="run numbers from the listing to write")
    parser.add_argument("--out", type=Path, default=HERE / "mock_runs")
    args = parser.parse_args()
    _self_check()
    src = args.backup.expanduser()
    runs = find_runs(src)
    for run in runs:
        c = run["counts"]
        dur = (run["end"] - run["start"]).total_seconds()
        print(f"#{run['index']:2} {run['id']} {dur:6.0f}s requests={c['request']:6} flips={c['flip']:3} "
              f"thoughts={c['thought']:4} actions={c['action']:4} reports={c['report']:3} canaries={c['canary']:3} lockdowns={c['lockdown']}")
    if args.runs:
        finals = final_sessions(src)
        for n in args.runs:
            write_run(src, runs[n], finals, args.out)


if __name__ == "__main__":
    main()
