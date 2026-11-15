# Three UNO Q setup

Three Arduino UNO Q boards. One runs the lab; two are LED-matrix displays. Containers are **not** split across boards — safety rule 1 forbids trap↔real traffic over Wi-Fi.

## The board

Dual-brain: Qualcomm chip runs Debian Linux (Docker side) + STM32 microcontroller (LED matrix / sketch). Boots from built-in eMMC — no microSD or USB drive. Set up via **Arduino App Lab**, not the Arduino IDE (the IDE only programs the STM32).

Confirmed on board 1: Docker 26.1.5, `aarch64` (arm64), Compose 2.26.1, Docker usable without sudo, 3.58 GB RAM, ~21 GB free. SSH user `arduino`.

## Onboarding (each board, ~5 min, one at a time)

1. USB-C → Mac.
2. Open App Lab (auto-detects the board).
3. Set a board password.
4. Name it (`charon`, `olympus`, `tartarus` — one each).
5. Pick Wi-Fi: **HackUMass** (event network; eduroam/UMASS use client isolation and block device-to-device).
6. Let it update.
7. Terminal `>_`: confirm `docker --version` and `docker compose version`.

## Roles

| Board | Name | Runs |
|---|---|---|
| 1 | the lab | all ~17 containers, `docker compose up --build` |
| 2 | display | script reads dash-api WebSocket → LED matrix (one zone) |
| 3 | display | same, different zone |

## Deploy the lab to board 1

```bash
rsync -av --exclude node_modules --exclude .git "FlyTrap/" arduino@<board-ip>:~/FlyTrap/
ssh arduino@<board-ip> 'cd ~/FlyTrap && docker compose up --build'
```

RAM is tight (lab needs ~2–2.5 GB of 3.58 GB). Builds are slow on-board; build on the Mac first to confirm, then copy.

## Security — venue Wi-Fi

Team compose publishes 8080/8090 on all interfaces, no login on control buttons. On HackUMass Wi-Fi anyone could hit them. Bind to `127.0.0.1` (laptop) or `10.42.0.2:8080` via `!override` (board), or use a phone hotspot for the demo.
