# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **HackUMass XIV judges and demo audience (primary for the landing page).** They have about 30 seconds to understand what the project does, then want to see it working live.
- **The demo operator (primary for the console).** A team member running the live demo on one laptop: releases the red swarm, watches visitors get trapped, approves drastic actions as Zeus, and triggers lockdown or the kill switch.

## Product Purpose

Dolos (formerly Flytrap) is a honeypot for rogue AI that hides inside a real website. One public address. Visitors who touch bait no real customer would ever see are silently moved into an identical copy of the site filled with fake data. Success is measured by one number: real records exposed stays at zero.

## Positioning

Classic honeypots sit to the side and hope to be found. Dolos stands in front of the real site like a load balancer with a trapdoor, swapping attackers into a same-code copy (Tartarus) while real customers stay on the real servers (Olympus). The switch is decided by plain in-memory rules, so the AI is never in the request path.

## Operating Context

- Runs on one laptop with Docker Compose; the console is a Vite React app on port 5173, talking to dash-api on 8090 over `/api` and `/ws`.
- The bait site (HackUMass Labs) is served on port 8080. It is the deception itself and must never carry the Dolos name, theme, or any giveaway word.
- Demo flow: release the swarm, watch flips on the live map, read Clio's incident report, show the zero counter.

## Capabilities and Constraints

- Cast: Charon (gateway), Olympus (real servers web-1, web-2, db-real), Tartarus (5 trap pods plus backup-01 and model-vault), Zeus (human approval). Blue swarm defenders: Athena, Argus, Hephaestus, Cerberus, Mnemosyne, Clio, Hermes (16 agents). Red swarm test raiders: Prometheus, Pandora, Odysseus, Icarus, Sisyphus.
- Tripwires: hidden paths, leaked `.env`, migration login in a page comment, hidden links and form fields, notes only AI agents read, stolen token use, record-ID walking, attack signatures.
- Every bait value is unique per visitor, so a used token names who took it and links visitors into campaigns.
- Drastic actions (release, global patches, lockdown, restarts) wait for Zeus.
- Infrastructure identifiers (docker project, container, image and database names, env vars) stay `flytrap`; only the brand changed.
- The console must render without the backend (landing page) and must keep lockdown, breach status, kill switch and replay state visible at all times.

## Brand Commitments

- Name: **Dolos** (Greek ΔΟΛΟΣ, the spirit of trickery). Never on anything an attacker can reach.
- World pinned by the user (second round, replaces the Matrix world): Greek gods, with Hermes, trickster and guide of souls to the underworld, as the defending AI agent. Black and green shades only.
- Type pinned by the user from 2016.makemepulse.com: Montserrat for UI and copy (wide uppercase tracking for labels), an ultra-condensed display face standing in for Univers Ultra Condensed (Sofia Sans Extra Condensed, which also carries the Greek letters).
- Landing hero pinned by the user's reference image: two hands reaching toward one object on black (a Creation of Adam composition). Here the object is the bait, a glowing `.env` vial; the hands come from Michelangelo's public-domain fresco.
- Console model pinned by the user: an interactive bento grid with cursor-following glow cards, reading only real feed data.
- Colour meaning across surfaces: sage = what looks real (Olympus), bright green = the trap (Tartarus) and the primary action, amber = Zeus and lockdown, red = "containment breached" only.

## Evidence on Hand

- README.md and plan/plan.md: the five-step mechanism, the cast, the claim "Real records exposed: zero."
- Live data from dash-api (sessions, flips, stats, reports) and recorded runs in `runs/` (golden.jsonl) for replay.
- No customers, benchmarks, pricing or testimonials exist; do not invent any.

## Product Principles

1. Show the mechanism, not a claim: one door, two worlds, and the switch between them.
2. Plain words first; myth names are labels, never the explanation.
3. The operator never loses sight of safety state: breach, lockdown, kill switch.
4. The deception stays perfect: nothing branded leaks into the bait site.

## Accessibility & Inclusion

Respect `prefers-reduced-motion`: hero motion, the glyph hand and the how-it-works animation freeze; content stays visible. Every pointer effect has a keyboard equivalent.
