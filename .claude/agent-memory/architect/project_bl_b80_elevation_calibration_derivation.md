---
name: bl-b80-elevation-calibration-derivation
description: How BL-B80 derived the 9K113's unmeasured elevation raw-to-degree conversion from two already-sourced facts, without a new probe
type: project
---

`body-layer/src/belief/sight_effector.py`'s own comment calls arg 876's (9K113 elevation readback)
degrees-per-unit "still unmeasured" — `CockpitMi24.dll` hides the true native angle from Lua; only
the piecewise gauge value reaches Export.lua. `plans/9k113-sight-pointing/plan.md` (BL-B80) derived
a conversion anyway, from two facts already on disk and otherwise unrelated:

1. The sourced physical field-of-regard limits, `optics.py`'s `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_
   OPTIC`: `regard_elevation_up_deg=20.0`, `regard_elevation_down_deg=-15.0`, sourced from the
   English Mi-24P manual §3.4.
2. The measured piecewise gauge split, `mainpanel_init.lua`'s declared mapping confirmed live
   (`aircraft-layer/research/2026-10-21-9k113-slew-readback-probe-findings.md`): command value →
   arg_876 is `value` for value ≥ 0, `0.75 × value` for value < 0.

The ratio `0.75` exactly equals `15/20`. That is the tell: `elevation_deg = arg_876 × 20.0` fits
*both* signed endpoints of the sourced physical range with zero free parameters (value=+1 → arg
+1.0 → 20°; value=−1 → arg −0.75 → −15°).

**Why this did not need an Investigator dispatch**: the unmeasured fact is genuinely unreachable
from the installed files (the angle is native, not exposed to Lua) — a further file-grep could not
have closed it, so Investigator had nothing more to find. What closed it was noticing that two
already-recorded, previously-unconnected measurements constrained each other to one answer. **How
to apply elsewhere**: before dispatching Investigator on an "unmeasured" DCS-internals gap, check
whether two sourced-but-separate numbers (a physical limit from the manual, a piecewise/ratio
measured live) already pin the value down algebraically — that search costs a few `grep`s and is
cheaper than a probe, and is a different move from "read more files" or "fly a probe."

The formula is still flagged `status="derived"`, not `"measured"`, and the plan stages a live
sanity check against the two known mechanical stops (same acceptance pattern azimuth's own
conversion used) — algebra from sourced facts narrows the risk, it does not retire it.
