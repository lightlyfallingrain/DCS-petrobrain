---
name: project_los_terrain_tolerance_accepted_omniscience_trade
description: world-model's terrain LOS check now has a 12.0 m tolerance band; accepted user trade, not a finding to re-raise.
metadata:
  type: project
---

`world-model/src/query/line_of_sight.py`'s `_TERRAIN_TOLERANCE_M = 12.0` (added
`fix/los-elevation-tolerance`, e58daec) makes terrain block only when it exceeds the sightline by
more than 12 m, instead of any amount. This necessarily lets Petrovich see units masked by terrain
clearing the sightline by less than 12 m — a deliberate, user-approved relaxation of the
no-omniscience invariant, sized to the theatre's own measured SRTM-vs-DCS stddev (11.52 m,
`world-model/ROADMAP.md` M7 entry).

**Why:** SRTM elevation grid is a sampled estimate, not ground truth; an exact-match terrain
check could place a real unit "underground" at its own position and block it from every angle
permanently (`plans/missed-aaa-detection/debug.md` — a real missed-AAA-detection defect).

**Lapse condition, carried in the constant's own comment:** 12 m is acceptable specifically
because the Mi-24P attacks in a run rather than from a masked pop-up hover. If this primitive is
ever asked to model a Ka-50, Apache, or other pop-up-and-shoot airframe, the tolerance was never
re-derived for that tactic and needs revisiting.

**How to apply:** Do not re-flag this tolerance as an omniscience violation in a future security
pass on this code unchanged — it is an implemented, reviewed decision (security-review.md,
`plans/missed-aaa-detection/`). Do re-check it if: (a) the constant changes, (b) a second caller
or an override parameter appears (implementation was deliberately a private module constant with
no override — a future override surface would need the same scrutiny as the original decision),
or (c) a pop-up-and-shoot airframe is added to scope, per the lapse condition above.
