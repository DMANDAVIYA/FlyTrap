# Flytrap

A honeypot for rogue AI that hides inside your real website.

One public address. Visitors who touch bait no real customer would ever see are silently moved into an identical copy of the site filled with fake data. Every step is recorded, each visitor is labelled human, scanner or AI agent, and a swarm of seven defending AI agents responds through least-privilege tools. Real records exposed: zero.

Built at HackUMass XIV.

> Every company already has a load balancer at the front door. Flytrap is a load balancer with a trapdoor.

## The cast

| Name | What it is |
|---|---|
| Olympus | The real servers (web-1, web-2, db-real) |
| Tartarus | The trap network: 5 trap pods and 2 fake internal machines |
| Charon | The gateway that routes every request |
| Zeus | The human approval button |
| Athena, Argus, Hephaestus, Cerberus, Mnemosyne, Clio, Hermes | The blue swarm (defenders) |
| Prometheus, Pandora, Odysseus, Icarus, Sisyphus | The red swarm (test attackers, pointed only at our own lab) |

## Quick start

```bash
python scripts/init_env.py     # creates .env (random secrets) and .env.ai (add your AI keys)
docker compose up --build
```

- Site: http://localhost:8080
- Dashboard API: http://localhost:8090
- Dashboard: `cd dashboard && npm install && npm run dev`, then http://localhost:5173

Full plan and specification: [`plan/plan.md`](plan/plan.md). Coding agent brief: [`plan/agent-context.md`](plan/agent-context.md).

## Safety

- The trap network has no route to the real servers or the internet.
- Test attackers can reach exactly one host, our gateway, with one HTTP tool. No shell, no code execution, no files.
- Only the controller has internet, and only to call AI APIs. Keys live in `.env.ai`, which is never committed.
- All data is generated. No real personal data, no real provider key formats.
