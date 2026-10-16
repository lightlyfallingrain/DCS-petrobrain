### Implementation Summary

`BL-B70` — the attack-run guidance fixes from the 2026-10-15 sortie (§1, §2, §4, §8, §9, and §10/§11's
revision of §5's fallback phrasing, both pulled in from `main` mid-task). `BL-B71`'s optic ladder is
untouched, as scoped.

**Branch state note:** `main` advanced twice during this task (§10 "announce the transitions, not
every line" and §11 "the loss announcement keys on resolvability, not masking") — both pulled in by
fast-forward merge before implementing the affected behaviour, so the final design matches the
*current* acceptance doc, not the brief as originally dispatched.

#### The cause taxonomy (`belief.attack_run._no_look_cause`)

A new pure function, computed in `check_visibility`'s own gate order: `"masked"` (cockpit mask,
`cockpit_mask.is_visible` on the *true* body-relative direction, including bank — deliberately not
`decide`'s own bank-removed `alignment_direction` output, which would misjudge the mask during a
turn) → `"obstructed"` (`Contact.live_los_clear is False` and fresher than the new
`ATTACK_TARGET_LOS_MAX_AGE_S`) → `"too_far"` (range beyond the naked eye's own presence threshold,
`perception.visibility.tier_ranges` under `UNAIDED_OPTIC`) → `"unknown"` (fail-open default).

#### §1 — text-equality veto

`_should_emit` is now `return text != state.last_spoken_text` — the angular change-driven clause and
`ATTACK_RUN_CHANGE_THRESHOLD_DEG` are deleted entirely, not retuned. `AttackRunState.last_spoken_azimuth_deg`/
`last_spoken_elevation_deg` are removed with it (their only other reader, `crew_console.
drain_attack_run`'s speech-log fields, now reads two new fields, `current_azimuth_deg`/
`current_elevation_deg`, updated unconditionally every tick regardless of emit — see "Notable
discoveries" below for why this was necessary).

#### §2 — masked silence

`cause == "masked"` returns `(state, None)` before any speech is composed. The run stays engaged.
Per the Co-moving Fields rule, a masked tick touches `last_known_target_alt_m`/`current_azimuth_deg`/
`current_elevation_deg` (ordinary per-tick memory) but **not** `last_spoken_text`, `last_spoken_clock_hour`,
or `last_spoken_unresolved`.

#### §4 — twelve o'clock marker

New fields `AttackRunState.last_spoken_clock_hour: int | None` and a new public `belief.speech.
alignment_clock_hour(azimuth_deg) -> int | None` (the same sector test `render_alignment`/
`alignment_phrase` use internally, exported so `decide` can track the baseline against the identical
test). `announce_twelve` fires on *any* entry into the sector from the o'clock register (resolved
decision 1), rendered as a prefix on the same utterance via `render_alignment`'s new
`announce_twelve: bool` parameter — `"Twelve o'clock, come left."`, not a second utterance.

#### §8 — cause-keyed qualifier

`render_alignment`'s `tier: Literal[1, 2]` parameter is **removed** — it no longer knows about tiers
at all. In its place: `qualifier: str | None = None`, caller-supplied. `decide` sets it to
`", obstructed"` only when `tier == 2 and cause == "obstructed"`; `"unknown"` gets no qualifier.

#### §9 — attack-target LOS freshness + the §9 tripwire

New constant `perception.naked_eye_source.ATTACK_TARGET_LOS_MAX_AGE_S` (1.5 s, `tuning.real`,
`lo=0.5, hi=3.0`), used only inside `_no_look_cause`'s obstructed test (`now_sim - contact.
last_seen_sim <= ATTACK_TARGET_LOS_MAX_AGE_S`). No change to the join itself or to aircraft-layer, per
the plan's resolved decision 5.

The presence/skew tripwire (plan: "a per-poll presence/skew tripwire on the belief-truth row") is
implemented as a new `kind: "attack_run_los_tripwire"` row, written once per poll whenever an attack
run is active:

- `belief_truth_log.BeliefTruthLogWriter.write_poll` gained a keyword-only
  `attack_run_target_contact_id: str | None = None` and a new private method,
  `_write_attack_run_tripwire`, which looks the target up in this poll's `DetectionTraceCollector`
  (via the existing `observation_id_to_contact_id` join, read-only, no new coupling) and records
  `present_in_snapshot`/`join_skew_s` (`DetectionTrace.los_skew_s`)/`live_los_clear`.
- `logger.py`'s two `write_poll` call sites now pass
  `attack_run_target_contact_id=runner.attack_run_state.last_contact_id if runner.attack_run_state
  is not None else None` — no new state; `ConsolePerceptionRunner.attack_run_state` already carries
  this.

This is **a deviation from the plan's own Affected Modules table**, which did not list
`belief_truth_log.py`/`logger.py` for this item and assigned it to `crew_console.py` ("pass the
cause/age inputs through `drain_attack_run`... no logic"). On inspection, `crew_console.drain_attack_run`
has no path to `DetectionTraceCollector` at all — only `logger.py`'s poll loop does, at a different
point in the same poll — so the only way to implement a *per-poll* (not per-utterance) tripwire is to
thread it through `write_poll` instead. Flagging this rather than silently reassigning it.

#### §10/§11 — the four-state "losing sight"/"regaining sight" register (superseding the original
§5 fallback, pulled in from `main` mid-task)

Two new `belief.speech` templates, `render_attack_run_lost_sight(phrase, what, where, ago_s)` →
`"<Phrase> <what> <where>, last seen <age> ago."` and `render_attack_run_regained_sight(phrase)` →
`"Eyes on, <phrase>."`, plus `alignment_phrase` extracted from `render_alignment` as a standalone
bare-phrase function (lowercase, no terminal punctuation) so both the ordinary renderer and these two
transition templates share one source of "what would be said."

A new `_attack_run_last_seen_phrase(ago_s)` in `speech.py` supplies the coarse "a moment"/"a
minute"/"a couple of minutes"/"about N minutes" wording the user specified in §10 — **not**
`_spoken_age_phrase` reused verbatim, which already ends in `"old"` and would double up against this
caller's own trailing `"ago"` (`"last seen under a minute old ago"`).

New `AttackRunState.last_spoken_unresolved: bool` tracks whether `last_spoken_text` was produced
while `cause == "too_far"`. `decide` computes `now_unresolved = cause == "too_far"` and:

- `False -> True`: `render_attack_run_lost_sight` — full remembered-sighting claim, once.
- steady `True`: ordinary bare guidance, no appended clause (`qualifier=None`).
- `True -> False`: `render_attack_run_regained_sight` — `"Eyes on, ..."`, once.
- steady `False`: ordinary rendering (§4/§8 as usual).

**Per §11 (direction, user's own words — "the important question is whether Petrovich sees the
target when we turn to see what is happening"), this is keyed on `cause`, never on tier and never on
having been masked.** A `"masked"` tick leaves `last_spoken_unresolved` untouched (it returns before
reaching this logic at all), so a break that masks the target between two `"too_far"` ticks neither
re-announces the loss nor announces "eyes on" — pulling off target on every pass does not narrate a
loss once per pass. The condition is written against `cause == "too_far"` rather than `tier == 1`
specifically so a range closing while tier stays 2 (still no fresh relative percept, but no longer
too far) also correctly announces "eyes on" — not only a tier flip, which is the more literal reading
of "resolvable" the brief implied but the sortie data cannot exercise either way.

#### Co-moving Fields, all confirmed

- `last_spoken_text`: never written on a `MASKED` tick. ✓ (returns before the write)
- `last_spoken_clock_hour`: carried via `replace()`, resets to `None` on a re-point. ✓ (fresh
  `AttackRunState(last_contact_id=...)` defaults it)
- `last_spoken_unresolved`: same reset on re-point. ✓, and covered by
  `test_decide_retarget_resets_last_spoken_unresolved`.
- The fresh-construction trap (F4): `decide`'s emit path uses `replace(state, ...)`, not
  `AttackRunState(...)`, everywhere except the deliberate contact-re-point reset.

---

### Files Changed

- `body-layer/src/belief/attack_run.py` — cause taxonomy (`NoLookCause`, `_no_look_cause`); `_should_emit`
  reduced to a text-equality veto; `decide` rewritten around cause/tier/transition composition;
  `AttackRunState` gains `last_spoken_clock_hour`, `last_spoken_unresolved`, `current_azimuth_deg`,
  `current_elevation_deg`, loses `last_spoken_azimuth_deg`/`last_spoken_elevation_deg`;
  `ATTACK_RUN_CHANGE_THRESHOLD_DEG` removed.
- `body-layer/src/belief/speech.py` — `render_alignment` loses `tier`, gains `qualifier`/
  `announce_twelve`; new `alignment_phrase`, `alignment_clock_hour`, `render_attack_run_lost_sight`,
  `render_attack_run_regained_sight`, `_attack_run_last_seen_phrase`.
- `body-layer/src/perception/naked_eye_source.py` — new `ATTACK_TARGET_LOS_MAX_AGE_S` tuning constant.
- `body-layer/src/belief/crew_console.py` — `drain_attack_run`'s speech-log fields read `current_azimuth_deg`/
  `current_elevation_deg` instead of the removed `last_spoken_*` baseline fields.
- `body-layer/src/belief_truth_log.py` — `write_poll` gains `attack_run_target_contact_id`; new
  `_write_attack_run_tripwire` (§9).
- `body-layer/src/logger.py` — both `write_poll` call sites thread
  `runner.attack_run_state.last_contact_id` through.
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`): drops
  `ATTACK_RUN_CHANGE_THRESHOLD_DEG`, adds `ATTACK_TARGET_LOS_MAX_AGE_S`.
