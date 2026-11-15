---
version: 1
slug: "dashboard-src-pages-console-tsx"
primary_target: "dashboard/src/pages/Console.tsx"
related_targets: ["dashboard/src/components/ui/glow-card.tsx"]
---

# Console

Scope: `dashboard/src/pages/Console.tsx` (route `#/console`). Mode: Operate.
User: the demo operator on a laptop at the judging table. Task: release the swarm, watch visitors get trapped, approve Zeus actions, hit lockdown or the kill switch, open a trapped session's incident report.
Main screen, split in two sides by the user's request: attackers on the left (live real-vs-trapped traffic, trapped visitors, raider messages, what they took), defenders on the right (vitals: real records exposed, trapped, flip time; the pantheon; visitor types as Argus labels them; defender messages; Zeus approvals when one waits). Always visible: lockdown overlay, breach status, kill switch, lockdown button, REPLAY badge. Incident report, trackers, roster, full agent streams and replay live in the right-hand drawer. Every card reads the real feed; empty states say what fills them.

## Direction contract

THESIS: A calm bento of live readings lit by a torch: the cursor carries a green glow across card borders and faces. Refuses a wall of equal panels and any 3D or terminal costume.

OWN-WORLD: Same black and green tokens as the landing page. Montserrat wide capitals for card titles and controls, Sofia Sans Extra Condensed for the big numerals that do not tick, JetBrains Mono tabular figures for live data and the log. Sage = real, bright green = trapped, amber = Zeus and lockdown, red = breach only. Rounded cards with a hairline border; no boxes inside cards.

STORY: The operator sees at a glance that containment holds (zero exposed), watches trapped traffic rise against real traffic, reads Hermes' messages, and acts from one control row.

FIRST VIEWPORT: Top bar: mark and wordmark, status, live state, controls (Release, Reset, Kill switch, Lockdown), Details. Two mirrored sides under a hairline seam, each with its own heading and one-line summary. Attackers (bright green heading): traffic across the top, trapped visitors down the outer left edge, raider messages and what they took beside it. Defenders (sage heading): vitals across the top, the defender log down the outer right edge, pantheon and visitor types beside it. A Zeus card leads the defenders' side while an approval waits.

FORM: Pinned by the user brief (interactive bento with glow cards, Greek theme), position 1 of 1. seed:a1faaef247878c11 (direction pinned by the user; roll recorded only)

Signature move: torch-light glow that follows the pointer across cards; the trapped line glows on the traffic chart.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
