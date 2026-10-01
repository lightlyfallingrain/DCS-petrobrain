# Terrain feature probing — watershed sweep (Stages 1-2)

Dated: 2026-10-01. Covers Stage 1's "pick the smoothing window and relief/width gates by
looking" and Stage 2's "retune against real Stage 1 output", for the marker-controlled-watershed
(Option C) mechanism that replaces the discrete-Laplacian classifier, per
`plans/terrain-feature-probing/plan.md`. Method mirrors the 2026-09-29 spacing sweep and M6
Stage 2's own sweep-and-record approach: region-scoped test builds, `tools/inspect_terrain.py`'s
rendered output and a basin-by-basin text report, judged against the consumer (would a pilot call
this one feature, would a pilot say "that's a valley") and against the two concrete, falsifiable
tests the Explore conversation set — the Bekaa must fail the width gate, Palmyra's isolated ridges
must still fire.

## Setup

Three region-scoped test builds from real SRTM `.hgt` tiles (`tools/build_world_model.py
<region> --srtm-dir data/raw/dem/syria-full --srtm-grid-spacing-m <N>`), no probe/routes/OSM
layers needed for this question:

- **`latakia-20km`** — the existing precedent region, real An-Nusayriyah-foothill relief.
- **`baalbek-20km`** (new region, registered this session, `src/build/region.py`) — centred on the
  `named_place` "Baalbek" row already in `syria-full.sqlite` (x=-114453.8, z=25280.8), the
  concrete Bekaa-equivalent test the width gate has to fail.
- **`palmyra-20km`** (new region, registered this session) — centred on the `named_place`
  "Palmyra" row (x=-54775.0, z=217141.7), the flat-desert-with-isolated-ridges regression check
  against the one thing the old detector got right.

All three built at 500 m, 250 m and 100 m SRTM storage spacing (same `.hgt` tiles already on disk
from the 2026-09-29 sweep, plus four newly copied tiles — `N33E035/036`, `N34E035/036` for
Baalbek and `N34E038`, `N35E038` for Palmyra — into this worktree's `data/raw/dem/syria-full/`,
which does not ship with the repo).

Four knobs, not two (per the plan's "Risks & Unknowns"): smoothing-window radius (cells),
relief threshold (m), width ceiling (m), and processing spacing (m) — plus one internal knob the
plan didn't name as a top-level sweep target but which turned out to matter just as much:
**valley core fraction**, the share of a basin's own relief its low-elevation "core" (the body
`qualifying_valleys` actually extracts a line from) is allowed to span.

## Processing spacing — 500 m confirmed again, under the new mechanism

The 2026-09-29 note found the *old* classifier's checkerboard ceiling was spacing-invariant
(finer spacing reproduced the same noise at higher density). This plan's own "What survives from
Stages 1-2" section explicitly warned against inheriting that finding blind, since it was a fact
about the Laplacian, not about watershed basins — a sharp 500 m-wide V-notch is one cell at 500 m,
so finer processing might resolve features the old mechanism couldn't.

Checked directly, holding the smoothing window's *real-world* size constant (~1.5 km) across
spacings rather than its cell count (a window of `N` cells covers less real distance as spacing
gets finer, so comparing cell counts across spacings is not apples-to-apples):

| spacing | window (cells / real) | min_cell_count (area-equivalent) | result |
|---|---|---|---|
| 500 m | 3 / 1.5 km | 6 | 8 valleys/ridges over Latakia, median sinuosity 2.49 |
| 250 m | 6 / 1.5 km | 24 | 1 component survives — most candidates fall below the area-equivalent floor |
| 100 m | 15 / 1.5 km | 150 | 1 component survives, median sinuosity **29.9** — zigzag amplifies with cell count |

**Finer processing spacing does not help this mechanism either, for a related but distinct
reason**: the geometry-extraction step (`_principal_axis` + projection-sort, reused unchanged
per the plan) threads a 2D point cloud into a single polyline by sorting on major-axis
projection; a blob of width > 1 cell zigzags across its own minor axis as cell count grows, so
finer spacing — which increases absolute cell count for the same real feature — makes this worse,
not better. **Decision: 500 m for both storage and processing spacing**, same single-grid design
as 2026-09-29, now independently re-confirmed rather than inherited.

## Smoothing window — 3 cells (1.5 km at 500 m)

Swept at 500 m spacing over Latakia:

