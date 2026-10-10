# `BL-B47` — `_is_air_defence` could not recognise a class-level SAM

User direction, 2026-10-10: *"`_is_air_defence` does not recognise a class-level SAM — fix this as
well."* Branch `fix/air-defence-class-level`, based on `feature/bl13-crew-query-path`'s tip
(`153efc0`) deliberately, since both touch `body-layer/src/belief/speech.py`.

### Implementation Summary

`belief.speech._is_air_defence` resolved a believed classification through
`perception.object_model.profile_for`, which keyword-matches DCS **type** designations. A
classification held at **class** level carries the `OP_*` string itself and matched nothing, falling
into the default bucket. Measured before the fix:

```
profile_for("SA-6 Kub LN") -> OP_MRSAM          (resolved)
profile_for("OP_SRSAM")    -> OP_GROUPSOMETHING (default bucket)
profile_for("OP_LRSAM")    -> OP_GROUPSOMETHING (default bucket)
```

A class-level belief is what a contact holds *before* it is identified to type, which at range is
most of the time — so this was a silent gap on the **push** path (unprompted callouts) for the one
thing `_OP_CLASS_DISPLAY`'s own comment calls out as mattering most: *"the difference between a
short-range and a long-range SAM is the difference between a threat you can fly around and one you
cannot."*

### The boundary decision

The root was a conflation of two functions that are **not** interchangeable:

| function | resolves |
|---|---|
| `classification.parent_class_of` | a **believed classification** to its parent class |
| `object_model.profile_for` | a **DCS type name** to a profile |

`_is_air_defence` takes a believed classification, so it belongs on the **classification/lattice**
side. It now reads `_summary_op_class(facts) in AIR_DEFENSE_OP_CLASSES` — reusing the mechanism the
pull path's `_summary_air_defence_clause` and `crew_console.descriptor_verdict` already use, rather
than minting a second lattice walk. Push and pull now agree on what air defence is by construction
instead of by coincidence.

**Not** done by adding `OP_*` strings to `profile_for`'s keyword table, which would have pushed
class-level vocabulary into a type-name resolver.

**The switch is a strict widening, enumerated rather than argued.**
`classification._op_class_of` early-returns any non-default `OP_*` string and otherwise delegates to
`profile_for`, so it agrees with the old lookup everywhere the old lookup resolved. Enumerated over
**1060 distinct candidate values** — all 10 declared `op_class` values, all **131** keyword entries
in `perception.object_model` (`_KEYWORD_PROFILES` 70 + `_REPORTING_NAME_KEYWORD_PROFILES` 61), and
all **595** real DCS type names in `perception.reporting_names`' mapping plus its reporting-name
values. Each resolved both ways — `object_model.profile_for(v).op_class` against
`classification.parent_class_of(v)` — and tested for `AIR_DEFENSE_OP_CLASSES` membership:

- **0 air-defence verdicts lost.**
- **4 gained:** `OP_SRSAM`, `OP_MRSAM`, `OP_LRSAM`, `OP_SPAAG`.
- `OP_ZU23` was already covered **by accident** — the literal string `"OP_ZU23"` matches that
  table's own `"zu23"` keyword. This matters for reading the counterfactual below, where it is the
  one class-level case that passes without the fix.

The `parent_class_of("ZSU-23-4") is None` / `parent_class_of("ZSU-23-4 Shilka") is OP_SPAAG`
wrinkle did not drive the design: the bare designation is fixture-authored, the real DCS type
carries the suffix, and under *both* resolvers the bare form is not air defence — so it is not a
regression and the lattice was not "fixed" to accept it.

### Push-path behaviour change — this is a live behaviour change, not a pure bug fix

`_is_air_defence`'s only two callers both compute `is_air_defence_repeat` inside
`render_group_disclosure`, and both are gated on `not is_new_class` — so the gain is narrowly the
**repeat** case. A class-level air-defence arrival that was a *new* class already spoke, via
`is_new_class`.

| call site | branch | what changes |
|---|---|---|
| new-arrival branch | a differentiated member joins a group that already spoke | a second class-level SAM joining a group that already had one now speaks `"Short range SAM, in N o'clock group."` where it was **silent** |
| `never_spoken_partially_covered` branch | members each announced individually, grouping itself not news | an unreported class-level SAM whose class is already known among the reported members now speaks the same short clause instead of returning `None` |

