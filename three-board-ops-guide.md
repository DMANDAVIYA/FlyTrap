# Three UNO Q — step-by-step ops guide

How to run Dolos/Flytrap on three Arduino UNO Q boards: **one board runs the whole lab, two drive LED-matrix displays.** Containers are **not** split across boards — safety rule 1 forbids trap↔real traffic over Wi-Fi.

This replaces the old split-across-boards version of this file. Board overview (hardware, onboarding, roles) lives in `docs/uno-q-setup.md`; this guide is the operational step-by-step and does not repeat it.

**Grounding.** Every command marked *(observed on Mac)* was run end-to-end on an arm64 Mac on 2026-11-15: stack built, `db-setup` ran, 19 services up, 15 raiders released, all 15 trapped, 0 real records exposed. Anything marked **[unverified on board]** was NOT reproduced on a UNO Q yet — the board is native Linux (not OrbStack), so the Postgres networking in particular may differ. Those steps say how to check, not what the answer will be.

---

## 0. Layout and the network decision

| Board | Hostname (from your note) | Runs |
|---|---|---|
| 1 | `charon` | the lab — all **19** services, one `docker compose` |
| 2 | `olympus` | LED display — WS client → matrix (one zone) |
| 3 | `tartarus` | LED display — WS client → matrix (another zone) |

The 19 services on board 1: gateway, controller, dash-api, web-1, web-2, pod-1..5, raider-1..5, crowd, rebuilder, backup-01, model-vault.

**Pick the network first — it decides two later steps.**
- **HackUMass / eduroam / UMASS**: eduroam and UMASS use client isolation (no device-to-device), so boards 2 and 3 cannot reach board 1. HackUMass allows it but is a shared venue network, and dash-api on 8090 exposes **unauthenticated** control endpoints (release, stop, reset, lockdown).
- **Phone hotspot (recommended for the demo)**: private LAN, device-to-device on, only your four devices present. Removes both problems above.

The rest of this guide calls board 1's address on the chosen network `BOARD1_IP`.

---

## 1. Onboard all three boards

Do the onboarding in `docs/uno-q-setup.md` for each board first (USB-C → App Lab → password → name → Wi-Fi → update → confirm `docker --version` / `docker compose version`). Name them `charon`, `olympus`, `tartarus`. Then continue here. Everything in sections 2–7 runs on **board 1 (`charon`)**.

---

## 2. Board 1 — copy the code

**Warning — `.env` travels.** `rsync` ignores `.gitignore`, so your Mac's `.env` (DB password) and `.env.ai` (**live API keys**) land on the board unless you exclude them. Two choices:

- **Ship them on purpose (simplest):** the keys now live on board 1, and the board's Postgres role password must equal the `DB_PASSWORD` in the shipped `.env` (section 4).
- **Keep them off the board:** add `--exclude '.env*'` and recreate on the board (section 3).

```bash
# from the Mac, repo parent dir. Add --exclude '.env*' if you do NOT want keys on the board.
rsync -av --exclude node_modules --exclude .git --exclude runs "FlyTrap/" arduino@BOARD1_IP:~/FlyTrap/
```
Expected: a file list ending in `sent … bytes`. node_modules and the dashboard build are not needed on board 1 (the console runs on your laptop, or not at all for a headless demo).

---

## 3. Board 1 — `.env` and `.env.ai`

If you shipped them in step 2, confirm the DB block is present:
```bash
cd ~/FlyTrap && grep -E '^(DB_HOST|DB_PORT|DB_USER|EVENTS_DB_NAME|REAL_DB_NAME)=' .env
```
Expected *(observed on Mac)*:
```
DB_HOST=host.docker.internal
DB_PORT=5432
DB_USER=postgres
EVENTS_DB_NAME=flytrap
REAL_DB_NAME=hlabs
```

If you excluded them, create them on the board:
```bash
cd ~/FlyTrap
python3 scripts/init_env.py            # writes .env + .env.ai from the examples
# set a DB password (no echo), then add keys to .env.ai:
sed -i "s|^DB_PASSWORD=$|DB_PASSWORD=$(openssl rand -hex 24)|" .env
nano .env.ai                           # DEEPSEEK_API_KEY (raiders), ANTHROPIC_API_KEY or GEMINI_API_KEY (defenders)
```
No keys at all → the whole system still runs in **rules mode**. DeepSeek drives the raiders; Claude/Gemini defend.

