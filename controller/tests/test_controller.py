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
    assert llm.label == "qwen:qwen-plus"  # the first model is never benched, it is tried first on every call
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


def test_model_chains_live_in_code(monkeypatch):
    """Every AI agent has a chain in models.py, env model settings are ignored, providers are all known."""
    from app.llm import LLM, PROVIDERS
    from app.models import CHAINS, chain
    from app.raiders.personas import PERSONAS
    from app.swarm.roles import ROLES
    monkeypatch.setenv("BLUE_MODEL_ATHENA", "openai:gpt-4o")
    assert chain("athena").startswith("anthropic:claude-opus-5-5")
    assert chain("odysseus").startswith("kimi:kimi-k3.1-pro")
    assert chain("argus") == ""                                    # code-only role
    ai_agents = {r.name for r in ROLES if r.uses_ai} | {p.name for p in PERSONAS if p.default_mode == "ai"} | {"clio"}
    assert ai_agents <= set(CHAINS)
    assert {spec.split(":")[0] for models in CHAINS.values() for spec in models} <= set(PROVIDERS)
    from app.models import RED_PROVIDERS
    for p in PERSONAS:                                            # red team: Chinese models only
        assert {spec.split(":")[0] for spec in CHAINS[p.name]} <= RED_PROVIDERS, p.name
    assert chain("athena").startswith("anthropic:claude-opus-5-5")
    monkeypatch.setenv("MUSE_API_KEY", "k")
    e = LLM("meta:muse-spark-1.3").endpoints[0]
    assert e.base == "https://api.meta.ai/v1" and e.configured


def test_ai_agent_replaying_the_beacon_is_not_human():
    """Regression (AI run): an AI agent read px.js and replayed the beacon after touching bait."""
    v = score(base(js_beacon=True, mouse_keys=12, assets_loaded=2, median_gap_s=3.1, gap_spread_s=2.5,
                   tripwires=[{"id": "T2", "event": 70}]))
    assert v.label == "ai_agent"


def test_ai_agent_exploring_at_reading_pace_is_not_scanner():
    """Regression (AI run): many guessed paths at reading pace plus a hidden-link hit means AI, not scanner."""
    v = score(base(median_gap_s=2.8, not_found=9, requests_total=30, tripwires=[{"id": "T4", "event": 80}]))
    assert v.label == "ai_agent"


def test_fast_bait_toucher_is_still_scanner():
    v = score(base(median_gap_s=0.2, requests_total=20, tool_user_agent=True, not_found=7,
                   tripwires=[{"id": "T2", "event": 90}, {"id": "T1", "event": 91}]))
    assert v.label == "scanner"


def test_json_mode_skipped_for_anthropic(monkeypatch):
    """Anthropic's OpenAI-compatible API rejects response_format; others get it."""
    from app.llm import Endpoint
    sent = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            sent.append(json)
            return FakeResp()

    monkeypatch.setattr("app.llm.httpx.AsyncClient", FakeClient)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    for spec in ("anthropic:claude-opus-5-5", "deepseek:deepseek-v4-pro"):
        asyncio.run(Endpoint(spec, 5).chat([{"role": "user", "content": "x"}], None, 0.2, 10, True))
    assert "response_format" not in sent[0] and sent[1]["response_format"] == {"type": "json_object"}


def test_no_credits_sits_out_longer(monkeypatch):
    import time as _time
    from app.llm import LLM, LLMError, Endpoint, Reply, COOL_DOWN_S
    Endpoint._down_until.clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "k1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k2")
    llm = LLM("openrouter:qwen/qwen3.7-max,deepseek:deepseek-chat")

    async def broke(*a, **k):
        raise LLMError("openrouter HTTP 402: needs credits", 402)

    async def ok(*a, **k):
        return Reply("hi", model="deepseek:deepseek-chat")

    llm.endpoints[0].chat, llm.endpoints[1].chat = broke, ok
    asyncio.run(llm.chat([{"role": "user", "content": "x"}]))
    assert Endpoint._down_until["openrouter:qwen/qwen3.7-max"] - _time.monotonic() > COOL_DOWN_S * 5
    Endpoint._down_until.clear()


def test_report_words_tolerate_code_fences():
    from app.llm import Reply
    from app.swarm.report import _ai_words

    class FakeLLM:
        async def chat(self, *a, **k):
            return Reply('Here it is:\n```json\n{"summary": "s", "goal": "g"}\n```')

    assert asyncio.run(_ai_words(FakeLLM(), {}))["goal"] == "g"


