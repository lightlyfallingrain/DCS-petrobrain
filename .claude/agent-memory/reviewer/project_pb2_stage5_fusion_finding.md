---
name: project_pb2_stage5_fusion_finding
description: PB-2 Stage 5 confirmed certainty/classification fusion is last-writer-wins, not quality-weighted; PB-2/BL-2 fixture-testable work is done. Classification half of this backlog item CLOSED by BL-2.6 (2026-09-09) — see update below.
metadata:
  type: project
---

**UPDATE 2026-09-09 (BL-2.6 Stages 1-4 review):** the classification half of the backlog item
below is now closed. `Contact.record` no longer overwrites `Contact.classification` — it folds via
`belief.classification.fold_classification` (refine/reinforce/hold/contradict), verified directly
against the code (`plans/classification-refinement/review.md`). `last_class_raw` deliberately still
*is* overwritten unconditionally on every call, but that's now a documented, separate field kept
specifically as the association gate's input, not an accidental leftover last-writer-wins path.
The **certainty** half of the finding (`belief.decay.certainty_of` being pure recency, no
quality-weighting) is untouched by BL-2.6 and still stands as-is.

Stage 5 (2026-09-09, `body-layer/tests/test_cross_channel_fusion.py`, commit `e927899`) is the
last fixture-testable stage of PB-2/BL-2 — Stage 6 is live-only (real DCS sortie) and user-only.
Reviewer independently re-verified (not just trusted the implementer's report) that:

- `belief.decay.certainty_of` is purely `now_sim - contact.last_seen_sim` — no per-observation
  quality/uncertainty weighting exists anywhere in it.
- `belief.contacts.Contact.record` overwrites `last_class_raw` unconditionally on every call —
  genuinely last-writer-wins, not merely under-tested.
- This is captured as a backlog item in `todo/todo.md` ("BL-2's certainty/classification fusion
  is last-writer-wins, not quality-weighted"), correctly framed as an expected consequence of
  Stage 2's documented pure-recency placeholder design, not a bug introduced in Stage 5.

**Why this matters for future review:** if a later milestone (BL-3/BL-4, or a PB-2 revisit) adds
quality-weighted fusion to `decay.py`/`contacts.py`, re-check this backlog item is actually
closed (not just superseded silently) and that the new logic doesn't reintroduce a best-match
tiebreak into `association_over_time` in the process — see [[project_pb2_belief_invariants]]
invariant 2, a different mechanism but an easy place for scope to bleed together.

**How to apply:** when reviewing any future stage that touches `decay.py` or `Contact.record`,
confirm this backlog item's premise still holds before assuming it's stale, and check whether the
new work was scoped as "close this backlog item" or something unrelated that happens to touch the
same functions.
