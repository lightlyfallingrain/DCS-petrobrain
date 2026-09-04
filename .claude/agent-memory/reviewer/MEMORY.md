# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [M1 coordinate-transform review](project_m1_coordinate_transform_review.md) — plan-stage deviation was legit; confirmed-confidence label earned via 226-pt live probe match
- [Verify transform confidence labels](feedback_transform_confidence_verification.md) — trace confidence="confirmed" back to research note's actual number, don't trust the field name
- [Provenance pattern reference](provenance_confidence_pattern.md) — `coordinates/projections.py`'s dataclass+confidence+source shape is the template; check new modules against it directly.
- [M2 raster registration review outcome](m2-raster-registration-approved.md) — Stage 2 approved clean; sign-asymmetry and provisional-confidence handling done correctly on first pass.
- [ruff cwd-dependent isort](project_ruff_cwd_dependent_isort.md) — world-model ruff check's I001 verdict flips by cwd (no known-first-party config); flip direction is unstable across sessions, re-check fresh; canonical-command failure is a required fix.
- [Check agent-memory files are staged](feedback_check_agent_memory_staged.md) — run full `git status`, not just feature diff; other agents' memory writes can be left uncommitted, breaking DoD.
- [Attribution on artifact, not just logs](feedback_attribution_on_artifact_not_just_logs.md) — M3: OSM attribution must be burned into the saved image, not just printed/logged in docs.
- [M4 elevation review outcome](m4-elevation-review-outcome.md) — approved w/ minor fixes; code/tests/checks clean, third recurrence of unstaged agent-memory files as the only blocker.
- [M5 Stage 0+1 review outcome](m5-stage1-offline-sources-approved.md) — approved clean; both named traps + airfield-derivation overclaim risk all pinned by tests; conservative ambiguity resolution; mypy tests cwd-quirk noted.
- [M5 Stage 2 roadnet review outcome](m5-stage2-roadnet-approved.md) — approved w/ minor fixes; resync + subtype-null tests genuinely prove claims; route-count discrepancy honestly left open, re-check before M6 trusts it.