Gate: compose must interpolate cleanly.
```bash
docker compose config --services | wc -l      # expect 19
```

---

## 4. Board 1 — Postgres on the host  **[unverified on board]**

The app reaches Postgres at `${DB_HOST}` = `host.docker.internal`. On the Mac, OrbStack routed that to the host and the default config worked. **On the board (native Linux Docker) you must check, not assume.** Not verified: whether Postgres is installed, whether `arduino` has `sudo`, the Debian 13 Postgres version against this schema.

**4a. Install if absent.** Debian ships a `postgres` superuser role already (unlike Homebrew).
```bash
dpkg -l | grep -q postgresql || sudo apt update && sudo apt install -y postgresql
sudo -u postgres psql -c "ALTER ROLE postgres LOGIN SUPERUSER PASSWORD '$(grep ^DB_PASSWORD= ~/FlyTrap/.env | cut -d= -f2-)'"
```
This sets the cluster's `postgres` role password to match `.env`.

**4b. Probe reachability from a container (do this before editing any config).**
```bash
cd ~/FlyTrap
PW=$(grep ^DB_PASSWORD= .env | cut -d= -f2-)
docker run --rm --add-host host.docker.internal:host-gateway -e PGPASSWORD="$PW" postgres:16-alpine \
  sh -c 'getent hosts host.docker.internal; PGCONNECT_TIMEOUT=5 pg_isready -h host.docker.internal; \
         PGCONNECT_TIMEOUT=5 psql -h host.docker.internal -U postgres -d postgres -tAc "select 1"'
```
Branch on the result:
- **`accepting connections` + `1`** → reachable, go to 4c. *(This is what the Mac showed; the board may not, because it is native Linux.)*
- **`no response` / connection refused** → Postgres is not listening where the container connects. Edit `listen_addresses` in `postgresql.conf` to include the Docker bridge gateway shown by `getent hosts host.docker.internal` (resolve with `ip -4 addr show docker0` and any `br-*` for the custom networks) plus `localhost`, then `sudo systemctl restart postgresql` and re-probe.
- **`no pg_hba.conf entry for host "X"`** → X is the container's source IP. Add one line to `pg_hba.conf`: `host all all X/16 scram-sha-256`, reload with `sudo systemctl reload postgresql`, re-probe.

**Security.** Do **not** add `listen_addresses` for the Wi-Fi interface, and do not open `pg_hba` to `0.0.0.0/0`. Keep Postgres on the Docker bridge + `localhost`. If you end up needing `listen_addresses='*'`, firewall port 5432 on the Wi-Fi interface, or stay on the hotspot.

**4c. Create the databases and schema.**
```bash
docker compose run --rm db-setup
```
Expected *(observed on Mac)*:
```
created database flytrap
created database hlabs
event-log schema applied to flytrap
TimescaleDB not installed: using plain tables and a plain stats_1m view
```
TimescaleDB absent is fine — the event log falls back to plain tables.

---

## 5. Board 1 — images

The board is `aarch64`; Mac images built on Apple Silicon are `arm64` — same arch, so they load directly.

