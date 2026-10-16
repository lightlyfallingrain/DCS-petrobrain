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

---

## `BL-B71` — the least-capable-optic guidance ladder (§6, §7)

Staged behind `BL-B70` as planned; built once `BL-B70` was merged (tip `98ee1f7a`).

### What shipped

**Stage 1, `optic_policy.least_capable_sufficient_optic(range_m, object_type, *, floor, ceiling)`.**
A naive per-tick ladder lookup over a new `_LADDER = (UNAIDED_OPTIC, BINOCULAR_OPTIC, SIGHT_WIDE_OPTIC,
SIGHT_NARROW_OPTIC)` (presence-ascending, matching `BL-B71.md`'s own derivation that this ordering
already exists in the shipped table) — the least capable optic between `floor`/`ceiling` whose own
`tier_ranges(...)[0]` still reaches `range_m`, falling back to `ceiling` if even that cannot resolve
the target.

**Stage 3, `optic_policy.guidance_request_for(range_m, object_type, previous, *, floor, ceiling)`.**
The hysteresis wrapper: escalation is immediate (re-derives via `least_capable_sufficient_optic`
whenever the current rung's own threshold is exceeded); de-escalation steps down exactly one rung at
a time and only once range is past the lower rung's threshold by `GUIDANCE_OPTIC_HYSTERESIS_FRACTION`
(new `tuning.real`, `0.25`, `lo=0.05, hi=0.9`). `previous` is the *caller's own* last request
(`AttackRunState.requested_optic`), never `optic_policy`'s own granted `guidance_optic` — the two can
legitimately diverge (see "Design decisions" below).

**Stage 2, `OpticState.guidance_optic`/`guidance_optic_since_sim`, and `decide`'s new
`guidance_request: Optic | None = None` keyword.** `decide`'s existing body is renamed
`_decide_without_guidance` (unchanged) and wrapped by a new public `decide` that applies a
post-dispatch step, `_apply_guidance`, unless `decision.suppressed` (the hands-busy window). This is
the literal implementation of the plan's "leaves the phase machine otherwise untouched": the ordinary
SCANNING/GLASSING/SEARCHING/SIGHTING dispatch runs exactly as before, and `_apply_guidance` only ever
rewrites `decision.optic` plus the two `guidance_*` state fields.

`_apply_guidance`:

1. `guidance_request is None` → revoke any standing grant (`guidance_optic`/`guidance_optic_since_sim`
   both to `None` together).
2. **Sight ceiling clamp, re-derived every call from `state.home_phase`, never cached**: a
   sight-ranked request is capped to `BINOCULAR_OPTIC` whenever `home_phase is not SIGHTING`. This is
   what makes the hard gate ("the 9K113 is never reached for autonomously") structural — a pilot's
   "Observ off" or a violated `sight_steady` (`_force_observ_off`) both only ever change `home_phase`,
   read fresh here, so a standing sight grant demotes to binoculars on the very next poll with no
   separate transition-handling code needed.
3. Guard 3 (`GUIDANCE_OPTIC_MIN_INTERVAL_S`, new `tuning.real`, `10.0`, `lo=1.0, hi=60.0`): a change
   is refused if less than the interval has passed since the last grant; the standing grant (if any)
   is held, and a refusal never advances `hands_busy_until_sim`.
4. A real change charges `HANDS_BUSY_DURATION_S` **iff the optic actually in use is changing** —
   compared against the standing grant if one exists, or against `_HOME_OPTIC[state.home_phase]`
   otherwise (the first grant of a run, nothing yet to compare against; see "Design decisions").

**Wiring.** `attack_run.decide` computes `AttackRunState.requested_optic` every non-`MASKED` tick
(guard 1 — the field is simply never touched after the `cause == "masked"` early return, so "falls
out of §2" needed no separate check) via `guidance_request_for(range_m(observer,
contact.last_position), contact.last_class_raw, state.requested_optic, floor=UNAIDED_OPTIC,
ceiling=SIGHT_NARROW_OPTIC)`. `logger.py`'s `run_once` threads
`self.attack_run_state.requested_optic` into `decide_optic`'s new `guidance_request` keyword — one
poll lagged relative to `drain_attack_run` (which recomputes it), the same lag
`attack_run_transition`/`observ_transition` already accept elsewhere in that file.

### Design decisions settled during implementation (not individually in the plan)

- **`guidance_request_for`'s hysteresis lives in `optic_policy`, keyed by the caller's own `previous`
  argument, not by `OpticState.guidance_optic`.** The plan names Stage 1's predicate signature
  explicitly (no "current" parameter) and leaves Stage 3's home unstated. Putting the margin math
  beside `tier_ranges`/`_LADDER` (which it needs) and having `attack_run` supply its own memory
  (`AttackRunState.requested_optic`) keeps the two modules' roles exactly as drawn ("attack_run owns
  the request, optic_policy owns the decision") — `attack_run`'s ladder tracks what the target's
  geometry alone would ask for, independent of whether a sight request was ever actually granted
  (home_phase may clamp it). One consequence, noted rather than guarded against: if OBSERV turns on
  mid-run, the ladder's already-correct standing request becomes grantable immediately, rather than
  needing several more ticks to re-climb from `BINOCULAR_OPTIC` — judged a feature (no needless
  guidance lag), not a defect.
- **First-grant hands-busy comparison baseline.** The plan does not say what "the optic actually
  changing" compares against on the very first grant of a run (nothing has been granted yet).
  Compared against `_HOME_OPTIC[state.home_phase]` (`UNAIDED_OPTIC` for `SCANNING`, `SIGHT_WIDE_OPTIC`
  for `SIGHTING`) — the optic Petrovich would otherwise be using — so a run that only ever confirms
  "naked eye is already enough" never charges a spurious first-grant cost.
- **`_no_look_cause`'s `TOO_FAR` range test still uses `UNAIDED_OPTIC` unconditionally**, not the
  currently-granted guidance optic. `BL-B70.md`'s own entry flags this coupling as out of scope for
  that entry ("`BL-B71`'s optic ladder... is out of scope for this entry"); this task's Stages (1-5,
  `plan.md`) likewise never ask `_no_look_cause` to change. Left as-is — the cause taxonomy and the
  optic ladder answer related but distinct questions (why no fresh look right now, vs. which
  instrument would help), and widening `_no_look_cause`'s scope was not requested. Flagged for whoever
  next touches that function.

### Co-moving Fields — exit transitions enumerated (grepped, not read off the plan's list)

Every place `OpticState.phase`/`home_phase` changes or an attack run ends, checked against whether
`guidance_optic` needs a write path there:

| transition | where | effect on `guidance_optic` |
|---|---|---|
| `disengage`/`drop_target`/vanished-contact (any `drain_attack_run` path that returns `None`) | `crew_console.drain_attack_run` → `runner.attack_run_state = None` | next poll's `guidance_request` is `None` → `_apply_guidance` revokes |
| pilot "Observ off" | `logger.py`'s command dispatch sets `home_phase=SCANNING` directly | **not written here at all** — the ceiling clamp re-reads `home_phase` fresh on the *next* `decide` call and demotes any sight-ranked grant to `BINOCULAR_OPTIC` there |
| `_force_observ_off` (violated `sight_steady`) | inside `_decide_without_guidance`'s `_decide_sighting` dispatch | same as above — `home_phase` changes, `_apply_guidance` re-clamps on this *same* call since it runs on `_decide_without_guidance`'s own output state |
| pilot "Observ on" | `logger.py`'s command dispatch sets `home_phase=SIGHTING` | raises the ceiling, not a revocation; no special handling needed |
| ordinary `lower_binoculars` (ambient manoeuvre/command lowering an unrelated glass/sight look) | `optic_policy.lower_binoculars` | **does not touch `guidance_optic`** — confirmed deliberately out of scope: that function governs the phase's own *look* state (`look_contact_id` etc.), which is now orthogonal to the guidance override (the override replaces `decision.optic` regardless of what the phase machine is doing with its look target) |
| fresh `OpticState(...)` construction entering `SEARCHING` or `GLASSING` from `SCANNING`-at-home | `_decide_without_guidance`'s own two fresh-construction sites | **had to be fixed** — neither site originally carried `guidance_optic`/`guidance_optic_since_sim` forward, which would have silently reset a standing grant's bookkeeping and triggered a spurious second hands-busy charge on an unrelated ordinary scan/glass event. Added explicit carry-forward at both sites, confirmed by mutation (see "Checks" below). |

The plan's own list named only the first three rows (disengage/drop_target/run-ends,
Observ-off-demotes, `_force_observ_off`-demotes). The fresh-construction trap was found by the same
audit `BL-B64`/`BL-B70` each flag as their own recurring class, not named in `BL-B71.md`'s Co-moving
Fields table.

### Files Changed

- `body-layer/src/belief/optic_policy.py` — `_LADDER`, `GUIDANCE_OPTIC_HYSTERESIS_FRACTION`,
  `GUIDANCE_OPTIC_MIN_INTERVAL_S` (new tuning constants); `least_capable_sufficient_optic`,
  `guidance_request_for` (new pure functions); `OpticState` gains `guidance_optic`/
  `guidance_optic_since_sim`, carried forward explicitly at both fresh-`OpticState(...)` construction
  sites; `decide` renamed to `_decide_without_guidance` and wrapped by a new public `decide` with a
  `guidance_request` keyword and the new `_apply_guidance` post-processing step.
- `body-layer/src/belief/attack_run.py` — `AttackRunState` gains `requested_optic`, reset to `None`
  on a contact re-point; `decide` computes it every non-masked tick via `optic_policy.
  guidance_request_for`.
- `body-layer/src/logger.py` — `run_once`'s `decide_optic` call threads
  `self.attack_run_state.requested_optic` into the new `guidance_request` keyword.
- `body-layer/config/defaults.toml` — regenerated; adds `GUIDANCE_OPTIC_HYSTERESIS_FRACTION`,
  `GUIDANCE_OPTIC_MIN_INTERVAL_S`.
- `body-layer/tests/test_optic_policy.py` — `TestLeastCapableSufficientOptic`,
  `TestGuidanceRequestFor`, `TestGuidanceOverride` (new).
- `body-layer/tests/test_attack_run.py` — `TestRequestedOptic` (new).

### Tests Added

- `TestLeastCapableSufficientOptic` (5 tests) — naive ladder lookup: within/beyond each rung,
  falls back to ceiling, and a `ceiling=BINOCULAR_OPTIC` caller never gets a sight optic back.
- `TestGuidanceRequestFor` (5 tests) — no-previous starts at floor; escalation is immediate; the
  de-escalation band is withheld then crossed; de-escalation steps one rung at a time; a `previous`
  below a raised `floor` is clamped up.
- `TestGuidanceOverride` (11 tests) — `guidance_request=None` true no-op; a grant overrides the optic
  and charges hands-busy; the hard sight gate (and its lift once `home_phase is SIGHTING`); the
  hand-built diverged state (`guidance_optic is SIGHT_WIDE_OPTIC` while `home_phase is SCANNING`,
  per the plan's own explicit instruction to construct this by hand) demoting on one poll; guard 3
  refusing then allowing a change; revocation on disengage; suppression during hands-busy; a fresh
  `SEARCHING` entry not resetting a standing grant.
- `TestRequestedOptic` (6 tests, `test_attack_run.py`) — starts `None`; naked-eye/binocular requests
  by range; guard 1's masked freeze (range changed underneath a masked tick, request does not move);
  the de-escalation band through the full `decide()` path; a re-point resets the request.

### Checks

- `ruff format --check src tests`: pass (2 files needed reformatting after being written, fixed with
  `ruff format`, then re-verified clean).
- `ruff check src tests`: pass (one `F401` unused-import caught and fixed before this run).
- `mypy src` (CWD-only, run from inside `body-layer`): `Success: no issues found in 60 source files`.
- `pytest tests -q`: **2087 passed, 4 xfailed** (baseline before this task: 2061 passed, 4 xfailed —
  net +26, all new).

**Counterfactuals run, by `shasum` before/after, for the three structural claims that could pass a
test for the wrong reason:**

1. **The sight ceiling clamp** (`_apply_guidance`'s `if` block) — replaced with `if False:`, re-ran
   `test_the_hard_gate_the_9k113_is_never_reached_for_autonomously` and
   `test_the_diverged_state_sight_granted_while_scanning_is_home_demotes_at_once`: both failed, each
   asserting the request was granted as `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC` rather than clamped to
   `BINOCULAR_OPTIC` — exactly the stated reason. Restored; `shasum` of `optic_policy.py` matched the
   pre-mutation value exactly.
2. **The fresh-`SEARCHING`-construction carry-forward** — dropped the two `guidance_optic*` kwargs
   from that one construction site, re-ran
   `test_a_fresh_search_phase_entry_does_not_reset_a_standing_grant`: failed,
   `assert new_state.guidance_optic_since_sim == 0.0` got `16.0` (the clock had been silently reset
   and re-stamped, exactly the spurious-recharge the test guards against). Restored; `shasum`
   matched.
3. **Guard 1's placement** (the masked early-return in `attack_run.decide`) — moved the
   `requested_optic` update above the `if cause == "masked": return` line (the mutation the task
   explicitly flagged as the dangerous one), re-ran
   `test_a_masked_tick_freezes_the_request_guard_1`: failed, the request jumped from `UNAIDED_OPTIC`
   to `BINOCULAR_OPTIC` on the masked tick. Restored; `shasum` matched.

### Notable Discoveries

- **The generator's `_first_sentence` strips only a single leading/trailing backtick, not whole
  inline-code spans.** Both new tuning constants' `#:` comments originally opened with a
  backtick-wrapped term (`` `BL-B71`'s... ``); the rendered `config/defaults.toml` line read
  `` BL-B71`'s de-escalation... `` — the opening backtick silently eaten, the closing one left
  dangling, because `str.strip("*`")` only trims characters from the very ends of the matched
  sentence, not every inline span inside it. Fixed by not opening either comment's first sentence
  with a backtick-wrapped term; not a general fix to the generator (out of scope here), but worth a
  future pass given the generator's own docstring already documents two other failure modes of the
  same shape (`tools/generate_defaults.py`'s module docstring; see also
  `.claude/agent-memory/implementer/project_tuning_generator_comment_extraction.md`).
- **The two new constants have no live run-loop coupling to assert, but one worth naming**: `GUIDANCE_
  OPTIC_MIN_INTERVAL_S` (10.0) is sized to exceed `HANDS_BUSY_DURATION_S` (1.0) comfortably — if a
  future retune pushed the interval below the hands-busy duration, a grant could in principle be
  rechargeable before its own hands-busy window even finishes. Not enforced in code (the margin is
  10x today), stated in the constant's own `#:` comment's second sentence (which the generator does
  not render — see the first discovery above) rather than guarded in `tuning.py`, per the role's
  guidance to flag rather than silently add cross-key machinery beyond what the plan asked for.