| window (cells) | basins | outcome |
|---|---|---|
| 2 | 24 | noisy — close to the old checkerboard's component count |
| **3** | **10** | usable split; real basins separated, real ridges located |
| 4 | 2 | over-smoothed — most of the region collapses into one basin |
| 5 (original guess) | 1 | fully flattened — one basin covers the entire 20×20 km window |

**Decision: `DEFAULT_SMOOTHING_WINDOW_CELLS = 3`**, `DEFAULT_SEED_FOOTPRINT_CELLS = 3` (same
window, per the plan's point 2 — a basin seed should never be finer-grained than the surface it's
seeded on). The original Stage 1 guess of 5 was wrong by one step in a very unforgiving direction
— at 500 m spacing a 5-cell window is 2.5 km, enough to erase an entire 20 km test region's
internal structure.

## Relief threshold and width ceiling

Swept at 500 m / window=3 over all three regions. Relief threshold 50/80/100/150 m made little
practical difference over this fixture set (most real divides/basins in these three regions clear
80 m by a wide margin or miss it by a wide margin, not close to any of these boundary values) —
**`DEFAULT_RELIEF_THRESHOLD_M = 100.0`** (midpoint of the Explore conversation's 50-150 m range)
chosen as the least arbitrary of several practically-equivalent values, not because 100 uniquely
separates real cases in this sample.

Width ceiling is load-bearing for exactly one case and not close for it: the Bekaa basin's
measured core width is **8,611 m**, 3.4x even the loosest end of the plan's candidate range —
**`DEFAULT_WIDTH_CEILING_M = 2500.0`** (midpoint of 2-3 km) excludes it with large margin; the
exact value within 2-3 km does not change that outcome.

## Valley core fraction — not named as a top-level knob, turned out to be the load-bearing one

`qualifying_valleys` extracts a line from a basin's own low-elevation "core" — cells within
`core_fraction * relief_m` of the basin's floor — because a basin's full extent (point 3) reaches
all the way up to the surrounding divide crest, which is not what a pilot means by "the valley".
The plan's Stage 1 text didn't name this as one of the swept knobs, but it turned out to directly
trade fragmentation against sinuosity for valleys, and neither baseline metric moves independently
of it:

| core_fraction | valleys (n) | % under 15 cells | median sinuosity |
|---|---|---|---|
| 0.1 | 6 | 83% | 3.57 |
| 0.2 | 7 | 57% | 3.57 |
| 0.3 | 9 | 22% | 4.74 |
| 0.4 | 8 | 25% | 5.94 |
| 0.5 (initial guess) | 6 | 33% | 6.18 |

A wider core (larger fraction) pulls in more cells — directly lowering the "% under 15 cells"
figure — but every one of those additional cells sits further up the basin's own flank, which is
exactly where the zigzag in the shared projection-sort geometry step gets worse, not better (more
cells spread across more of the basin's minor-axis width). **No value tested beats the baseline on
both fragmentation and sinuosity for valleys at once** — see "Stage 1 acceptance" below.
**Decision: `DEFAULT_VALLEY_CORE_FRACTION = 0.1`**, chosen for the best sinuosity among tested
values and the tightest, most defensible "valley floor" semantics (a core at 0.5 pulls in cells
more than halfway up a basin's own slope, which the user's own "between hills" framing does not
support calling the valley itself).

## Stage 1 acceptance — reported plainly, not retuned until it reads as a pass

**(a) Fragmentation and sinuosity vs. baseline (75%/70% under 15 cells, sinuosity 2.17/2.21),
pooled across all three test regions at the chosen defaults (window=3, relief=100, width=2500,
min_cell_count=6, core_fraction=0.1):**

| kind | n | % under 15 cells | median sinuosity |
|---|---|---|---|
| ridge | 10 | **30%** (vs. baseline 75%) | **2.22** (vs. baseline 2.17) |
| valley | 6 | **83%** (vs. baseline 70%) | **3.57** (vs. baseline 2.21) |

**Ridges are materially better on fragmentation and statistically indistinguishable on sinuosity
at this sample size.** Parasitic pairing (finding 4, see (b) below) is eliminated structurally,
not just reduced — ridge gating no longer has any dependency on whether a neighbouring region
qualifies as a valley.

**Valleys do not beat baseline on either metric, and this is not a tuning gap** — see the core-
fraction table above: pushing core_fraction up to match baseline's loose fragmentation makes
sinuosity roughly 2-3x worse, not better. The root cause is shared with ridges' zigzag (the
`_principal_axis` + projection-sort geometry step, reused unchanged per the plan), but valleys
feel it more because a basin's low-elevation core is inherently wider across its minor axis than
a basin-pair's boundary line is. **This acceptance criterion is not met for valleys** at the
chosen defaults or any other core_fraction tested. The underlying defects it was meant to catch
(parasitic pairing, break-of-slope-not-body) are independently confirmed fixed by (b)/(c)/(d)
below; this specific metric, inherited from the old mechanism's failure mode, does not transfer
cleanly to a basin-core's different failure mode (its real problem is zigzag width, which "% under
15 cells" does not measure directly).

**(b) No ridge paired with a valley along its own foot:** confirmed by construction, not just by
inspection — `qualifying_ridges` and `qualifying_valleys` share no classification state (a ridge
is gated on divide prominence between two basins; a valley is gated on one basin's own relief and
core width), so the parasitic-pairing mechanism (break-of-slope at a hill's toe reads as `valley`
purely because it's locally concave) cannot occur. Visually confirmed over both Latakia
(`images/2026-10-01-latakia-final.png`, not committed — gitignored `data/`) and Palmyra renders:
every ridge line sits on a genuine basin-pair boundary; every valley line sits inside one basin's
own interior, never tracing a ridge's flank.

**(c) Bekaa fails the width gate:** confirmed directly. The basin covering the bulk of the
Baalbek-20km window (1,020 of 1,614 sampled cells, floor 1,003.6 m, relief 1,274.2 m — easily
clears the relief gate) has a measured core width of **8,611 m** against the 2,500 m ceiling — a
3.4x margin, not a close call. It produces zero `valley` rows. The region's one surviving valley
(13-24 cells depending on core_fraction) is a small, separate basin at ~2,100-2,186 m near the
window's edge — a mountain-top depression, not the Bekaa floor.

**(d) Palmyra's isolated ridges still fire:** confirmed. 3 ridges (2-3 depending on min_cell_count)
extracted at real basin-pair boundaries, elevations 554-749 m against a desert floor around
460-530 m — correctly located divides between genuinely separate basins, matching the old
detector's one correct finding ("located correctly, shaped badly") while fixing the "badly".

## Decision

- **Processing spacing: 500 m** (confirmed independently under the new mechanism, not inherited
  from the 2026-09-29 Laplacian-specific finding).
- **Storage spacing: 500 m**, same grid as processing — no finding justifies a decoupled fine
  processing grid (same conclusion as 2026-09-29, re-checked rather than assumed to still hold).
  `build.pipeline.DEFAULT_SRTM_GRID_SPACING_M` stays 500.0, unchanged.
- **`DEFAULT_SMOOTHING_WINDOW_CELLS = 3`**, **`DEFAULT_SEED_FOOTPRINT_CELLS = 3`**
  (`terrain.curvature`), down from the original Stage 1 guess of 5.
- **`DEFAULT_RELIEF_THRESHOLD_M = 100.0`**, **`DEFAULT_WIDTH_CEILING_M = 2500.0`**,
  **`DEFAULT_MIN_CELL_COUNT = 6`**, **`DEFAULT_VALLEY_CORE_FRACTION = 0.1`** (`terrain.features`).

## What this does not fix, named plainly

**Line sinuosity is not solved by the mechanism change.** The plan replaced *what* gets grouped
(basin membership vs. per-cell break-of-slope), which fixes parasitic pairing and the Bekaa-body
problem structurally. It explicitly kept *how* a connected group of cells becomes one `LineString`
(`_connected_components`/`_principal_axis`, point 6) unchanged, and that step is the actual source
of sinuosity: sorting a 2D point cloud by projection onto its own major axis zigzags across the
minor axis whenever the cloud is more than 1 cell wide, regardless of why the cloud was grouped.
Ridges happen to come out thin enough (a basin-pair boundary) that this mostly doesn't show;
valley cores, even at the tightest core_fraction tested, are wide enough that it does. Fixing this
would mean changing the geometry-extraction step itself (e.g. a skeleton/centreline extraction
instead of projection-sort) — out of this plan's explicit scope ("`_connected_components`/
`_principal_axis`... reused unchanged") and not attempted here.

## Images

Not committed (`data/` is gitignored, same as every prior terrain-inspection note) — regenerate
with `tools/inspect_terrain.py <region>.sqlite` using the defaults above, or `--near Baalbek`/
`--near Palmyra` against a `syria-full` build once SRTM for the whole theatre is staged.