- `body-layer/tests/test_attack_run.py` — see "Tests rewritten" below.
- `body-layer/tests/test_belief_truth_log.py` — three new tests for the §9 tripwire.

---

### Tests Added / Rewritten

**Rewritten (required by the plan's own escalation flag — `ATTACK_RUN_CHANGE_THRESHOLD_DEG` ceases
to exist):**

- `test_decide_falls_through_to_tier_2_when_the_contact_has_no_percept` — expected text drops
  `", obstructed"` (no live LOS verdict ⇒ `"unknown"` cause, not `"obstructed"`).
- `test_decide_falls_through_to_tier_2_once_the_relative_observation_goes_stale` — same; the test now
  sets `contact.live_los_clear = False` with a fresh `last_seen_sim` to exercise a *genuine*
  `"obstructed"` cause, since under `"unknown"` the tier-1/tier-2 "A little lower." texts collide and
  the transition goes silent (a separate, deliberate test below covers that collapse).
  `test_decide_change_driven_cadence_resuppresses_unchanged_errors` — docstring only (describes the
  veto instead of the deleted threshold).
- `test_decide_tier_transition_speaks_the_qualifier_without_flipping_direction` and
  `test_decide_lined_up_tier_transition_speaks_once_each_way` — both now explicitly set
  `contact.live_los_clear = False` with a fresh `last_seen_sim` at each tier-2 step, to produce a
  genuine `"obstructed"` cause; without that the qualifier would not appear at all under the new
  rule.