**Volume.** Each firing is one short delta clause, never a full roster, and it fires only on a
**membership change** — not per poll. Range/clock drift alone still lands in the silent branch, so
the "re-spoken every ~500 m of opening range" failure class is untouched.

**Repetition — the honest answer is yes, in one narrow scene, and it widens an existing hazard
rather than creating one.** The scheduler suppresses a group's line by comparing
`content_signature` against `belief_group.last_spoken_signature` — the *immediately preceding*
signature only, not a history set. For this clause `content_signature == text`. So if clustering
jitter oscillates a class-level SAM in and out of a group, each rejoin is a fresh "new arrival" and
now speaks, and an alternating A/B/A pattern of lines defeats a single-slot guard. Before this fix
those rejoins were silent *for air defence*; they were already not silent for a new-class arrival,
so the mechanism is pre-existing and this adds one more line shape that can churn through it.

Flagged rather than merely noted, because repetition is a defect class this project has fixed twice
and the pilot has complained about directly. It is **not** fixed here: doing so means changing the
scheduler's suppression from a single slot to a history set, which is a scheduler change on the
callout path and well outside a predicate fix. Worth filing.

### Files Changed

- `body-layer/src/belief/speech.py`
  - `_is_air_defence` — body replaced with `_summary_op_class(facts) in AIR_DEFENSE_OP_CLASSES`;
    docstring records the boundary decision, the measured before/after, and the 0-lost/4-gained
    enumeration next to the predicate itself.
  - `_summary_air_defence_clause` docstring — **prose fallout.** It asserted, in the present tense,
    that `_is_air_defence` goes through `profile_for` and cannot see a class-level SAM. True when
    written, false after this commit. Rewritten as a dated historical note; the design rationale
    (the pull path calls `_summary_op_class` directly because that is the mechanism) is preserved.
  - the freshness-marker docstring — same correction, same reason.
  - **No pull-path code changed.** `_summary_air_defence_clause`, `_summary_op_class`, the freshness
    marker and the word budget are untouched; Q2's mutation-verified air-defence regression is
    un-weakened (full suite green, and the counterfactual shows it passing under both predicates).
- `body-layer/tests/test_speech.py` — the tests below, plus the same dated correction to
  `test_render_report_summary_marks_a_stale_sam_the_air_defence_clause_skips`'s docstring, which
  carried the same now-false present-tense claim about `_is_air_defence`.

### Tests Added

21 tests, all confirmed **by name** in unfiltered `pytest -v` output (not a `-k` run).

- `test_is_air_defence_recognises_a_class_level_belief` (5, parametrised over
  `AIR_DEFENSE_OP_CLASSES` **itself**, not a hand-copied list, so a class added to that set is
  covered without anyone remembering) — the `BL-B47` case, named as the broken one in its docstring.
- `test_is_air_defence_still_recognises_a_type_level_belief` (4) — the coverage that already worked,
  pinned so the widening cannot be a trade. Every designation is a **real entry** in
  `object_model`'s keyword table; the first draft used a fabricated `"S-300PS 5P85C ln"`, which
  failed and would have read as a gap in the fix rather than a bad fixture.
- `test_is_air_defence_rejects_a_non_air_defence_belief` (8) — the negative half of the bar, without
  which the positives would all pass under a predicate that answered `True` for everything. Includes
  `"OP_GROUPSOMETHING"`, the interesting case: `parent_class_of` early-returns a non-default `OP_*`
  string, so the default bucket's own name has to be excluded explicitly.
- `test_is_air_defence_answers_false_for_facts_without_a_classification` (1) — the one behavioural
  side effect, pinned as a decision: missing/non-dict `classification` now answers `False` where it
  raised. Strictly more lenient; no caller relies on the raise (both check `_classification_level`
  first).
- `test_render_group_disclosure_class_level_air_defence_repeat_arrival_is_a_delta` — push-path call
  site 1.
- `test_render_group_disclosure_class_level_air_defence_among_unreported_is_a_delta` — push-path
  call site 2. Tested separately because the two branches build `known_classes` from different
  member sets, so a fix to one would not show up in the other.
- `test_render_group_disclosure_non_air_defence_among_unreported_is_silent` — the bound on call
  site 2, which had no negative. "One more truck makes no difference" still holds.

