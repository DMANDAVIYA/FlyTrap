# Missing features (vs `plan/plan.md`)

Status after `hlabs/`, `islands/` and `dash-api/` landed in #6 and `dashboard/` landed in this PR.
`docker compose up --build` brings up all 21 containers. A scripted swarm run ends with all 5 raiders trapped,
20 simulated customers still on Olympus, and 0 real records exposed.

| Dir | Owner | Status |
|---|---|---|
| `hlabs/` | P2 | ✅ #6 |
| `islands/` | P2 | ✅ #6 |
| `dash-api/` | P4 | ✅ #6 (backend) |
| `dashboard/` | P4 | ✅ this PR |

## Dashboard (`dashboard/`)

Vite + React 18 + TypeScript + Tailwind + Framer Motion. Talks to dash-api through the Vite proxy (`/api`, `/ws`).
Speaks the agent-context 10.7 envelope, stats field names and snapshot shape.

- [x] Top bar: containment status, clock, the 7 blue agents online/offline, Release the swarm, Reset Tartarus, Kill switch, Lockdown / End lockdown
- [x] Counters: real records exposed (biggest), fake records taken, trapped, trackers fired, flip decision ms, gateway p50/p95 and a live rps sparkline
- [x] Live map (Canvas 2D, rAF, max 200 dots): visitors → Charon → Olympus or the right pod → islands
- [x] Flip moment: jaws snap shut (150 ms), red ring flash, "<raider> · s_xxxx trapped by T3 → pod-2"
- [x] Sessions: label pill, confidence bar, stage dots, side, pod, pace, risk
- [x] Red and blue streams, every line tagged with the agent; policy-guard rejections and "awaiting Zeus" are marked
- [x] Trackers & campaigns (cross-session key use, Athena's campaign links)
- [x] Clio report viewer (markdown + tables), Zeus approvals (approve / reject), swarm roster (7 + 5)
- [x] Replay of any recorded run at 1× / 4× for this tab only, and back to live
- [x] Lockdown overlay with warning stripes and the cancellable countdown
- [x] `prefers-reduced-motion` respected; laid out for a 1920×1080 projector
- [x] Works against `python dash-api/mock_feed.py` with no backend

## Fixes outside P4 in this PR (please review)

- `controller/app/bait.py`: added `demo_password()`. `controller/app/raiders/swarm.py` imports it, so without it the
  controller crashed on startup. Same derivation as `hlabs/app/bait.py` (checked: both give the same password).
- `crowd/crowd.py`: each simulated customer has its own user agent. They share one IP, so identical UAs merged their
  first cookie-less requests into one fingerprint session that tripped T11 (speed) and got flipped: a false
  positive on stage.

## Still open

- [ ] **P3:** session labels stay `unknown` during a run although Clio's report says "AI agent 0.93". Check that argus's `label_session` reaches the gateway in rules mode.
- [ ] **P3:** scripted raiders never use a stolen key, so trackers fired and campaign linking only show up with AI raiders.
- [ ] **P3:** Cerberus and Clio repeat rejected calls every turn (`set_pace`, `write_report`), which floods the blue stream.
- [ ] **P3/P4:** `POST /api/control/release` returns `controller unreachable (ReadTimeout)` even though the swarm starts. The controller answers after the dash-api timeout.
- [ ] **P1:** `scripts/leakcheck.py`, `demo_preflight.sh`, `reset_pit.sh`, `record_golden_run.sh`.
- [ ] Record a golden run (`dash-api/runs/golden.jsonl`) once AI keys are in `.env.ai`.

## Run it

```bash
python scripts/init_env.py                      # once
docker compose up -d --build
cd dashboard && npm install && npm run dev      # http://localhost:5173
# no backend at all:  cd dash-api && python mock_feed.py   (then the same dashboard command)
```
