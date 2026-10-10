# Review — `BL-B47`: `_is_air_defence` could not recognise a class-level SAM

Branch `fix/air-defence-class-level`, tip `eb11b7a704a7e1df337910872cebc7011edee5bd`.
Diff reviewed: **`153efc0..eb11b7a`**, one commit. Everything at or below `153efc0` is BL-13 and
was not re-reviewed.

Worktree started at `e2e2164` (`main`), a strict ancestor of the named tip with a clean tree;
fast-forwarded to `eb11b7a` before reviewing. `body-layer/ROADMAP/BL-B47.md` absent as stated.
Input documents all present and read in full.

### Review Summary

Correct fix, on the correct side of the boundary, with the strongest evidence this diff could
carry. Every one of the six claims was re-verified independently and all six hold; two were
verified more broadly than the implementer checked and came out stronger, and one — the
repetition hazard, the only thing in this diff with real judgement in it — came out *weaker*
than the implementation log suggests, in the fix's favour.

One required fix, and it is a wrong number in a docstring, not behaviour.

**Verification performed (all re-run, not read):**

| claim | method | result |
|---|---|---|
| 2, strict widening | enumerated **1060** candidate values — both keyword tables (131 entries), all 10 declared `op_class` values, and all **595** real DCS type names in `reporting_names`' mapping plus its reporting-name values | **0 lost, exactly 4 gained** (`OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM`/`OP_SPAAG`) |
| 3, `OP_ZU23` accident | direct call | `profile_for("OP_ZU23").op_class` → `OP_ZU23`; old `True`, new `True`. Confirmed |
| 4, no pull-path code changed | AST diff of `speech.py` base vs head with all docstrings stripped | **the `_is_air_defence` body is the only code change in the file.** Proven mechanically, not read |
| 5, counterfactual | reverted the predicate body in an isolated `git archive` snapshot | **7 failed / 1625 passed / 4 xfailed**, byte-identical to the reported figure; `OP_ZU23` param green, all 4 type-level params and all 8 negatives green |
| 6, real keyword entries | matched each fixture against `_KEYWORD_PROFILES` | all four hit a real entry (`"kub "`, `"shilka"`, `"osa"`, `"s-300ps 40b6m tr"`) |
| negative bounds real | mutated the predicate to `return True` | **12 red**, including the new `non_air_defence_among_unreported_is_silent` and `test_2c_transcript_fixture_renders_four_lines_not_seven`. The call-site-2 negative is load-bearing |
| +21 test delta | collected on an isolated `153efc0` snapshot vs head | **1615 → 1636**. Exactly +21 |
| checks | `ruff format --check src tests`, `ruff check .`, `mypy src` (cwd inside `body-layer/`), `pytest` | 118 formatted · all checks passed · 54 files clean · **1632 passed / 4 xfailed**. audio-adapter **255 passed / 1 skipped** |
| invariants | `/invariant-check` | all greppable invariants PASS; the 7 swallowed-exception and 4 `type: ignore` WARNs are pre-existing and untouched |

**Claim 1, the boundary decision — agreed, and it is the right side.** `_is_air_defence` is handed
a *believed classification*; `profile_for` is a DCS-type-name resolver. Resolving a belief through
a type-name keyword table was the defect's root, not its symptom, and
`AIR_DEFENSE_OP_CLASSES`-membership on the lattice walk is the same test the pull path's
`_summary_air_defence_clause`, the freshness marker and `crew_console.descriptor_verdict` already
apply. The reuse is genuine rather than papered over: `_summary_op_class` takes the same `facts`
dict and reads the same `classification["value"]`, so there is no shape adapter and no second
meaning of "air defence". Adding `OP_*` strings to `profile_for`'s table would have been the wrong
fix for the stated reason.

