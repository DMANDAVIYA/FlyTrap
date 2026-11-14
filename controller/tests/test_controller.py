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


def test_app_imports_cleanly():
    """Importing the app must not fail; a bad import here would crash the container on start."""
    import app.main  # noqa: F401


def test_demo_password_matches_site():
    """Same formula as hlabs/app/bait.py; value computed from the site's implementation."""
    assert bait.demo_password("test-secret") == "WIJHRQkkrGVmp7n2"


def test_records_counting():
    from app import records
    assert records.count("user:41") == 1
    assert records.count("invoice:9001-9020") == 20
    assert records.by_type(["user:1-500", "api_token:3", "user:900"]) == {"user": 501, "api_token": 1}


def test_swarm_state_clear_keeps_demo_mode():
    from app.context import SwarmState
    s = SwarmState(demo_mode=False)
    s.planted.add("s_1")
    s.lockdown_requested_at = 1.0
    s.clear()
    assert s.demo_mode is False and not s.planted and s.lockdown_requested_at is None


def test_plan_act_accepts_evidence_as_tool_arg():
    """Regression: label_session passes its own `evidence` arg; it must not clash with the citation."""
    from app.swarm.plan import Plan
    plan = Plan()
    plan.act("label_session", "why", [7], session="s_1", label="ai_agent", evidence=[7, 8])
    plan.act("alert", "why", session="s_1", message="m", evidence=[9])
    assert plan.intents[0].evidence == [7] and plan.intents[0].args["evidence"] == [7, 8]
    assert plan.intents[1].evidence == [9]


def test_policy_fills_required_reason_from_caller():
    """Regression: tools that require `reason` were rejected when the reason came separately."""
    from app.config import Settings
    from app.context import Ctx, SwarmState
    from app.policy import Policy

    logged = []

    class FakeDB:
        async def insert_action(self, actor, tool, session, args, reason, evidence, status):
            logged.append(status)
            return 1

        async def emit(self, *a, **k):
            return 1

    class FakeGW:
        async def lockdown(self, state, by, reason):
            return True, {"ok": True}

    ctx = Ctx(settings=Settings(), db=FakeDB(), gw=FakeGW(), http=None, state=SwarmState())
    result = asyncio.run(Policy(ctx).execute("athena", "request_lockdown", {}, "two sessions probed the real side"))
    assert result.ok and logged == ["done"]


def test_plan_act_accepts_reason_as_tool_arg():
    """Regression: link_campaign and request_lockdown pass their own `reason` argument."""
    from app.swarm.plan import Plan
    plan = Plan()
    plan.act("link_campaign", "log line", [3], sessions=["a", "b"], reason="key reused", evidence=[3])
    intent = plan.intents[0]
    assert intent.reason == "log line" and intent.args["reason"] == "key reused" and intent.evidence == [3]


def test_cheap_tools_do_not_exhaust_swarm_budget():
    """Regression: hundreds of labels must not starve drastic tools of the swarm-wide budget."""
    from app.config import Settings
    from app.context import Ctx, SwarmState
    from app.policy import Policy

    policy = Policy(Ctx(settings=Settings(), db=None, gw=None, http=None, state=SwarmState()))
    for i in range(500):
        assert policy._rate_ok("argus", "label_session", f"s_{i}")
    assert policy._rate_ok("athena", "request_lockdown", "-")
    # per-agent, per-tool, per-target cap still holds
    assert all(policy._rate_ok("cerberus", "block", "s_x") for _ in range(3))
    assert not policy._rate_ok("cerberus", "block", "s_x")


def test_lockdown_held_visitors_are_not_hunted():
    """Visitors moved into Tartarus only by lockdown get no bait, pacing, reports or fingerprints."""
    from app.context import Ctx, SwarmState
    from app.config import Settings
    from app.swarm import rules_mode

    ctx = Ctx(settings=Settings(), db=None, gw=None, http=None, state=SwarmState())
    held = {"session": "s_c", "side": "trap", "pod": "pod-1", "flip_kind": "lockdown", "stage": "collection",
            "pace": "normal", "records_taken": {}, "canaries_fired": [], "requests_total": 9, "real_records_served": []}
    caught = {**held, "session": "s_a", "flip_kind": "instant"}
    assert rules_mode.hephaestus(ctx, [held], []).intents == []
    assert rules_mode.cerberus(ctx, [held], []).intents == []
    assert [i.tool for i in rules_mode.hephaestus(ctx, [caught], []).intents] == ["plant_bait", "plant_bait"]


