---
version: 1
slug: "dashboard-src-pages-landing-tsx"
primary_target: "dashboard/src/pages/Landing.tsx"
related_targets: ["dashboard/src/components/ui/modern-animated-hero-section.tsx","dashboard/src/components/three/Pills.tsx"]
---

# Landing page

Scope: `dashboard/src/pages/Landing.tsx` (route `#/`). Mode: Persuade.
Audience: HackUMass judges. Job: understand Dolos in 30 seconds, then take the red pill into the live console.
Proof: the README's five-step mechanism and the "Real records exposed: zero" claim. No invented numbers.
Constraints: renders with the backend down; never calls useFeed; WebGL lazy-loaded; reduced motion freezes rain, scramble and pills.

## Direction contract

THESIS: The page is the Matrix choice itself. One door, two worlds: the visitor chooses a pill and the page answers with what the attacker sees versus what really happens. Refuses the category default of a centred headline over a row of feature cards.

OWN-WORLD: Phosphor black ground (green-tinted), raining Latin and Greek letters in dim slate with phosphor-green flickers, JetBrains Mono for the decoding title and data, Mona Sans for plain-language copy. Blue (#4c8dff family) always means what looks real; red (#ff3355 family) always means the trap and the truth. Glossy translucent 3D capsules are the only objects.

STORY: The visitor reads "a honeypot for rogue AI that hides inside your real website", sees the two pills, learns each step as a mirrored pair (they see / really), and takes the red pill to the console.

FIRST VIEWPORT: Full-bleed letter rain. Centre: scramble title cycling DOLOS and ΔΟΛΟΣ at display scale, the hook line under it, then the two 3D pills side by side (blue left, red right) at hero scale with real buttons beneath each: "Blue pill: stay in the illusion" (opens the bait site) and "Red pill: see the truth" (opens the console). Scroll cue at the bottom edge.

FORM: Pinned by the user brief (Matrix raining letters + red/blue pill), position 1 of 1. seed: none (unavailable)

Signature interaction: Latin/Greek text scramble that decodes the truth line of each step as it enters view; pills tilt toward the pointer and swell on hover.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
