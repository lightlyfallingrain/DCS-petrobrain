---
name: store_writer_fail_closed_geometry_guard
description: insert_features' new sub-2-point LineString/Polygon guard rejects the whole transaction, not just the bad row -- confirmed fail-closed 2026-10-01
metadata:
  type: project
---

`store/writer.py`'s `insert_features` (terrain-feature-probing, 2026-10-01) gained a check that
raises `ValueError` for any `LineString`/`Polygon` `StoredFeature` with fewer than 2 points, added
after a review found `terrain.features`'s axis-sliced-line extraction could collapse a
multi-cell component to 1 point under a rounding tie (fixed at the source too, in
`_round_half_away_from_zero`; this check is the generic backstop for any future producer).

Confirmed fail-closed: the check runs inside the same function that then does the whole-batch
`INSERT`/R*Tree-bbox transaction, so raising aborts the entire `insert_features` call -- no
partial/degenerate geometry can reach the DB, and it is not reachable as an attacker-triggerable
denial-of-build by ordinary data (only a rounding-tie defect in `terrain.features`'s own geometry
math could produce the bad input, and that path is independently guarded at the source too).

See [[world_model_first_native_deps_numpy_scipy]] for the rest of this feature's security review.
