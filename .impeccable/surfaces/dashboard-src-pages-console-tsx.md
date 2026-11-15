---
version: 1
slug: "dashboard-src-pages-console-tsx"
primary_target: "dashboard/src/pages/Console.tsx"
related_targets: ["dashboard/src/components/ui/glow-card.tsx"]
---

# Console

Scope: `dashboard/src/pages/Console.tsx` (route `#/console`). Mode: Operate.
User: the demo operator on a laptop at the judging table. Task: release the swarm, watch visitors get trapped, approve Zeus actions, hit lockdown or the kill switch, open a trapped session's incident report.
Main screen, modelled on the user's reference dashboard (soft analytics cards) and kept black and green: traffic trends with a highlight band and a legend chip; six live readings as tiles (real records exposed, trapped, flip time, active sessions, fake records taken, marked keys used) with change chips over the last minute of live readings; visitors as Argus labels them around a lit orb; the pantheon over the gateway's decision-time chart; a tabbed table (trapped visitors, agent messages, requests, trackers) with Open report and All streams. Zeus approvals lead the page while one waits. A Raw switch at the top right of the header shows the same feed as a terminal UI. Always visible: lockdown overlay, breach status, kill switch, lockdown button, REPLAY badge. Incident report, trackers, roster, full agent streams and replay live in the right-hand drawer. Every card reads the real feed; empty states say what fills them.

## Direction contract

THESIS: Soft, rounded analytics cards on black, lit green: the reference dashboard's calm grid carrying a live trap. A Raw switch turns the console into a terminal UI of the same feed, for operators who want every field.

OWN-WORLD: Same black and green tokens as the landing page, with three console surfaces: page, card, inner panel. Montserrat sentence-case card titles and semibold readings; JetBrains Mono for times, ids, chart axes and the whole raw view. Sage = real, bright green = trapped, amber = Zeus and lockdown, red = breach only (never for a negative change).

STORY: The operator sees at a glance that containment holds (zero exposed), watches trapped traffic against real traffic, picks a trapped visitor and opens its report, and acts from one control row.

FIRST VIEWPORT: Header: mark, status, live state, controls (Release, Reset, Kill, Lockdown, Details) and the Raw switch at the far right. Zeus approvals when any wait, then two rows: traffic beside the six reading tiles; visitors, the pantheon over the gateway, and the tabbed table.

FORM: Pinned by the user: their reference dashboard image, recoloured green on black, plus a raw terminal view. seed:a1faaef247878c11 (direction pinned by the user; roll recorded only)

Signature move: the glowing trapped line with its highlight band, and the lit visitors orb.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
