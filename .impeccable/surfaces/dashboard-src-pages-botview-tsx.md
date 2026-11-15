---
version: 1
slug: "dashboard-src-pages-botview-tsx"
primary_target: "dashboard/src/pages/BotView.tsx"
related_targets: ["dashboard/src/components/see/CompareFlow.tsx"]
---

# What the bot sees

Scope: `dashboard/src/pages/BotView.tsx` (route `#/see`), opened by every "See what the bot sees" button. Mode: Persuade.
Audience: HackUMass judges. Job: feel the deception by dragging between the two worlds, then open the console or the live bait site.
Proof: the README's five steps; no invented numbers. Renders without the backend.

## Direction contract

THESIS: A before/after compare window, like an image-enhancement slider, laid over a live flow chart: the same five steps in the same places, seen by the bot on one side and as they really are on the other. Refuses a static two-column table.

OWN-WORLD: The landing page's black and green world: Montserrat wide capitals, Sofia Sans Extra Condensed display, sage for what the bot sees, bright green for what really happens, Olympus above the floor and Tartarus below it.

STORY: The visitor drags the bar left and watches the calm website give way to Charon, the tripwire, the trapdoor and Tartarus, while the bot walks the steps live; step buttons and a two-column caption keep both texts readable.

FIRST VIEWPORT: Nav (mark, Home, Console). Title "What the bot sees" and one line telling the visitor to drag. The compare window with a live-flow bar (step counter, pause), the draggable bar at 50% after one hint sweep. Below: step buttons, the step heading, "They see" and "What really happens".

FORM: Pinned by the user request (before/after slider over a real-time flow chart), position 1 of 1. seed:bc636251517c51a6 (direction pinned by the user; roll recorded only)

Signature interaction: dragging the bar; left reveals what really happens, right reveals what the bot sees. Keyboard: arrow keys, Home and End on the grip.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