- **The gaze/optic structural seam the plan names as deliberately unfixed (`BL-B71.md`: "the run
  claims the gaze in `logger._active_gaze`... the optic comes from `optic_policy.decide`'s own scan
  cycle") is confirmed still open after this change, in the specific direction that matters**: when
  `home_phase is SIGHTING` and a guidance grant actually reaches a sight optic, `_apply_active_gaze`
  still lets `_decide_sighting`'s own internally-chosen look target (via `choose_look`, which may be
  glassing a *different* contact than the attack target) override the attack-run-narrowed
  `scan_plan` whenever `decision.look_azimuth_deg is not None` — this change only ever overrides
  `decision.optic`, never `look_azimuth_deg`/`look_elevation_deg`. For the realistic common case
  (`home_phase is SCANNING`, the vast majority of runs since OBSERV needs an explicit pilot command)
  this does not arise: `BINOCULAR_OPTIC` has no field of regard and `decision.look_azimuth_deg` stays
  `None` in that branch, so the attack-run-narrowed gaze is untouched. Confirmed by reading
  `_apply_active_gaze`, not by a new test — `BL-B71.md` itself names the consolidation
  (`OpticPhase.GUIDING`) that would resolve this, assigned to `BL-B66`.

## BL-B71 review fix round (2026-10-16)

