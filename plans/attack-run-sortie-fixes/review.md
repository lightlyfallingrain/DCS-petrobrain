### Review Summary

Reviewed `feature/attack-run-fixes` at `5215daa69fea106943fe5a9a449e7a23979843e0` against
`docs/acceptance/2026-10-15-attack-run-sortie-feedback.md` §1/§2/§4/§8/§9/§10/§11,
`plans/attack-run-sortie-fixes/plan.md`, and `implementation.md`. `BL-B71` (the optic ladder) is
confirmed untouched (`optic_policy.py` has no diff against `main`).

All claimed checks reproduced exactly: `ruff format --check .` fails only on the pre-existing
out-of-scope `research/2026-10-05-security-audit.md`; `ruff check .` and `mypy src` clean;
`pytest -q` → **2014 passed, 4 xfailed**. The §1 replay (125→78 emissions, 47 suppressed) and the
§2 replay (41/66 "obstructed" calls → masked) were independently re-run against the real sortie
log and matched the implementer's figures exactly.

Most of the design holds up well under construction, not just reading: the masked-tick early
return genuinely never touches `last_spoken_text`/`last_spoken_clock_hour`/`last_spoken_unresolved`
(verified by reading the control flow, not the docstring); the re-point reset genuinely clears all
three announce-flags via a fresh `AttackRunState(last_contact_id=...)`; `replace()` is used
everywhere except that one deliberate reset; the removed test's invariant is genuinely no longer
true and its replacement documents the right fact; the two reported plan deviations are both
correct and complete (grepped for a third reader of the removed fields — none exists; grepped for
`DetectionTraceCollector` access from `crew_console.py` — none exists).

Two real defects were found by construction/mutation that no existing test catches.

---

### Required Fixes

