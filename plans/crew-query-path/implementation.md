# BL-13 — the crew query path: implementation log

Stages 1, 2 and 3 of `plan.md`. Stages 4 (the `last_gazed_sim` ledger) and 5 (landmark `where`)
are **not started**, as scoped.

### Implementation Summary

`report|describe [<what>] [<where>] [<how far>]` is one slotted token end to end. audio-adapter
owns every mechanic (parse, anchor, slot, mutual exclusion) and hands body-layer
`{token: "report", slots: {...}}` over the existing HTTP/JSON channel; body-layer filters belief by
those slots and answers with one summary utterance.

All three measured findings in the plan's "What I measured before designing" section were
reproduced against `command_matcher.match_transcript` on the target commit before any code was
written, and each is now a regression test. `report left` → `report_bearing_e` at ratio 0.75 is
closed: `BL-B28`.

### Files Changed

**audio-adapter**

- `src/vocabulary.py` — new `"report"` token in `VOICE_ONLY_TOKENS`; five slotted bias phrasings
  under `PHRASES["report"]`; `_REPORT_VERBS`/`report_verbs()`; `SECTOR_WORDS`/`parse_sector_word`,
  `RELATIVE_WORDS`/`parse_relative_word`, `BAND_WORDS`/`parse_band`. `parse_descriptor`/
  `parse_clock` untouched and reused verbatim.
- `src/command_matcher.py` — `_parse_report_slots`, `_where_slot_count`, and the report verb
  branch, placed after the `follow` branch and before the phrase table.
- `tests/test_vocabulary.py` — the new token's group membership, the bare-verb exclusion, the three
  mirror tables' own membership, and each parser including the whole-word and multi-word cases.
- `tests/test_command_matcher.py` — `TestSlottedReport`, 14 tests; plus two cases moved out of
  `test_exact_phrase_hits_every_token_family` (see "Behaviour changes" below).

**body-layer**

- `src/belief/crew_console.py` — `"report"` in `DISPATCHED_COMMAND_TOKENS`, its `handle_command`
  branch and `_handle_slotted_report` slot validation, a `_describe_token_for_confirm` slots
  branch; module-level `descriptor_verdict`/`DescriptorVerdict` extracted from
  `_descriptor_score`; `_SECTOR_FOR_WORD`, `_REPORT_BAND_BOUNDS_M`, `_REPORT_BAND_LABELS`;
  `_handle_report` split into `_report_scope`/`ReportScope` + `_render_report_lines`, with the
  summary wired at the pull site and `_band_label_for` supplying its distance clause.
- `src/belief/speech.py` — `render_report_summary`, `REPORT_SUMMARY_MAX_WORDS`, and its helpers
  `_summary_op_class`, `_spoken_number`, `_summary_count_clause`, `_CLOCK_SIGNED_OFFSET`,
  `_summary_clock_clause`, `_dominant_op_class`, `_summary_air_defence_clause`,
  `_summary_deferral_clause`, `_is_stale`. `render_report`/`render_clear`/`render_no_view`
  unchanged.
- `src/belief/decay.py` — **not touched.** `OBSERVED_WINDOW_S` imported only.
- `tests/test_crew_console.py`, `tests/test_speech.py` — 27 and 19 new tests respectively; six
  existing report tests' expectations updated (below).

### Decisions made during implementation

**1. `PHRASES["report"]` cannot carry the bare verb.** The plan says *"phrase `("report",)`-style
bare verb"*, but `report_all` already owns `"report"` and `"describe"`, and
`normalized_phrase_index` **raises** on a collision rather than letting one token shadow the
other — so that literal reading does not import. The new token instead carries five slotted
phrasings as recogniser bias hints (one per slot shape, both verbs), which is what `PHRASES` is
documented to be, and bare `"report"` keeps falling through to `report_all` exactly as the plan
requires.

