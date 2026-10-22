---
name: bl-b80-elevation-calibration-derivation
description: SUPERSEDED 2026-10-22 -- BL-B80 v1 derived a 9K113 elevation raw-to-degree formula from arg 876, but 874/876 turned out to echo the demand, not the head; the derivation technique stands, the formula is void
type: project
---

**Superseded 2026-10-22.** Probe runs 1-10 (`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`)
showed args 874/876 echo the AI-axis *demand*, not the sight head, and the AI axis is a rate
command. So the v1 formula `elevation_deg = arg_876 * 20.0` (BL-B80 v1, now
`plans/9k113-sight-pointing/plan-v1-position-model.md`) calibrated an echo, and v2 removes it. The
real readback is the ASP-17 mark (565/566 az, 555/556 el), calibrated in flight (v2 Stage 0).

**What still holds -- the technique:** before dispatching Investigator on an "unmeasured" value,
check whether two sourced-but-unrelated numbers (a manual limit, a measured ratio) pin it down
algebraically (0.75 == 15/20 was the tell).

**The new lesson on top:** an elegant zero-free-parameter fit says nothing about whether the
*signal* means what you think. Ask "what physical quantity is this arg?" before fitting it -- the
fit was perfect and the arg was the wrong quantity.