**Claim 4, the docstring rewrites — accurate, all three.** Each asserted the defect in the present
tense and became false on this commit; each now reads as a dated historical note with the design
rationale (the pull path calls the helper because it *is* the mechanism, not because the predicate
was broken) preserved. Checked against the code: `_summary_air_defence_clause` does test
`_summary_op_class(facts)` + `AIR_DEFENSE_OP_CLASSES` at `speech.py:729-732`, and
`_summary_air_defence_freshness_clause` at `speech.py:878-879` — both rewrites describe what the
code does. BL-13's Q2 regression is un-weakened: all 30 `-k air_defence` tests pass, and every one
of them was green under the counterfactual too, so none of them is carrying this fix's weight.

### Required Fixes

1. **`body-layer/src/belief/speech.py:1939`, `body-layer/tests/test_speech.py:2760`, and
   `plans/air-defence-class-level/implementation.md:47` — the enumeration cites "all 128 keyword
   entries in `perception.object_model`". The real figure is 131** (`_KEYWORD_PROFILES` 70 +
   `_REPORTING_NAME_KEYWORD_PROFILES` 61). No behavioural consequence, and the *conclusion* is
   stronger than claimed, not weaker — I re-ran the enumeration over 1060 values including all 595
   mapping keys and still got 0 lost / 4 gained. But this project treats a quoted measurement as
   checkable, and the next person to re-run it will get 131 and have to work out whether the table
   grew or the number was wrong. Correct the figure in all three places (and it is worth saying
   *which* tables and the 595 mapping keys, since that is what makes it a real enumeration).

### Observations — the push-path behaviour change

**I agree the scheduler fix is out of scope, and the measurement makes that call stronger than the
implementation log does. The log's "widens a pre-existing mechanism rather than creating one" is
*correct*, and now measured.** Three probes, driving `render_group_disclosure` + `mark_group_spoken`
in the sequence `CalloutScheduler.tick` uses, oscillating a contact in and out of a group on
alternate ticks:

| scenario | pre-fix | post-fix |
|---|---|---|
| one oscillating class-level SAM, base group already has its class | silent throughout | **one** line, then silent for all 5 remaining ticks |
| one oscillating class-level SAM **+** one oscillating armor, out of phase | one line total (t=2), then silent for 8 ticks | **10 lines in 10 ticks**, alternating indefinitely |
| two oscillating contacts of two distinct **new** classes (no air defence anywhere) | **10 lines in 10 ticks**, alternating indefinitely | same |

Three things follow, and the third is the one that decides scope.

- **A single oscillator cannot churn, before or after.** `mark_group_spoken` refreshes
  `last_spoken_member_contact_ids` *only when the group speaks*, so a contact announced once as an
  arrival stays in the snapshot and a later rejoin is not an arrival at all. The new clause's own
  A/A repetition is suppressed twice over — by that, and by the one-slot content signature.
- **The ratchet needs two alternating line shapes**, because each speech refreshes the snapshot
  without the *other* oscillator and so re-arms it. That is the mechanism, and the one-slot
  signature guard is powerless against it.
- **That configuration is fully reachable with no air defence involved at all** (row 3, measured
  against the pre-fix predicate). So this fix does not create the failure mode; it lowers the
  ingredient count from "two oscillators with distinct unknown classes" to "one oscillating
  air-defence contact plus any one other arriving class". A real widening of reachability, strictly
  inside a larger hole that already existed.

So: **ship it.** The right fix is the scheduler's suppression becoming a history set rather than a
single slot, and that fix is owed to the *pre-existing, larger* instance regardless of this commit —
it is not an air-defence item and should not be filed as one. The implementation log's framing is
right; its "worth filing" note risks being minted as "SAM repeat churns", which would under-scope
it. **File it as: `belief.callouts`' group suppression is a one-slot signature plus a
speak-only membership-snapshot refresh, and any two alternating group lines defeat both — measured
at 10 lines in 10 ticks with no air defence involved.** Attach these numbers; they are the argument.