**The existing `test_render_group_disclosure_air_defence_repeat_arrival_is_a_delta` passed
throughout**, because `"ZSU-23-4 Shilka"` is a *type* designation `profile_for` matched — exactly
the blind spot. It was left unmodified.

### Counterfactual (executed, restored by checksum)

Reverted `_is_air_defence`'s body to its old form — **not** by perturbing `AIR_DEFENSE_OP_CLASSES`,
which the test imports and which would move the bar along with the code. Result:

```
7 failed, 1625 passed, 4 xfailed
```

- 4 of the 5 class-level params fail. **`OP_ZU23` passes** — the documented accident above, and the
  reason the parametrised test is honest rather than uniform.
- Both push-path tests fail, for the stated reason.
- The missing-classification test fails (`KeyError`), as documented.
- **All 4 type-level params and all 8 negatives still pass**, so nothing here is a tautology that
  would go red under any change.

`shasum src/belief/speech.py` was `340048b67b86a5001ac3e05db474a13776b70bb1` before the revert and
is byte-identical after restoring.

### Checks

body-layer (the only subproject touched):

- `ruff format --check src tests`: **pass** (118 files already formatted)
- `ruff check .`: **pass** (one `I001` on the new import was fixed, not suppressed — recurring in
  this file)
- `mypy src`: **pass** — no issues in 54 source files, run with cwd inside `body-layer/`
- `pytest`: **pass** — **1632 passed / 4 xfailed** against a baseline of 1611/4 (+21, matching the
  tests added exactly)

audio-adapter, run to confirm untouched: **255 passed / 1 skipped**, matching baseline.

### Notable Discoveries

- **`classification._op_class_of` is a strict superset of `object_model.profile_for`** — it
  early-returns a non-default `OP_*` string and otherwise delegates. This is what made the fix a
  zero-risk widening rather than a trade, and it is worth knowing for any *other* predicate in this
  codebase still resolving a believed classification through `profile_for`.
- **`OP_ZU23` resolves through `profile_for` by accident**, because the literal class name matches
  the `"zu23"` keyword entry. Any reasoning of the form "all five air-defence classes behaved the
  same way" is wrong, and a test that only sampled `OP_ZU23` would have found nothing.
- **A third copy of the air-defence class set exists** in `crew_console.py` (~line 265), with
  membership identical to `AIR_DEFENSE_OP_CLASSES` and a structural test asserting coverage
  (`test_air_defence_classes_cover_every_air_defence_class_in_the_object_model`). It already
  resolves via the lattice, so it was correct and is untouched — but it is a second place to
  disagree about what air defence is.
- **The callout scheduler's repetition guard is a single slot, not a set.** `last_spoken_signature`
  holds only the previous line, so any alternating pair of lines defeats it. Pre-existing and not
  air-defence-specific, but this fix widens what can flow through it. See the push-path section.
- **Three docstrings asserted the defect in the present tense** and became false the moment it was
  fixed — two in `speech.py`, one in `test_speech.py`. None appeared in the task's own list of what
  the fix touches. A docstring that records *why* something was worked around is a liability at the
  moment the thing stops needing a workaround.

### Out of scope, confirmed untouched

- `belief/groups.py` — not modified. `BL-B48` (infantry as an unbounded cohesion bridge) stays
  filed.
- `decay.py` — read-only, not modified.
- No new constant introduced; `AIR_DEFENSE_OP_CLASSES` was reused.
- `BL-B47`'s own entry file is absent from this worktree, as expected — it was filed on
  `chore/file-bl13-review-findings`.

---

## Round 2 — Reviewer's one required fix: the cited keyword-entry count

`plans/air-defence-class-level/review.md` "Required Fixes" item 1. Documentation only; **no code
change**, and `_is_air_defence`'s body is byte-identical to round 1.

### What was wrong

Three places cited *"all 128 keyword entries in `perception.object_model`"*. There is no 128 in that
module. The real figure is **131**, and more importantly the sentence did not say *which* tables it
had counted, which is what made the error unresolvable by the next reader.

### Re-run, not copied

