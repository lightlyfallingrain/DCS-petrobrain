---
name: group-contact-model-stage1-2-minor-fixes
description: Structural gate-vs-cluster-radius mismatch found in Stage 2, and how to hand-verify it
metadata:
  type: project
---

Reviewed 2026-09-18, `feature/group-contact-cardinality` Stages 1-2 (`8ea06b6`, `ece33ed`,
`62d125e`). APPROVED WITH MINOR FIXES. 632 tests passed, clean ruff/mypy, reran myself.

Key technique: when a plan claims "X and Y are the same number by construction," don't take the
claim on the docstring's word — find the two formulas and compare their shapes, not just their
inputs. Here `perception/clustering.cluster_candidates` splits on `max(radius_a, radius_b)`
(single-sided) while `belief/association_over_time.spatial_gate_radius_m` re-tests on
`radius_a + radius_b + growth` (double-sided sum, from BL-2.6's legitimate symmetric-budgeting
fix). Same underlying per-side radius function (genuinely shared, not duplicated — verified via
grep), but the *combination* differs, so the belief gate is structurally ~2x the cluster-split
threshold. Any split whose children sit near the cluster's own resolution boundary — the common
case, since that's exactly when a split first becomes possible — gets re-absorbed by the gate.
Worked the actual numbers by hand for the mock-flight fixture (690 m range, 400 m separation):
cluster radius ≈205 m, gate radius ≈410 m+. This is a structural mismatch, not a tunable constant
Stage 3's listed scope (cluster-radius policy, chaining cap, tier table) would fix — required fix
was a documentation-level correction to the plan's Stage 3 scope, not a code change, since the
disclosed test behaviour is a genuine improvement over the pre-existing permanent-false-merge bug.

Also confirmed: a "generalization beyond the plan's four named fold cases" (partial-overlap
interval refine in `fold_cardinality`) was NOT scope creep here — it was required by the plan's
own decision to keep ED's `OP_TO5UNITS(4,5)`/`OP_5TO7UNITS(5,7)` boundary overlap intact; without
it that boundary case would wrongly fall into the contradiction branch. Check whether an
"unrequested generalization" is actually load-bearing for a stated design decision before flagging
it as drift.

Determinism check technique that worked: for majority-vote tie-breaking
(`naked_eye_source._build_observations`), verified `max(sorted(votes), key=...)` sorts keys before
taking max (lexicographic tie-break, not dict/insertion-order-dependent) — this is the pattern to
check for per [[project_junctions_streaming_fix_minor_fix]]-style "ties must not resolve by
iteration order" findings.
