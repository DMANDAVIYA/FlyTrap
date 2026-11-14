import asyncio

import pytest

from app import bait
from app.raiders.loot import LootBoard
from app.raiders.runner import ScopeError, check_path
from app.scorer import score


def base(**over):
    s = {"session": "s_1", "requests_total": 10, "median_gap_s": 3.0, "gap_spread_s": 3.0, "js_beacon": False,
         "mouse_keys": 0, "assets_loaded": 0, "not_found": 0, "tripwires": [], "followed_ai_note": None,
         "tool_user_agent": False, "last_event": 99}
    s.update(over)
    return s


def test_human_from_browser_signals():
    v = score(base(js_beacon=True, mouse_keys=20, assets_loaded=3))
    assert v.label == "human" and v.confidence > 0.6


def test_ai_agent_from_hidden_note():
    v = score(base(followed_ai_note={"event": 50, "seconds_after_page": 1.2},
                   tripwires=[{"id": "T1", "event": 40}, {"id": "T3", "event": 41}]))
    assert v.label == "ai_agent" and 50 in v.evidence


def test_scanner_from_speed_and_tool_agent():
    v = score(base(median_gap_s=0.1, requests_total=30, tool_user_agent=True, not_found=6))
    assert v.label == "scanner"


def test_unknown_when_quiet():
    assert score(base(requests_total=1)).label == "unknown"


def test_bait_formats():
    token = bait.api_token()
    assert token.startswith("hl_live_") and len(token) == 32
    key_id, secret = bait.cloud_key()
    assert key_id.startswith("HLK") and len(key_id) == 20
    assert secret.startswith("hlsk_") and len(secret) == 37
    assert bait.canary_customer().endswith(".example")
    # each planted value is unique
    assert bait.api_token() != bait.api_token()


def test_loot_sharing_links_raiders():
    board = LootBoard()
    token = "hl_live_" + "A" * 24
    board.scan("prometheus", "/.env", f"KEY={token}")
    assert board.first("api_token", not_from="pandora").value == token
    assert len(board.shared_with("pandora")) == 1
    assert board.shared_with("prometheus") == []


def test_runner_scope_blocks_offsite():
    assert check_path("/login") == "/login"
    for bad in ("http://evil.com", "//evil.com", "https://x", "\\\\host"):
        with pytest.raises(ScopeError):
            check_path(bad)


def test_policy_rejects_tool_outside_allowlist():
    from app.config import Settings
    from app.context import Ctx, SwarmState
    from app.policy import Policy

    class FakeDB:
        async def insert_action(self, *a, **k):
            return 1

        async def emit(self, *a, **k):
            return 1

    ctx = Ctx(settings=Settings(), db=FakeDB(), gw=None, http=None, state=SwarmState())
    policy = Policy(ctx)
    # cerberus does not hold plant_bait
    result = asyncio.run(policy.execute("cerberus", "plant_bait", {"session": "s_1", "kind": "api_token", "where": "account"}))
    assert not result.ok and result.status == "rejected"