**2. The *where* mutual exclusion is the matcher's, not the parser's.** `_parse_report_slots`
returns every slot it finds; `match_transcript` counts the three *where* slots and returns the
detected-error shape. Same split `parse_bearing`'s three-way outcome already follows — the parser
reports, the caller decides what a detected error earns.

**3. `_handle_report` is split into `_report_scope` + `_render_report_lines`.** Two reasons, and
the second is a defect (below): Decision C's summary is computed from the in-scope facts, so that
set has to be a thing a caller can hold; and the in-scope set is the only place a filter's effect
is observable.

**4. `_summary_op_class` uses `parent_class_of`, not `object_model.profile_for`.** Measured:
`profile_for("BMP-2")` is `OP_ARMORED` but `profile_for("OP_ARMORED")` and `profile_for("OP_SRSAM")`
both fall through to the default bucket, because it keyword-matches *type* names. A `class`-level
belief holds the `OP_*` value itself, so the lattice walk is the only lookup resolving both forms —
and it is the one `descriptor_verdict` already uses, so the summary's classes and the filter's
classes agree by construction. The air-defence clause tests membership on `_summary_op_class` for
the same reason rather than calling the existing `_is_air_defence`, which would miss a
*class*-level SAM — precisely the case Q2 exists for. `_is_air_defence` itself is left alone.

**5. Clock hours are numerals, not number words.** Decision 13's mock spells them out; every
report line this crew already speaks uses numerals (`_contact_report_text`,
`render_group_report`). One answer typographically unlike all the others is the worse outcome, and
it also avoids a fourth clock-word table.

**6. The deferral uses the singular display word.** `"the trucks group"` (from
`_OP_CLASS_DISPLAY_PLURAL`) against mock B's `"the truck group"` — `"group"` is already doing the
pluralising.

**7. The air-defence clause says "and one X", never "and a X".** The indefinite article would have
to agree with the following word's sound, and `"a AAA"` is wrong written and wrong spoken
(`_respell_for_tts` turns it into "triple A"). A count word sidesteps agreement entirely.

### Behaviour changes that are not purely additive

- **`report east` / `report three o'clock` now resolve to the slotted `report` token**, not to
  `report_bearing_e` / `report_clock_3`. Unavoidable: the slot branch sits in front of the phrase
  table, which is what the plan specifies and what makes `report left` work. The legacy tokens stay
  in `TOKENS` for the F10 path, the bench corpus and body-layer's dispatch; voice simply routes the
  slotted forms through the slot. Two cases moved out of
  `test_exact_phrase_hits_every_token_family` into
  `TestSlottedReport::test_legacy_report_forms_now_resolve_to_the_slotted_token`, with the move
  explained in both docstrings; bare `"report"` replaces them as that test's report-family case.
- **The clock filter is ±1 hour**, so shipped `report_clock_*` answers include more contacts.
- **Every report answer's wording changed** (Stage 3), including `report_all` and the legacy
  families, since they share `_handle_report`.

### Tests Added

**audio-adapter — `tests/test_command_matcher.py` (`TestSlottedReport`)**

- `test_report_left_is_not_report_east` — `BL-B28`'s measured wrong-direction match, asserted by
  name.
- `test_report_right_resolves_symmetrically` — the `token=None` half of the same asymmetry.
- `test_no_relative_form_can_resolve_to_a_cardinal` — Stage 1's acceptance criterion over all four
  relative words and both verbs.
- `test_describe_is_a_substitutable_verb_not_just_an_anchor` — six slotted forms, `report` ≡
  `describe`. This is what `0caa39e` left undone.
- `test_each_slot_parses_on_its_own`, `test_all_three_slot_kinds_together`.
- `test_the_band_was_already_being_heard_and_discarded` — measured finding 3.
- `test_two_where_slots_are_a_detected_error_not_a_guess`,
  `test_a_band_alongside_two_where_slots_still_rejects`.
