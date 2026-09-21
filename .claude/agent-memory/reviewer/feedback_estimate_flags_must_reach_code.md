---
name: estimate-flags-must-reach-code
description: Sourced-vs-estimated numeric fields need per-field inline code comments, not just a research-doc citation link
metadata:
  type: feedback
---

When a plan requires "cite, don't guess" sourcing for hand-entered domain figures (e.g.
`body-layer/research/2026-09-21-s300-radar-dimensions.md`'s S-300 40B6M/64H6E dimensions), a
citation link in a table-row comment ("see research doc for sourcing") is not sufficient by itself
when some fields on that same row are cited real figures and others are estimates. Found in
`aspect-aware-profiles` review: `object_model.py`'s S-300 rows mixed two sourced numbers
(mast height 24 m, 64H6E length/width 13.2×3.0 m) with two estimates (40B6M footprint, 64H6E
erected height) under one undifferentiated comment — a reader of the source file alone cannot tell
which numbers are which without opening the research doc.

**Why:** the whole point of flagging an estimate is that a future reader (esp. one doing a later
threshold recalibration) sees the caveat at the point of use, not several hops away. A generic
"see research doc" citation satisfies "sourced, not silently invented" but not "flagged loudly
where used."

**How to apply:** when reviewing a change that adds hand-authored numeric/factual fields with mixed
provenance (some sourced, some estimated) on the same struct/row, check whether each *individual*
estimated value carries its own inline flag, not just a shared citation comment for the whole row.
Also check for circular-evidence cases specifically — an estimate derived from the same dataset
the feature will later be validated against (e.g. a sortie's own visual estimate feeding a model
that will be checked against that sortie's results) needs its own explicit callout, since that
caveat is easy to lose between the research doc and the code.
