---
name: project_terrain_watershed_saddle_formula_mismatch
description: terrain-feature-probing (watershed) review — implementation.md claimed a saddle-elevation bug fix that the shipped code does not contain; caught by constructing a divergent test case, not by reading.
metadata:
  type: project
---

Reviewed `feature/terrain-landform-features` @ `54bdef4` (marker-controlled-watershed
replacement for the ridge/valley curvature detector). Found two required fixes, both in
`world-model/src/terrain/features.py`:

1. **Claimed-fixed bug that isn't fixed.** `implementation.md`'s first round reports catching
   and fixing a saddle-elevation bug: the divide pass-height must be `min` over contact points
   of `max(elevation each side)`, not a naive `min` over the combined/mixed boundary-cell set.
   The shipped `qualifying_ridges` does exactly the naive thing (`saddle_elevation =
   min(elevations)` over the union of both sides' boundary cells) — the docstring even says "the
   lowest boundary cell". No test distinguishes the two formulas because the one ridge test's
   `relief_threshold_m=80` is low enough that both the naive (140) and correct (300) values pass
   identically in that fixture. **How this was caught**: constructed a small synthetic grid
   where the two formulas diverge (naive=50, correct=250) and ran the actual function with a
   threshold between them (100) — the shipped code rejected a ridge the documented-correct
   formula would accept. Reading the code and the docstring together was not enough; the
   docstring itself asserts the wrong formula in plain English ("the lowest boundary cell"),
   so it reads as self-consistent on a skim.

2. **Degenerate single-point `LineString`.** `_axis_sliced_line` bins cells by rounding their
   axis projection; Python's round-half-to-even collapses a small symmetric cluster (e.g. a
   literal 2x2 square, `GridCell(0,0),(0,1),(1,0),(1,1)`) to exactly one bin, producing a
   1-point line. This contradicts both the module's own "cannot zigzag by construction" claim
   and `store/models.py`'s documented `LineString` convention (>=2 points), and nothing in the
   pipeline or `store/writer.py` guards against it. Didn't manifest in the three real test
   regions (smallest real feature there has 4 points) because real terrain features aren't
   that symmetric, and all three hand-built test fixtures are deliberately asymmetric/monotonic
   specifically to avoid tie-breaking (stated in the test file's own docstring) — which also
   means the fixture-construction discipline that makes tests deterministic also happens to
   hide this exact bug class.

**General lesson**: when an implementation log claims "caught and fixed [specific bug],
confirmed by hand-deriving test fixture values" — verify by constructing a case where the
claimed-wrong and claimed-right formulas *actually diverge*, not just by reading the code next
to the docstring claim. A docstring can misdescribe the code in a way that reads as consistent
on a skim (here: "lowest boundary cell" is literally what the code does, and only wrong because
it's the *naive* formula being reasserted as the fix). See [[provenance_confidence_pattern]] for
the module's otherwise-solid provenance/confidence conventions, unaffected by this finding.

Despite these two bugs, **the four Stage 1 acceptance numbers reproduced exactly from a real
region-scoped build** (ridge 30%/1.22 sinuosity, valley 22%/1.19, Bekaa width-gate exclusion,
Palmyra ridge regression) — copied real SRTM `.hgt` tiles + `towns.lua` from the main checkout
(read-only) into the review worktree, built all three regions through the real `build_region`
pipeline with monkeypatched town/beacon parsers, and measured fragmentation/sinuosity directly
from the resulting `feature` rows rather than trusting the research note's own numbers. Verdict:
NEEDS REVISION, narrow scope, acceptance claims hold.