- `test_zero_slot_report_still_falls_through_to_report_all` — all five legacy phrasings.
- `test_legacy_report_forms_now_resolve_to_the_slotted_token`.
- `test_numeric_bearings_still_take_the_bearing_branch`.
- `test_follow_branch_is_tried_before_the_report_branch` — pins the branch order in the source,
  not only the two outcomes.
- `test_adversarial_sentences_do_not_falsely_fire_a_report` — including `"the scribe wrote it
  down"`, which anchors the report verb at ratio 0.857.
- `test_a_landmark_where_degrades_rather_than_saying_again`.

**audio-adapter — `tests/test_vocabulary.py`** — token group membership; bare verbs stay with
`report_all`; `report_verbs()`; phrasing coverage of both verbs and all five slot shapes; the three
mirror tables' own membership (Decision E); each new parser, including whole-word matching
(`north` inside `northeast`), split compass spellings, the multi-word band forms, transcript-order
tie-break, and disjointness of all five slot vocabularies.

**body-layer — `tests/test_crew_console.py`** — `_SECTOR_FOR_WORD`/`_REPORT_BAND_BOUNDS_M` mirror
membership; zero-slot and unrecognised-slot degradation; slotted ≡ legacy for `clock`/`sector`
including the rear-hemisphere refusal; dispatch registration and confirm readback (including a slot
it cannot yet filter on); band filters-not-sorts and its lower-inclusive boundary; descriptor
includes unclassified and excludes only known-wrong, can empty the answer, and `"group"` keeps its
cardinality meaning; relative agrees with `scan`'s wedge table; all four relative sectors inside
the cockpit mask (the `render_no_view` enumeration, checked not asserted in prose); clock span ±1
with its bound; slots combine; the pull path is not filtered by gaze (Decision D); the group-roster
leak is closed; band label follows the query then the furthest contact; band labels derived from
the filter bounds; freshness window is `decay`'s own, driven across the boundary;
`descriptor_verdict`'s three outcomes and its `"group"` branch; `_descriptor_score` maps the shared
verdict onto its weights.

**body-layer — `tests/test_speech.py`** — mock B reproduced; single-hour collapse; the arc-not-
arithmetic span (11 through 1); one class folds into the count and a mixed scene hedges; an
unclassified contact still counts as a unit; `at least` for an open-ended interval; air defence
named among a majority, each tier apart, not named twice, and never with a bare article; a wholly
remembered answer qualified and a fresh one not; at most one deferral and none when everything is
stale; the drop order with the class clause surviving the first drop; the pointer kept when
nothing else fits; an empty scope rejected; and the dominant-air-defence-class regression.

### Counterfactuals executed

Each with `shasum` before and after, restored and re-verified. Recorded only because they were
run.

| probe | expected red | result |
|---|---|---|
| `_where_slot_count(...) > 1` → `if False` | the two mutual-exclusion tests | 2 failed, for the stated reason |
| `_parse_report_slots` returns `{}` instead of `None` | the fallthrough + adversarial tests | 6 failed, including two pre-existing |
| clock span `> CALLOUT_GROUP_CLOCK_SPAN_HOURS` → `> 0` | the span test | 1 failed |
| descriptor filter `continue` disabled | the three descriptor tests | 3 failed |
| pull site reverted to `_render_report_lines` | the leak test and the wording tests | 11 failed; the leak test showed `"Armor, truck and infantry"` |
| air-defence clause suppresses the dominant class unconditionally | *nothing* | **18 passed — the regression was untested**, so `test_render_report_summary_keeps_a_dominant_air_defence_class_when_the_clause_drops` was written, and reproduces it |

### Checks

**audio-adapter**
- `ruff format --check src tests tools`: pass (32 files)
- `ruff check src tests tools`: pass
- `mypy src` (from inside the subproject): pass, 15 files
- `pytest`: pass — 255 passed, 1 skipped (baseline 222/1)

