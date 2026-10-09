# WM-W4 — `feature/terrain-landform-features` — marker-controlled watershed

**OPEN** — this entry says *"Parked 2026-10-01 — see [[WM-B6]]"* and that *"Stages 3-5 (adjacency,
bearing, callout) remain unbuilt — nothing in the cockpit changes from this"*, while [[WM-B6]]
says it was *"Unparked 2026-10-01, same day it was parked"* and, further down, that *"Stages 3-5
built, Revision 3, 2026-10-05"*. Mechanically settled: `world-model/src/query/divides.py`,
Revision 3's own divide counter, is present on `main`, so the unbuilt claim is the stale half.
Both records are carried verbatim and neither was edited.

- [x] **`feature/terrain-landform-features` — marker-controlled watershed replaces the WM-M6
  curvature ridge/valley detector (Stages 1-2). Merged 2026-10-01 (`0bef4b9`), and the user's own
  full-theatre build confirms it.** #status/done Acceptance ran against the real `syria-full` store, not a test
  region, and both falsifiable checks hold: **zero valleys within 8 km of Baalbek** (the Bekaa
  floor correctly excluded by the width gate, with three ridges flanking it at 2.1/7.4/7.8 km) and
  **Palmyra's isolated chains intact** (14 ridges within 20 km). Counts collapsed from the old
  11,749 ridges / 11,477 valleys to **8,189 / 2,314**, and sinuosity landed where the test regions
  predicted — **1.202 ridge / 1.172 valley** against the old 2.17/2.21.

  **One prediction missed, recorded rather than smoothed over**: ridge fragmentation came out
  **51.1 %** under 15 cells against the pooled test regions' 30.0 % (valleys: 28.9 % against
  22.2 %, close). Inspection of the densest patch shows this is **basin-pair segmentation at
  triple points**, not noise — a ridge is the divide between two specific basins, so a continuous
  crest is cut into separate features wherever a third basin touches it, and the segments sit on
  real crests. At the ~5 km working radius a 2-3 km segment is a serviceable referent, so this is
  not being tuned now; if "follow the ridge" navigation ever needs whole crests, the fix is merging
  adjacent segments that share a basin and continue in heading. **The broader lesson for this
  project's tuning method**: the three test regions were chosen because their answers were already
  known, so they do not sample ordinary terrain and over-promised by ~20 points on the one metric
  the motivating cases did not exercise.

  **Parked 2026-10-01 — see [[WM-B6]].** The user judged the detector's real output wrong on the
  ground (aligned hillshade renders, three spacings): *"The real problem is that the ridge/valley
  detection itself does not seem to produce correct results."* The merge stands and the code is
  sound as written, but **the `ridge`/`valley` rows in `syria-full.sqlite` should not be treated as
  a layer to build on** until [[WM-B6]] is reopened. Stages 3-5 are parked with it.

  Card: `docs/acceptance/2026-10-01-terrain-landform-build.md` /
  https://claude.ai/artifact/AKXxX4R4R5a3tcztsR2qJC. DoD: `plans/terrain-feature-probing/
  dod-check.md`. Stages 3-5 (adjacency, bearing, callout) remain unbuilt — nothing in the cockpit
  changes from this. Follow-up queued as [[WM-B4]] (curve-smooth the polylines, user direction the
  same day after seeing the staircase in a real render).
