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