**body-layer**
- `ruff format --check src tests`: pass (118 files)
- `ruff check src tests`: pass
- `mypy src` (from inside the subproject): pass, 54 files
- `pytest`: pass — 1595 passed, 4 xfailed (baseline 1551/4)

### Notable Discoveries

1. **The filters leaked through `render_group_full_disclosure`'s full-roster rule, and the plan did
   not anticipate it.** Measured: three contacts at two o'clock at 1/3/7 km cohere into one
   `Group`, and `report two o'clock near` answered *"Armor, truck and infantry, 2 o'clock, 1
   kilometre."* — a truck at 3 km and infantry at 7 km named to a pilot who asked about *near*. The
   renderer is correct for the unfiltered report it was written for; the moment there is a filter,
   any in-scope member drags its group-mates in. **Stage 2 alone would have shipped visibly wrong
   answers.** Stage 3 closes it by construction (aggregates over the filtered set), which is why the
   three stages must ship together — do not merge Stage 2 on its own.

2. **The dominant class was non-deterministic.** `max(set(op_classes), key=op_classes.count)`
   iterates a set, so a tie resolved by hash order — and because the dominant class is suppressed
   from the air-defence clause, that silently decided whether a SAM got named. It is now weighted
   by believed unit count, which is also what "mostly" means to a pilot: decision 13's own example
   is a 1-1 tie by contacts and 6-1 by units, so contact-counting would have got the user's own
   mock wrong.

3. **Two budget rules plus Q2 collided.** The air-defence clause skipped the dominant class to
   avoid saying it twice, but that clause is the second thing the budget drops — so a scene whose
   modal class was `OP_LRSAM` lost the long-range SAM entirely. The clause is now recomputed per
   budget candidate. An unconditional-suppression probe passed against the whole original test
   set, so nothing would have caught it.

4. **`object_model.profile_for` and `classification.parent_class_of` are not interchangeable for a
   believed classification.** `profile_for("OP_SRSAM")` and `profile_for("OP_ARMORED")` both return
   the default bucket. Anything reading a `class`-level belief must use `parent_class_of`.
   `speech._is_air_defence` uses `profile_for`, so it does **not** recognise a class-level SAM —
   pre-existing, out of scope here, and worth a look wherever it is used on the push path.

5. **`parent_class_of("ZSU-23-4")` is `None`.** The lattice does not resolve that string, so a
   ZSU-23-4 is unclassified rather than air defence — consistent with that fixture's own existing
   note about `GROUP_REPORTING_UNKNOWN_SIZE_M`. It made an obvious-looking "the AAA must be named"
   expectation wrong.

6. **`belief.groups` cohesion is erratic at these fixture scales.** Two contacts 2 km apart did not
   group; two contacts at clock 12 and clock 3 did; three at 1/3/7 km did. Not touched here, but it
   makes any spoken-output fixture fragile — which is why the Stage 2 filter tests assert the scope.
   Worth its own look.

7. **`ruff format .` reformats Python code blocks inside Markdown.** It rewrites
   `body-layer/research/2026-10-05-security-audit.md`, a pre-existing drift unrelated to this work.
   The gate was run in the subproject's own documented form (`ruff format src tests`), and the `.`
   form's one finding is left alone.

8. **`describe two o'clock` resolved to `report_clock_2` at 0.667 `ambiguous=True` on the target
   commit**, not `token=None` as the plan's table recorded for `main`. The plan measured before
   `0caa39e` merged. The outcome is the same either way — it was never usable.

9. **mypy narrows a `str` to a `Literal` union on a membership test against a tuple of literals**,
   and `--strict` then rejects an explanatory `cast` as redundant.

---

## Round 2 — the Reviewer's required fix and its four optional corrections

