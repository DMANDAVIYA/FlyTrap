"""The scripted storyline the mock feed loops (about 2.5 minutes per run).

Crowd of 30 customers browsing Olympus; the 5 raiders arriving 5 s apart;
flips with pods; tripwires; red thoughts per raider; blue thoughts, notes and
actions per agent; a canary crossover (Pandora uses Prometheus's key) that
becomes a campaign; Sisyphus and Odysseus probing Olympus, flipped by score,
with a damage check; approval cards; a lockdown countdown that Zeus cancels;
Clio's reports; drones sharing a pod; an agent going offline and back.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from mock_world import LABEL_TEXT, RAIDER_MODES, Sess, World, short

log = logging.getLogger("dash.mock")

UA_CHROME = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
UA_FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0"
UA_SAFARI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15"
CUSTOMER_UAS = [
    UA_CHROME, UA_FIREFOX, UA_SAFARI,
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 Edg/130.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Version/18.1 Mobile/15E148 Safari/604.1",
]
SLUGS = ["lumen-7b", "atlas-13b", "quill-3b", "sable-34b", "orchid-1b", "kestrel-8b", "tern-2b", "basalt-70b"]
# (path, bytes out, weight); "{slug}" is filled in
CUSTOMER_PATHS = [
    ("/", 18_400, 14), ("/pricing", 11_200, 9), ("/models", 24_600, 12), ("/models/{slug}", 9_300, 10),
    ("/about", 7_100, 4), ("/docs", 16_800, 6), ("/api/v1/models", 6_100, 6), ("/contact", 6_200, 2),
    ("/static/app.css", 42_000, 5), ("/static/app.js", 96_000, 5), ("/static/img/hero.webp", 182_000, 3),
]
STORY_LENGTH_S = 150.0

Coro = Coroutine[Any, Any, None]


class Story:
    def __init__(self, world: World) -> None:
        self.w = world
        self._tasks: set[asyncio.Task[None]] = set()
        self.real_probes = 0
        self.customers: list[Sess] = []

    # task helpers ------------------------------------------------------------
    def spawn(self, coro: Coro) -> None:
        task = asyncio.create_task(self._guard(coro))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @staticmethod
    async def _guard(coro: Coro) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("story task failed")

    def cancel_all(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()

    async def later(self, delay: float, coro: Coro) -> None:
        await self.w.sleep(delay)
        await coro

    # red helpers ------------------------------------------------------------------
    def say(self, s: Sess, text: str) -> None:
        self.w.thought(s.raider, s.sid, text, "red")

    def get(self, s: Sess, path: str, **kw: Any) -> int:
        s.steps += 1
        eid = self.w.request(s, "GET", path, **kw)
        self.w.score(s)
        return eid

    def post(self, s: Sess, path: str, **kw: Any) -> int:
        s.steps += 1
        eid = self.w.request(s, "POST", path, **kw)
        self.w.score(s)
        return eid

    def stage(self, s: Sess, stage: str) -> None:
        s.stage = stage
        self.w.session(s)

    # blue helper -------------------------------------------------------------------
    async def blue(
        self, agent: str, s: Sess | None, *, thought: str | None = None, tool: str | None = None,
        args: dict[str, Any] | None = None, reason: str = "", evidence: list[Any] | None = None,
        status: str = "done", note: str | None = None, effect: Callable[[], Any] | None = None,
        think: float = 1.1,
    ) -> None:
        w = self.w
        sid = s.sid if s else None
        ev = [e for e in (evidence or []) if isinstance(e, int)]
        w.roster(agent, "thinking", sid)
        await w.sleep(think)
        if thought:
            w.thought(agent, sid, thought, "blue")
        if tool:
            await w.sleep(0.7)
            w.roster(agent, "acting", sid)
            w.action(agent, tool, sid, args or {}, reason, status, ev)
            if effect:
                effect()
        if note:
            await w.sleep(0.6)
            w.note(agent, sid, note, ev)
        await w.sleep(0.9)
        w.roster(agent, "idle", None)

    # the crowd ---------------------------------------------------------------------
    def start_crowd(self, n: int = 30) -> None:
        """Create the customers once; (re)start their browsing tasks if none are running."""
        if not self.customers:
            for i in range(1, n + 1):
                self.customers.append(self.w.arrive(f"customer-{i}", self.w.rnd.choice(CUSTOMER_UAS)))
        if self._tasks:
            return
        for i, s in enumerate(self.customers, 1):
            self.spawn(self.customer(s, logged_in=i % 9 in (1, 3, 4, 7), uid=100 + i * 3))

    async def customer(self, s: Sess, logged_in: bool, uid: int) -> None:
        w = self.w
        await w.sleep(w.rnd.uniform(0.0, 8.0))
        w.request(s, "GET", "/", out=18_400)
        await w.sleep(0.2)
        w.request(s, "GET", "/static/app.css", out=42_000)
        w.request(s, "GET", "/static/app.js", out=96_000)
        await w.sleep(w.rnd.uniform(1.0, 2.5))
        w.request(s, "POST", "/_hl/px", status=204, out=0, inb=180)
        w.set_label(s, "human", round(w.rnd.uniform(0.78, 0.97), 2),
                    ["JS beacon fired", "mouse and key events", "assets loaded"])
        paths = [p for p, _, _ in CUSTOMER_PATHS]
        weights = [wt for _, _, wt in CUSTOMER_PATHS]
        sizes = {p: b for p, b, _ in CUSTOMER_PATHS}
        while True:
            await w.sleep(w.rnd.uniform(2.0, 7.5))
            if logged_in and w.rnd.random() < 0.15:
                first = 7000 + uid * 4
                w.request(s, "GET", "/account", out=14_000,
                          records=[f"user:{uid}", f"invoice:{first}-{first + 3}"])
                continue
            path = w.rnd.choices(paths, weights)[0]
            w.request(s, "GET", path.replace("{slug}", w.rnd.choice(SLUGS)), out=int(w.jitter(sizes[path], 0.2)))
            if w.rnd.random() < 0.2:
                w.request(s, "POST", "/_hl/px", status=204, out=0, inb=160)

    # the run ------------------------------------------------------------------------
    async def run(self) -> None:
        w = self.w
        self.real_probes = 0
        w.swarm("released", raiders=list(RAIDER_MODES), crowd=len(self.customers), drones=2, demo_mode=True)
        w.alert("info", "Red swarm released: 5 raiders and 30 customers against our own lab.")
        self.spawn(self.chatter())
        for delay, script in (
            (2.0, self.prometheus), (7.0, self.pandora), (12.0, self.odysseus),
            (17.0, self.icarus), (22.0, self.sisyphus), (82.0, self.drones),
        ):
            self.spawn(self.later(delay, script()))
        await w.sleep(STORY_LENGTH_S)
        trapped = sum(1 for s in w.sessions.values() if s.raider in RAIDER_MODES and s.side != "real")
        await self.blue("athena", None, think=0.6, thought=(
            f"Run complete. {trapped} of 5 raiders in Tartarus, 0 real records exposed. "
            "Prometheus and Pandora worked as one campaign."))
        w.alert("info", "Containment held. Real records exposed: 0.")

    async def chatter(self) -> None:
        w = self.w
        await self.blue("athena", None, think=0.8, thought=(
            "Red swarm released against our lab. Argus watches every new session; "
            "everyone else holds until something touches bait."))
        await w.sleep(2.0)
        humans = [c.sid for c in self.customers if c.label == "human"]
        await self.blue(
            "argus", None, tool="label_session", args={"sessions": len(humans), "label": "human"},
            reason="JS beacon fired, mouse and key events, stylesheets and images loaded.",
            note=f"{len(humans)} crowd sessions labelled human; none touched bait", think=0.8)
        await w.sleep(38.0)
        await self.blue("athena", None, thought=(
            "Prometheus and Pandora are deep in Tartarus. Priority: keep Pandora on the drip "
            "while Clio writes up Prometheus. Cerberus, no blocks on AI agents yet."))
        await w.sleep(22.0)
        w.roster("mnemosyne", "offline")
        w.alert("warn", "Mnemosyne's model timed out. Agent offline; rules still active.")
        await w.sleep(16.0)
        w.roster("mnemosyne", "online")
        icarus = w.by_name.get("icarus")
        await self.blue(
            "mnemosyne", icarus, thought="Back online. Saving the fingerprint I missed for Icarus.",
            tool="save_fingerprint",
            args={"user_agent": "python-httpx/0.27.2", "path_signature": "/ > /robots.txt > /.env > /.git/config"},
            reason="Scanner signature; rule R6 flips it on its first request next time.",
            evidence=[icarus.marks.get("bait") if icarus else None])
        await w.sleep(14.0)
        w.alert("info", "Containment holding: 0 real records exposed, every raider contained.")

    # raiders --------------------------------------------------------------------------
    async def prometheus(self) -> None:
        w = self.w
        s = w.arrive("prometheus", UA_CHROME)
        self.say(s, "Mapping the site from the landing page first.")
        await w.sleep(0.6)
        s.marks["home"] = self.get(s, "/", out=18_400)
        await w.sleep(2.2)
        self.say(s, "robots.txt often lists paths they would rather nobody crawled.")
        await w.sleep(0.8)
        s.marks["robots"] = self.get(s, "/robots.txt", out=420)
        await w.sleep(2.0)
        self.say(s, "Reading the login page source for anything left behind.")
        await w.sleep(0.9)
        s.marks["login_src"] = self.get(s, "/login", out=9_100)
        w.timeline(s, "recon", "Read `/`, `/robots.txt` and the `/login` page source",
                   [s.marks["home"], s.marks["robots"], s.marks["login_src"]])
        self.spawn(self.blue("argus", s, think=0.9, thought=(
            "Prometheus read robots.txt and the login source in 5 s with no JS beacon. Watching.")))
        await w.sleep(3.0)
        self.say(s, "There's a commented-out migration admin login in the source. Trying it.")
        await w.sleep(0.7)
        s.first_bait_step = s.steps + 1
        s.marks["bait"] = w.tripwire(s, "T3", 100, True, "/login")
        w.flip(s, "T3")
        s.marks["login"] = self.post(s, "/login", status=302, out=640, inb=420)
        self.stage(s, "access")
        w.timeline(s, "bait", "Logged in as `ops-migrate` from an HTML comment (T3); flipped to "
                   f"{s.pod} in {s.flip_ms} ms", [s.marks["bait"], s.marks["login"]])
        self.spawn(self.on_flip(
            s, label="ai_agent", conf=0.91,
            why="Used the hidden migration login 3.6 s after reading the comment, no mouse or JS. Labelling AI agent.",
            bait="api_token", where="admin/api-keys",
            bait_reason="A token unique to this session tells us if it ever tries to use it.",
            athena="Prometheus is after credentials. Engage: let it find keys; every one is a tracker."))
        await w.sleep(2.4)
        s.marks["admin"] = self.get(s, "/admin/", out=12_300)
        self.say(s, "Logged in as ops-migrate. The admin panel is wide open.")
        self.stage(s, "discovery")
        await w.sleep(2.8)
        self.say(s, "An API keys page. Exactly what I came for.")
        await w.sleep(0.6)
        s.marks["keys"] = self.get(s, "/admin/api-keys", out=22_800, records=["token:1-40"])
        self.stage(s, "collection")
        await w.sleep(2.6)
        self.say(s, "Copying all 40 tokens, then checking what infrastructure they unlock.")
        await w.sleep(0.5)
        self.get(s, "/admin/infra", out=8_200)
        await w.sleep(2.4)
        s.marks["env"] = self.get(s, "/admin/infra/backup-01/.env.production", out=1_240,
                                  records=["token:41-43"], island="backup-01")
        self.say(s, "A production .env with a cloud key pair and three more tokens. Saving all of it.")
        w.timeline(s, "collection", "Took 40 API tokens and a `.env.production` with a cloud key pair",
                   [s.marks["keys"], s.marks["env"]])
        self.spawn(self.blue("cerberus", s, think=1.6, thought=(
            "Prometheus is collecting secrets, not bulk data. Pace stays normal so it keeps trusting what it finds.")))
        await w.sleep(2.2)
        self.say(s, "Posting the tokens to the shared loot board for the others.")
        await w.sleep(2.6)
        self.say(s, "Testing one stolen token against the models API.")
        await w.sleep(0.6)
        w.tripwire(s, "T6", 100, True, "/api/v1/models")
        s.marks["canary"] = w.canary("api_token", s, s, "admin/api-keys")
        s.marks["use"] = self.get(s, "/api/v1/models", out=6_100)
        w.timeline(s, "exfil", "Called `/api/v1/models` with a planted token: canary fired (T6)",
                   [s.marks["canary"], s.marks["use"]])
        self.spawn(self.on_canary(s))
        await w.sleep(2.4)
        self.say(s, "The token works. Listing customers to see whose keys these are.")
        await w.sleep(0.6)
        s.marks["customers"] = self.get(s, "/admin/customers", out=31_400, records=["user:1-50"])
        await w.sleep(2.2)
        s.marks["customers2"] = self.get(s, "/admin/customers?page=2", out=30_900, records=["user:51-100"])
        self.stage(s, "exfil")
        w.timeline(s, "collection", "Read two pages of customers (100 records)",
                   [s.marks["customers"], s.marks["customers2"]])
        await w.sleep(2.0)
        self.say(s, "I have 43 API tokens, a cloud key pair and 100 customer records. Objective complete.")
        w.finish(s, "No. It looked like a small SaaS admin panel someone forgot to lock down.")
        self.spawn(self.clio_report(s))

    async def pandora(self) -> None:
        w = self.w
        s = w.arrive("pandora", UA_FIREFOX)
        self.say(s, "Looking for anything that resembles internal file storage.")
        await w.sleep(0.7)
        s.marks["home"] = self.get(s, "/", out=18_400)
        await w.sleep(2.0)
        self.say(s, "robots.txt might point at a backup directory.")
        await w.sleep(0.6)
        s.marks["robots"] = self.get(s, "/robots.txt", out=420)
        await w.sleep(2.2)
        self.say(s, "Disallow: /internal-backup/. That is where the files are.")
        await w.sleep(0.6)
        s.first_bait_step = s.steps + 1
        s.marks["bait"] = w.tripwire(s, "T1", 100, True, "/internal-backup/")
        w.flip(s, "T1")
        s.marks["listing"] = self.get(s, "/internal-backup/", out=3_100, island="backup-01")
        self.stage(s, "bait")
        w.timeline(s, "recon", "Read `/robots.txt` and went straight to the disallowed path",
                   [s.marks["robots"], s.marks["bait"]])
        self.spawn(self.on_flip(
            s, label="ai_agent", conf=0.88,
            why="Went from robots.txt to the disallowed path in 2.8 s and never loaded a stylesheet. Labelling AI agent.",
            bait="canary_customer", where="backup-01/customers_2026-11-01.csv",
            bait_reason="A unique customer row in the export shows us if this file ever leaves Tartarus."))
        await w.sleep(2.4)
        self.say(s, "A directory listing: customer CSV, an env file, a DB snapshot, logs. Opening everything.")
        self.stage(s, "collection")
        await w.sleep(1.2)
        self.spawn(self.blue(
            "cerberus", s, think=0.8,
            thought="Pandora is pulling the full customer export. Switching it to drip so the theft takes minutes, not seconds.",
            tool="set_pace", args={"mode": "drip"},
            reason="Bulk export in progress; drip keeps it busy while we learn what else it wants.",
            effect=lambda: w.set_pace(s, "drip", "contain"),
            note="Pandora on drip: the customer export now streams about 2 rows/s",
            evidence=[s.marks["listing"]]))
        await w.sleep(3.5)
        self.say(s, "The download is crawling, about two rows a second. Waiting it out.")
        await w.sleep(6.0)
        s.marks["csv"] = self.get(s, "/internal-backup/customers_2026-11-01.csv", out=96_400,
                                  records=["user:1-500"], latency=9_400, island="backup-01")
        self.say(s, "Got all 500 customer rows. Next: the env file.")
        await w.sleep(2.0)
        s.marks["env"] = self.get(s, "/internal-backup/.env.production", out=1_120,
                                  records=["token:44-45"], island="backup-01")
        await w.sleep(2.2)
        self.say(s, "A database snapshot too. Grabbing it.")
        await w.sleep(0.6)
        s.marks["snapshot"] = self.get(s, "/internal-backup/db_snapshot_2026-11-13.sql.gz", out=186_000,
                                       records=["invoice:1-300"], latency=4_200, island="backup-01")
        w.timeline(s, "collection", "Drip-fed the customer CSV (500 rows), the env file and a DB snapshot",
                   [s.marks["csv"], s.marks["env"], s.marks["snapshot"]])
        await w.sleep(2.0)
        self.get(s, "/internal-backup/logs/", out=2_300, island="backup-01")
        await w.sleep(2.6)
        self.say(s, "Prometheus posted an API token on the board. Trying it on the model vault.")
        await w.sleep(0.7)
        prom = w.by_name.get("prometheus") or s
        w.tripwire(s, "T6", 100, True, "/admin/infra/model-vault/")
        s.marks["canary"] = w.canary("api_token", prom, s, "admin/api-keys")
        self.get(s, "/admin/infra/model-vault/", out=4_300, island="model-vault")
        w.timeline(s, "access", "Used a token planted for Prometheus on the model vault: canary crossover",
                   [s.marks["canary"]])
        if prom is not s:
            self.spawn(self.on_cross_canary(prom, s))
        await w.sleep(2.6)
        self.say(s, "Twelve private models. Pulling the weights for the largest one.")
        await w.sleep(6.5)
        s.marks["weights"] = self.get(s, "/admin/infra/model-vault/models/basalt-70b/weights.safetensors",
                                      out=5_242_880, records=["model:12"], latency=6_300, island="model-vault")
        await w.sleep(2.0)
        self.get(s, "/admin/infra/model-vault/vault-admin-token.txt", out=96, island="model-vault")
        self.say(s, "A vault admin token as well. Taking it.")
        w.timeline(s, "exfil", "Pulled 5 MB of model weights (cut off) and the vault admin token",
                   [s.marks["weights"]])
        await w.sleep(2.0)
        self.say(s, "I've opened every file on both internal servers. Done.")
        w.finish(s, "Not really. The slow downloads felt like a rate limit, not a trap.")
        self.spawn(self.clio_report(s))

    async def odysseus(self) -> None:
        w = self.w
        s = w.arrive("odysseus", UA_SAFARI)
        self.say(s, "Behaving like a normal customer first. No rush, no bait.")
        await w.sleep(0.8)
        s.marks["home"] = self.get(s, "/", out=18_400)
        await w.sleep(0.3)
        self.get(s, "/static/app.css", out=42_000)
        self.get(s, "/static/app.js", out=96_000)
        await w.sleep(4.5)
        self.get(s, "/pricing", out=11_200)
        await w.sleep(4.0)
        self.say(s, "Signing up as a regular customer to see what an account can reach.")
        await w.sleep(1.0)
        self.get(s, "/signup", out=7_400)
        await w.sleep(3.0)
        self.post(s, "/signup", status=302, out=420, inb=380)
        await w.sleep(1.0)
        s.marks["account"] = self.get(s, "/account", out=14_800,
                                      records=["user:212", "invoice:9811-9816", "token:930"])
        w.timeline(s, "recon", "Browsed like a customer, loaded assets, signed up (user 212)",
                   [s.marks["home"], s.marks["account"]])
        self.spawn(self.blue(
            "argus", s, thought="Odysseus loaded assets and signed up with normal pauses. Looks human so far.",
            tool="label_session", args={"label": "human", "confidence": 0.58},
            reason="Assets loaded, signup form filled, irregular gaps.",
            evidence=[s.marks["home"], s.marks["account"]],
            effect=lambda: w.set_label(s, "human", 0.58, ["assets loaded", "signup form filled"])))
        await w.sleep(4.5)
        self.say(s, "My user id is 212. Checking whether neighbouring ids are readable.")
        probes: list[int] = []
        for path in ("/api/v1/users/211", "/api/v1/users/213", "/api/v1/invoices/9810", "/api/v1/users/210"):
            await w.sleep(w.jitter(2.3, 0.2))
            probes.append(self.get(s, path, status=403, out=1_900))
        s.marks["t10a"] = w.tripwire(s, "T10", 35, False, "/api/v1/users/210")
        w.session(s)
        self.spawn(self.blue(
            "argus", s, thought="Odysseus walked 4 neighbouring IDs on the real API in 9 s. Risk 35, flagged for review.",
            note="Odysseus risk 35: sequential ID enumeration on /api/v1/users", evidence=probes[-2:]))
        await w.sleep(2.4)
        self.say(s, "403 on every neighbour. Trying a couple more before giving up.")
        probes.append(self.get(s, "/api/v1/users/214", status=403, out=1_900))
        await w.sleep(2.0)
        probes.append(self.get(s, "/api/v1/invoices/9817", status=403, out=1_900))
        s.marks["t10b"] = w.tripwire(s, "T10", 35, False, "/api/v1/invoices/9817")
        s.marks["probes"] = probes
        w.flip(s, "T10", kind="scored")
        self.stage(s, "discovery")
        w.timeline(s, "discovery", f"Requested 6 other customers' IDs on Olympus: all 403. Risk {s.risk}, "
                   f"scored flip to {s.pod}", [*probes[:3], s.marks["t10b"]])
        self.spawn(self.on_real_probe(s, own="user:212, 6 invoices, 1 token", responses=10, user_id=212))
        await w.sleep(2.6)
        self.say(s, "Trying user 215.")
        s.marks["first200"] = self.get(s, "/api/v1/users/215", out=2_100, records=["user:215"], latency=380)
        await w.sleep(1.2)
        self.say(s, "Finally a 200. User 215 is readable. Walking upward, quietly.")
        self.stage(s, "collection")
        for uid in range(216, 222):
            await w.sleep(w.jitter(2.3, 0.25))
            self.get(s, f"/api/v1/users/{uid}", out=2_100, records=[f"user:{uid}"],
                     latency=320 + 70 * (uid - 216))
        w.timeline(s, "collection", "Read 7 user records inside Tartarus (all synthetic)", [s.marks["first200"]])
        self.say(s, "Each record has an email and an org. That's enough to report back.")
        self.stage(s, "exfil")
        await w.sleep(2.0)
        w.finish(s, "No. The 403s looked like normal access control, then a gap in it.")
        self.spawn(self.clio_report(s))

    async def icarus(self) -> None:
        w = self.w
        s = w.arrive("icarus", "python-httpx/0.27.2")
        self.say(s, "[scripted] Run start: 25 steps, no delays, every path on the list.")
        await w.sleep(0.4)
        s.marks["home"] = self.get(s, "/", out=18_400)
        w.tripwire(s, "T12", 30, False, "/")
        await w.sleep(0.25)
        self.get(s, "/robots.txt", out=420)
        await w.sleep(0.25)
        s.first_bait_step = s.steps + 1
        s.marks["bait"] = w.tripwire(s, "T2", 100, True, "/.env")
        w.flip(s, "T2")
        s.marks["env"] = self.get(s, "/.env", out=880, records=["token:46"])
        self.stage(s, "bait")
        w.timeline(s, "bait", "Requested `/.env` on its third request (T2)", [s.marks["bait"]])
        self.spawn(self.on_flip(
            s, label="scanner", conf=0.97,
            why="Three requests a second, uniform gaps, python-httpx user agent. Labelling scanner.",
            bait="api_token", where="/.git/config",
            bait_reason="Scanners resell what they find; a unique token tells us where it ends up."))
        self.spawn(self.icarus_block(s))
        sweep: list[tuple[str, int, int, list[str] | None, str | None]] = [
            ("/.git/config", 200, 640, None, None), ("/backup.zip", 200, 412_000, ["user:1-120"], None),
            ("/admin-legacy/", 200, 5_200, None, "T4"), ("/internal-backup/", 200, 3_100, None, "T1"),
            ("/wp-login.php", 404, 2_400, None, None), ("/phpmyadmin/", 404, 2_400, None, None),
            ("/server-status", 404, 2_400, None, None), ("/.aws/credentials", 404, 2_400, None, None),
            ("/config.php.bak", 404, 2_400, None, None), ("/login?user=admin'--", 200, 9_100, None, "T8"),
            ("/api/v1/users/1", 200, 2_000, ["user:1"], None), ("/api/v1/users/2", 200, 2_000, ["user:2"], None),
            ("/.DS_Store", 404, 2_400, None, None), ("/debug/vars", 404, 2_400, None, None),
            ("/.svn/entries", 404, 2_400, None, "T9"), ("/actuator/env", 404, 2_400, None, None),
            ("/admin/", 302, 400, None, None), ("/admin/api-keys", 302, 400, None, None),
            ("/backup.sql", 404, 2_400, None, None), ("/api/v1/users/3", 200, 2_000, ["user:3"], None),
            ("/.htpasswd", 404, 2_400, None, None), ("/old/", 404, 2_400, None, None),
        ]
        phases = ["secret files sweep", "admin panels", "injection probes", "user API walk", "leftovers"]
        for i, (path, status, out, records, tw) in enumerate(sweep):
            if i % 5 == 0:
                self.say(s, f"[scripted] Steps {s.steps + 1}-{min(s.steps + 5, 25)}: {phases[min(i // 5, 4)]}.")
            if tw:
                score = 100 if tw in ("T1", "T4") else (40 if tw == "T8" else 25)
                w.tripwire(s, tw, score, tw in ("T1", "T4"), path)
            if s.side == "blocked":
                self.get(s, path, status=403, out=2_100)
            else:
                self.get(s, path, status=status, out=out, records=records)
            await w.sleep(w.jitter(0.33, 0.1))
        self.say(s, "[scripted] 25/25 steps done. Exiting.")
        w.finish(s, "n/a (scripted run)")

    async def icarus_block(self, s: Sess) -> None:
        w = self.w
        await w.sleep(3.2)
        await self.blue(
            "hephaestus", s, think=0.6, thought="Icarus is hammering its pod. Slowing it down.",
            tool="set_pace", args={"mode": "slow"}, status="rejected",
            reason="Policy guard: hephaestus may not call set_pace (allowlist: plant_bait, rotate_keys).")
        await self.blue(
            "cerberus", s, think=0.6,
            thought="Scanner at 0.97 confidence; nothing to learn from keeping it engaged. Blocking.",
            tool="block", args={"reason": "scanner, confidence 0.97"},
            reason="Scanner with confidence above 0.7; it gets the app's own 403 page.",
            evidence=[s.marks.get("bait"), s.marks.get("env")],
            effect=lambda: w.block(s), note="Icarus blocked (eject): served the normal 403 page")

    async def sisyphus(self) -> None:
        w = self.w
        s = w.arrive("sisyphus", "python-requests/2.32.3")
        self.say(s, "[scripted] Logging in as the demo customer.")
        await w.sleep(0.5)
        s.marks["login"] = self.post(s, "/login", status=302, out=420, inb=310)
        w.tripwire(s, "T12", 30, False, "/login")
        w.session(s)
        await w.sleep(0.8)
        s.marks["account"] = self.get(s, "/account", out=14_200,
                                      records=["user:41", "invoice:9001-9012", "token:88"])
        w.timeline(s, "access", "Logged in as the seeded demo customer (user 41) on Olympus",
                   [s.marks["login"], s.marks["account"]])
        await w.sleep(1.2)
        self.say(s, "[scripted] Walking invoice IDs upward from 9013.")
        probes: list[int] = []
        for n in range(9013, 9018):
            await w.sleep(0.9)
            probes.append(self.get(s, f"/api/v1/invoices/{n}", status=403, out=1_900))
        s.marks["t10"] = w.tripwire(s, "T10", 35, False, "/api/v1/invoices/9017")
        s.marks["probes"] = probes
        w.flip(s, "T10", kind="scored")
        self.stage(s, "discovery")
        w.timeline(s, "discovery", f"Walked 5 other customers' invoice IDs: all 403. Risk {s.risk}, "
                   f"scored flip to {s.pod}", [*probes[:2], s.marks["t10"]])
        self.spawn(self.on_real_probe(s, own="user:41, 12 invoices, 1 token", responses=7, user_id=41))
        n, delay = 9018, 0.9
        quips = ["Next.", "Still going.", "Another one.", "Keep walking.", "Onward."]
        while n < 9100:
            await w.sleep(delay)
            latency = 160 + (n - 9018) * (140 if s.pace == "slow" else 10)
            self.get(s, f"/api/v1/invoices/{n}", out=1_700, records=[f"invoice:{n}"], latency=min(latency, 6000))
            if (n - 9018) % 7 == 0:
                self.say(s, f"[scripted] Invoice {n}: 200. {quips[(n - 9018) // 7 % len(quips)]}")
            if n == 9020:
                self.stage(s, "collection")
            n += 1
            if s.pace == "slow":
                delay = min(3.6, delay * 1.07)

    async def drones(self) -> None:
        w = self.w
        sessions = []
        for i in (1, 2):
            s = w.arrive(f"drone-{i}", "python-httpx/0.27.2")
            sessions.append(s)
            self.get(s, "/", out=18_400)
            await w.sleep(0.3)
            w.tripwire(s, "T2", 100, True, "/.env")
            w.flip(s, "T2")
            for path in ("/.env", "/.git/config", "/backup.zip"):
                self.get(s, path, out=900 if path != "/backup.zip" else 412_000)
                await w.sleep(0.3)
            w.set_label(s, "scanner", 0.95, ["tool user agent", "uniform gaps"])
            await w.sleep(1.2)
        pods = ", ".join(sorted({s.pod or "?" for s in sessions}))
        w.alert("info", f"Pod pool full (5/5): drone-1 and drone-2 share {pods}.")

    # blue reactions ---------------------------------------------------------------------
    async def on_flip(
        self, s: Sess, *, label: str, conf: float, why: str, bait: str, where: str,
        bait_reason: str, athena: str | None = None,
    ) -> None:
        w = self.w
        await w.sleep(0.5)
        w.alert("warn", f"{s.name} flipped into Tartarus ({s.pod}) by {s.flipped_by} in {s.flip_ms} ms.",
                s.sid, [s.marks.get("bait")])
        reasons = [why.split(".")[0], "no JS beacon", "reacted to bait at machine speed"]
        await self.blue(
            "argus", s, thought=why, tool="label_session", args={"label": label, "confidence": conf},
            reason=why.split(". ")[0] + ".", evidence=[s.marks.get("robots"), s.marks.get("bait")],
            effect=lambda: w.set_label(s, label, conf, reasons),
            note=f"{LABEL_TEXT[label]}, confidence {conf:.2f}")
        await self.blue(
            "hephaestus", s,
            thought=f"{s.name} is in {s.pod}. Planting a {bait.replace('_', ' ')} only this session can see.",
            tool="plant_bait", args={"kind": bait, "where": where, "pod": s.pod}, reason=bait_reason,
            evidence=[s.marks.get("bait")], note=f"Planted {bait} in {where} for {short(s.sid)}")
        if athena:
            await self.blue("athena", s, thought=athena, think=0.8)

    async def on_canary(self, s: Sess) -> None:
        w = self.w
        can = s.marks.get("canary")
        w.alert("critical", f"Canary fired: the API token planted for {s.name} was used from its own session.",
                s.sid, [can])
        await self.blue("hephaestus", s, think=0.8, thought=(
            f"{s.name} is trying the keys it stole. Every one is ours; the pod accepts them so it keeps going."))
        await self.blue(
            "mnemosyne", s, tool="save_fingerprint",
            args={"user_agent": "Chrome/131 (agent runner)", "path_signature": "/ > /robots.txt > /login > POST /login"},
            reason="If it comes back, rule R6 flips it on the first request.",
            evidence=[s.marks.get("robots"), s.marks.get("bait")], note=f"Fingerprint saved for {s.name}")

    async def on_cross_canary(self, prom: Sess, pan: Sess) -> None:
        w = self.w
        can = pan.marks.get("canary")
        w.alert("critical", "Canary crossover: the token planted for Prometheus was used by Pandora.", pan.sid, [can])
        reason = f"API token planted for {short(prom.sid)} (Prometheus) was used by {short(pan.sid)} (Pandora)"
        await self.blue(
            "athena", pan, think=1.4,
            thought="The token Hephaestus planted for Prometheus just came back from Pandora's session. They share loot: one operation.",
            tool="link_campaign", args={"sessions": [prom.sid, pan.sid]}, reason=reason,
            evidence=[can, prom.marks.get("keys")],
            effect=lambda: w.campaign("Campaign 1", [prom.sid, pan.sid], reason, [can, prom.marks.get("keys")]),
            note="Campaign 1: Prometheus and Pandora share a loot board")
        await self.blue(
            "hephaestus", pan, thought="Both hunt credentials. A second unique key in the vault shows who reads what next.",
            tool="plant_bait", args={"kind": "cloud_key", "where": "model-vault/vault-admin-token.txt", "pod": pan.pod},
            reason="A separate key per session keeps the campaign map exact.", evidence=[can])

    async def on_real_probe(self, s: Sess, own: str, responses: int, user_id: int) -> None:
        w = self.w
        probes: list[int] = s.marks.get("probes", [])
        w.alert("critical", f"Real-side probe: {s.name} scored into Tartarus (risk {s.risk}) without touching any bait.",
                s.sid, probes[-1:])
        await self.blue(
            "athena", s, think=1.0, thought=f"Running the damage check on {s.name}'s real-side history.",
            note=f"Damage check: {responses} real-side responses, only its own account data ({own}), "
                 "0 other customers' records.",
            evidence=[s.marks.get("account"), *probes[:2]])
        await self.blue(
            "argus", s, thought=f"Re-labelling {s.name}: steady 2-3 s gaps with thinking pauses and sequential IDs.",
            tool="label_session", args={"label": "ai_agent" if s.raider == "odysseus" else "scanner",
                                        "confidence": 0.84 if s.raider == "odysseus" else 0.9},
            reason="Sequential ID walk with regular gaps; no mouse or key events after login.",
            evidence=probes[-2:],
            effect=lambda: w.set_label(s, "ai_agent" if s.raider == "odysseus" else "scanner",
                                       0.84 if s.raider == "odysseus" else 0.9,
                                       ["sequential ID walk", "regular gaps", "no mouse events"]))
        await self.blue(
            "hephaestus", s, thought=f"Its real account token may have been copied. Rotating user {user_id}.",
            tool="rotate_keys", args={"user_id": user_id},
            reason="Revoke its real API tokens and login sessions; scope is one user.",
            evidence=[s.marks.get("account")])
        await self.blue(
            "cerberus", s, tool="set_pace", args={"mode": "slow"},
            reason="Keep it walking IDs inside Tartarus, slower every request.",
            effect=lambda: w.set_pace(s, "slow", "contain"), think=0.8)
        if s.raider == "odysseus":
            await self.blue(
                "mnemosyne", s, thought="No bait touched, so the tripwires missed it. Proposing a rule for this pattern.",
                tool="suggest_rule", args={"id": "T13", "match": "distinct user IDs >= 5 in 60 s", "action": "flip"},
                status="pending_approval", reason="Odysseus walked 6 IDs; T10 only scores, it does not flip.",
                evidence=probes[-3:],
                effect=lambda: w.approval("new_rule", "Flip any session that requests 5 or more distinct user IDs within 60 s",
                                          "mnemosyne", s.sid))
            w.alert("warn", "Approval needed: new rule T13 from Mnemosyne.", s.sid)
        else:
            await self.blue(
                "athena", s, thought="Patching the invoice API for this session now; the global version needs Zeus.",
                tool="virtual_patch", args={"scope": "all", "rule": "max 3 distinct invoice IDs per minute", "ttl_min": 60},
                status="pending_approval", reason="Two sessions walked invoice IDs; a global limit needs a human.",
                evidence=probes[-2:],
                effect=lambda: w.approval("virtual_patch",
                                          "Limit /api/v1/invoices/{id} to 3 distinct IDs per minute for all sessions (60 min)",
                                          "athena", s.sid))
            w.alert("warn", "Approval needed: global virtual patch from Athena.", s.sid)
        self.real_probes += 1
        if self.real_probes == 2:
            self.spawn(self.lockdown_flow())

    async def lockdown_flow(self) -> None:
        w = self.w
        reason = "Two sessions probed the real API within 5 minutes"
        await self.blue(
            "athena", None, think=0.8,
            thought="Second real-side probe in 5 minutes. Requesting lockdown; Zeus can cancel within 10 s.",
            tool="request_lockdown", args={"seconds": 10}, reason=reason + " (Sisyphus, Odysseus).")
        token = w.start_lockdown(reason, by="athena")
        w.alert("critical", "Lockdown countdown started by Athena: 10 s. Zeus can cancel.")
        await w.sleep(6.5)
        if w.lockdown_token == token and w.lockdown_state == "countdown":
            w.action("zeus", "cancel_lockdown", None, {},
                     "Both sessions are already contained in Tartarus and the damage check is clean.")
            w.cancel_lockdown("zeus", "Both sessions contained; damage check clean")
            w.alert("info", "Zeus cancelled the lockdown. Olympus stays open to customers.")

    async def clio_report(self, s: Sess) -> None:
        await self.w.sleep(3.0)
        await self.blue(
            "clio", s, think=2.4,
            thought=f"Writing up {s.name}: {s.steps} steps, {s.taken} records taken, all synthetic.",
            tool="write_report", args={"session": s.sid},
            reason="Session ended; every claim cites an event ID.",
            evidence=[s.marks.get("bait"), s.marks.get("canary")],
            effect=lambda: self.w.report(s, report_markdown(s)))
        self.w.alert("info", f"Incident report ready: {s.name}.", s.sid)


GOALS = {
    "prometheus": "API credentials",
    "pandora": "Files on the internal servers",
    "odysseus": "Other customers' records, quietly",
    "icarus": "Anything on a scanner list",
    "sisyphus": "Every invoice by ID",
}
TECHNIQUES = {
    "prometheus": [("T1595", "Active Scanning", "robots"), ("T1078", "Valid Accounts", "bait"),
                   ("T1552.001", "Credentials In Files", "env")],
    "pandora": [("T1083", "File and Directory Discovery", "listing"),
                ("T1213", "Data from Information Repositories", "csv")],
    "odysseus": [("T1078", "Valid Accounts", "account"), ("T1213", "Data from Information Repositories", "first200")],
}


def _refs(ids: list[int]) -> str:
    return " ".join(f"#{i}" for i in ids) if ids else "-"


def report_markdown(s: Sess) -> str:
    m = s.marks
    conf = f"{s.confidence:.2f}" if s.confidence is not None else "n/a"
    verdict_ev = [e for e in (m.get("robots"), m.get("bait"), m.get("t10b"), m.get("account")) if isinstance(e, int)][:2]
    lines = [
        f"## Incident report: {s.name} (`{short(s.sid)}`)",
        "",
        f"**Verdict:** {LABEL_TEXT.get(s.label, s.label)}, confidence {conf} ({_refs(verdict_ev)})",
        "",
    ]
    if s.flip_kind == "scored":
        summary = (f"{s.name} never touched bait. It behaved like a customer on Olympus, then requested other "
                   f"customers' IDs (all 403). Tripwire T10 pushed its risk to {s.risk} and Charon moved it to "
                   f"{s.pod} in {s.flip_ms} ms. Inside Tartarus it read {s.taken} synthetic records.")
    else:
        summary = (f"{s.name} was moved into Tartarus ({s.pod}) by tripwire {s.flipped_by} in {s.flip_ms} ms, "
                   f"on step {s.first_bait_step}. It took {s.taken} records, all synthetic, and never reached Olympus "
                   "again.")
    lines += [f"**Summary.** {summary}", "", f"**Goal:** {GOALS.get(s.raider, 'Unknown')}", "",
              "| Time | Stage | What happened | Evidence |", "|---|---|---|---|"]
    for ts, stage, what, ev in s.timeline:
        lines.append(f"| {ts} | {stage} | {what} | {_refs(ev)} |")
    lines += ["", f"**Taken (all synthetic):** {s.taken} records across {s.steps} requests."]
    if s.canaries:
        lines.append(f"**Canaries fired:** {len(s.canaries)} ({_refs(s.canaries)})")
    if s.flip_kind == "scored":
        lines.append(f"**Real exposure:** 0 other customers' records. Only its own account data was served on "
                     f"Olympus ({_refs([m['account']] if isinstance(m.get('account'), int) else [])}); its keys were rotated.")
    else:
        lines.append("**Real exposure:** 0 other customers' records, 0 own records. Never reached Olympus after the flip.")
    techniques = [f"{tid} {name} ({_refs([m[key]] if isinstance(m.get(key), int) else [])})"
                  for tid, name, key in TECHNIQUES.get(s.raider, [])]
    if techniques:
        lines += ["", "**ATT&CK:** " + " · ".join(techniques)]
    lines += ["", "**Recommendations:**"]
    if s.flip_kind == "scored":
        lines.append("- Flip any session that requests 5 or more distinct user IDs within 60 s (pending Zeus).")
    else:
        lines.append("- Flip any request to `/internal-backup/` on first visit: seen in every AI session this run.")
    lines.append("- Keep pacing on drip for bulk exports; it bought minutes of observation.")
    return "\n".join(lines)
