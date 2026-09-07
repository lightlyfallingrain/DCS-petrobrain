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
- [M5 Stage 3 probe chunking review](m5-stage3-probe-chunking-review.md) — approved w/ minor fixes; grid coverage/SRTM-null verified true against real store, but scheduleFunction chunking mandate was silently dropped and log misdescribed the fallback as "append-mode".
- [M5 Stage 4 validation + resync fix review](m5-stage4-validation-and-resync-fix.md) — approved clean; surprising-number investigations checked against real code; declined to block on systematic route audit (flagged to M6 instead); test fixture drifted from corrected 3-point finding (optional).
- [Agent-memory path mistake recurs](feedback_agent_memory_path_recurrence.md) — implementer wrote under `world-model/.claude/agent-memory/` twice (f7a7ec1, M5 Stage 5); check the actual prefix on any agent-memory diff.
- [M6 terrain semantics review outcome](m6-terrain-semantics-review.md) — approved w/ minor fixes; real control-point tests, honest negative usefulness finding; fourth recurrence of unstaged agent-memory files.
- [M7 full-theatre review outcome](m7-full-theatre-review-approved.md) — APPROVED, zero required fixes; execution-boundary and provenance invariants independently verified via diff/grep, not trusted from prose.
- [M8 probe store read-path drift gap](m8-probe-store-read-path-drift-gap.md) — closed in 9a0d0d8 (check_probe_paired_with_base), verified via repro + 3 new tests; final verdict APPROVED.
- [Body-layer plan review](body-layer-plan-review.md) — plan violated its own provenance rule in worked examples; open question asserted as settled in concept docs; BL-5 froze tools later milestones build.
- [Aircraft-layer stage 1-2 review](aircraft-layer-stage1-2-review.md) — approved w/ minor fix: collector accept loop not resilient to abrupt disconnect (OSError uncaught); 5th unstaged-agent-memory recurrence.