- `test_tier2_azimuth_never_speaks_tier_1s_fine_grained_words`,
  `test_render_alignment_tier_2_appends_the_qualifier_outside_the_sector` (renamed
  `test_render_alignment_qualifier_appends_outside_the_sector`),
  `test_render_alignment_tier_2_appends_the_qualifier_to_the_direction_word` (renamed
  `..._qualifier_appends_to_the_direction_word`), `test_render_alignment_tier_2_elevation_word_is_unchanged_from_tier_1`,
  `test_render_alignment_tier_2_combines_both_axes_then_the_qualifier` (renamed `..._qualifier_combines_with_both_axes`),
  `test_render_alignment_tier_2_lined_up_speaks_the_qualifier_too` (renamed `..._lined_up_speaks_the_qualifier_too`),
  and the six plain tier-1 `render_alignment` tests — all updated to the new `qualifier=`/no-`tier=`
  signature.
- `test_last_spoken_tier_cannot_silently_carry_a_wrong_value_across_a_retarget` — **removed**, not
  merely edited. Its asserted property (tier-1 and tier-2 renders of the same angle can never collide
  as strings) is no longer true under a cause-keyed qualifier — the `"unknown"`-cause case can and
  does collide (`"Lined up."` both tiers). A comment at the old location explains why and points to
  its replacement fact, covered by the new test immediately below.
- `test_the_three_constants_are_unchanged_assumptions` → `test_the_two_constants_are_unchanged_assumptions`
  (drops the assertion on the removed constant).

**Added, new behaviour:**

- `test_no_look_cause_masked_behind_the_cockpit_mask`, `test_no_look_cause_obstructed_only_on_a_fresh_false_verdict`,
  `test_no_look_cause_too_far_beyond_naked_eye_presence_range` — the cause taxonomy itself, direct.
