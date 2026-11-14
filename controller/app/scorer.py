"""Argus's rules: label a session human, scanner or AI agent, with reasons.

Follows Palisade Research's two-gate idea (obeys a hidden instruction and
reacts at machine speed) plus browser signals. Weights are calibrated on our
own test runs; never quote an accuracy figure we didn't measure.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Verdict:
    label: str
    confidence: float
    reasons: list[str]
    evidence: list[int]


def score(s: dict) -> Verdict:
    points = {"human": 0.0, "scanner": 0.0, "ai_agent": 0.0}
    why: dict[str, list[tuple[float, str]]] = {k: [] for k in points}

    def add(label: str, pts: float, reason: str) -> None:
        points[label] += pts
        why[label].append((pts, reason))

    gap, spread = s.get("median_gap_s"), s.get("gap_spread_s")
    if s.get("js_beacon"):
        add("human", 40, "ran the page's JavaScript")
    if s.get("mouse_keys", 0) > 0:
        add("human", 20, "moved the mouse or typed")
    if s.get("assets_loaded", 0) >= 2:
        add("human", 10, "loaded stylesheets and images")
    if gap is not None and gap > 2 and (spread or 0) > 2:
        add("human", 10, "irregular pauses between pages")
    if s.get("tool_user_agent"):
        add("scanner", 30, "scripting-tool user agent")
    if gap is not None and gap < 0.4 and s.get("requests_total", 0) >= 8:
        add("scanner", 30, f"machine-speed requests ({gap} s apart)")
    if s.get("not_found", 0) >= 5:
        add("scanner", 20, f"{s['not_found']} not-found responses")
    if any(t["id"] == "T8" for t in s.get("tripwires", [])):
        add("scanner", 15, "matched attack signatures")
    note = s.get("followed_ai_note")
    if note:
        add("ai_agent", 60, "obeyed the hidden note only AI agents read")
        if note.get("seconds_after_page") is not None and note["seconds_after_page"] <= 20:
            add("ai_agent", 20, f"followed it {note['seconds_after_page']} s after reading the page")
    if any(t["id"] in ("T1", "T3") for t in s.get("tripwires", [])):
        add("ai_agent", 15, "read robots.txt or page source and acted on it")
    if gap is not None and 1 <= gap <= 15 and not s.get("js_beacon"):
        add("ai_agent", 10, f"thinking pauses of about {gap} s")
    if not s.get("js_beacon") and s.get("requests_total", 0) >= 5:
        add("ai_agent", 5, "never ran JavaScript")
        add("scanner", 5, "never ran JavaScript")

    best = max(points, key=points.get)
    total = sum(points.values())
    if points[best] < 30:
        return Verdict("unknown", 0.0, ["not enough signal yet"], [])
    confidence = round(min(0.99, 0.5 + 0.5 * points[best] / max(total, 1)), 2)
    reasons = [r for _, r in sorted(why[best], reverse=True)[:3]]
    evidence = [t["event"] for t in s.get("tripwires", [])][:4]
    if note:
        evidence.append(note["event"])
    return Verdict(best, confidence, reasons, sorted(set(evidence)))
