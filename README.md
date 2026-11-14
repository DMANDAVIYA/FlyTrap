# Flytrap

A honeypot for rogue AI that hides inside your real website.

One public address. Visitors who touch bait no real customer would ever see are silently moved into an identical copy of the site filled with fake data. Every step is recorded, each visitor is labelled human, scanner or AI agent, and a swarm of seven defending AI agents responds through least-privilege tools. Real records exposed: zero.

Built at HackUMass XIV.

> Every company already has a load balancer at the front door. Flytrap is a load balancer with a trapdoor.

## How it works

```
 visitors ──► Charon (gateway) ──► Olympus  (web-1, web-2, real data)
                   │
                   └── touched bait? ──► Tartarus (5 trap copies + backup-01 + model-vault, fake data)
                   │
                   ▼ every request, flip, tripwire and canary
            event log (PostgreSQL + TimescaleDB hypertable)
                   │
                   ▼
            blue swarm (7 agents) ──► actions through a policy guard ──► Charon admin API
```

1. **Charon** decides every request with plain rules in memory, so the switch adds no visible delay. The AI is never in the request path.
2. **Tripwires** fire on things no real customer does: a robots.txt-hidden path, a leaked `.env`, a migration login in a page comment, a hidden link, a hidden form field, a note only AI agents read, a stolen token being used, record-ID walking, attack signatures.
3. A tripped visitor is **flipped** into its own trap copy: same code, same pages, valid login, fake data. Instant flips are permanent; Charon enforces that in code.
4. Every value of bait is **unique per visitor**, so a stolen token used anywhere names who took it and links separate visitors into one **campaign**.
5. The **blue swarm** reads compact session summaries, decides, and acts only through tools its role holds. Drastic actions (release, global patches, lockdown, server restarts) wait for **Zeus**, a human.

## The blue swarm

| Agent | Job | Default model |
|---|---|---|
| Athena | Commander: campaigns, damage checks, lockdown requests | Claude Opus 5.5 |
| Argus | Labels visitors human, scanner or AI agent | rules (scoring) |
| Hephaestus | Plants unique bait, rotates keys after a real-side probe | Claude Opus 5.5 |
| Cerberus | Slows, drip-feeds, freezes, blocks trapped visitors | Meta Muse Spark 1.3 |
| Mnemosyne | Fingerprints attackers, suggests new tripwires | rules |
| Clio | Writes incident reports that cite event IDs | Claude Opus 5.5 |
| Hermes | Alerts | rules |

The red swarm releases 3 copies of each raider by default (15 raiders, each copy on its own runner and IP) and runs only Chinese models: Prometheus, Icarus and Sisyphus on DeepSeek V4 Pro, Pandora and Odysseus on Kimi K3.1 Pro, each falling back to the other. Claude and Gemini refuse the raider brief, so they only defend. Every chain lives in `controller/app/models.py` (keys go in `.env.ai`); the first model in a chain is retried on rate limits and never benched, a raider with no working model runs its scripted storyline, and without any keys the whole system runs in rules mode.

## The cast

| Name | What it is |
|---|---|
| Olympus | The real servers (web-1, web-2) |
| Tartarus | The trap network: 5 trap pods and 2 fake internal machines |
| Charon | The gateway that routes every request |
| Zeus | The human approval button |
| Athena, Argus, Hephaestus, Cerberus, Mnemosyne, Clio, Hermes | The blue swarm (defenders) |
| Prometheus, Pandora, Odysseus, Icarus, Sisyphus | The red swarm (test attackers, pointed only at our own lab) |

## Quick start

Needs Docker and a local PostgreSQL (any recent version; TimescaleDB optional).

```bash
python scripts/init_env.py           # creates .env and .env.ai; set DB_PASSWORD in .env
docker compose run --rm db-setup     # creates the flytrap and hlabs databases on your PostgreSQL
docker compose up --build
```

All database settings live in `.env` (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `EVENTS_DB_NAME`, `REAL_DB_NAME`). Containers reach your PostgreSQL through `host.docker.internal`, so you can browse both databases in pgAdmin. If TimescaleDB is installed, `db-setup` turns the event log into a hypertable with a continuous aggregate; otherwise it uses plain tables.