Reviewed at `44cb1db`. Worktree HEAD was `e2e2164`, a strict ancestor, tree clean —
fast-forwarded with `git merge --ff-only 44cb1db`. `review.md`, `plan.md` and this log all present
and read in full. Stage 4 and Stage 5 remain out of scope, and so do both of the review's
out-of-scope findings (the `_is_air_defence` class-level SAM gap, the infantry-as-unbounded-bridge
cohesion behaviour) — neither `belief/groups.py` nor `_is_air_defence` was touched. `decay.py`
untouched; no new constant.

### Files Changed

- `body-layer/src/belief/speech.py` — the required fix. Three changes, one defect:
  - **`_summary_count_clause` now returns `tuple[str, int]`** — the clause *and* the number it
    speaks. The caller substitutes a display word into that clause, so it has to know which of the
    three branches ran; re-deriving the number from the rendered string would be the second place to
    disagree.
  - **New `_unit_word(count)`**, the single `"unit"`/`"units"` site. **This is wider than the
    review named, deliberately**: it named the open-ended branch (`"at least one units"`), but
    enumerating all three noun sites in the function found the midpoint branch has the same defect
    (`"about one units"`, reachable whenever a `cardinality` interval's `lo` is zero, since
    `max(1, round(...))` floors the midpoint at one). Only the exact-total branch had ever
    inflected, which is exactly why the inconsistency survived. One noun site, not three.
  - **The fold picks `_OP_CLASS_DISPLAY` when the spoken count is one**, `_OP_CLASS_DISPLAY_PLURAL`
    otherwise — the same table and the same `count == 1` reasoning
    `_summary_air_defence_clause` already uses, rather than a third mechanism. The `"mostly"` hedge
    is now in an `elif` and stays unconditionally plural: it requires at least one *unclassified*
    contact alongside the classified ones, so its count is never one.
- `body-layer/src/belief/crew_console.py` — two comment corrections (review observations 1 and 4).
  The `relative` filter's docstring named a `belief.attention` re-export that does not exist;
  verified at the source — `crew_console.py:166` imports `SECTOR_WEDGE_DEG` directly from
  `perception.gaze`, and `attention.py:78` imports the private `_RELATIVE_SECTOR_WEDGE_DEG` for
  itself rather than re-exporting anything. The conclusion was right for the wrong reason, and the
  corrected wording says *identity* (`gaze.py:155` binds the public alias to the same object), not
  two tables kept in step. Separately, the revert note at the pull site now says what a revert
  costs: `_render_report_lines` documents the group-roster leak thoroughly but the pull-site comment
  is what a reverter reads *first*, and it claimed reverting "is this one call site" with no mention
  that a *filtered* query reverted to the enumeration speaks out-of-scope group-mates.
- `audio-adapter/src/vocabulary.py` — review observation 2, verified before rewriting rather than
  taken from the report. `LEGACY_F10_TOKENS` holds seventeen scan/watch/cancel tokens and no
  `report_*` token, so the legacy report families are not reachable from the F10 menu at all and the
  "referenced by `LEGACY_F10_TOKENS` ordering" clause (inherited verbatim from the plan's Decision
  A) is false. The four consumers that *do* justify retention were each checked at the source and
  are now named: `TOKENS` membership, which `tools/stt_bench.py`'s `_print_prompts` iterates to
  build the bench corpus; body-layer's `_CLOCK_REPORT_TOKENS`/`_BEARING_REPORT_TOKENS` and its
  `DISPATCHED_COMMAND_TOKENS` pinned test; `belief/brain_reply.py`; `belief/voice_commands.py`.
- `body-layer/tests/test_crew_console.py` — review observation 3. The stale clause inside the
  rewritten truncation test is replaced; the cohesion-backstop arithmetic in the same comment is
  correct and kept, and the deleted clause is quoted in place with a note that it described the test
  this one replaced.
- `body-layer/tests/test_speech.py` — four new tests (nine cases).

### Tests Added

- `test_singular_fold_openings_cover_every_inflecting_display_class` — pins the guard's own breadth.
  `_INFLECTING_OP_CLASSES` is **derived from the two display tables** (every class whose plural word
  differs from its singular) and asserted equal to the parametrised case table, so a class added to
  the object model later fails this test instead of silently escaping the guard.