- `test_decide_lined_up_tier2_unknown_cause_collapses_the_transition` — pins the plan's own flagged
  Risk as a structural property: under `"unknown"`, tier 1 and tier 2 render identically, so the
  transition is silent, and `last_spoken_tier` goes stale harmlessly (nothing was spoken to update
  it).
- `test_decide_masked_tick_is_silent_and_run_stays_engaged`,
  `test_decide_masked_tick_never_moves_the_cadence_or_unresolved_baseline` — §2.
- `test_decide_losing_and_regaining_sight_keys_on_resolvability_not_masking` — §10/§11's own worked
  scenario: losing sight once, a masked break that neither re-announces nor silently resolves it,
  turning back in still too far (bare guidance, no re-announcement), then back in range ("eyes on,
  ...", once).
- `test_decide_losing_sight_where_phrase_reports_the_clock_hour` — the `<where>` clause.
- `test_decide_retarget_resets_last_spoken_unresolved` — the Co-moving Fields reset.
- `test_decide_announces_twelve_oclock_entering_from_the_oclock_register`,
  `test_decide_does_not_re_announce_twelve_oclock_while_steady_in_the_sector` — §4 through `decide`
  itself (the pre-existing `render_alignment`-level tests only exercised the renderer in isolation).
- `test_render_alignment_announce_twelve_prefixes_without_capitalizing_the_rest` — the renderer-level
  form.
- `test_write_poll_attack_run_tripwire_present_in_snapshot`,
  `test_write_poll_attack_run_tripwire_absent_from_snapshot`,
  `test_write_poll_no_attack_run_tripwire_row_without_a_target` — §9's tripwire, in
  `test_belief_truth_log.py`.

---

### Checks

(body-layer only; no other subproject touched)

- `ruff format --check .`: **fails only on the pre-existing out-of-scope
  `research/2026-10-05-security-audit.md`**, exactly as the brief predicted. All source/test files
  this task touched are formatted.
- `ruff check .`: pass.
- `mypy src`: pass — `Success: no issues found in 60 source files`.
- `pytest -q`: **2014 passed, 4 xfailed** (baseline was 2000 passed, 4 xfailed; net +14 from one
  removed test and ~18 added).

---

### Demonstration against the real sortie data

Source: `body-layer/logs/dcs-belief-truth-20261015-164451.jsonl` (the main checkout's own copy,
gitignored). The outbound attack-run utterances live in this file's `kind: "speech"` rows (not
`dcs-speech-*.jsonl`, which is the *inbound* voice-command transcript) — 125 rows, matching the
plan's own cited figure exactly.

**§1 — replaying the recorded `(text)` sequence through the new text-only veto** (each row's `text`
compared against the previous *emitted* row's `text`, which is exactly `_should_emit`'s new
definition):

```
125 old emissions -> 78 new emissions
suppressed: 47 (38%)
```

Matches the plan's own "47 of 125 byte-identical" figure exactly, confirming the new veto suppresses
precisely the lines the old disjunction let through only because the angle had drifted past 3° with
the word unchanged.

**§2 — replaying the recorded `(attack_run_azimuth_deg, attack_run_elevation_deg)` of every
`"obstructed"` line through the real `perception.cockpit_mask.is_visible`:**

```
66 'obstructed' calls -> 41 would be MASKED (silent) under the new cause taxonomy
remaining non-masked 'obstructed'-shaped calls: 25
```

**Caveat, stated rather than hidden:** the logged `attack_run_azimuth_deg`/`attack_run_elevation_deg`
are `attack_run._tier1_alignment`'s bank-removed axes (the pilot-control decomposition,
`alignment_direction`'s own docstring) — not the true body-relative direction `_no_look_cause`'s real
mask check uses (`body_relative_direction` with `ownship.bank_deg`). This is the same approximation
the plan's own §3/§8 investigation used, and `belief_truth_log.write_speech`'s docstring records the
same caveat for exactly this reason. It is a close approximation at the logged pitch/bank values,
not an exact replay — a literal replay would require reconstructing full `ContactStore`/ownship
state per poll, which is out of scope for this verification.

Of the 25 remaining, **none can be assumed to be genuinely `"obstructed"` under the new cause
taxonomy** — the historical capture has no real `live_los_clear=False` signal distinguishing them
from `"unknown"` (the old code said `", obstructed"` for *every* non-masked tier-2 tick regardless of
cause, which is the defect §8 fixes). The honest claim this data supports is only: two-thirds of the
historical `"obstructed"` calls were rear-aspect and are now silent (§2); the remaining third's actual
distribution across `"obstructed"`/`"too_far"`/`"unknown"` needs a fresh sortie with real LOS data to
measure, not this log.

