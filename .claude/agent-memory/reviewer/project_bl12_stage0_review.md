---
name: project-bl12-stage0-review
description: BL-12 Stage 0 (BL-B48 both-EAGER, the 500 m eager cap, BL-B51 consolidation) — APPROVED with one documentation required fix; four mutations run.
metadata:
  type: project
---

`feature/bl12-group-contact-identity`, `bae8963..7b2e3b4`, reviewed 2026-10-11. Verdict: **APPROVED
WITH ONE REQUIRED FIX**, documentation only (see
[[feedback_calibration_true_vs_believed_geometry]]). Review at
`plans/group-contact-identity/review.md`.

**Techniques that earned their cost here, reusable:**

- **Reproducing a before/after table by monkeypatching the module-level function rather than
  checking out three commits.** `_cluster_contacts` resolves `_pair_backstop_m` as a module global at
  call time, so three variants (`any`+inf, `both`+inf, tip) ran in one process against the real
  profiles and real constants. Printing per-pair backstop, `pair_threshold`, unions **and** extents
  is what makes a "bit-identical" claim checkable — the three-infantry row is `90.0` at all three
  states because the relative test binds and the backstop is never read.
- **A counterfactual is scoped to the commit it was run on.** The implementer's "four tests red on the
  `or` revert" is true of `1ec68fb` and **three** at the tip, because the 0b cap now catches two of
  them instead of the predicate. Not a defect; re-run mutations at the tip before judging a
  counterfactual claim.
- **Checking a fixture's "no eager latitude" claim by resolving profiles, not by reading the
  docstring.** Class-level raws resolve unevenly: `OP_ARMORED` → `OP_GROUPSOMETHING` (so
  `_representative_size_m` substitutes 7.0 m, `STRICT`), while `OP_TRUCK` and `OP_INFANTRY` match
  their own keywords. Here it confirmed the claim, with the eager branch never entered at all.
- **A restore `shasum` the implementer recorded is an independent corroboration**, not just their
  bookkeeping — `object_model.py` at the tip hashes to the `17eb8070…` they cited.

**Judgement calls settled, so they are not relitigated:** a pair cap and *not* a cluster-extent rule
is right, because D7's own target sentence is about a **column** and a hard span cap would reject the
object the milestone exists to describe. The consequence is that A6's speech-time extent guard must
become **unconditional** for Stage 4 (the plan makes it conditional on declining 0b), since chaining
still permits ~1.2 km — 2.4 spoken range buckets.

**Still live after this merge:** a **fourth** unguarded copy of the air-defence vocabulary,
`crew_console._FOLLOW_DESCRIPTOR_OP_CLASSES`'s `"sam"` ∪ `"aaa"`, set-equal to
`AIR_DEFENSE_OP_CLASSES` and not covered by the new `<=` guard. Outside `BL-B51`'s stated three
copies; worth its own `BL-B` item.
