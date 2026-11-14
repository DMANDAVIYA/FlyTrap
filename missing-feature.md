# Missing features (vs `plan/plan.md`)

Status of the repo against the Main plan. Two whole tracks are unstarted and
`docker compose up` currently fails because these build contexts are referenced
in `docker-compose.yml` but do not exist on disk.

## Blocking: missing build contexts

| Missing dir | Owner | Referenced by | What it is |
|---|---|---|---|
| `hlabs/` | P2 | `web-1`, `web-2`, `pod-1..5` | The HackUMass Labs site. One codebase run as both real servers and trap pods. |
| `islands/` | P2 | `backup-01`, `model-vault` | Two fake internal machines reachable only from inside a pod. |
| `dash-api/` | P4 | `dash-api` | Snapshot API, WebSocket feed, replay, button proxy. |
| `dashboard/` | P4 | host dev server | The React/Vite containment console. |

## P2 — HackUMass Labs world (`hlabs/`, `islands/`)

- [ ] Site layout + 7 or more pages (home, pricing, docs, login, signup, account, API)
- [ ] Login / signup / account flows, lazy account creation
- [ ] SQLAlchemy 2 models + `seed.py` (real side and pod template, Faker fixed seed)
- [ ] `Dockerfile` and `APP_ROLE` switch (real vs pod)
- [ ] Bait rendering with HMAC values and `X-Edge-Bait` header
- [ ] `X-Edge-Records` header on every record response
- [ ] Pod admin panel (customers, drip-aware export, API keys, infrastructure)
- [ ] `/_edge/plant` and `/_edge/reset` endpoints
- [ ] Fake `.env` / backup files / model vault contents
- [ ] `backup-01` fake file server island
- [ ] `model-vault` fake model registry island
- [ ] Real key rotation endpoint, fake ops console, error pages
- [ ] `seed/texts.json`, seeded demo customer for Sisyphus and Odysseus

## P4 — Dashboard and story (`dashboard/`, `dash-api/`)

- [ ] `dash-api`: `mock_feed.py` + WebSocket, `/api/state`, session detail
- [ ] Live data path (LISTEN/NOTIFY → WebSocket), replay, button proxy
- [ ] Vite app: layout + tokens, counters, red/blue streams, sessions list
- [ ] Live map + snap animation, swarm roster, campaigns panel
- [ ] Report viewer, approvals (Zeus), lockdown overlay
- [ ] "Release the swarm" and "Reset Tartarus" buttons

## Suggested order

1. `hlabs/` — unblocks the whole compose stack (gateway has nothing to route to).
2. `islands/` — needed for Pandora's exploration story.
3. `dash-api/` + `dashboard/` — the demo is visual.