---

### Notable Discoveries

- **The plan's own claim "`AttackRunState.last_spoken_azimuth_deg`/`last_spoken_elevation_deg`...
  are not read anywhere else" was wrong** — `crew_console.drain_attack_run`'s `attack_run_fields`
  dict was a second reader, for the speech log's `attack_run_azimuth_deg`/`attack_run_elevation_deg`
  fields. Removing the fields outright would have silently broken that logging. Fixed by adding two
  new fields, `current_azimuth_deg`/`current_elevation_deg`, updated unconditionally every tick
  (mirroring `last_known_target_alt_m`'s own "memory, not a speech baseline" pattern) rather than
  reviving the removed cadence-baseline fields under a different name.
- **§10/§11 arrived as two separate mid-task supersessions of the brief**, both via `main` fast-
  forward merges, both confirmed to align with the design already in progress rather than requiring
  rework: §10 replaced the per-line age-phrase qualifier with the four-state transition register;
  §11 confirmed the register should key on `cause == "too_far"` rather than on having been masked,
  which is exactly how `last_spoken_unresolved` was already wired (the masked-tick early return
  never reaches the transition logic at all).
- **The §9 tripwire's true home differs from the plan's Affected Modules table** — see "§9" above.
  `crew_console.py` has no access to `DetectionTraceCollector`; only `logger.py`'s poll loop does.
- **Cross-key coupling to flag, per the role's own guidance**: `ATTACK_TARGET_LOS_MAX_AGE_S` (1.5 s,
  `hi=3.0`) is conceptually bounded by `LOS_MAX_AGE_S` (3.0 s, the join tolerance) — a future retune
  of either in isolation could set the attack-target bound *looser* than the general join tolerance,
  which would be incoherent (a verdict the join itself would have discarded as too stale still being
  treated as fresh for the one contact that matters most). Not asserted in code (per-key bounds
  already exist on each; a cross-key assertion was judged out of scope for this fix), but worth a
  reviewer's eye if either constant moves.
- **`profile_for("OP_ARMORED")` does not resolve to the armor keyword table** — `profile_for` matches
  on DCS *type* strings (e.g. `"BMP-2"`), not `OP_*` class strings, so every test fixture's
  `classification_raw="OP_ARMORED"` resolves to the default profile (5 m size, ~1667 m naked-eye
  presence range under `UNAIDED_OPTIC`), not the 7 m/~2.3 km figures the plan's own prose cites from
  the real sortie's actual DCS unit type. This did not affect correctness (the taxonomy is keyed on
  the *actual* profile regardless of which one fires), but it means the `_no_look_cause` tests had to
  be positioned at 1000 m ("near")/2000 m ("far") rather than the plan's own 2.3 km figure, which is
  specific to a real 7 m vehicle's keyword-matched profile, not the default one these fixtures get.

---

### Fix pass: `plans/attack-run-sortie-fixes/review.md`'s two required findings (2026-10-15)

Both required fixes from the review, nothing else. `BL-B71`'s optic ladder confirmed still untouched.

**Required fix 1 — `_no_look_cause`'s gate order.** Swapped the range/size check (`"too_far"`)
to run *before* the terrain-LOS check (`"obstructed"`), matching `check_visibility`'s real order
(`visibility.py:997-1023`: mask → optic FOV → range/size gate 3 → terrain LOS gate 4 → forest).
Updated the module docstring, `_no_look_cause`'s own docstring, and
`test_no_look_cause_too_far_beyond_naked_eye_presence_range`'s docstring, all of which previously
asserted a mirroring the code did not have.

Added `test_no_look_cause_too_far_wins_over_a_fresh_obstructed_verdict` — a contact that is
simultaneously (fresh `live_los_clear=False`, beyond presence range) must report `"too_far"`.
**Mutation proof, by hand**: swapped the two checks back to the wrong order (`shasum` of
`attack_run.py` recorded before and after), re-ran — the new test failed with
`AssertionError: assert 'obstructed' == 'too_far'`, for exactly the stated reason; restored the
file and confirmed the checksum matched the pre-mutation value and all 4 `no_look_cause` tests
passed again.