The enumeration was re-executed from scratch rather than the Reviewer's figures being transcribed —
a script in the scratchpad importing from this worktree's own `src/` (asserted: `object_model.
__file__` resolved to `…/agent-ae7f3106d19607b03/body-layer/src/perception/object_model.py`), run
with the root checkout's `body-layer/.venv/bin/python` and `PYTHONPATH=src:../world-model/src`.

| quantity | measured |
|---|---|
| `len(_KEYWORD_PROFILES)` | **70** |
| `len(_REPORTING_NAME_KEYWORD_PROFILES)` | **61** |
| total keyword entries | **131** |
| `len(reporting_names._load_mapping())` | **595** |
| declared `op_class` values | **10** (`OP_ARMORED`, `OP_GROUPSOMETHING`, `OP_INFANTRY`, `OP_LRSAM`, `OP_MRSAM`, `OP_SHIP`, `OP_SPAAG`, `OP_SRSAM`, `OP_TRUCK`, `OP_ZU23`) |
| candidate values, raw / **unique** | 1331 / **1060** |
| verdicts **lost** (`profile_for` air defence, `parent_class_of` not) | **0** |
| verdicts **gained** | **4** — `OP_LRSAM`, `OP_MRSAM`, `OP_SPAAG`, `OP_SRSAM` |

Candidate set = both keyword tables' keys + the 10 `op_class` values + every key *and* every value
of the 595-row `reporting_names` mapping, deduplicated. Each value was resolved both ways
(`object_model.profile_for(v).op_class` against `classification.parent_class_of(v)`) and tested for
`AIR_DEFENSE_OP_CLASSES` membership; the script exits non-zero unless lost is empty and gained is
exactly those four, and it exited 0.

**Agrees with the Reviewer on every figure** — 1060 candidates, 595 mapping rows, 131 entries,
0 lost / exactly 4 gained. So the conclusion is unchanged and strictly stronger than round 1
claimed: the widening was verified over 1060 values, not the ~141 round 1 actually covered.

### Files Changed (round 2)

- `body-layer/src/belief/speech.py` — `_is_air_defence` docstring: 128 → 131, with the table split
  (70 + 61), the 595 mapping rows, the 1060-value candidate set and the two resolver expressions
  that were compared. Docstring only.
- `body-layer/tests/test_speech.py` — same correction in
  `test_is_air_defence_still_recognises_a_type_level_belief`'s docstring.
- `plans/air-defence-class-level/implementation.md` — same correction in "The boundary decision",
  plus this section.
- `.claude/agent-memory/implementer/project_bl_b47_air_defence_class_level.md` — the same figure was
  wrong in memory, which is the copy that would have propagated the error to a future task.

### Tests Added (round 2)

**None.** The enumeration covered all 1060 values and found nothing the existing 21 tests miss: the
5 class-level params, the 4 type-level params and the 8 negatives already bracket every distinct
behaviour the sweep exhibits (early-return `OP_*`, keyword delegation, the default bucket, and
unresolvable free text). A test asserting "0 lost / 4 gained" would have to either re-import the
predicate it is checking — the trap in
[[feedback_equivalence_test_must_own_its_reference_arithmetic]] — or hard-code the two tables,
making it a change detector on `object_model` rather than a guard on this predicate.

### Checks (round 2)

- body-layer — `ruff format --check src tests`: pass · `ruff check .`: pass · `mypy src`: pass ·
  `pytest`: **1632 passed, 4 xfailed** (baseline, unchanged)
- audio-adapter — `ruff check .`: pass · `mypy src`: pass · `pytest`: **255 passed, 1 skipped**
  (baseline, unchanged)

### Notable Discoveries (round 2)

- **`object_model` has two keyword tables and the wrong figure came from treating it as one.** The
  second pass (`_REPORTING_NAME_KEYWORD_PROFILES`, 61 entries) runs only when the raw-type pass
  misses, so a `len()` on the first table alone reads as "the keyword table" and is 54% of it. Any
  count cited against that module has to name both.
- **The widest honest candidate set for a `profile_for`-vs-lattice comparison is the
  `reporting_names` mapping, not the keyword tables.** The tables are *keywords* — substrings — so
  enumerating them tests the matcher against its own vocabulary. The 595 mapping keys are real DCS
  type names and its values are real reporting names, which is what the predicate actually sees at
  runtime. That is 1060 of the 1060 candidates minus ~141, and it is where a trade would have shown
  up if one existed.
