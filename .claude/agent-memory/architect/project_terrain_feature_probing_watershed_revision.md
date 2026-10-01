---
name: terrain-feature-probing-watershed-revision
description: 2026-10-01 revision of the ridge/valley detector — from per-cell curvature to a seeded watershed over a smoothed grid, and why
metadata:
  type: project
---

The 2026-10-01 Explore conversation (`plans/terrain-feature-probing/explore-notes.md`) settled that
a "valley" must be a maskable concave *form between hills* (50-150 m of rise over a short run,
range-independent from a 200 m AGL sightline), not a wide flat basin and not whatever a per-cell
discrete-Laplacian happens to flag. `world-model/research/2026-10-01-terrain-features-full-build-
inspection.md` had already shown the shipped Stage 1/2 curvature detector (un-gated SRTM extraction
at 500 m, `plans/terrain-feature-probing/plan.md`) produces noise at landform scale on the real
`syria-full` theatre: 75%/70% of ridges/valleys under 15 cells, sinuosity ~2.2, and every ridge
paired with a parasitic valley along its own foot (break-of-slope, not a landform body).

**Decision: replaced the detector with a marker-controlled watershed** (smooth the grid at
landform scale with `scipy.ndimage.uniform_filter`, seed basins at local minima with `scipy.
ndimage.minimum_filter`, grow basins with a hand-written heapq priority-flood, gate valleys on
basin relief *and* width, gate ridges on divide prominence independent of whether either side
qualifies as a valley) — not the user's own candidate (full D8 flow-accumulation hydrology), and
not the cheaper alternative I considered first (smoothed multi-scale curvature, same mechanism
just at a wider stencil).

**Why not the cheaper curvature-smoothing fix**: it's still an edge detector with no basin extent,
so it cannot express the Bekaa-exclusion rule (a basin must be *narrow enough*, not just between
hills) as anything but a bolted-on heuristic, and the parasitic ridge/valley pairing is structural
to any per-cell concavity test — a hill's own toe is genuinely concave at every scale. The
watershed gives exact basin width (the Bekaa check) and makes "ridge vs. valley" mutually exclusive
by construction (every cell belongs to exactly one basin; a divide is only a divide between two
*different* basins) — it fixes defect 4, not just reduces its frequency.

**Why not full D8 hydrology**: pit-filling + flow-accumulation + stream-threshold tuning exists to
answer which way water ultimately drains to the sea, a question this consumer (contact-report
terrain qualifiers within ~5 km) never asks. The watershed-over-smoothed-grid approach takes the
user's own water-flow analogue at the structural level that matters (basins + divides) without
that machinery.

**Free bonus from choosing the watershed**: Stage 3 ("next valley" = adjacency across one divide)
stops being a geometric nearest-neighbour heuristic over independently-extracted `LineString`s (what
the original 2026-09-29 plan expected to build) and becomes a direct read of the basin-adjacency
structure the watershed already computed — two valleys are adjacent iff their basins share a
boundary that itself qualifies as a ridge. Worth checking for on any future plan that assumes a
"compute nearest-neighbour adjacency" step is still needed here — it no longer is.

**Dependency note**: numpy/scipy approved by user direction (2026-10-01, relayed via coordinator,
not an architect-unilateral call) specifically because stdlib was inadequate for the smoothing/
extremum steps at theatre-scale (~2.5M cells) — the user's own framing was "fine if actually
needed," not blanket permission. The basin-growth watershed itself stays hand-written stdlib
(heapq) because it's an inherently serial priority-queue traversal that doesn't vectorize, and
`_connected_components`/`_principal_axis` (world-model's existing closed-form 2x2-eigenvector
axis extraction, "no numpy needed") are reused unchanged for boundary/axis extraction — the
dependency add did not become a reason to rewrite code that wasn't the bottleneck. If a future
terrain change reaches for numpy somewhere small, check whether stdlib is really inadequate there
too, rather than treating this approval as a green light generally.

**Branch state note**: this revision happened in a worktree accidentally checked out at the
branch's old HEAD (`4453b03`), several commits behind the real tip (`0ea038f`) which already held
the explore conversation and Stage 1/2's implementation. Verified via `git merge-base --is-
ancestor` both ways, then read all controlling context from a `git archive <tip> | tar -x` snapshot
rather than the stale worktree. The revised `plan.md` was written as the full target content (not
an incremental diff against the stale base) — whoever integrates this should take the file content
directly rather than attempt a naive cherry-pick, since the commit's parent lacks the intervening
history for this file.

See also [[project_bl2_contact_memory_design]] for the store's general provenance/tags
conventions this revision reuses (`connecting_road_ids`/`inner_rings` precedent for the new
`adjacent_feature_ids`/`basin_width_m` reserved tags).
