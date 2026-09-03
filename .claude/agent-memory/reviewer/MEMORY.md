# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [M1 coordinate-transform review](project_m1_coordinate_transform_review.md) — plan-stage deviation was legit; confirmed-confidence label earned via 226-pt live probe match
- [Verify transform confidence labels](feedback_transform_confidence_verification.md) — trace confidence="confirmed" back to research note's actual number, don't trust the field name
- [Provenance pattern reference](provenance_confidence_pattern.md) — `coordinates/projections.py`'s dataclass+confidence+source shape is the template; check new modules against it directly.
- [M2 raster registration review outcome](m2-raster-registration-approved.md) — Stage 2 approved clean; sign-asymmetry and provisional-confidence handling done correctly on first pass.
- [ruff cwd-dependent isort](project_ruff_cwd_dependent_isort.md) — world-model ruff check's I001 verdict flips by cwd (no known-first-party config); verify with canonical repo-root command before trusting a "regression".