- `test_render_report_summary_speaks_a_singular_noun_for_a_count_of_one` — six parametrised cases,
  asserting the full answer string. Parametrised rather than single-cased because the review's point
  is that the *class choice* is load-bearing, and a one-class guard is one rename away from being
  back on a mass noun. `OP_GROUPSOMETHING` is in the table with its own expectation
  (`"One unit"` — it never reaches the fold, because `_summary_op_class` reads "is the default
  bucket" and "has not resolved to a bucket" as the same answer) rather than filtered out: a class
  filtered out of a guard is a class nobody is watching.
- `test_render_report_summary_agrees_the_unit_noun_on_an_open_ended_count` — the `"at least"`
  branch at `lo == 1`, both folded (`"At least one truck"`) and unfolded (`"At least one unit"`),
  since the fold is a substitution *after* the clause is built. The existing
  `test_render_report_summary_says_at_least_for_an_open_ended_count` exercises the same branch at
  `lo == 4` over `OP_ARMORED`, so it could not have caught either.
- `test_render_report_summary_agrees_the_unit_noun_on_a_hedged_count_of_one` — the `"about"`
  branch's floored midpoint. This is the site the review did not name and the enumeration found.

**Both counterfactuals were executed, not reasoned about.** `speech.py` was copied to the scratchpad
and restored by `shasum` (`31e4675a…`) each time, never by eye and never with `git checkout --`:

| perturbation | result |
|---|---|
| fold forced back to `display = plural` (the pre-fix path) | **6 failed, 133 passed** — the five inflecting fold cases plus the folded half of the open-ended test, each with the exact `"One long range SAMs"`-shaped diff |
| `_unit_word` forced to `return "units"` | **3 failed, 136 passed** — `OP_GROUPSOMETHING`, the open-ended test, the hedged-midpoint test |

`test_render_report_summary_collapses_a_single_hour` (the review's *"One armor"* example) **passed
under both**, which is the review's claim about it reproduced rather than accepted: it was never a
guard on this.

### Checks

body-layer (`src tests` form — `ruff format .` rewrites Python blocks inside Markdown and touches an
unrelated research note; mypy run from inside the subproject, config discovery being CWD-only):

- ruff format src tests: **pass** (1 file reformatted — line-wrapping of the new conditional
  expression only)
- ruff check .: **pass**
- mypy src: **pass** (54 files)
- pytest: **pass** — 1604 passed, 4 xfailed (baseline 1595/4; +9 is exactly the nine new cases)

audio-adapter:

- ruff format src tests: **pass** (29 files unchanged)
- ruff check .: **pass**
- mypy src: **pass** (15 files)
- pytest: **pass** — 255 passed, 1 skipped (matches baseline)

### Notable Discoveries

10. **The midpoint branch had the same singular/plural defect as the open-ended one, and nothing
    reported it.** The review enumerated two noun sites; the function had three. Writing the guard
    for the one that was named would have left `"About one unit"` wrong, reachable through a
    `cardinality` interval whose `lo` is zero. Enumerating the containing unit rather than the named
    site is what found it, and `_unit_word`'s docstring now carries that enumeration next to the
    code so a fourth site cannot be added quietly.

11. **`OP_GROUPSOMETHING` is the one display class whose singular and plural are different *words*,
    and it never reaches the fold.** `"group"` versus `"contacts"` — not a suffix. It is filtered
    out upstream by `_summary_op_class`, which treats the default bucket and an unresolved
    classification as the same answer, so a lone `OP_GROUPSOMETHING` belief speaks `"One unit"`.
    That is existing deliberate behaviour and is untouched, but it means the set of classes a fold
    guard must cover and the set a *display table* guard must cover are not the same set — worth
    knowing before anyone writes the next one.
