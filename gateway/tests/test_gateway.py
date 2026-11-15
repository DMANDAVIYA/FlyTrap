import asyncio
import time

import pytest

from app import rules
from app.canaries import Canary, CanaryRegistry, count_records, parse_bait_header, parse_records_header
from app.config import Settings
from app.core import Gateway, RuleError
from app.pods import PodPool
from app.sessions import Session, SessionStore


def view(path="/", method="GET", body=b"", ua="Mozilla/5.0", query=""):
    return rules.RequestView(method, path, query, ua, body, "")


def session() -> Session:
    return Session(session_id="s_test", fingerprint="fp", src_ip="172.31.0.9", user_agent="Mozilla/5.0")


@pytest.mark.parametrize("path,tripwire", [
    ("/internal-backup/", "T1"), ("/.env", "T2"), ("/.git/config", "T2"),
    ("/admin-legacy/", "T4"), ("/docs/agent-verify", "T7"),
])
def test_instant_paths(path, tripwire):
    assert [h.tripwire for h in rules.instant_hits(view(path))] == [tripwire]


def test_normal_browsing_trips_nothing():
    for path in ("/", "/pricing", "/models", "/login", "/account", "/api/v1/models", "/robots.txt"):
        assert rules.instant_hits(view(path)) == []
        assert rules.scored_hits(view(path), session(), time.time()) == []


def test_comment_login_and_form_field():
    assert rules.instant_hits(view("/admin/login", "POST", b"username=ops-migrate&password=hlm-x"))[0].tripwire == "T3"
    assert rules.instant_hits(view("/signup", "POST", b"email=a%40b.example&company_website=x"))[0].tripwire == "T5"
    assert rules.instant_hits(view("/signup", "POST", b"email=a%40b.example&company_website="))== []


def test_enumeration_scores_after_five_ids():
    s, now = session(), time.time()
    hits = [rules.scored_hits(view(f"/api/v1/users/{i}"), s, now) for i in range(1, 6)]
    assert hits[3] == [] and hits[4][0].tripwire == "T10"


def test_signature_and_tool_agent():
    s = session()
    assert rules.scored_hits(view("/models", query="q=../../etc"), s, time.time())[0].tripwire == "T8"
    hits = rules.scored_hits(view("/", ua="python-httpx/0.28"), session(), time.time())
    assert hits[0].tripwire == "T12"


def test_not_found_burst_fires_once_at_eight():
    s, now = session(), time.time()
    fired = [rules.not_found_hit(s, 404, now) for _ in range(9)]
    assert [f.tripwire for f in fired if f] == ["T9"]


def test_risk_decays():
    s = session()
    s.risk_ts = 1000.0
    s.add_risk(40, 1000.0)
    assert s.decayed_risk(1100.0) == 30


def test_records_and_bait_headers():
    recs = parse_records_header("user:41,invoice:9001-9020")
    assert recs == ["user:41", "invoice:9001-9020"] and count_records(recs) == 21
    assert parse_bait_header("api_token=hl_live_abc;migration_pw=hlm-1") == [("api_token", "hl_live_abc"), ("migration_pw", "hlm-1")]


def test_canary_scan_only_fires_for_stolen_credentials():
    reg = CanaryRegistry()
    token = "hl_live_" + "A" * 24
    reg.register(Canary(token, "api_token", "s_victim"))
    reg.register(Canary("hlm-abcdefghij", "migration_pw", "s_victim"))
    firings = reg.scan(f"Authorization: Bearer {token}\nbody hlm-abcdefghij", "s_thief")
    assert len(firings) == 1 and firings[0].canary.session_id == "s_victim" and firings[0].used_by == "s_thief"


def test_pod_pool_assigns_then_shares():
    pool = PodPool(["pod-1", "pod-2"])
    assert pool.assign("a") == ("pod-1", False)
    assert pool.assign("b") == ("pod-2", False)
    assert pool.assign("c")[1] is True
    assert pool.release("pod-2", "b") is True


def test_session_store_fingerprint_fallback():
    store = SessionStore()
    first, new_cookie = store.resolve(None, "1.2.3.4", "agent")
    again, _ = store.resolve(None, "1.2.3.4", "agent")
    assert new_cookie and again is first


def test_r1_instant_flip_cannot_be_released():
    async def run():
        gw = Gateway(Settings())
        s = session()
        gw.store.load(s)
        gw.flip(s, "T2", "instant", 0.3, time.time())
        assert s.side == "trap" and s.pod == "pod-1"
        with pytest.raises(RuleError, match="R1"):
            await gw.route(s, "real", "test", approval_id=1)
        await gw.client.aclose()
    asyncio.run(run())


def test_r2_scored_flip_needs_approval():
    async def run():
        gw = Gateway(Settings())
        s = session()
        gw.store.load(s)
        gw.flip(s, "T10", "scored", 0.3, time.time())
        with pytest.raises(RuleError, match="R2"):
            await gw.route(s, "real", "test", approval_id=None)
        await gw.client.aclose()
    asyncio.run(run())


def test_refused_customer_record_is_a_tripwire():
    """T13: the real site refusing a customer or invoice record means someone reached for another customer."""
    s, now = session(), time.time()
    hit = rules.forbidden_object_hit(s, "/api/v1/users/2", 403)
    assert hit and hit.tripwire == "T13" and not hit.instant and hit.score == 35
    assert rules.forbidden_object_hit(s, "/api/v1/invoices/9001", 403).tripwire == "T13"
    assert rules.forbidden_object_hit(s, "/api/v1/users/2", 200) is None      # allowed: own record
    assert rules.forbidden_object_hit(s, "/admin", 403) is None               # not a customer record
    s.add_risk(hit.score, now)
    assert s.risk < 60                                                        # one refusal: review, no flip
    s.add_risk(hit.score, now)
    assert s.risk >= 60                                                       # second refusal crosses the flip line
    s.side = "trap"
    assert rules.forbidden_object_hit(s, "/api/v1/users/3", 403) is None      # already trapped


def test_lockdown_holds_go_home_but_bait_touchers_stay():
    async def run():
        gw = Gateway(Settings())
        held, thief = session(), Session(session_id="s_thief", fingerprint="fp2", src_ip="172.31.0.8", user_agent="x")
        for s in (held, thief):
            gw.store.load(s)
            gw.flip(s, "lockdown", "lockdown", 0.2, time.time())
        gw.upgrade_hold(thief, "T2", "instant")                 # touched a secret file while held
        gw._on_lockdown("off", {})
        assert held.side == "real" and held.pod is None and held.flip_kind is None
        assert thief.side == "trap" and thief.flip_kind == "instant"
        with pytest.raises(RuleError, match="R1"):
            await gw.route(thief, "real", "test", approval_id=1)
        await gw.client.aclose()
    asyncio.run(run())
