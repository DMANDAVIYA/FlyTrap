# Flytrap

A honeypot for rogue AI that hides inside your real website.

One public address. Visitors who touch bait no real customer would ever see are silently moved into an identical copy of the site filled with fake data. Every step is recorded, each visitor is labelled human, scanner or AI agent, and a swarm of seven defending AI agents responds through least-privilege tools. Real records exposed: zero.

Built at HackUMass XIV.

> Every company already has a load balancer at the front door. Flytrap is a load balancer with a trapdoor.

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

Add the keys you have to `.env.ai` (Gemini, Anthropic, OpenAI, DeepSeek, Kimi/Moonshot, Qwen, GLM, OpenRouter), then restart the controller and test them:

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
