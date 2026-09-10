---
name: project_bl3_gating_placement
description: BL-3 pattern — policy/attention-gating logic must live in belief/, not perception/; verify by checking the geometry-layer function takes a plain scalar knob, not a Contact/Attention type.
metadata:
  type: project
---

BL-3 (world enrichment, `plans/bl3-world-enrichment/plan.md`) established a reusable review
check: when a `perception/` primitive (e.g. `geometry.project_terrain_aware`) needs a
caller-tunable knob whose value depends on `belief`-side state (contact attention, distance
thresholds), the knob must arrive as a plain scalar (`max_iterations: int`), with the actual
policy decision (what value to pass) computed in `belief/` (here, `enrichment.py`). Confirmed by
grepping the perception-layer function's body for any import/reference to `belief.contacts`'
`Attention` type — it must have none.

**Why:** `perception/` must never import `belief/` (documented import-discipline rule, reused
from BL-2.6's own perception→belief prohibition). A gating policy accidentally written inside
`geometry.py` would force that import.

**How to apply:** For any future milestone that adds a caller-tunable knob to a `perception/`
function, check where the *decision* about the knob's value lives, not just that the knob
exists. Grep the perception file for belief-layer imports as the mechanical check.
