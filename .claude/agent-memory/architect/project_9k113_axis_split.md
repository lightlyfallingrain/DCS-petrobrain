---
name: project_9k113_axis_split
description: BL-B64 splits on perception-versus-effectors, not ATGM-versus-non-ATGM — the sight's multipliers/FOV were already measured and sitting unused, so the perception half is nearly free while every cockpit-visible use sits behind an unverified write channel
metadata:
  type: project
---

Planning `BL-B64` (the 9K113 sight), 2026-10-15. `plans/9k113-sight/plan.md`.

**The brief assumed the cheap first slice was the non-ATGM uses** (hold the crosshair so the pilot
reads the target off the ASP-17; pinpoint a unit on request). **It is not** — both require the pilot
to *see* where the sight points, which requires the real cockpit switches to move. They sit at the
far end of the dependency chain.

**The axis that actually splits this feature:**

| axis | delivers | depends on |
|---|---|---|
| **A — perception** | sight-grade detection/class/type range, and position belief precise at that range | nothing outside body-layer |
| **B — effectors** | switches moving, ASP-17 mark, ATGM run | unverified write channel on devices 6/7, 9K113 telemetry args, a sub-1 s loop, missile speed/range (missing), a readiness lamp with no read path |

**Why axis A is nearly free, and this is the transferable part — three assets already on disk:**

1. **The multipliers were already measured** and are sitting *in a docstring* rather than as
   constants: `perception/optics.py` records wide 3.55/7.00/6.50, narrow 5.81/13.75/15.00 from
   detection-cones slice 2A, deliberately not instantiated. FOV (11.5°/6.0°) and field of regard
   (±60° az, +20/−15° el) are in `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`.
   **No calibration sortie is needed.** Found by reading the file the plan was going to edit —
   which is the step this role keeps skipping.
2. **`BINOCULAR_OPTIC` has no cockpit representation and never has.** A purely simulated optic is
   the established pattern here, not a shortcut. Worth knowing before anyone argues a sight needs
   its switches to exist first.
3. **`BL-B55` is one parameter** (`self.optic` already in scope at `naked_eye_source.py:949`), so
   per-optic position sigma folds into the same stage. It must not be separated from the optic:
   a sight seeing to 8 km with `σ_down ≈ 0.17·R` tells the pilot a precise-sounding range wrong by
   1.4 km — worse than not having the sight.

**Two existing mechanisms that covered things the spec framed as new:**
- `optic_policy.STEADY_RATE_LIMIT_DEG_S = 12.0` already does "manoeuvre makes the instrument
  unusable" off attitude rate. Reuse the mechanism, separate constant (gyros tolerate more than
  hands).
- The 1 s eyes-away/hands-busy cost is expressible as one `hands_busy_until_sim` field; the spec's
  eyes-away → switch → eyes-back is then two in sequence, not a special case.

**How to apply.** When a spec arrives written as one monolith, look for the seam between *what the
crew member perceives* (usually pure, usually in-process, usually cheap) and *what moves in the
cockpit* (cross-subproject, unverified, expensive to accept). This project's optics have that seam
by construction and it is where the staging belongs. Related:
[[project_binocular_stage3b]], [[project_two_perception_mechanisms_relative_vs_map]].
