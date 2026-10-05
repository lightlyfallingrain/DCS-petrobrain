---
name: sortie-1005-items234-scan-ahead-cadence-review
description: Review outcome for sortie-2026-10-05-refinements items 2/3/4 — APPROVED, verification technique for a dwell-cadence drop claim
metadata:
  type: project
---

Reviewed `feature/sortie-refinements` items 2 (describe synonym), 3 (group watch), 4 (scan-ahead
11-12-1 sweep) at tip `ecd3d67` — APPROVED, no required fixes.

**Technique worth repeating**: item 4 claimed a naked-eye observation count drop (16→3) from
widening `_SECTOR_LEGS["ahead"]` from a static `(12,)` to a cycling `(11, 12, 1)`. Rather than
re-deriving the arithmetic by hand and trusting it matched, I instrumented the actual fixture
(`test_mock_flight_chain.py`, via `Edit`, printing `gaze_at`'s label and new-observation-count per
poll) and ran it for real. My own hand-derived prediction (5 polls landing on the 12-o'clock leg
within the pre-mask window) was *wrong* — the real run showed only 3 of 7 legitimately-12-o'clock
polls actually produced an observation, due to other pre-existing gating this item doesn't touch.
The claimed total (23) was right; the comment's own narration of *which* polls land on 12 o'clock
("0, 6, 12, 18") was itself off by inspection — real values are 0, 5, 6, 11, 12, 17, 18, of which
only 0, 6, 12 produce new observations. Logged as an optional refinement, not a blocker, since the
test's own numeric assertion is correct and independently reproduced.

**Lesson**: when a plan/implementation comment gives a dwell-cadence or cone-timing arithmetic
claim, don't just recompute it on paper and declare "✓ it checks out" — run it. Paper math and the
real `gaze_at`/`command_t_sim` modular arithmetic can disagree in non-obvious ways (here, a
`created_sim=1_000_000.0` task-anchor offset makes the cycle phase non-trivial — `1e6 % 6 == 4`,
not `0`), and a reviewer's own hand-derivation is just as fallible as the implementer's.

Also confirmed (grep, not assumption): item 3's `_mark_watched_with_group` is the only place that
needed the group-tagging treatment — `belief/console.py`'s typed debug `watch <id>` command calls
`watch_contact_task` directly on an operator-named id and correctly doesn't need it (different
semantics: explicit target, not a resolver pick). No sibling-callsite gap this time.

Branch had moved one commit past the reviewed tip by the time of review (`0de048a`, cross-cutting
hook/config bookkeeping) — flagged as optional per CLAUDE.md's "non-code bookkeeping belongs on
main" rule, did not affect the verdict since it touches none of items 2/3/4's files.
