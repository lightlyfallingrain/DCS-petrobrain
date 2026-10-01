# Terrain features — what the first full-theatre extraction actually looks like

Dated: 2026-10-01. Closes Stage 1's acceptance item in `plans/terrain-feature-probing/plan.md`
(*"the inspection output says whether they are landmark-scale or noise"*), which
`research/2026-09-29-terrain-feature-probing-spacing.md` could only answer over one 20 km test
region. The user ran the full `syria-full` build on 2026-09-30; this is the look at its output.

## What was inspected

`world-model/data/world-model/syria-full.sqlite`, built 2026-09-30 13:11 with Stage 1's un-gating
and Stage 2's 500 m storage spacing. First built theatre to contain any `ridge`/`valley` rows at
all: **11 749 ridge, 11 477 valley** (the 2026-09-16 build has zero of both).

`tools/inspect_terrain.py` gained a render window this session (`--near NAME` / `--center X,Z`
with `--radius-km`) — a whole-theatre render is 1543×1656 cells, i.e. a ~19k×20k px image, both
slow and unreadable. **Classification and component extraction still run over the full grid**; only
the drawing is cropped, so no edge effects are introduced by the crop.

Three 40×40 km windows, chosen for three different terrain types:

| window | terrain | image |
|---|---|---|
| Latakia | coast + An-Nusayriyah foothills (M6's own test region, now in theatre context) | `images/2026-10-01-terrain-latakia-20km.png` |
| Baalbek | Bekaa valley floor between two ranges | `images/2026-10-01-terrain-baalbek-20km.png` |
| Palmyra | flat desert with isolated ridge chains | `images/2026-10-01-terrain-palmyra-20km.png` |

## Findings

**1. Flat terrain is quiet — no false positives.** Palmyra's desert floor and the sea off Latakia
classify as `neither` almost everywhere. The classifier does not invent landforms where there are
none, which was not guaranteed and is worth having checked.

**2. Isolated relief is located correctly but shaped badly.** Palmyra's ridge chains show up as
clean, narrow, continuous bands of classified cells — the *right* features, in the right places.
The extracted polylines over them are not: they zigzag cell-to-cell, and every ridge band carries a
parasitic valley line along its own foot (the concave break-of-slope flanking any convex crest).
Theatre-wide, median sinuosity (path length ÷ end-to-end distance) is **2.17 for ridges, 2.21 for
valleys**, p90 **4.3 / 5.2** — a "line" that wanders twice as far as it travels.

**3. High-relief terrain still checkerboards**, as M6 warned at 500 m probe spacing and as SRTM at
the same spacing reproduces. The Latakia foothills and the Bekaa's flanks are a red/blue hash, and
the components extracted from it are fragments, not landforms: **75 % of ridges and 70 % of valleys
are under 15 cells**; only 3 % / 7 % reach 40. Median end-to-end extent is **2.2 km (ridge) /
2.5 km (valley)**.

**4. The Bekaa valley is not a `valley`.** This is the finding that matters for the consumer. The
valley floor is flat, so discrete-Laplacian curvature classifies it `neither`; what gets labelled
`valley` is the concave break-of-slope at the foot of the mountains on either side. The detector
finds **break-of-slope, not landform bodies** — it answers "is this cell locally concave", which is
not the question *"armor, 10 o'clock, next valley"* asks. A pilot naming a valley means the flat
space between two ranges; the extraction names its edges.

## What this means for the plan

Stage 1's acceptance question — landmark-scale or noise? — answers **noise, at landform scale**,
with the one exception of isolated desert relief where the location (not the shape) is right.
Stages 3–5 (adjacency, bearing, callout) are all built on these `LineString`s, so building them on
the current output would wire a callout to features the pilot cannot see the referent of.

Threshold retuning alone does not reach it, and the 2026-09-29 sweep already shows why: raising the
threshold removes cells uniformly, so valley components vanish before the checkerboard clears
(1000 m: zero valleys by threshold 30; 500 m: 41 % → 23 % classified between thresholds 20 and 50
with component counts collapsing in step). Finding **4** is a different problem from **2** and **3**
— it is not a tuning failure but a definition mismatch, and no threshold fixes a detector that is
measuring the wrong thing.

Not decided here: what replaces or supplements the Laplacian. Candidates worth a look before any
Stage 3 work — multi-scale smoothing of the grid before classification (landform scale is
kilometres, not one 500 m cell), morphological basin/catchment extraction for valley *bodies*
rather than edges, and polyline smoothing/pruning to fix sinuosity independently of all of it.