Reviewer's required fix: `_no_look_cause`'s range test measured against `UNAIDED_OPTIC`
unconditionally, so once the ladder granted binoculars a live, resolvable tier-1 look could still
be reported `"too_far"` (tested against the wrong, narrower threshold) and trigger the
`losing_sight` branch — "last I saw..." about a target currently in view. User direction asked
directly whether this was a test artefact or real behaviour: **"actual behavior must measure by
used optic."**

### Files Changed (this round)

- `body-layer/src/belief/attack_run.py` — `_no_look_cause` takes a new `optic: Optic =
  UNAIDED_OPTIC` keyword parameter, used for the range gate (`tier_ranges(..., optic=optic, ...)`)
  instead of the hardcoded constant. `decide` takes a new `granted_optic: Optic | None = None`
  parameter, threaded straight through to `_no_look_cause` (falling back to `UNAIDED_OPTIC` when
  `None`) and read nowhere else in the function — kept the function pure and did not widen its
  signature beyond this one need, per the task's own direction. Corrected the docstring's "`tier ==
  1` with `cause == "too_far"` is not reachable in practice" claim: it is reachable once the ladder
  is live and the admitting optic is not threaded through, which is exactly the bug this round
  fixes — left a trail to the review rather than silently deleting the old claim.
- `body-layer/src/belief/crew_console.py` — `drain_attack_run` takes a new keyword-only
  `granted_optic: Optic | None = None`, passed straight through to `decide_attack_run`. Added the
  `Optic` import.
- `body-layer/src/logger.py` — the `drain_attack_run` call site now passes `granted_optic=runner.
  optic_state.guidance_optic`. This is **not** one-poll stale the way `AttackRunState.
  requested_optic` (read the other direction, into `decide_optic`) deliberately is: `decide_optic`
  runs earlier in the same poll (inside `run_once`) and has already updated `optic_state.
  guidance_optic` for *this* tick before `drain_attack_run` is called, so it reflects the optic
  that actually admitted this tick's percepts.
- `body-layer/src/belief/optic_policy.py` — two unrequired-but-folded-in fixes from the review's
  optional findings:
  - `GUIDANCE_OPTIC_MIN_INTERVAL_S`'s `#:` comment: moved the cross-key coupling warning
    (`must stay above HANDS_BUSY_DURATION_S`) into the comment's **first** sentence, since the
    generator renders only that one — verified against the rendered `config/defaults.toml`, not
    the comment (root `CLAUDE.md`'s named trap, third recurrence per the review). Stated plainly in
    the comment that the declared `lo`/`hi` bounds (1.0..60.0 and the paired constant's 0.1..5.0)
    do permit violating the coupling at the extremes and that nothing enforces it — no cross-key
    assert added, since the task said to flag rather than invent unrequested machinery when one
    isn't cheaply expressible, and this one is a tuning caution rather than an invariant that must
    hold.
  - The first-grant hands-busy baseline (`_apply_guidance`'s `previous_optic` comparison against
    `_HOME_OPTIC[state.home_phase]` rather than `decision.optic`): left uncorrected, with a comment
    explaining the narrow gap and why — it only ever overcharges a cost that was not strictly
    owed, never skips a real one, so it is not safety-relevant and fixing it would have gone beyond
    this task's scope (the review itself called it optional).

### Tests Added (this round)

- `test_no_look_cause_optic_param_lowers_the_too_far_threshold` — direct unit proof that `optic`
  moves `_no_look_cause`'s range gate: the same contact is `"too_far"` against the default
  (`UNAIDED_OPTIC`) and `"unknown"` against a granted `BINOCULAR_OPTIC`.
- `test_decide_with_granted_binoculars_resolves_tier_1_instead_of_losing_sight` — the combination
  the review found untestable through `_contact_at` (deliberately tier-2-only): a fresh tier-1
  percept at a range beyond the naked eye's own presence threshold but within the granted
  binoculars'. Asserts `decide()` with `granted_optic=BINOCULAR_OPTIC` speaks the ordinary "Lined
  up." rather than the `render_attack_run_lost_sight` "last I saw..." phrasing, and that
  `last_spoken_unresolved` is `False`.

  **Counterfactual confirmed, not merely asserted**: reverted `_no_look_cause`'s call site inside
  `decide` to a hardcoded `optic=UNAIDED_OPTIC`, re-ran the new `decide()`-level test — failed,
  `speech.text` read `'Lined up armor ahead, last seen a moment ago.'` instead of `'Lined up.'`,
  exactly the stated failure mode. Restored the fix; `shasum` of `attack_run.py` before and after
  the mutation matched exactly (`1f0cfff8fda03dddc037746d4e5c4acdd4d81af7`).

### Checks (this round)

- `ruff format --check src tests`: pass, 133 files already formatted.
- `ruff check src tests`: pass, all checks passed.
- `mypy src` (from inside `body-layer/`): pass, no issues in 60 source files.
- `pytest tests -q`: **2089 passed, 4 xfailed** (baseline 2087 passed / 4 xfailed; +2 for the two
  new tests, confirmed by name in `-v` output).

### Notable Discoveries (this round)

- Confirmed by reading `_apply_guidance` that every branch setting `decision.optic` away from the
  ordinary phase dispatch's own choice keeps it in lockstep with `state.guidance_optic` *after*
  that call returns, **except** the "refused due to guard 3, no standing grant yet" branch, where
  `decision.optic` is whatever the ordinary dispatch picked (which need not be `UNAIDED_OPTIC`) while
  `state.guidance_optic` stays `None`. In that one edge case, reading `OpticState.guidance_optic`
  (as this fix does, per the review's own explicit recommendation) is slightly more conservative
  than reading the admitting `decision.optic`/`runner.optic` directly would be — it could in
  principle test range against `UNAIDED_OPTIC` on a tick where the ordinary dispatch had already
  put binoculars in use for an unrelated reason. Not fixed here (the review named `guidance_optic`
  specifically and the user's direction was about measuring against the *granted* optic, not every
  possible admitting optic); worth noting for anyone revisiting this area.

## BL-B71 `resolving_optic` correction round (2026-10-16)

The "Not fixed here" note directly above was wrong to leave as a known gap. The user, asked
directly whether the naked-eye-only range test was a test artefact or real behaviour, ruled: **"actual
behavior must measure by used optic."** `OpticState.guidance_optic` is the attack-run guidance
ladder's own standing *grant* — it is `None` through ordinary glassing (`OpticPhase.GLASSING` with
no guidance request at all), so the previous round's fix, wired at `logger.py:2019` as
`granted_optic=runner.optic_state.guidance_optic`, reintroduced the original defect in miniature:
binoculars raised for an ordinary look, no guidance grant, a target resolvable at binoculars and
not the naked eye — `_no_look_cause` fell back to `UNAIDED_OPTIC`'s narrower threshold and the run
could say "last I saw…" about a target actively being tracked.

### Files Changed (this round)

- `body-layer/src/logger.py` — the `drain_attack_run` call site (line ~2019) now passes
  `resolving_optic=runner.optic` instead of `granted_optic=runner.optic_state.guidance_optic`.
  `runner.optic` is `optic_decision.optic` from this same poll's `decide_optic` call (`self.optic =
  optic_decision.optic`, `run_once`), and is the exact value `_apply_active_gaze` assigns onto
  `source.optic`, which `NakedEyePerceptionSource.poll` passes straight to
  `perception.visibility.check_visibility`'s `optic=` keyword — confirmed by reading that call
  chain (`naked_eye_source.py:754`, `:1174`), not assumed. Nothing overwrites `runner.optic` between
  `run_once()` and the `drain_attack_run` call later in the same poll iteration of
  `_run_crew_text_poll_loop`, so it is not one poll stale.
- `body-layer/src/belief/attack_run.py` — `decide()`'s keyword renamed `granted_optic` →
  `resolving_optic` (it no longer means "the ladder's grant"); docstrings on `decide` and
  `_no_look_cause` corrected to describe the used-optic contract and to say explicitly that the
  prior `granted_optic`/`guidance_optic` wiring was wrong, not merely superseded.
- `body-layer/src/belief/crew_console.py` — `drain_attack_run()`'s keyword renamed to match, and its
  docstring corrected the same way.
- `body-layer/tests/test_attack_run.py` — updated the one existing `decide(..., granted_optic=...)`
  call site to the new keyword; no behavioural change, this test already exercised the right
  value.
- `body-layer/tests/test_logger.py` — new regression test (below), inserted after the
  `test_crew_text_poll_loop_logs_the_coverage_summary_in_its_finally_block` block.

### Tests Added (this round)

- `test_crew_text_poll_loop_passes_the_used_optic_not_the_guidance_grant` — drives the real
  `_run_crew_text_poll_loop` on a thread (the established pattern this file already uses for
  loop-level wiring, e.g. the coverage-summary tests immediately above it), with `runner.run_once`
  replaced by a no-op so the loop body runs against hand-set `runner` state: `runner.optic =
  BINOCULAR_OPTIC`, `runner.optic_state = OpticState(phase=OpticPhase.GLASSING, guidance_optic=
  None)` — the narrower case from the review: ordinary glassing, no guidance grant at all.
  `crew_console.drain_attack_run` is replaced with a spy that only records its `resolving_optic`
  kwarg (not a reimplementation of `decide`'s own logic — that combination is already covered by
  `test_attack_run.py`'s `resolving_optic`-at-the-`decide()`-level tests). Asserts the captured
  value is `BINOCULAR_OPTIC`, not `runner.optic_state.guidance_optic` (which is `None`).

  **Counterfactual confirmed, not merely asserted**: reverted the call site back to
  `resolving_optic=runner.optic_state.guidance_optic`, re-ran the new test — failed with
  `AssertionError: assert None is Optic(name='binocular', ...)`, exactly the stated failure mode
  (the test would have gone on to misattribute a live binocular look as "too far"). Restored the
  fix; `shasum` of `logger.py` before and after the mutation matched exactly.

### Checks (this round)

- `ruff format --check src tests`: pass, 133 files already formatted (one file — the new test —
  needed `ruff format` applied once before the check passed; recorded here per the quality-gate
  habit, not left silently fixed).
- `ruff check src tests`: pass, all checks passed.
- `mypy src` (from inside `body-layer/`): pass, no issues in 60 source files.
- `pytest tests -q`: **2090 passed, 4 xfailed** (baseline for this round: 2089 passed / 4 xfailed;
  +1 for the new test, confirmed by name in unfiltered `-v` output, not a `-k` run).

### Notable Discoveries (this round)

- **`runner.optic` confirmed as the right datum**, by reading the call chain rather than assuming
  it: `self.optic = optic_decision.optic` (`logger.py:593`) and `source.optic = optic`
  (`_apply_active_gaze`, same `decision.optic` value, `logger.py:1020`) are the same value, which
  `NakedEyePerceptionSource.poll` passes to `visibility.check_visibility(..., optic=self.optic,
  ...)` (`naked_eye_source.py:754`) — the exact instrument admitting this tick's percepts. Nothing
  sits between `run_once()` and the `drain_attack_run` call in `_run_crew_text_poll_loop` that could
  overwrite `runner.optic` for the same poll.
- **The previous round's "Not fixed here" edge case** (guard-3-refused grants, where
  `decision.optic` and `state.guidance_optic` can briefly disagree) is now moot: `resolving_optic`
  reads `runner.optic` (== `decision.optic`) directly, which is the *more* accurate of the two, not
  the more conservative one the previous round chose. No remaining known gap in this area.
- Writing the new test exposed how little of the real perception/attack-run pipeline is actually
  needed to pin this specific regression: no naked-eye detection chain, no `ContactStore`, no
  command-dispatched `select target`/`engage` — hand-setting `runner.optic`/`runner.optic_state`
  before a no-op'd `run_once()` and spying on `drain_attack_run` isolates the wiring defect from
  everything already covered elsewhere (`test_attack_run.py` for `decide()`'s own logic,
  `test_optic_policy.py` for `decide_optic`'s GLASSING-continuation branch).
