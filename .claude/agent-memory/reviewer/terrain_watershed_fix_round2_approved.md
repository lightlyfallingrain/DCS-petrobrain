---
name: terrain_watershed_fix_round2_approved
description: terrain-feature-probing fix round (dca354d) reviewed APPROVED — both required fixes genuinely closed; technique for re-deriving pooled acceptance numbers a third time without reusing the fixer's own method
metadata:
  type: project
---

Round 2 review of `feature/terrain-landform-features` tip `dca354d` (fix for round 1's two
required findings — naive vs. per-contact saddle-elevation formula, and `round()`'s
round-half-to-even collapsing a symmetric 2x2-cell component to a 1-point "LineString"). Verdict:
APPROVED, no required fixes. Full record: `plans/terrain-feature-probing/review.md`, "Round 2"
section.

**Technique: don't just re-run the fixer's own verification method — use a different one.** The
fixer verified "fix changes nothing on real data" by toggling `features.py` between old/new on the
same build. For this round I instead did a from-scratch rebuild (fresh venv, fresh SRTM copy, real
`build_region` call) and measured `cell_count`/sinuosity straight from the resulting sqlite's
`tags_json`, landing on identical pooled numbers (ridge n=10, 30.0%, median sinuosity 1.223; valley
n=9, 22.2%, 1.191) via a completely independent code path. Two different verification methods
landing on the same number is much stronger evidence than re-running the same method twice — worth
doing whenever a "re-derive once more" instruction appears and the first derivation's method is
known.

**Technique: a saddle/pass-height formula claim is worth hand-running on the actual fixture, not
reading the diff and trusting the math.** Wrote a 15-line script importing the real
`_saddle_elevations` plus a hand-copied naive `min()` against the shared test fixture; got
140.0 (naive) vs. 300.0 (correct) — confirmed the new test's `relief_threshold_m=200.0` sits
strictly between them, so the regression test genuinely distinguishes the two formulas rather than
reading as one on a skim. This is the same class of check `feedback_regression_test_empirical_
check.md` already records for other features — reinforcing, not a new lesson.

**Judgment call worth remembering**: a "this only ever makes the gate more permissive, never more
restrictive" asymmetry, correctly reasoned through and documented, does not need a code guard —
it's a known monotonic shift in what's accepted, not a condition to detect and reject. The one
legitimate gap is *where* it's documented: `implementation.md` (a session log) rather than
`plan.md` or a docstring a later-stage implementer would actually read before building on top of
the gate. Filed as optional, not required — correct reasoning in a less durable location is not
the same defect class as wrong reasoning.