- **`_no_look_cause`'s gate order does not match `check_visibility`'s real gate order, despite
  explicitly claiming to** (`attack_run.py` module docstring, `_no_look_cause`'s own docstring, and
  both of `test_no_look_cause_obstructed_only_on_a_fresh_false_verdict`/
  `test_no_look_cause_too_far_beyond_naked_eye_presence_range`'s docstrings all assert this).
  `check_visibility`'s actual gate sequence (`visibility.py:997-1023`) is gaze → cockpit mask →
  optic FOV → **range/size (gate 3)** → **terrain LOS (gate 4)** → forest. `_no_look_cause` checks
  **LOS (`"obstructed"`) before range (`"too_far"`)** — the two are inverted relative to the
  pipeline it claims to mirror. Confirmed by mutation: swapping the two checks to the correct
  order left all 2018 tests passing (nothing exercises a contact that is simultaneously
  fresh-`False` on LOS and beyond presence range). Consequence: a contact whose `live_los_clear`
  is a fresh `False` from a closer look, but whose *current* range (recomputed independently, using
  ownship's current position) has since opened past the presence threshold, is spoken as
  `", obstructed"` when the honest cause — the one `check_visibility` would actually have rejected
  it on first — is `"too_far"`. The plan's own F3 measured opening rates up to +130 m/s, which
  crosses the presence-threshold band within the 1.5 s `ATTACK_TARGET_LOS_MAX_AGE_S` freshness
  window, so this is reachable, not merely theoretical. Fix: check range (`"too_far"`) before LOS
  (`"obstructed"`), matching the real gate order, and add a test that pins a contact which is both
  (fresh `live_los_clear=False`, beyond presence range) and asserts `"too_far"` wins.

- **§10's `<where>` clause mixes digit and word clock-hour forms, and duplicates the clock
  position when the guidance phrase is itself an o'clock call.** `decide`'s losing-sight branch
  builds `where = f"{where_hour} o'clock"` from the raw `int` returned by `alignment_clock_hour`
  (`attack_run.py:653-654`), never routing it through `_ALIGNMENT_CLOCK_WORDS` the way
  `alignment_phrase` does one function away in the same module. `test_decide_losing_sight_where_
  phrase_reports_the_clock_hour` pins the exact result: `"Three o'clock armor 3 o'clock, last seen
  a moment ago."` — the clock position spoken twice, once as a word (from `phrase`, which is
  itself an o'clock phrase whenever azimuth is outside the 12 o'clock sector — the common case for
  a `"too_far"` target) and once as a bare digit (from `where`). This is exactly the TTS
  inconsistency the rest of this file is careful about (`_format_range_km` spells out
  "kilometres", `_ALIGNMENT_CLOCK_WORDS` exists for exactly this reason) and reads as a defect, not
  character. Fix at minimum: word the hour via `_ALIGNMENT_CLOCK_WORDS`. Worth also asking whether
  `<where>` should be suppressed when it would restate `phrase` verbatim — as currently built, the
  template never produces anything else when azimuth is outside the sector.

---

### Optional Refinements

- **Cross-key coupling, flagged by the implementer and not asserted**: `ATTACK_TARGET_LOS_MAX_AGE_S`
  (`hi=3.0`) is conceptually bounded by `LOS_MAX_AGE_S` (`= 3.0`, hardcoded, not itself wrapped in
  `tuning.real`). Since the binding constant is not tunable via config, only a future source-level
  change to `LOS_MAX_AGE_S` (not a `defaults.toml` edit) could create the incoherence the
  implementer named, and such a change would be a visible diff in the same review flow. Low
  probability; a one-line assertion at import (`assert ATTACK_TARGET_LOS_MAX_AGE_S_hi <=
  LOS_MAX_AGE_S` or similar) would close it cheaply if the project wants zero residual risk here,
  but it is reasonable to leave as the implementer judged.
- **§10's risk ("Mid-run ages are seconds, so nearly every utterance renders 'a moment'")** is
  already flagged by the implementer and the plan as a sortie question, not a code defect — no
  action needed before flying, consistent with how `_attack_run_last_seen_phrase` was actually
  built (correctly reusing the coarse-bucket shape without reusing `_spoken_age_phrase` verbatim,
  which would have doubled "old"/"ago").
- `tuning.real`'s rendered `defaults.toml` entry for `ATTACK_TARGET_LOS_MAX_AGE_S` was read directly
  (not the source comment) and is correctly rendered, arithmetically consistent (60 m/s × 1.5 s =
  90 m, matches the source docstring), with no corrupted backtick spans — no action needed, noted
  because the checklist specifically asks this be read rather than assumed.

---

### Verdict

**NEEDS REVISION**

Both required fixes are small (reorder two branches in `_no_look_cause`; route `where_hour` through
the existing word table) and localized to `attack_run.py`. Neither invalidates the design or the
measured payoff (§1/§2's suppression figures are unaffected by either fix) — this is not a
rewrite-scale finding, just two defects that construction/mutation surfaced and tests did not.

### Review Confidence

Full read of `attack_run.py`, `speech.py`'s attack-run-relevant functions, `belief_truth_log.py`'s
new tripwire code, `crew_console.py`'s read-site, and the relevant slice of `visibility.py`
(`check_visibility`'s real gate order, read from source, not docstring). Checks re-run directly
(ruff/mypy/pytest) and the sortie-log replay re-run independently rather than trusted from the
implementation report. `optic_policy.py`/`logger.py`'s `decide_optic` wiring confirmed untouched
(diff-empty) rather than assumed from the plan's staging note. Not independently re-derived: the
`Contact.live_los_clear` admission-pipeline question (whether `False` can ever reach a `Contact` in
practice, given gate 4's fail-closed posture appears to only let `True` survive into a `Percept`) —
traced far enough to be a genuine open question worth an architect/debugger's attention, but it is
pre-existing machinery explicitly out of this plan's Affected Modules and not resolved here one way
or the other; flagging it in case it is not already known, not asserting it as a defect of this
diff.
