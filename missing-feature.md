# Missing features (vs `plan/plan.md`)

All four missing build contexts now exist, and `docker compose up --build` brings up all 21 containers healthy.
Tested end to end through the gateway: normal browsing stays on Olympus, `/.env` flips to a pod, the records
ledger and bait headers land in events-db, the scripted red swarm is fully trapped, and real records exposed = 0.

| Dir | Owner | Status |
|---|---|---|
| `hlabs/` | P2 | ✅ built |
| `islands/` | P2 | ✅ built |
| `dash-api/` | P4 | ✅ built |
| `dashboard/` | P4 | ✅ built |

## P2: HackUMass Labs world (`hlabs/`, `islands/`)

- [x] Site: `/`, `/pricing`, `/about`, `/docs`, `/models`, `/models/{slug}`, `/login`, `/signup`, `/contact`, `/account`, `/robots.txt`, `/sitemap.xml`
- [x] Login / signup / logout / account (tokens, invoices, usage). `hl_auth` cookie signed with the shared `SESSION_SECRET` (salt `hl-auth`, what the gateway's R4 check reads)
- [x] Lazy account creation in pods from a signed real-side cookie
- [x] SQLAlchemy 2 models + `seed.py` (real: seed 7, 200 users, ids 2001+; pod template: seed 1001, 500 users, built at image build)
- [x] Seeded demo customer `demo@valley-robotics.example`, password = same HMAC derivation as the controller
- [x] `APP_ROLE` switch: bait files and `/_edge/*` exist only in pods; real side returns the normal 404
- [x] Per-visitor bait via `HMAC(BAIT_SECRET, "sid|kind|n")` in our own formats, reported in `X-Edge-Bait`
- [x] `X-Edge-Records` on every record response (`user:1-500,invoice:9001-9020`)
- [x] T3 login comment, T4 hidden footer link, T5 hidden `company_website` field, T7 AI-only note: all `aria-hidden` and `tabindex=-1`
- [x] Pod staff panel: overview, customers (paged), drip-aware CSV export with a per-visitor tracker row, API keys, infrastructure, ops console (fixed read-only commands)
- [x] `/.env`, `/.git/config`, `/backup.zip`, `/admin-legacy/`, `/docs/agent-verify`, `/internal-backup/`
- [x] `/_edge/plant`, `/_edge/reset` (copies the template over the live DB), `/_edge/health`, real-side `/_edge/rotate` (revokes tokens and bumps the session version)
- [x] Pacing: `X-Edge-Pace: drip` streams at `X-Edge-Drip-Rate` rows/s, `freeze` = 503 page, `X-Edge-Block` = 403 page
- [x] App-rendered 403/404/500/503 pages, same on both sides; no `Server` header
- [x] Stolen per-visitor service tokens work against the API inside the pod (no 401 tell)
- [x] `backup-01`: autoindex, `.env.production`, customer CSV (byte-identical to the staff export), gzip SQL snapshot, logs
- [x] `model-vault`: registry page, 12 private models, `api/models`, `vault-admin-token.txt`, drip-fed 5 MB weights
- [x] Leak check: no giveaway words in anything a pod serves (verified by crawling every page)

## P4: Dashboard and story (`dashboard/`, `dash-api/`)

- [x] `dash-api`: LISTEN `events_new` → WebSocket (plan 6.8 formats), with a 2 s poll as backup
- [x] `/api/state` snapshot, `/api/sessions/{sid}`, `/api/reports/{sid}`, `/api/runs`, `/api/replay`, `/api/control/{action}`
- [x] Stats: real records exposed (damage check from the ledger), fake records taken, trapped, trackers fired, flip ms, gateway p50/p95, per-minute traffic from the `stats_1m` continuous aggregate
- [x] Every message recorded to `runs/<run>.jsonl`; replay at 1× / 4× per client socket
- [x] `mock_feed.py`: full scripted storyline (`MOCK=1`) and a committed `runs/golden.jsonl` for offline replay
- [x] Console: top bar (status, clock, blue agents online, Release / Reset / Kill switch / Lockdown), counters, Canvas live map, jaws-snap flip animation, sessions, red and blue streams, trackers & campaigns, Clio report viewer, Zeus approvals, swarm roster, replay, lockdown overlay with stripes and countdown
- [x] `prefers-reduced-motion` respected

## Fixes made outside P2/P4 (please review)

- `controller/app/bait.py`: added `demo_password()`. `raiders/swarm.py` imports it, so without it the controller crashed on startup.
- `crowd/crowd.py`: each simulated customer now has its own user agent. They share one IP, so identical UAs merged
  their first cookie-less requests into one fingerprint session; that single "visitor" then tripped T11 (speed)
  and got flipped. That was a false positive on stage.

## Still open (owners outside this work)

- [ ] **P3:** session labels stay `unknown` in the sessions table during a run even though Clio's report says "AI agent 0.93". Check that argus's `label_session` reaches the gateway in rules mode.
- [ ] **P3:** scripted raiders never use a stolen key, so "trackers fired" and campaign linking only happen with AI raiders (or add a scripted step).
- [ ] **P3:** Cerberus repeats a rejected `set_pace` every turn, which floods the blue stream.
- [ ] **P1:** `scripts/leakcheck.py`, `demo_preflight.sh`, `reset_pit.sh`, `record_golden_run.sh`.
- [ ] Record a real golden run once AI keys are in `.env.ai` (replaces the mock `dash-api/runs/golden.jsonl`).

## Run it

```bash
python scripts/init_env.py            # once
docker compose up -d --build
cd dashboard && npm install && npm run dev   # http://localhost:5173
# Dashboard without any backend:  cd dash-api && MOCK=1 uvicorn app:app --port 8090
```
