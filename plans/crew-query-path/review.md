# BL-13 — the crew query path: review (Stages 1–3)

Reviewed `e2e2164..5f73925` on `feature/bl13-crew-query-path` (four commits: `0986caf`, `e95132b`,
`b63a006`, `5f73925`). Worktree HEAD was `e2e2164`, a strict ancestor of the named tip, tree clean —
fast-forwarded with `git merge --ff-only 5f73925`. All three input documents present and read in
full. Stages 4 and 5 are out of scope and their absence is not a finding.

### Review Summary

The plan is implemented as written, and more carefully than most. Decisions A, B, C, D and E all
hold against the code rather than against the log, and the two constants the plan permits are the
only two added. Both subprojects' gates were re-run here and match the reported figures exactly.
The three flagged deviations are each the right call. **One required fix**: the summary's
folded-class clause speaks a plural noun against a singular count, so a single truck is reported as
*"One trucks"*.

### Verification performed

- **Gates re-run in the worktree** (main checkout's venv binaries, cwd inside each subproject):
  audio-adapter `ruff format --check src tests` / `ruff check .` / `mypy src` / `pytest` →
  **255 passed, 1 skipped**. body-layer same sequence → **1595 passed, 4 xfailed**. Both match the
  log's figures; no drift and no reliance on the reported numbers.
- **`decay.py` untouched** — confirmed from `git diff --name-only`, not from the log's claim.
- **Decision D proven by grep, not by reading the comment**: `_callout_may_speak` appears in
  `src/belief/contacts.py` only (definition and its one push-path call) plus the explanatory
  comment at `crew_console.py:1852`. It is applied nowhere on the pull path.
- **Mutation checks.** Replacing the per-candidate air-defence recompute
  (`speech.py:883`, `dominant_op_class if (names_dominant or folded_dominant) else None`) with an
  unconditional `dominant_op_class` turns
  `test_render_report_summary_keeps_a_dominant_air_defence_class_when_the_clause_drops` red with
  exactly the reported symptom (`"Eight units, 11 o'clock through 2 o'clock, inside 2 kilometres,
  and one short range SAM, one medium range SAM, one triple A."` — the modal `OP_LRSAM` gone). The
  self-found defect and its regression test are both real. File restored and the suite re-run clean.
- **Wedge-table identity checked at the source**, not taken from the docstring:
  `perception/gaze.py:156` defines `SECTOR_WEDGE_DEG` as the same object as
  `_RELATIVE_SECTOR_WEDGE_DEG`, and `attention.project_relative_area` (`attention.py:228`) computes
  `(heading_true_deg + relative_center) % 360.0` — character-for-character what
  `_report_scope` does. `report left` and `scan left` genuinely cannot disagree.
- **Legacy-token reachability enumerated** (deviation 2): `report_all`, the eight
  `report_bearing_*`, the nine `report_clock_*` and `report_bearing_deg` are all still in
  `vocabulary.TOKENS`, so the STT bench corpus (`tools/stt_bench.py:359-361`, which iterates
  `TOKENS`/`PHRASES`) still prompts them; body-layer still dispatches them
  (`_CLOCK_REPORT_TOKENS`, `_BEARING_REPORT_TOKENS`, `DISPATCHED_COMMAND_TOKENS`); and
  `belief/brain_reply.py` and `belief/voice_commands.py` — the brain's structured replies and the
  typed-console path — still resolve them. Reverting the slot branch is therefore still a local
  change. See Observation 2 for the one part of that claim that is wrong.
- **Mirror tables tested literally on both sides** and not derived from the table they mirror
  (`test_crew_console.py:3471`, `:4162`; `audio-adapter/tests/test_vocabulary.py`). A drift fails a
  test.

### Required Fixes

1. **`body-layer/src/belief/speech.py:844-851` (and `:596`) — the folded class clause speaks a
   plural noun against a singular count.** When one class is in scope the count clause's unit word
   is replaced with `_OP_CLASS_DISPLAY_PLURAL`'s value unconditionally, including when the count is
   one. Measured, by calling `render_report_summary` directly over one `class`-level contact per
   display class:

   ```
   OP_TRUCK   -> "One trucks, at 2 o'clock, inside 2 kilometres."
   OP_SRSAM   -> "One short range SAMs, at 2 o'clock, inside 2 kilometres."
   OP_MRSAM   -> "One medium range SAMs, ..."
   OP_LRSAM   -> "One long range SAMs, ..."
   OP_SHIP    -> "One ships, ..."
   ```

   `:596`'s open-ended branch has the same defect without the fold: `"At least one units"`, and
   `"At least one trucks"` once folded.

   This is not cosmetic and not rare — a single believed contact is the most common scene a `report`
   will ever answer, and the pilot hears it through TTS. The module already holds everything needed
   to get it right: `_summary_count_clause` switches `unit`/`units` on the count two lines above,
   and `_summary_air_defence_clause` deliberately uses `_OP_CLASS_DISPLAY` (singular) for its
   `count == 1` branch — so the same function is already correct in one clause and wrong in the
   other. Use `_OP_CLASS_DISPLAY` when the spoken count is one, and make `:596`'s `units` agree
   with `total_lo`.

   **Why no test caught it.** Every existing fold test uses `OP_ARMORED` or `OP_INFANTRY`, whose
   plural display word equals the singular (`"armor"`, `"infantry"`), so
   `test_render_report_summary_collapses_a_single_hour` asserts `"One armor"` and passes
   incidentally. The fix should add the count-of-one case over a class whose plural actually
   inflects (`OP_TRUCK` is the obvious one), or the next class added will reintroduce it silently.

### The three flagged deviations — each judged

1. **`PHRASES["report"]` carrying five slotted bias phrasings instead of the bare verb — correct,
   and the fall-through is preserved.** `normalized_phrase_index` does raise on a collision, so the
   plan's literal reading could not import; and `PHRASES` is documented as a non-exhaustive
   recogniser-bias list, which is exactly what the five phrasings are. Fall-through verified two
   ways: `vocabulary.PHRASES["report_all"]` still holds `("report", "report contacts", "what do you
   see", "describe", "describe contacts")` and `"report"`/`"describe"` are absent from
   `PHRASES["report"]`, so a zero-slot utterance never reaches the slot branch's return;
   `test_zero_slot_report_still_falls_through_to_report_all` covers all five phrasings. Body-layer
   also answers a zero-slot `report` defensively (`test_slotted_report_with_no_slots_answers_the_
   whole_scene`), which is the right posture for a token arriving over JSON.
2. **The behaviour change to `report east` / `report three o'clock` — unavoidable, correctly
   scoped, and the legacy tokens are genuinely still reachable.** See the enumeration above. The
   change is inherent to putting the slot branch in front of the phrase table, which is what makes
   `report left` work at all, so it is the plan's own consequence rather than drift. The branch
   order is pinned in the source, not only in outcomes
   (`test_follow_branch_is_tried_before_the_report_branch` asserts
   `source.index("_parse_follow_slots(text)") < source.index("_parse_report_slots(text)")`), which
   is the right way to pin an ordering a comment claims is load-bearing.
3. **The six rewritten body-layer tests — this did not cross `AGENTS.md`'s escalation line, and I
   say so plainly.** The rule covers tests that *must be rewritten rather than extended*; here the
   command's output contract changed by the plan's own Decision C, which the user chose in his own
   words, so no amount of extension could have preserved the old expectations. More importantly,
   each rewrite keeps a real property rather than recording the new string:
   - `test_report_all_summarises_rather_than_truncating_multiple_contacts` keeps the reason the
     original existed (the seam driven end to end through the real dispatch over four contacts of
     four classes at four ranges) and adds the property that replaces truncation — *nothing was
     dropped for want of room*, asserted as `"and more" not in lines[0]` plus the count of four
     reaching the answer.
   - `test_report_speaks_a_persisted_group_as_one_counted_answer` keeps "every in-scope contact
     accounted for exactly once" and **additionally** asserts that
     `render_group_full_disclosure` still speaks the full roster, so "the pull path changed" cannot
     be mistaken for "the group renderer broke". That is stronger than what it replaced.
   - `test_report_speaks_an_already_spoken_group_in_full` still arms the gate it is about
     (`render_group_disclosure` is shown to go silent on the second call) before asserting the pull
     path answers anyway. The docstring is honest that the claim now holds by a different
     mechanism. This one is the Decision D guard and is worth keeping exactly as written.

   No rewrite here is a test bent to match the code.

### Plan constraints — all verified

- **No second constant.** `CALLOUT_GROUP_CLOCK_SPAN_HOURS` is imported and used for the ±1-hour
  span (`crew_console.py:2037`); `perception.gaze`'s wedge table is used for `relative`;
  `decay.OBSERVED_WINDOW_S` is imported and passed through for freshness, and `decay.py` is
  untouched. The only new constants are `_REPORT_BAND_BOUNDS_M`'s 2 000/5 000 and
  `REPORT_SUMMARY_MAX_WORDS`. `_REPORT_BAND_LABELS` is derived from the bounds rather than written
  out, so the spoken number and the filtered number cannot drift — a good call the plan did not ask
  for.
- **Q1 (band filters, not sorts)** — `band_bounds` is a `continue` in `_report_scope`, with a
  lower-inclusive boundary test.
- **Q2 (air defence always named)** — `_summary_air_defence_clause` is appended in every budget
  candidate and survives both drops; the per-candidate recompute (mutation-verified above) is what
  makes that true when the dominant-class clause is the thing dropped.
- **Decision E seam** — no new cross-subproject import; the slots arrive as `{token, slots}` and
  every one is validated against the table that owns its values on this side, dropping an
  unrecognised value rather than refusing. Both mirror pairs are tested on each side literally.
- **Word budget** — 25 words, drop order deferral-then-class, with the final candidate spoken even
  if it overruns. Tests cover both drops.

### Observations (optional)

1. **`crew_console.py:1835` names a mechanism the code does not use.** The docstring says `relative`
   resolves through "`perception.gaze._RELATIVE_SECTOR_WEDGE_DEG` via `belief.attention`'s
   re-export"; the import at `:166` is `from perception.gaze import RELATIVE_SECTORS,
   SECTOR_WEDGE_DEG`, i.e. the public alias, direct, with `belief.attention` not involved. The
   conclusion survives (`SECTOR_WEDGE_DEG` *is* `_RELATIVE_SECTOR_WEDGE_DEG`, same object), so this
   is a wrong reason attached to a true claim rather than a defect. Worth one line's correction,
   because the next reader may go looking for an `attention` re-export that is not there.
2. **The `LEGACY_F10_TOKENS` justification for retaining the legacy report tokens is false**, in
   `vocabulary.py:157-158` and inherited verbatim from the plan's Decision A. `LEGACY_F10_TOKENS`
   contains the seventeen scan/watch/cancel tokens and **no** `report_*` token — it never did, so
   the legacy report families are not reachable from the F10 menu and are not "referenced by
   `LEGACY_F10_TOKENS` ordering". The retention decision is unaffected: the bench corpus,
   body-layer dispatch, `brain_reply.py` and `voice_commands.py` each independently justify it. Drop
   the F10 clause.
3. **A stale inline comment inside the rewritten truncation test.**
   `test_crew_console.py:3306-3315` still ends *"so this test is naturally about `group_facts`'s
   report-space bucketing and `REPORT_MAX_GROUPS` truncation alone, as intended"* — which the
   test's own new docstring, eighty lines above, explains is no longer what the test is about. The
   cohesion-backstop arithmetic in the same comment is still correct and worth keeping.
4. **The revert instruction does not mention the leak it would reintroduce.** `_render_report_lines`'
   docstring documents the group-roster leak thoroughly, and that is where a reverter would end up —
   but the comment at the pull site (`crew_console.py:1910-1918`), which is the thing a reverter
   reads *first* and which says reverting "is this one call site", does not say that a filtered
   query reverted to the enumeration will speak out-of-scope group-mates. One clause there would
   close the loop. The implementation log's stronger statement ("do not merge Stage 2 on its own")
   lives only in the log.
5. **`REPORT_SUMMARY_MAX_WORDS`' docstring says ~10.6 s** where the plan says 24 words ≈ 10.2 s.
   Harmless, and the constant is 25 either way.

### Out-of-scope findings — confirmed, refuted, and one that should be filed

1. **`speech._is_air_defence` does not recognise a class-level SAM — CONFIRMED.** Measured:
   `object_model.profile_for("OP_SRSAM")` and `profile_for("OP_LRSAM")` both return
   `OP_GROUPSOMETHING`, the default bucket, while `profile_for("SA-6 Kub LN")` correctly returns
   `OP_MRSAM`. Its two callers (`speech.py:2281`, `:2299`) compute `is_air_defence_repeat`, so a
   belief held only at `class` level loses the air-defence repeat treatment on the push path.
   Pre-existing, correctly left alone here, and the right size for a **body-layer backlog item**
   rather than a note — it is a silent no-omniscience-adjacent gap on the path that warns the pilot
   about the thing the project says matters most.
2. **`parent_class_of("ZSU-23-4")` is `None` — CONFIRMED**, while `parent_class_of("ZSU-23-4
   Shilka")` resolves to `OP_SPAAG`. The bare designation is a fixture-authored string and the DCS
   type name carries the suffix, so nothing in the live path is known to be affected. Low severity;
   a note is enough unless a sortie log ever shows the bare form arriving.
3. **"`belief.groups` cohesion is erratic at these fixture scales" — REFUTED as erratic, and the
   real behaviour is worse than the word suggests.** It is deterministic and traceable to
   `_OP_CLASS_COHESION_BACKSTOP`: `OP_INFANTRY` is `EAGER`, which drops the absolute backstop to
   `math.inf` for a pair where **either** member is infantry. Measured, same clock, `_three_banded_
   contacts`-style fixtures:

   ```
   armor@1km + truck@3km                  -> 0 groups
   armor@1km + truck@3km + ship@7km       -> 0 groups
   armor@1km + infantry@3km               -> 1 group of 2
   armor@1km + infantry@7km               -> 1 group of 2   (6 km apart)
   armor@1km + truck@3km + infantry@7km   -> 1 group of 3
   ```

   So **an infantry contact acts as an unbounded bridge that merges non-infantry contacts** —
   a tank and a truck 2 km apart, which do not cohere on their own, become one group because an
   infantry contact 6 km further out is also in scope. The user's direction behind `EAGER` was
   *"ok to merge infantry too eagerly"*; merging armour into infantry's group across 6 km is
   broader than that sentence grants, and it affects the live push path's
   `render_group_full_disclosure` today, not just fixtures. **Worth filing as a body-layer backlog
   item**, with these five measurements. Nothing in this diff caused it, and Stage 3's summary is
   immune (it aggregates the filtered set), which is itself a point in Decision C's favour.

### Verdict

**CHANGES REQUIRED** — one required fix (the singular/plural fold at `speech.py:844-851` and
`:596`), plus the test case over a class whose plural inflects. Everything else above is optional.

Nothing here claims the feature "runs": no agent can reach a live DCS session. What is covered is
the matcher, the slot validation, the five filters, the summary wording and both seams, by
**255** audio-adapter and **1595** body-layer tests. The pilot's acceptance step is a sortie on
**`feature/bl13-crew-query-path`** — the D13 answer shape (*"About eight units, mostly infantry,
1 o'clock through 2 o'clock, inside 2 kilometres. Still checking the truck group."*) is the thing
only he can judge, together with whether 25 words is too long in a hover (plan Q3, still open).

### Review Confidence

**Full read.** Every changed source line read; both gates re-run from the worktree rather than
trusted; four claims (the air-defence regression, the wedge-table identity, legacy-token
reachability, and all three out-of-scope findings) re-established by mutation, grep or direct
measurement rather than from the implementation log.

---

# Round 2 — review of the fix

Reviewed `44cb1db..417cce6` (one commit, `417cce6` *"Make the report summary's count clause agree
with its own number"*). Worktree HEAD was `e2e2164`, a strict ancestor of the named tip, tree clean
— fast-forwarded with `git merge --ff-only 417cce6`. All three input documents present and read in
full. Stages 4 and 5 still absent, still not a finding.

### Review Summary

**The required fix is correct, and the round is stronger than the fix it was asked for.** The third
noun site it reports is real, the enumeration it claims is complete for the unit it scopes itself
to, and the guard is genuinely derived from the display tables rather than hand-written — I broke it
in both directions to be sure. Both gates re-run here match the reported figures exactly, the +9 are
exactly the nine new cases, and nothing was weakened or deleted. **No required fixes.** One optional
finding is a measured falsehood in a comment the fix itself added; the decision that comment defends
is nonetheless the right one.

### Verification performed

- **Both gates re-run in the worktree** (main checkout's venv binaries, cwd inside each subproject,
  `src tests` form). audio-adapter: format/lint clean, mypy 15 files clean, **255 passed, 1
  skipped**. body-layer: format/lint clean, mypy 54 files clean, **1604 passed, 4 xfailed**. Both
  match the reported figures.
- **The +9 are exactly the new cases.** `pytest --collect-only` lists
  `test_singular_fold_openings_cover_every_inflecting_display_class`, six parametrised
  `..._speaks_a_singular_noun_for_a_count_of_one[...]` cases, `..._on_an_open_ended_count` and
  `..._on_a_hedged_count_of_one` — nine, against a 1595 baseline. `git diff --numstat` on the test
  files is `105/0` for `test_speech.py` (pure addition; no existing test touched, no assertion
  weakened, nothing deleted) and `6/3` for `test_crew_console.py`, whose three removed lines are the
  stale comment clause observation 3 asked for. `audio-adapter/tests` untouched. **The six earlier
  rewrites are exactly as round 1 left them.**
- **Both reported counterfactuals reproduced, not accepted.** `speech.py` copied out and restored
  by `shasum` (`632529fd…`) each time:

  | perturbation | my result | reported |
  |---|---|---|
  | `_unit_word` forced to `return "units"` | **3 failed, 136 passed** | 3 / 136 |
  | fold forced back to `display = plural` | **6 failed, 133 passed** | 6 / 133 |

  `test_render_report_summary_collapses_a_single_hour` passed under **both**, which is round 1's
  claim about its `"One armor"` reproduced rather than taken on trust.
- **Every one of the nine new cases is defended by a mutation**, not just the set: the five
  inflecting fold cases by the second perturbation, the `OP_GROUPSOMETHING` case and the hedged case
  by the first, the open-ended case by both, and the cover test by the two below.
- **The derivation is real, checked in both directions** — a set-level equality can pass while no
  individual entry is pinned, so I mutated per entry:
  - dropping `"OP_SHIP": "One ship"` from `_SINGULAR_FOLD_OPENINGS` → **1 failed**
    (`..._cover_every_inflecting_display_class`), so each entry is held by something;
  - adding `"OP_FAKE": "widget"/"widgets"` to the two display tables → **1 failed**, same test, with
    the suite otherwise green. So a class added to the object model later genuinely fails a
    membership test instead of escaping the guard. `_INFLECTING_OP_CLASSES` is a comprehension over
    `_OP_CLASS_DISPLAY.items()` comparing `_OP_CLASS_DISPLAY_PLURAL[op_class]`, and it resolves to
    exactly the six classes named.
- **`OP_GROUPSOMETHING` carrying `"One unit"` is right, and the case is not vacuous.** Measured:
  `parent_class_of("OP_GROUPSOMETHING")` is `None` (while `parent_class_of("OP_TRUCK")` is
  `OP_TRUCK`), so `_summary_op_class` filters it before the fold and the generic noun is correct.
  It is also the one fold-table case that goes red under the `_unit_word` perturbation — so naming
  it rather than filtering it out of the set bought a real assertion, not a placeholder.
- **The enumeration claim is complete for the unit it scopes.** `_unit_word`'s docstring says *"all
  three of `_summary_count_clause`'s branches"*; that function has exactly three `return`s and all
  three go through `_unit_word`. The other `"unit"` literals in the module (`:1132`–`:1150`) belong
  to the per-contact bearing-line noun, a different renderer, and are correctly outside the claim.
- **Q2's air-defence recompute is intact and unweakened** — the per-candidate
  `dominant_op_class if (names_dominant or folded_dominant) else None` and its comment are
  character-for-character what round 1 mutation-verified, and its test is in the untouched 105/0
  file. `folded_dominant` is still set on exactly the same condition: the restructure moved it
  inside `if display:`, and `display` is falsy only when the class is absent from *both* display
  tables, which the exhaustiveness test (`test_speech.py:1607-1611`) forbids.
- **Decision D intact** — `_callout_may_speak` appears in `contacts.py` (definition, one push-path
  call, one docstring) plus `crew_console.py:1856`'s explanatory comment. Never on the pull path.
- **The restructured conditional has exactly one behavioural delta beyond the fix, and it is
  unreachable.** The old `if plural:` guarded both arms; the new form enters the fold arm even when
  `plural` is `None`, which at a count of one now folds through `_OP_CLASS_DISPLAY` instead of doing
  nothing. That needs a class present in the singular table and absent from the plural one, which
  the exhaustiveness test forbids — and the new behaviour would be the better one anyway.
- **Optional correction 1 (the wedge table) is right, including the part that corrects round 1.**
  `attention.py:78` imports `_RELATIVE_SECTOR_WEDGE_DEG` for its own use (its only `as`-re-export is
  `RelativeSector`); `gaze.py:156` binds the public alias to that same object; `crew_console.py:166`
  imports it directly. There is no `belief.attention` re-export, so *identity* is the correct word
  and round 1's "same object" conclusion stood on a mechanism that does not exist.
- **Optional correction 2 (the legacy tokens) verified at the source.** `LEGACY_F10_TOKENS` holds
  seventeen `scan_*`/`watch_*`/`cancel_*` entries and no `report_*`. `stt_bench.py:356-362`'s
  `_print_prompts` does iterate `TOKENS` and index `PHRASES[token]`, so `TOKENS` membership is the
  right consumer to name.
- **Optional correction 4 (the revert note) is accurate** — the leak it now names is the one
  `_render_report_lines`' own docstring measures at `crew_console.py:2090-2091` (*"Armor, truck and
  infantry"* for a 1/3/7 km group). `render_report`, `REPORT_MAX_GROUPS` and `_render_report_lines`
  are all still present and still unreached by the pull path.
- **Scope.** `decay.py` untouched; `belief/groups.py` and `speech._is_air_defence` absent from the
  diff (0 hits); no new constant; no `TODO`/`FIXME`/`print(`/`breakpoint` added anywhere. The
  implementer's `MEMORY.md` edit is an append plus an extension of its own existing entry — no
  wholesale rewrite.
- Tree clean after every mutation; `git status --porcelain` empty.

### Required Fixes

**None.**

### Optional Refinements

1. **`speech.py:893-896`'s comment gives a reason that is false in both of its halves — measured.**
   It reads: *"'mostly' is a claim about a mix, which needs at least one unclassified contact
   alongside the classified ones, so the count is never one."* Both clauses are wrong:

   ```
   truck(0,1) + unclassified(0,1) -> "About one unit, mostly trucks, at 2 o'clock, ..."
   truck(1,1) + ship(1,1)         -> "Two units, mostly ships, at 2 o'clock, ..."
   truck(0,1) + ship(0,1)         -> "About one unit, mostly ships, at 2 o'clock, ..."
   ```

   The second case fires the hedge with **no unclassified contact at all** (two classified contacts
   of different classes defeat `single_class`), and the first and third speak a count of **one**
   beside the plural hedge. **The decision the comment defends is still correct** — the hedge
   describes a mix of at least two contacts, and `"mostly truck"` would read worse than
   `"mostly trucks"` whatever the midpoint says — so this is a wrong reason attached to a right
   call, exactly the shape of round 1's observation 1, and optional on the same grounds. Worth
   fixing because it asserts a reachable state is unreachable, in new code, and the implementation
   log repeats it.

2. **`perception/gaze.py:303` still asserts the `belief.attention` re-export that correction 1 just
   established does not exist** (*"would ripple through `_RELATIVE_SECTOR_WEDGE_DEG`/`belief.
   attention`'s re-export/the label tables"*). Pre-existing and outside this diff, so not a
   regression — but it is now the only surviving assertion of a mechanism this round went to the
   trouble of disproving, and it is the next place a reader goes hunting. One word.

3. **The hedged-count-of-one case is a renderer-contract case, not a live-reachable one today, and
   saying so would save a future reader a sortie-log hunt.** `_unit_word`'s docstring and the new
   test both say *"reachable when a `cardinality` interval's `lo` is zero"*. True of
   `render_report_summary`' dict contract; not true of the current belief path, because the only
   `lo == 0` bucket in `cardinality.py` is `UNKNOWN`, which is `(0, inf)` and therefore lands in the
   open-ended branch, never the midpoint. Defending the contract is the right call for a public
   renderer — this is a one-clause clarification, not a reason to drop the test.

4. **Pre-existing, one line:** `vocabulary.py`'s module docstring still calls `LEGACY_F10_TOKENS`
   *"the 15 that happen to coincide with the F10 menu today"* while the tuple holds seventeen. Not
   this diff's doing; noticed while verifying correction 2.

### Verdict

**APPROVED.** No required fixes. All four optional items above are genuinely optional — none
changes behaviour, and item 1 is a comment whose conclusion is right.

Next steps are Security and Performance Reviewer, then DoD.

As in round 1, nothing here claims the feature "runs" — no agent can reach a live DCS session. What
is covered is the matcher, the slot validation, the five filters, the summary wording (now including
singular agreement across every display class whose plural inflects) and both seams, by **255**
audio-adapter and **1604** body-layer tests. The pilot's acceptance step is a sortie on
**`feature/bl13-crew-query-path`**: the D13 answer shape, and plan Q3 (whether 25 words is too long
in a hover) which is still open.

### Review Confidence

**Full read.** Every changed line of the round-2 diff read. Both gates re-run from the worktree
rather than trusted; both reported counterfactuals reproduced; the guard's derivation broken in two
directions and each of the nine new cases tied to a mutation that fails it; all five optional-claim
corrections re-established at the source; and the one finding above measured by running the renderer
rather than by reading it.

---

# Round 3 — Reviewer on the fix for the Security deep analysis's required finding

Diff under review: **`6ec99f1..153efc0`**, one commit (*"Speak freshness for a stale SAM, not only
when everything is stale"*) on `feature/bl13-crew-query-path`. Worktree HEAD was `e2e2164` (stale, as
assumed), a strict ancestor; fast-forwarded to `153efc0` and verified by `git rev-parse`. All five
input documents present and read in full. Rounds 1–2 (`a44401e`) and the two report documents
(`985978b`, `6ec99f1`) were not re-reviewed.

The whole round-3 diff is **purely additive — 612 insertions, zero deletions anywhere**, which
settles most of the regression list mechanically rather than by inspection.

### Review Summary

`plans/crew-query-path/security.md`'s required fix 1 is **closed**, and closed in the shape the
user's decision calls for rather than the shape the finding suggested. The marker fires for a stale
air-defence contact in a mixed-staleness scene, survives both budget drops, names the oldest stale
air-defence contact, and states an age that is true at every age it can be spoken at. The two
divergences from the brief (its own named subject instead of an apposition; the rounded-minute rung
instead of the user's literal phrase) are both correct, and both were flagged by the implementer
rather than buried.

**Claims verified independently, not read:**

1. **The marker fires on the finding's own scene and is non-droppable.** Reproduced: the
   1-fresh-plus-3-stale scene renders *"About twelve units, 1 o'clock through 4 o'clock, inside 2
   kilometres, and one short range SAM, one long range SAM. The air defence is a couple minutes
   old."* with `"Still checking"` and `"mostly"` both absent — i.e. after both drops fired.
   Non-droppability proven by **mutation, not by reading the call site**: gating the append behind
   `with_deferral` (counterfactual 3, the one that matters) gives **5 failed, 1606 passed**,
   including the security-measured scene. The finding is reproduced by the perturbation and absent
   without it. `shasum src/belief/speech.py` = `fd36e5a6…` before and after, byte-identical,
   `git status --porcelain` empty.
2. **The divergence from the brief is the right shape.** Confirmed at the source, not accepted:
   `_summary_air_defence_clause` skips an `op_class` equal to `dominant_op_class`
   (`speech.py:726`), so the clause genuinely is *absent* in the folded-dominant case — the
   `"Two short range SAMs, at 2 o'clock, inside 2 kilometres."` scene has nothing to hang an
   apposition on, and the new test covers exactly that. And the clause enumerates every in-scope
   air-defence tier including fresh ones, so an apposition on it would hedge a contact seen a second
   ago. Naming its own subject is correct. "Appended in every budget candidate" does make it
   non-droppable — the loop is `((True, True), (False, True), (False, False))` and the append sits
   above the `with_deferral` guard in all three.
3. **The age phrase is true at every reachable age, and no constant was added.** Brute-forced
   `_spoken_age_phrase` over the whole reachable range (16.1 s → 160 s at 0.1 s steps) against the
   real `decay` values (`OBSERVED_WINDOW_S` = 16.0, `LOST_THRESHOLD_S` = 120.0): rungs flip at
   **30.1 s** (→ *"about a minute old"*), **90.0 s** (→ *"a couple minutes old"*) and **150.1 s**
   (unreachable from the pull path). No rung states a false age; the user's own phrase is preserved
   on 90–120 s, which is the band he spoke it about. The function introduces **no named constant** —
   only `round(ago_s / 60.0)` — and `decay.py` is absent from the diff.
   It also cannot speak a floor-value age: `_is_stale` returns `False` for a non-numeric
   `last_seen_ago_s`, so `oldest_ago_s` can never still be its `0.0` initialiser when `op_classes`
   is non-empty. The `isinstance` re-check inside the loop is therefore redundant but harmless.
4. **It names the oldest, not `stale[0]`.** `oldest_ago_s = max(...)` over the stale air-defence
   subset, with a test that would say *"under a minute old"* if it under-claimed. The deferral
   clause's `stale[0]` is untouched and still arbitrary — correctly out of scope, since it is no
   longer load-bearing as a freshness signal.
5. **Counterfactual 1 re-run as well as 3**, because a selectivity guard that no test defends is a
   comment: dropping the `AIR_DEFENSE_OP_CLASSES` membership test gives **3 failed**, and the
   accepted-trade test is one of them, red for the stated reason. So the trade is asserted as an
   intention, not left implicit.
6. **`BL-B47` does not reach the pull path — confirmed at the source, not from the report.**
   Measured in the reviewed tree: `classification.parent_class_of("OP_SRSAM")` → `"OP_SRSAM"`, while
   `object_model.profile_for("OP_SRSAM").op_class` → `"OP_GROUPSOMETHING"`. The new clause goes
   through `_summary_op_class` (the lattice walk), so a `class`-level SAM belief *is* recognised;
   a marker built on `_is_air_defence` would have been silently dead in the one scene it exists for.
   `_is_air_defence` is untouched by the diff. This was the most consequential thing to check and it
   holds.

**Nothing regressed.** Zero deletions in the diff is the proof for most of it: `decay.py`,
`belief/groups.py` and `speech._is_air_defence` are absent from the diff; Decision D's
`_callout_may_speak` exclusion, Q1's band filter, Q2's mutation-verified air-defence regression and
both mirror-pair membership tests are byte-unchanged; `render_report`/`REPORT_MAX_GROUPS` still
present and unused; Stage 4/5 absent. **Zero existing tests modified** — confirmed mechanically
(`git diff --numstat` shows `246 0` on `tests/test_speech.py`), so rounds 1–2's cases are exactly as
I left them.

**Checks re-run in the worktree** with the root checkout's venv binaries, cwd inside each
subproject: body-layer `ruff format --check` (118 files), `ruff check`, `mypy src` (54 files) all
clean, **1611 passed / 4 xfailed**; audio-adapter `ruff check`, `mypy src` (15 files) clean,
**255 passed / 1 skipped**. The **+7** is exactly the seven new cases: the diff adds 7 `def test_`
and removes none, and the one that loops asserts three ages inside a single case.

**Performance constraint honoured.** The clause is computed once before `_assemble`, not per
candidate, and is one extra O(n) pass. Measured directly at the sortie's 52-contact scale:
**11 µs**, against `performance.md`'s 0.034 ms/query for everything BL-13 added and the 352 ms of
pre-existing warm-cache enrichment the same poll body already pays. Nothing per-contact is added
beyond that pass, and nothing new reaches the per-poll push path.

**Plan Decision D's new note is accurate and does not overstate.** Every factual claim in it checks
out (the 120 s/16 s asymmetry, the all-stale-only firing, the quote verbatim, the never-dropped
placement, the unchanged prefix). It says plainly that some stale belief is now spoken as present
tense *as an accepted trade*, which is what a later reader needs in order to tell a decision from a
defect, and it is explicit that *"or otherwise decision-relevant"* is left unbuilt rather than
implying the user scoped it to air defence alone. `implementation.md` Discovery 15 carries the one
candidate (a moving contact, four `POSITION_HALF_LIFE_S` old) to the user as a question. Correct
handling.

### Required Fixes

None.

### Judgement for the record — 28 words against a 25-word budget, and two never-dropped clauses

**Acceptable as it stands.** Confirmed by measurement: the finding's scene renders at **28 words**
and the simpler fresh-infantry-plus-stale-LRSAM scene at exactly **25**. The overrun is 3 words, in
the final candidate, absorbed by the pre-existing *"a too-long pointer beats no answer"* floor that
round 1 already established and that is documented at the loop. The growth is bounded — both
never-dropped clauses are air-defence-driven, so the worst case is pointer + tier list + one marker,
with no unbounded path.

**What it implies if the budget is later halved** (plan Q3, still open with the user, and
`REPORT_SUMMARY_MAX_WORDS`'s own comment anticipating ~13): at 13 words the pointer alone — count,
direction, band — is already 11–13 words, and the marker is a further 7–8. Every stale-air-defence
answer would then overrun by roughly half, which means the constant would no longer be a budget on
the summary at all, only on its droppable tail. So halving is not a tuning change that can be
applied to this code as written; it forces a choice the user owns: a shorter marker form (an
apposition reopens the fresh-tier hedging problem this round correctly avoided), or redocumenting
the constant as a droppable-tail budget, or deciding which of pointer-versus-honesty yields in a
hover. **Recommend that paragraph be the input to Q3** rather than rediscovered by whoever lowers
the number. Not a fix now.

### Optional Refinements

- **The collective subject can over-claim staleness about a fresh tier.** With three distinct
  air-defence tiers in scope, two stale and one fresh, the marker falls through to *"The air defence
  is a couple minutes old."* — hedging the tier seen a second ago. Reachable but rare (it needs
  three tiers in one band-filtered query), and it errs in the **safe** direction: over-hedging costs
  a little precision, never the pilot's safety. Not worth a branch unless the user hears it.
  (optional)
- `OP_SPAAG` and `OP_ZU23` both display *"AAA"*, so one stale of each is two distinct `op_classes`
  and falls to *"The air defence is…"* where *"The AAA is…"* would read better. Cosmetic. (optional)
- The new Decision D note cites *"(Decision 6, Q2)"*. Q2 is local to this plan; "decision 6" is
  `plans/post-review-fixes/explore-notes.md` item 6 (air-defence classes as the exception), which is
  how `speech.py` cites its siblings elsewhere — but inside a plan whose own decisions are lettered
  A–E, a bare "Decision 6" sends a reader looking in the wrong file. One path would fix it.
  (optional)

### Verdict

**APPROVED.**

The Security deep analysis's one required finding is closed, verified by reproducing the finding
through mutation rather than by reading the fix. No required fixes. Next step is DoD.

As in rounds 1 and 2, nothing here claims the feature "runs" — no agent can reach a live DCS
session. What is covered is the matcher, the slot validation, the five filters, the summary wording
including the selective freshness marker, and both seams, by **255** audio-adapter and **1611**
body-layer tests. The pilot's acceptance step is a sortie on **`feature/bl13-crew-query-path`**:
the D13 answer shape, whether the marker reads naturally over the intercom, and plan Q3 (whether 25
words is too long in a hover) which is still open.

### Review Confidence

**Full read.** Every changed line of the round-3 diff read. Both gates re-run from the worktree
rather than trusted. Three of the implementer's claims re-established by running code rather than
reading it — counterfactuals 3 and 1 reproduced with the checksum confirmed byte-identical
afterwards, the age ladder brute-forced across its whole reachable range against the real `decay`
values, and the `parent_class_of`-versus-`profile_for` divergence measured in the reviewed tree. The
word counts and the clause's per-query cost are measured, not estimated.
