---
name: m1-coordinate-transform-review
description: M1 coordinate-transform review outcome and what "earned confirmed confidence" looks like in this project
metadata:
  type: project
---

M1 (DCS x/z <-> WGS84 for Syria, `world-model/src/coordinates/`) reviewed 2026-09-03 on
`feature/m1-coordinate-transform` — APPROVED, no required fixes.

Notable pattern worth recognizing again in future reviews of this project: the Implementer
deviated from the plan's staged "provisional now, confirm later" sequencing because the
blocking Windows-side probe had already completed before implementation started. This is
legitimate, not scope drift, when (a) `implementation.md` states the deviation and reason
explicitly, and (b) the `confidence="confirmed"` label is backed by a specific reproducible
number in `world-model/research/` (here: 226-point live `coord.LOtoLL` reproduction at
0.00-0.03m residual) rather than just "looks right." Check the research note's actual
residual numbers before accepting a "confirmed" label — don't take the confidence field at
face value.

Also a good model for a control-point threshold that isn't papering over a bug: the
verification note showed the ~1-1.3km real-world ARP residual has non-systematic
direction/magnitude across three widely-separated points (ruling out a global projection
defect) and is separately explained (terrain-art placement error) with the systematic-defect
hypothesis independently ruled out by the 0.00-0.03m live-probe match. A threshold is honest
when the test comment cites the measured values and a contrasting failure-mode magnitude
(here: prior ~327km wrong-axis-order bug), not just a round number.

See [[feedback_transform_confidence_verification]] for the general check to apply.
