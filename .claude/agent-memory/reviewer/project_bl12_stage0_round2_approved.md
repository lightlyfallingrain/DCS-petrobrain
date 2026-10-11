---
name: bl12-stage0-round2-approved
description: BL-12 Stage 0 fix round APPROVED; a review's own figures were wrong twice, and a dedup key was cited as proof of truth-provenance it cannot give.
metadata:
  type: project
---

`feature/bl12-group-contact-identity`, `a673512`, 2026-10-11. A documentation-only fix round
answering round 1's one required fix. **APPROVED**, no required fixes.

**Two of my own round-1 figures were wrong, and the implementer corrected rather than transcribed
them.** Worth remembering as the shape, not the instance:

- *"all four cross-checks are ground truth"* was a **miscount of a five-bullet block** — three were
  spacings, two were conversions of the constant itself (a clock-hour width, a unit-widths
  currency). A conversion of the number under review is not a cross-check *of* it, and lumping the
  two kinds together is how a count goes wrong. **Count and classify bullets separately.**
- A tabulation spanning 2–7 km described **a regime the unit type cannot occupy**. Infantry
  (`size_m=1.8`) tops out at 600/1406 m unaided and 1452/3403 m binocular, and the 9K113 is not
  implemented (`vars(optics)` holds exactly two `Optic`s). **Before tabulating a defect across a
  range sweep, check the detectability envelope at each row** — the same lesson the acceptance
  document draws about `BL-B48`'s 6 km fixture nobody could fly.

**The finding worth transferring (optional refinement 1).** The docstring argued two measured
spacings were ground truth *because* the log was *"deduplicated by `object_id`"*. Deleting the
mechanism: `BeliefTruthRow` carries **both** `true_x/true_z` and `believed_x/believed_z`, keyed by
`object_id`. So the dedup key proves the rows are one-per-object and proves **nothing** about which
position field was read — deduplicating believed positions removes duplicate contacts while leaving
each belief's own error intact. The reduction script was not retained, so it is unprovable from the
repo either way. Graded optional because the conclusion survives both readings.

This is [[feedback_docstring_so_clause_delete_the_mechanism]] landing on a *provenance* claim rather
than a behavioural one, and it is the same class as
[[feedback_estimate_flags_must_reach_code]]: **a log that records truth and belief side by side makes
"it came from the log" a non-answer.** Ask which field.

**Technique that paid off: AST-compare with every docstring node stripped, not just "constants
blanked".** Two `git archive` extractions, one 30-line script, `ast.dump` after deleting every
docstring `Expr`. Strictly stronger than the implementer's own check, and it settles "prose only"
without trusting a baseline test count. Note the wrinkle: in `groups.py` the prose is `#:` comments,
which never enter the AST at all, so equality there was never at risk from the prose — the strip is
what makes the *test file's* real docstring comparison meaningful.

Also: **a coverage gap stated in a docstring and filed nowhere.** The round correctly killed a false
claim and replaced it with *"no test asserts that, only `BL-B51`'s grep did"* — true (proved by grep:
no `is AIR_DEFENSE_OP_CLASSES` identity assertion anywhere, and an identity check is the only cheap
thing that distinguishes a shared set from an identical local copy). Recommended for filing rather
than fixed, since `BL-B51` left it. See [[project_bl_b47_air_defence_class_level_review]] and
[[a_literal_pin_is_not_a_drift_guard]].

Dispatch note: worktree HEAD was `main` and **diverged**, not behind — no `--ff-only` available by
definition. Verified from a detached checkout of the tip, and the cherry-pick proved content-identical
to the implementer's `0f1bd9b` by byte-comparing `git show --format=""` output for both.