def test_raider_nudged_when_it_replies_without_a_tool_call():
    from types import SimpleNamespace
    from app.llm import Reply, ToolCall
    from app.raiders.llm_raider import run_llm
    from app.raiders.runner import Page

    replies = [Reply("I would GET /login next."),
               Reply("", [ToolCall("c1", "http_request", {"method": "GET", "path": "/login", "reason": "look"})],
                     {"role": "assistant", "content": ""}),
               Reply("DONE")]
    seen = []

    class FakeLLM:
        async def chat(self, messages, **k):
            seen.append(messages[-1]["content"])
            return replies.pop(0)

    class FakeRun:
        calls = []
        async def do(self, *a, **k):
            FakeRun.calls.append(a)
            return Page(200, {}, "<html>login</html>", 1.0)

    async def emit(*a):
        pass

    persona = SimpleNamespace(name="odysseus", base="odysseus", objective="test", user_agent="ua")
    asyncio.run(run_llm(persona, FakeLLM(), FakeRun(), emit, LootBoard(), "pw", 10, 1, asyncio.Event()))
    assert len(FakeRun.calls) == 1 and "http_request tool" in seen[1] and not replies


def test_kimi_gets_no_temperature(monkeypatch):
    """Kimi K3.x accepts only temperature 1, so we leave it to the provider default."""
    from app.llm import Endpoint
    sent = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "OK"}}]}

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            sent.append(json)
            return FakeResp()

    monkeypatch.setattr("app.llm.httpx.AsyncClient", FakeClient)
    monkeypatch.setenv("MOONSHOT_API_KEY", "k")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    asyncio.run(Endpoint("kimi:kimi-k3.1-pro", 5).chat([{"role": "user", "content": "x"}], None, 0.2, 10, False))
    assert "temperature" not in sent[0] and sent[0]["max_tokens"] == 10


def test_primary_retried_on_rate_limit_and_backup_benched(monkeypatch):
    """Opus gets retried on a 429 instead of handing the call to Sonnet; a failing backup sits out."""
    from app import llm as llm_mod
    from app.llm import LLM, LLMError, Endpoint, Reply
    Endpoint._down_until.clear()
    monkeypatch.setattr(llm_mod, "MAX_RETRY_WAIT_S", 0.0)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    chain_ = LLM("anthropic:claude-opus-5-5,anthropic:claude-sonnet-5-5,deepseek:deepseek-v4-pro")
    calls = []

    async def opus(*a, **k):
        calls.append("opus")
        if len(calls) == 1:
            raise LLMError("busy", 429)
        return Reply("ok", model="anthropic:claude-opus-5-5")

    chain_.endpoints[0].chat = opus
    assert asyncio.run(chain_.chat([{"role": "user", "content": "x"}])).model == "anthropic:claude-opus-5-5"
    assert calls == ["opus", "opus"]

    async def down(*a, **k):
        raise LLMError("server error", 500)

    async def ok(*a, **k):
        return Reply("ok", model="deepseek:deepseek-v4-pro")

    chain_.endpoints[0].chat = chain_.endpoints[1].chat = down
    chain_.endpoints[2].chat = ok
    assert asyncio.run(chain_.chat([{"role": "user", "content": "x"}])).model == "deepseek:deepseek-v4-pro"
    assert chain_.endpoints[0].ready and not chain_.endpoints[1].ready   # Opus stays first, Sonnet sits out
    Endpoint._down_until.clear()


def test_raider_copies_get_names_and_separate_slots():
    from app.raiders.personas import BY_NAME, PERSONAS, copy_number, copy_of, persona_for
    from app.raiders.swarm import RedSwarm
    from types import SimpleNamespace

    odd = copy_of(BY_NAME["odysseus"], 3)
    assert odd.name == "odysseus-3" and odd.base == "odysseus" and copy_number(odd.name) == 3
    assert persona_for("odysseus-3") == odd and persona_for("odysseus") is BY_NAME["odysseus"]
    assert persona_for("nobody") is None

    slots = [f"raider-{i}" for i in range(1, 6)]
    swarm = RedSwarm.__new__(RedSwarm)
    swarm.ctx = SimpleNamespace(settings=SimpleNamespace(raider_slots=slots))
    for p in PERSONAS:
        used = {swarm._slot_for(copy_of(p, k)) for k in range(1, 4)}
        assert len(used) == 3, p.name   # copies of one raider never share a runner, so never share an IP
