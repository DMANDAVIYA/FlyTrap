---
version: 1
slug: "dashboard-src-pages-console-tsx"
primary_target: "dashboard/src/pages/Console.tsx"
related_targets: ["dashboard/src/components/three/TrapMap.tsx"]
---

# Console

Scope: `dashboard/src/pages/Console.tsx` (route `#/console`). Mode: Operate.
User: the demo operator on a laptop at the judging table. Task: release the swarm, watch visitors fall into Tartarus, approve Zeus actions, hit lockdown or the kill switch, open a trapped session's incident report.
Information on the main screen only: 3D trap map, three vitals (real records exposed, visitors trapped, flip time), trapped-session list, Zeus approvals when one waits, controls, breach/lockdown/replay state. Everything else (agent streams, trackers and campaigns, incident report, roster, replay) lives in a right-hand drawer with tabs.

## Direction contract

THESIS: A minimal containment console whose hero is the trap made visible: a 3D cross-section with Olympus above a glass floor and Tartarus, its mirrored red copy, below it, connected by Charon's trapdoor. Refuses the default wall of equal panels.

OWN-WORLD: Same phosphor-black ground and tokens as the landing page; Mona Sans for labels, JetBrains Mono tabular numerals for data. Blue = real traffic and Olympus, red = trapped traffic and Tartarus, amber = Zeus and lockdown, phosphor green = containment holding. Hairline borders, no cards inside cards.

STORY: The operator sees at a glance that containment holds (zero exposed), watches each new visitor travel through Charon and either reach Olympus or drop through the trapdoor, and acts from one control row.

FIRST VIEWPORT: Top bar: Dolos mark and wordmark, status, live state, controls (Release, Reset, Kill switch, Lockdown), Details toggle. Body: map at roughly three quarters width, full height; right rail with the three vitals stacked, approvals when pending, then trapped sessions. Flip banner over the map.

FORM: Pinned by the user brief (3D live map of what the traps are, minimal data), position 1 of 1. seed: none (unavailable)

Signature move: visitors as particles that fall through the trapdoor into the mirrored copy; the trapped pod pulses red on each flip.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
