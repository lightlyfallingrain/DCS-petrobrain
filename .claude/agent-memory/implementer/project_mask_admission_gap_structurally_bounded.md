---
name: project_mask_admission_gap_structurally_bounded
description: in body-layer naked-eye scenarios, the time a founded contact stays masked before a second nearby contact is admitted is bounded by separation - admission_range + mask_range, not freely tunable via speed/offset alone
metadata:
  type: project
---

Found while rebuilding `BL-B104` Stage 7's "two groups on one bearing"
scenario (`plans/bl-b104-ground-contacts-on-ground/`, review.md Finding 5)
to produce a genuine masked-then-fold-risk window long enough to exercise
Stage 8's growth-rate gate.

**The structural bound**: for two ground units on the same bearing line at
separation `S` (e.g. 1500 m), with the near unit's forward cockpit-mask
threshold `mask_range = AGL / tan(22deg)` and the naked-eye channel's own
typical first-admission true range `admission_range` (empirically ~1900-
2400 m, noisy/stochastic, roughly independent of AGL or lateral offset in
the range tried), the achievable gap between "near unit enters mask" and
"far unit gets admitted" is approximately:

    gap_distance ≈ S - admission_range + mask_range
    gap_time = gap_distance / speed

**Consequences, both measured, not derived from first principles:**

- **Widening `S` (group separation) to buy more gap time is
  self-defeating** for a fold-risk test specifically: the covariance
  growth needed to actually fold scales with `S` too, so a bigger gap_time
  bought this way requires proportionally more growth to still fold —
  tried `S=2900` (vs. baseline `1500`), got `gap_time≈105s` but the
  scenario never folded even with the gate reverted (growth over the
  longer gap still fell far short of the now-much-larger distance needed).
- **`mask_range` (via AGL) is the lever that actually works**, since it
  does not change `S`. Raising AGL from 300 to 600 m (within this
  project's own 50-800 m "normal" envelope) widens the gap without
  changing the fold's own difficulty.
- **There is a ceiling on `mask_range`**: once `mask_range` exceeds
  `admission_range`, the near unit is masked before it can ever be
  admitted at all — zero detections for the whole run (confirmed at
  AGL=800, mask_range≈1980 vs. admission_range≈1900-2400). Keep AGL
  comfortably below the point where `mask_range` would overtake
  `admission_range`.
- **Lateral offset (z) barely matters** for `gap_distance` — both
  `mask_range` and `admission_range` shrink by the same `sqrt(threshold²
  - z²)` factor as `z` grows, so the net difference is roughly offset-
  independent; it is a believability/shape knob, not a gap-time lever.

See `plans/bl-b104-ground-contacts-on-ground/implementation.md`'s "Finding
5" section for the full probe methodology and final chosen parameters
(600m AGL, 12 m/s, compressed approach to stay under the shared
`_THREAD_JOIN_TIMEOUT_S`).