def test_deepseek_provider_is_known():
    from app.llm import LLM
    e = LLM("deepseek:deepseek-chat").endpoints[0]
    assert e.provider == "deepseek" and e.model == "deepseek-chat" and e.base == "https://api.deepseek.com"


def test_chain_skips_providers_without_keys(monkeypatch):
    from app.llm import LLM
    for k in ("QWEN_API_KEY", "KIMI_API_KEY", "GLM_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    llm = LLM("qwen:qwen-plus,kimi:kimi-k2,openrouter:qwen/qwen-plus,deepseek:deepseek-chat")
    assert llm.available and llm.label == "deepseek:deepseek-chat"
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    assert not LLM("qwen:qwen-plus,deepseek:deepseek-chat").available
    assert LLM("").label == "rules"


def test_chain_falls_through_on_failure(monkeypatch):
    from app.llm import LLM, LLMError, Endpoint, Reply
    Endpoint._down_until.clear()
    monkeypatch.setenv("QWEN_API_KEY", "k1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k2")
    llm = LLM("qwen:qwen-plus,deepseek:deepseek-chat")

    async def boom(*a, **k):
        raise LLMError("down")

    async def ok(*a, **k):
        return Reply("hi", model="deepseek:deepseek-chat")

    llm.endpoints[0].chat, llm.endpoints[1].chat = boom, ok
    reply = asyncio.run(llm.chat([{"role": "user", "content": "x"}]))
    assert reply.model == "deepseek:deepseek-chat"
    assert llm.label == "deepseek:deepseek-chat"  # qwen sits out after failing
    Endpoint._down_until.clear()


def test_base_url_override(monkeypatch):
    from app.llm import LLM
    monkeypatch.setenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/")
    assert LLM("qwen:qwen-plus").endpoints[0].base == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_request_body_per_provider(monkeypatch):
    """Claude 5.x and newer OpenAI models reject temperature; OpenAI wants max_completion_tokens."""
    import json as _json
    from app.llm import Endpoint
    sent = {}

    class FakeResp:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "OK"}}]}

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            sent[url] = json
            return FakeResp()

    monkeypatch.setattr("app.llm.httpx.AsyncClient", FakeClient)
    for spec, env in (("anthropic:claude-haiku-5-5", "ANTHROPIC_API_KEY"), ("openai:gpt-5-mini", "OPENAI_API_KEY"),
                      ("deepseek:deepseek-chat", "DEEPSEEK_API_KEY")):
        monkeypatch.setenv(env, "k")
        asyncio.run(Endpoint(spec, 5).chat([{"role": "user", "content": "x"}], None, 0.2, 10, False))
    bodies = list(sent.values())
    assert "temperature" not in bodies[0] and bodies[0]["max_tokens"] == 10            # anthropic
    assert "temperature" not in bodies[1] and bodies[1]["max_completion_tokens"] == 10  # openai
    assert bodies[2]["temperature"] == 0.2 and bodies[2]["max_tokens"] == 10            # deepseek


def test_per_agent_model_and_meta_provider(monkeypatch):
    from app.config import Settings
    from app.llm import LLM
    monkeypatch.setenv("BLUE_MODEL_ATHENA", "anthropic:claude-opus-5-5")
    monkeypatch.delenv("BLUE_MODEL_CERBERUS", raising=False)
    s = Settings(blue_model="gemini:gemini-3-flash-preview")
    assert s.blue_model_for("athena") == "anthropic:claude-opus-5-5"
    assert s.blue_model_for("cerberus") == "gemini:gemini-3-flash-preview"
    monkeypatch.setenv("MUSE_API_KEY", "k")
    e = LLM("meta:muse-spark-1.3").endpoints[0]
    assert e.base == "https://api.meta.ai/v1" and e.configured