**Path A — build on the Mac, ship the images (recommended; the board's 4×A53 build is slow and RAM is tight).**
```bash
# on the Mac
docker compose build
docker save flytrap-controller flytrap-crowd flytrap-dash-api flytrap-gateway \
            flytrap-hlabs flytrap-islands flytrap-raider flytrap-rebuilder postgres:16-alpine \
  | ssh arduino@BOARD1_IP docker load
```
The eight `flytrap-*` images total ~1.6 GB *(observed on Mac)*; `postgres:16-alpine` is needed for `db-setup`. The image list comes from `docker compose config --images` plus `postgres:16-alpine`.

**Path B — build on the board.** `docker compose build` on board 1. Slower, and the lab needs ~2–2.5 GB of the 3.58 GB RAM.

---

## 6. Board 1 — start and verify

```bash
docker compose up -d --no-build
```
`--no-build` uses the loaded images; `--build` would rebuild on the board (the Mac's build cache does not travel). Expected: 19 containers `Created` then `Started` *(observed on Mac)*.

Verify the AI keys resolve:
```bash
docker compose exec -T controller python -m app.check_models
```
Expected: every chain `OK` *(observed on Mac: Claude, Gemini, DeepSeek all OK)*.

Full preflight:
```bash
python3 scripts/demo_preflight.py
```
Runs on stock `python3` *(verified on Mac — it shells out via `docker compose exec`)*. Expected tail:
```
Containers:  OK  19/19 services running
Endpoints:   OK  site through the gateway (HTTP 200) / dash-api (HTTP 200)
Swarm:       OK  blue agents (16) / red raiders (5) / trap copies 5/5
Controls:    OK  kill switch answers (HTTP 200)
READY FOR THE DEMO
```

---

## 7. Board 1 — bind the control ports (before anyone else is on the network)

Compose publishes gateway **8080** and dash-api **8090** on all interfaces with no auth on the control endpoints. Create a **board-local** `docker-compose.override.yml` (it auto-loads; do not rsync it back to the Mac) that binds them to board 1's LAN address so displays can reach 8090 but the open network cannot bind `0.0.0.0`:
```yaml
services:
  gateway:
    ports: ["BOARD1_IP:8080:8080"]
  dash-api:
    ports: ["BOARD1_IP:8090:8090"]
```
```bash
docker compose up -d        # recreate with the override
```
On an isolated phone hotspot you may skip this and leave the default `0.0.0.0` bind. If `BOARD1_IP` is DHCP-assigned, re-check it with `ip -4 addr` after the hotspot reconnects.

---

## 8. Boards 2 and 3 (`olympus`, `tartarus`) — LED displays  **[two gaps — not in the repo]**

Nothing for the displays exists in the codebase yet. Two pieces are missing:

**Gap 1 — the WebSocket→metric script (I can write this; the interface is grounded).**
- Connect `ws://BOARD1_IP:8090/ws?client=display-2` (use a fresh client id per connection; the server ignores any text you send, so a periodic ping keeps it alive).
- On connect you receive a snapshot, then live envelopes shaped `{"type": <string>, "ts": <iso>, "data": {...}}`. The types a display cares about:
  - `stats` (~every 2 s) → `data` has `trapped`, `real_records_exposed`, `fake_records_taken`, `canaries_fired`, `avg_flip_ms`, `active_sessions`, `rps_real`, `rps_trap`.
  - `flip` → a raider was just swapped into a trap (flash the matrix).
  - `lockdown` → `data.state` is `off`/`countdown`/`on` (red alert).
- Reference client: `dashboard/src/feed.ts` reduces this exact stream for the console.
- Suggested zones: board 2 shows `trapped` + a flash on each `flip`; board 3 shows `real_records_exposed` (the "0 = containment holding" hero number) + `rps_trap`.

**Gap 2 — driving the LED matrix from Linux  [unverified].** The red LED matrix is wired to the **STM32**, not the Qualcomm/Linux side where the WS script runs. Getting pixels from Linux to the matrix needs the Arduino App Lab bridge (serial from Linux to the STM32) or an STM32 sketch that reads serial and lights the matrix. This mechanism is not in the repo and is board-specific; confirm it from Arduino App Lab before wiring the script to it.

Ask me to write Gap 1 (the Python WS client) whenever you want it — Gap 2 needs the UNO Q matrix bridge pinned down first.

---

## 9. Day-to-day (board 1)

```bash
docker compose ps                                              # status
curl -X POST http://localhost:8090/api/control/release -H 'content-type: application/json' -d '{}'   # start a swarm
curl -X POST http://localhost:8090/api/control/stop            # kill switch
curl -X POST http://localhost:8090/api/control/reset           # reset counters (Reset Tartarus)
docker compose down                                            # stop the stack
```
Release with defaults launches 5 personas × 3 copies = 15 raiders *(observed on Mac: all 15 trapped, 0 real records exposed)*. On 4×A53 that may be heavy — start smaller with `-d '{"copies":1}'` (5 raiders) or trim the crowd with `-d '{"crowd":10}'`.

**Update flow:** re-`rsync` the code (or re-`docker save | docker load` new images), then `docker compose up -d --no-build`.

---

## 10. Not yet verified on a board — check these on first bring-up

- Postgres installed on Debian 13 and whether `arduino` has `sudo` (section 4).
- Debian 13's Postgres version against this schema.
- RAM and the 4×A53 cores under 15 AI raiders (the Mac had far more headroom). If it struggles, drop `copies`.
- What `10.42.0.2` in `docs/uno-q-setup.md` refers to (looks like a board's own AP address — confirm).
- Everything in section 8 (both displays).