**Required fix 2 — the `<where>` clause's digit/word mismatch and duplication.** Read: the review
offered two options — "word the hour" (minimal mechanical fix) or "suppress `<where>` when it
would restate `phrase`" (design question). **Took the second, which subsumes the first**: when
`alignment_clock_hour(azimuth_deg)` is not `None` (outside the 12 o'clock sector), `phrase` is
itself a worded clock-hour phrase (`"Three o'clock"`) and `<where>` is now suppressed entirely
(`where=None`) rather than worded — there is no digit left to mismatch, because there is no
separate `<where>` token at all in that case. When inside the sector, `phrase` is a qualitative
word (`"come left"`/`"lined up"`) carrying no position, so `<where>` still renders as `"ahead"`,
unchanged from before. `render_attack_run_lost_sight(phrase, what, where, ago_s)`'s `where`
parameter is now `str | None`; `None` omits the clause from the composed sentence rather than
rendering an empty or malformed one.

Rewrote the test that pinned the old defective string
(`test_decide_losing_sight_where_phrase_reports_the_clock_hour` →
`test_decide_losing_sight_where_suppressed_when_it_restates_the_clock_hour`, asserting
`"Three o'clock armor, last seen..."` and that `"3 o'clock"` is absent) and added
`test_decide_losing_sight_where_phrase_kept_in_the_qualitative_register` to pin the unchanged
`"ahead"` case (`"Lined up armor ahead, last seen..."`), so the two registers' different outcomes
are both covered rather than only the one the review flagged.

**On `Contact.live_los_clear`'s reachability (not in scope, reported per the brief).** Traced the
only two writers of `Contact.live_los_clear` (`contacts.py:676`/`751`, both an unconditional
overwrite from `Percept.live_los_clear`) back through `belief/percept.py:191` (a straight
passthrough of `Observation.live_los_clear`) to `naked_eye_source.py`. There,
`live_los_clear_by_object_id` (line ~775) is built only from the `visible` list — candidates for
which `check_visibility` returned non-`None` — and gate 4 (`visibility.py:1023`,
`if not candidate.live_los_clear: return None`) is fail-closed with no emitter bypass (the
bypass covers gates 3 and 5 only), so every member of `visible` already has
`candidate.live_los_clear is True` by construction. The per-cluster fold at line ~1115
(`live_los_clear = next(iter(member_los)) if len(member_los) == 1 else None`) can therefore never
produce `False` either — its input set is all-`True` or empty, never mixed. Every other perception
source (`source.py:313`'s own docstring: "the hybrid channel has no geometric gate to source it
from and never sets this") leaves the field at its `None` default. **So `Contact.live_los_clear`
can be `True` or `None` through the live pipeline, but never `False` — the `"obstructed"` branch
fixed above is structurally unreachable in live play, reachable only through a test fixture or
`replay.py`'s offline path.** This means §8's word has no live caller today; it is pre-existing
machinery outside this plan's Affected Modules, so not fixed here, but worth an architect's or
debugger's attention since it means the `"obstructed"` qualifier the sortie feedback was about may
never actually fire against real DCS data.

**Verification**: `ruff format --check .` fails only on the pre-existing out-of-scope
`research/2026-10-05-security-audit.md`, `ruff check .` and `mypy src` clean, `pytest -q` →
**2016 passed, 4 xfailed** (baseline 2014/4; +2 from the two new tests, net of the one rewritten in
place). Re-ran the §1/§2 sortie-log replay independently (`125 → 78` emissions, `47` suppressed;
`41` of `66` "obstructed" calls masked) — both figures unchanged by either fix, as expected, since
neither fix touches `_should_emit`'s text-veto or the cockpit-mask gate.

#### Files Changed (this pass)

- `body-layer/src/belief/attack_run.py` — `_no_look_cause`'s gate order swapped (range before LOS);
  module/function docstrings corrected; `decide`'s losing-sight branch suppresses `<where>` instead
  of wording a mismatched digit.
- `body-layer/src/belief/speech.py` — `render_attack_run_lost_sight`'s `where` parameter is now
  `str | None`; omits the clause on `None`.
- `body-layer/tests/test_attack_run.py` — added
  `test_no_look_cause_too_far_wins_over_a_fresh_obstructed_verdict`; rewrote
  `test_decide_losing_sight_where_phrase_reports_the_clock_hour` →
  `test_decide_losing_sight_where_suppressed_when_it_restates_the_clock_hour`; added
  `test_decide_losing_sight_where_phrase_kept_in_the_qualitative_register`; corrected
  `test_no_look_cause_too_far_beyond_naked_eye_presence_range`'s docstring.