Its interaction with `BL-B48` is real and worth saying in that filing: `EAGER` infantry cohesion
producing a 6 km-wide group is precisely the input that makes membership flip tick-to-tick, which
is the ratchet's only required ingredient. Neither is dangerous alone; together they are the shape
the pilot has already complained about. Whichever is fixed first, the other stops mattering much.

### Observations — other

- **Three copies of the air-defence class set, and only one has a drift guard.** `crew_console`'s
  `_AIR_DEFENCE_OP_CLASSES` (`crew_console.py:264`) is guarded by
  `test_air_defence_classes_cover_every_air_defence_class_in_the_object_model`
  (`tests/test_crew_console.py:2019`), which asserts `air_defence_by_name <= _AIR_DEFENCE_OP_CLASSES`
  against both of `object_model`'s tables. `belief.groups.AIR_DEFENSE_OP_CLASSES`
  (`groups.py:234`) has only a literal pin (`test_groups.py:368`), which is a change detector, not
  a drift guard. **Verified by mutation**: injecting an `OP_XLRSAM` profile into `object_model`
  turns the `crew_console` test red and leaves `test_constants_are_the_stated_assumptions` green.
  That set is now what the push-path predicate, the pull-path clause *and* the freshness marker all
  resolve against — and the omission this guards against is not hypothetical, it cost `OP_LRSAM`
  months of silence in the other copy. Exposure is unchanged by this diff (the old predicate tested
  the same set), so **not a required fix** — but worth filing, as one set with one `<=` guard. The
  structural test is sufficient protection *for the copy that has it*; the issue is that two copies
  do not.
- **Leaving `crew_console`'s copy alone was right.** It already resolves via the lattice, its
  comment states a deliberate reason for living there ("which classes a *crew command* treats as
  air defence" is command vocabulary, not an object-model property), and touching it would have
  pulled a correct module into a defect fix.
- **`test_render_group_disclosure_air_defence_repeat_arrival_is_a_delta` is unmodified and passes**,
  and passed under the counterfactual — confirming it never exercised the broken path, because
  `"ZSU-23-4 Shilka"` is a type designation. Correctly left alone.
- **Constraints all hold**: `belief/groups.py` and `decay.py` not in the diff; no new constant;
  `AIR_DEFENSE_OP_CLASSES` reused. The only files touched are `speech.py`, `test_speech.py`,
  `implementation.md` and three implementer agent-memory files — the last at the repo-root path,
  and `MEMORY.md` appended by exactly two lines, not rewritten.
- **No debug leftovers, no TODO/FIXME** in the added lines.
- **Parametrising over `AIR_DEFENSE_OP_CLASSES` itself** is the right call and is not circular here:
  the counterfactual perturbed the predicate body rather than the set, so the bar did not move with
  the code. Five params present, none vacuous.
- **Merge-order dependency, for whoever merges:** `BL-B47`'s roadmap entry lives on
  `chore/file-bl13-review-findings`. This branch cannot mark it done, so the entry has to be closed
  when that branch lands — otherwise the fix merges and the backlog still says it is open.

### Verdict

**APPROVED WITH MINOR FIXES** — approved to merge once the `128` → `131` figure is corrected in the
three places named. Nothing behavioural is outstanding, and the one judgement call in the diff (the
scheduler's repetition guard being out of scope) is the right one, measured.

### Review Confidence

**Full read**, with independent re-execution of every claim: the widening enumeration re-run and
widened to 1060 candidates, the counterfactual reproduced from a clean `git archive` snapshot, the
"no pull-path change" claim proven by docstring-stripped AST diff rather than read, the negative
bounds mutation-tested, the baseline test count collected on an isolated base snapshot, and the
repetition hazard sized by three executed oscillation probes against both the fixed and the
pre-fix predicate. The worktree has no `.venv`; the root checkout's `body-layer/.venv` and
`audio-adapter/.venv` binaries were used with cwd inside each subproject, and imports were
confirmed to resolve to the worktree's own `src/` before any check was trusted.