- Site: http://localhost:8080
- Dashboard API: http://localhost:8090
- Dashboard: `cd dashboard && npm install && npm run dev`, then http://localhost:5173

## AI models

Add the keys you have to `.env.ai` (Gemini, Anthropic, OpenAI, DeepSeek, Kimi/Moonshot, Qwen, GLM, Meta, OpenRouter), then restart the controller and test them:

```bash
docker compose up -d --force-recreate controller
docker compose exec controller python -m app.check_models          # add --list to see each provider's model names
```

Every model setting is a fallback chain; providers without a key are skipped and agents fall back to rules mode if nothing works.

## Before the demo

```bash
python scripts/demo_preflight.py     # containers, site, swarm, trap copies, counters, kill switch
python scripts/leakcheck.py          # crawls the trap copies for anything that gives them away
```

Press Reset Tartarus afterwards (`curl -X POST localhost:8090/api/control/reset`). Every run is recorded to `runs/`; save the best one as `runs/golden.jsonl` for replay.

Full plan and specification: [`plan/plan.md`](plan/plan.md). Coding agent brief: [`plan/agent-context.md`](plan/agent-context.md).

## Safety

- The trap network has no route to the real servers or the internet.
- Test attackers can reach exactly one host, our gateway, with one HTTP tool. No shell, no code execution, no files.
- Only the controller has internet, and only to call AI APIs. Keys live in `.env.ai`, which is never committed.
- All data is generated. No real personal data, no real provider key formats.

## Tech stack

Python 3.12, FastAPI, httpx, asyncpg, SQLAlchemy 2, Jinja2, Faker; PostgreSQL 18 with TimescaleDB (hypertable plus continuous aggregate); Docker Compose (19 containers, 7 networks); AI through OpenAI-compatible APIs from Anthropic, Google Gemini, Meta, DeepSeek and Moonshot (Kimi); Qwen, GLM and OpenRouter are supported if a key is added.

## Measured on one laptop

Numbers from our own runs on a single Windows laptop (Docker Desktop, 19 containers, PostgreSQL 18 on the host). Nothing here is extrapolated.

| What | Result | How |
|---|---|---|
| Gateway decision time | p50 0.22 ms, p95 0.58 ms | `scripts/loadtest.py`, 60 s |
| Gateway throughput | peak 108 req/s, mean 86 req/s, 0 errors | 40 customers, 10 drones, raiders and 16 extra browsers at once |
| End-to-end page latency under that load | p50 274 ms, p95 868 ms, p99 1,328 ms | mostly the site itself (Python and Postgres on the same laptop) |
| Flip into Tartarus | 0.19 to 0.31 ms average | dash-api live stats |
| Other customers' records served to any raider | 0 | golden run: 15 AI raiders, 15 flips, 26 canaries, 14 reports |
| Argus labels in the golden run | 15 of 15 AI raiders ai_agent, 10 of 10 customers human, drones scanner | `runs/golden.jsonl` |
| Rolling rebuild after Zeus approves | 10 s, 58 requests during the roll, 0 failed | uptime probe every 0.2 s |

## Tests

```bash
docker build -t flytrap-gateway gateway && docker run --rm -v "$PWD/gateway/tests:/srv/tests:ro" flytrap-gateway python -m pytest -q tests
docker build -t flytrap-controller controller && docker run --rm -v "$PWD/controller/tests:/srv/tests:ro" flytrap-controller python -m pytest -q tests
docker build -t flytrap-hlabs hlabs && docker run --rm flytrap-hlabs python -m pytest -q
```

Gateway, controller, site and islands suites run inside their containers; `scripts/leakcheck.py` checks the live trap copies end to end.

## Prior art and credits

Routing attackers into decoys is not new: Bait-and-Switch (2003), Shadow Honeypots (2005), Honey-Patches (2014-2015) and Han et al.'s deployment study (2017). AI-agent honeypots exist too: Palisade Research's LLM Agent Honeypot, Beelzebub and HoneyMCP; Argus's "hidden instruction plus machine speed" signal follows Palisade's two-gate idea. Flytrap adds a same-code twin with one trap copy per attacker, evidence-backed human/scanner/AI labels, campaign linking through per-visitor bait, and a least-privilege defending swarm with human approval gates.

Built entirely during HackUMass XIV. All data is generated; the company, HackUMass Labs, is fictional.
