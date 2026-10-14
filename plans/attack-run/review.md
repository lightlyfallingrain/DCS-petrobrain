### Review Summary

Reviewed `feature/bl14-attack-run` at `a880e20a7cd89010d9c7f5df64de25bdb9a85db6` (fast-forwarded
from a stale worktree base `f25c57c`, which was a strict ancestor — clean fast-forward, no
divergence). Scope: BL-14 Stages 1–3 only (selection/drop-target + audio-adapter vocabulary; the
inert ownship-relative observation channel; the pure, unwired alignment derivation and renderers).
Stages 4–7 are correctly absent.

Full read of `plans/attack-run/plan.md` (1122 lines), `docs/acceptance/2026-10-14-attack-run-
guidance-direction.md` (539 lines, the user's own words, which outrank the plan), and
`plans/attack-run/implementation.md`. Read every changed file in `body-layer/src/belief/
attack_run.py`, `percept.py`, `contacts.py`, `speech.py` (the `render_alignment` family),
`crew_console.py` (`_resolve_attack_target`/`_handle_select_target`/`_handle_drop_target`/
`drain_attack_run`), `perception/naked_eye_source.py`, `perception/geometry.py`,
`perception/estimation.py`, `perception/clustering.py`, `perception/detection_trace.py`, and
`audio-adapter/src/command_matcher.py`/`vocabulary.py`. Ran all gates myself rather than trusting
the implementer's report; mutated the two highest-risk pinned tests from source.

The implementation matches the plan's Stage 1–3 scope closely, correctly declines to build
anything from Stage 4 onward, and the two "Notable Discoveries" in `implementation.md` (the false
plan premise on Decision 16, and the circular-import resolution for `render_alignment`'s word
tables) are accurately reported and correctly handled in the code.

### Verification — run myself

**body-layer/** (from `cd body-layer`, using the main checkout's venv by absolute path, confirmed
resolving `belief.attack_run` to *this* worktree's `src` before running anything):

- `ruff format --check src tests`: pass (126 files already formatted)
- `ruff check src tests`: pass
- `mypy src`: `Success: no issues found in 58 source files`
- `pytest tests -q`: **1790 passed, 4 xfailed** — matches the implementer's report exactly

**audio-adapter/** (same pattern):

- `ruff format --check src tests`: pass (29 files)
- `ruff check src tests`: pass
- `mypy src`: `Success: no issues found in 15 source files`
- `pytest tests -q`: **261 passed, 1 skipped** — matches the implementer's report exactly

### The five specific questions — findings

**1. `Contact.last_percept` — proportionality and surface widening.**

(a) *Proportionate.* `ContactStore` already has an accepted "full memory, never pruned" posture —
`BL-B23` (`body-layer/ROADMAP/BL-B23.md`) deliberately left `_contacts` itself untouched when it
fixed the *clustering*-cost quadratic blowup: "`_contacts` itself is untouched: nothing is
deleted, a `lost` contact stays full memory and remains answerable." `last_percept` is a single
object reference, **overwritten, not appended**, each `record()`/`from_percept()` call — O(1) per
contact, not O(n) growth like `contributing_observation_ids`' list already is. Against that
existing precedent, one more whole-object reference per contact is in line with, not a departure
from, how this store already treats memory. A narrower field (just `RelativeDirection` +
`ownship_at_observation` + `t_sim`) would save a handful of bytes per contact and buys nothing —
the implementer's stated reason for the whole object (grep-fence purity: `contacts.py` never has
to write a field literally named anything containing `relative_direction`) is a real, load-bearing
constraint, not an excuse. Not a required fix.

(b) *Does not widen the truth-derived surface the way the prompt's framing suggested.* I checked
this directly against `percept.py`: **`Percept` does not carry `derived_world_position`** — that
field exists only on `Observation`, and `Percept` is deliberately "stripped of every DCS truth
field" (its own docstring). So `last_percept` gives no belief code a one-hop path to ground truth
via that field; the only genuinely truth-adjacent field it newly reaches is `relative_direction`
itself, which is exactly the field the grep fence (next finding) is built to contain. The premise
in the review brief ("a `Percept` carries `derived_world_position` and now `relative_direction`")
is factually wrong about `Percept`; it is true only of `Observation`, which never crosses into
`belief/`.

**2. The grep fence — mutation-tested, holds.**

Confirmed by injecting a real leak (`contact.last_percept.relative_direction` appended to
`tools.py`, outside the two sanctioned files) and running
`test_belief_never_references_relative_direction_except_sanctioned_readers`: it failed with the
exact assertion the fence promises (`tools.py references relative_direction`). The fence is a
structural protection against the realistic failure mode — a future contributor reaching
`contact.last_percept.relative_direction` from inside some other `belief/` module — because that
access necessarily writes the literal string `relative_direction`, which the regex catches. It
would not catch a deliberately obfuscated access (`getattr(contact.last_percept, "relative" +
"_direction")`), but that is true of every grep fence in this codebase, including the pre-existing
`derived_world_position` one it mirrors, and is not a new weakness this feature introduces. The
architect's "structural, not merely informational" claim holds for the realistic case; it was not
weakened into a naming convention, and I verified that by breaking it, not by reading it.

**3. `render_alignment`'s tier-2 `NotImplementedError` — unreachable by construction, not just by sequencing.**

Traced every call site: `attack_run.decide` is the *only* caller of `render_alignment`, and it
passes `tier=1` as a hardcoded literal — there is no parameter, branch, or state field anywhere
that could make it pass `2`. `drain_attack_run` (unwired) calls only `decide`. No other code in
either subproject calls `render_alignment` at all except the test that explicitly expects the
`NotImplementedError`. So the guard cannot be reached from any live path today, independent of
Stage 5/6 sequencing — it is unreachable by construction, which is better than the brief's
question assumed.

One real improvement available, offered as optional: `tier: int` could be narrowed to
`tier: Literal[1]` now (widened to `Literal[1, 2]` when Stage 6 adds the second branch), which
would make the guard a type error at the call site rather than a runtime raise, and is a one-line,
structurally cheap change.

**4. `body-layer/CLAUDE.md` in the diff — belongs.**

The diff adds three "Module map" entries documenting new files this feature introduces
(`attack_run.py`), the new `tasks.py` `TaskKind`, and the new `attack_target_task` on `tools.py`.
This is the same category as the `docs/STRUCTURE.md`/`ROADMAP/BL-14.md` registrations the
implementer also made — documentation of the feature's own new surface, not cross-cutting
bookkeeping unrelated to this milestone. It belongs in these commits per `AGENTS.md`'s own
distinction (cross-cutting convention edits take their own worktree; documentation of a feature's
own new modules does not).

Minor, optional: `BL-14.md`'s top checkbox still reads `[ ] ... NOT STARTED` even though a
"2026-10-14 update — Stages 1-3 implemented" section was appended below it. The appended section
does answer CLAUDE.md's Milestone Completion question ("does not change what the next milestone
should be"), but the stale top-line status is a minor accuracy gap for the next reader skimming
just the checkbox. Not required — BL-14 genuinely isn't done yet.

**5. The three singled-out tests — present, and mutation-confirmed to fail when broken.**

- **Oblique heading + banked case**
  (`test_decide_oblique_heading_and_banked_ownship_does_not_mix_axes`): present. **Mutated**
  `_tier1_alignment` to route through `body_relative_direction(..., bank_deg=ownship.bank_deg)`
  instead of `alignment_direction` (i.e. reintroduced exactly the bank-mixing bug the plan's
  Decision 3 exists to prevent). Result: `level[0]` (13.93°) vs `banked[0]` (6.32°) — the test
  failed immediately with the expected assertion. Restored the file; suite green again (18/18 in
  `test_attack_run.py`).
- **9°-heading-apart re-rotation pin**
  (`test_decide_re_rotates_against_current_heading_not_the_observed_one`): present. **Mutated**
  `_tier1_alignment` to undo yaw using the *current* heading instead of the heading recorded at
  the observing poll (defeating the whole point of carrying an offset rather than a frozen angle).
  Result: `az_a - az_b` collapsed from the expected `9.0°` to `0.0°` — the test failed with the
  exact diagnostic. Restored; suite green.
- **Banked case is covered by the same test as the oblique-heading case** (one function,
  `heading_true_deg=37.0` plus `bank_deg=0.0` vs `bank_deg=60.0`), satisfying both the "oblique"
  and "banked" requirements in one assertion pair — not two separate tests, but both conditions
  are genuinely exercised, confirmed by the mutation above which only the banked half of that test
  would have caught.

Both mutations were reverted (`git diff --stat` confirms no residual change to `geometry.py` or
`attack_run.py`), and the full `test_attack_run.py` suite was re-run clean afterward.

### Specification-rule trace (direction document → code)

All verified directly against the acceptance document's §§1–11, not the plan's paraphrase:

- **Qualitative only, no degrees in spoken strings** — confirmed: `render_alignment`'s phrases are
  all from the word tables (`"come left"`, `"a bit right"`, `"higher"`, `"a little lower"`,
  o'clock words). No `f"{deg}"` or numeric interpolation anywhere in the rendered text.
- **Silence is the signal; one `"lined up"`, then nothing** — confirmed via
  `test_decide_dead_ahead_and_level_lines_up_and_speaks_once` and `_should_emit`'s change-driven
  gate (text-or-threshold, baselined against the last *spoken* value, not the previous sample —
  §10's own named slow-drift guard).
- **Range spoken once, never again** — `render_target_readback` deliberately omits range
  (`"Target, armour, 2 o'clock."`), with the full readback including range correctly deferred to
  `engage`'s own Stage-5 readback per its own docstring. Correct staging, not an omission.
- **Aligned is the conjunction of azimuth band and elevation gate** —
  `render_alignment`: `"Lined up."` only when *both* `_alignment_phrase_for` calls return `None`.
  Confirmed directly and by `test_render_alignment_elevation_only_fires_without_azimuth_word`.
- **Fine-grained elevation reachable by parameter alone, one helper, same table shape both axes** —
  confirmed by `test_both_axes_share_one_table_lookup_helper`, which swaps in a two-row elevation
  table and gets the finer phrase with no renderer change. `_alignment_phrase_for` is the one
  shared helper; nothing branches on "the vertical axis is coarse."
- **Three constants, one place, named, with reasoning, nobody tuned them** — all three
  (`ATTACK_RUN_LINED_UP_AZIMUTH_DEG=5.0`, `ATTACK_RUN_ELEVATION_GATE_DEG=10.0`,
  `ATTACK_RUN_CHANGE_THRESHOLD_DEG=3.0`) declared once in `attack_run.py` with extensive
  docstring reasoning tracing to the plan's Decision 11/11 REVISED, and pinned unchanged by
  `test_the_three_constants_are_unchanged_assumptions` — exactly the plan's proposed values.
- **`silence` mutes guidance, no exemption (§16)** — `drain_attack_run` calls `self._print`
  (no `bypass_gate=True`), which is the ordinary channel every other speech line goes through and
  which `self.silenced` already gates. No special-casing needed or added; correct by reuse.
- **No world-model elevation query (§17)** — confirmed: `_tier1_alignment` takes the target's own
  altitude from `Cluster.centroid_alt_m`/`percept.ownship_at_observation`, never from
  `geometry.elevation_at`. No new world-model call site in this diff.

### Other checks

- **Module responsibility**: `belief.speech` has zero import of `belief.attack_run` (confirmed by
  grep); `belief.attack_run` imports `render_alignment`/`OutgoingSpeech` from `belief.speech` and
  passes its own word tables in as data arguments — no circular import, exactly as the
  implementation notes claim, and I verified the import statements directly rather than trusting
  the claim.
- **No invariant violations found**: no DCS-install writes; no unverified forum/community claims
  encoded as fact; the one new perception datum (`RelativeDirection`) is produced in `perception/`
  and crosses the belief boundary through `percept_of` exactly like every other field, preserving
  the no-omniscience boundary's existing shape rather than adding a second path around it.
- **New files staged**: confirmed via the fast-forward diffstat and `git status --porcelain`
  (clean) — all new files (`attack_run.py`, `test_attack_run.py`, `group_view.py`,
  `test_group_view.py`, `crew_console.py`'s `group-collapse`-era additions, etc.) are committed on
  the branch already; nothing left to stage.
- **Leftover debug code / TODOs**: none found in the diff's new code. The one explicit, documented
  gap (watched-only callouts enrolling the attack-run target before Decision 5's Stage-5
  suppression gate lands) is called out in `implementation.md` and traced to the plan's own
  staging — a stated, deliberate gap, not an oversight.
- **Parallel-treatment grep check** (the standing check from this role's own memory): grepped for
  `relative_direction_set` (detection_trace's own call site) and `perturbed_relative_direction`
  (the new mechanism's own call site) rather than trusting the file list — both are wired at
  exactly one call site each, in `naked_eye_source.py`, matching the plan's single-channel scope
  (the naked-eye channel is the only one with a geometric gate chain to instrument; the
  scope/hybrid channel correctly gets neither, per `body-layer/CLAUDE.md`'s own note on why the
  detection trace is naked-eye-only).

### Required Fixes

None.

### Optional Refinements

- Narrow `render_alignment`'s `tier: int` to `Literal[1]` now (future `Literal[1, 2]` at Stage 6),
  turning the tier-2 guard into a type error rather than a runtime `NotImplementedError` at the
  one call site that could ever pass the wrong value. Cheap, and strictly stronger than what
  exists; not required because the guard is already unreachable by construction, verified above.
- Update `BL-14.md`'s top-line checkbox/status word (still `NOT STARTED`) now that Stages 1–3 are
  implemented, so a reader skimming only the checkbox doesn't contradict the appended update
  section below it. Cosmetic; the milestone genuinely isn't complete.

### Verdict

**APPROVED**

### Review Confidence

Full read of the plan, the acceptance direction document, the implementation notes, and every
changed source file in both touched subprojects. All four verification gates run directly from
inside each subproject against this worktree's own `src` (confirmed by import resolution before
running). Both of the two highest-risk pinned tests (re-rotation, bank-stabilisation) were
mutation-tested from source, not read-and-trusted: each failed with the expected diagnostic when
the mechanism it claims to protect was reintroduced as a bug, and each was cleanly reverted
afterward. The grep fence was mutation-tested the same way. No part of this review rests on the
implementer's account alone where a cheap independent check was available.

---

## Stage 4–5 review (2026-10-14, second pass)

**Scope**: `step` (Stage 4) and wiring the guidance loop — `engage`/`disengage`, tier 1 only, the
gaze claim, the suppression gate, the speech-log fields (Stage 5) — plus the two carried-over
refinements from the Stage 1–3 pass (`Literal[1]` on `render_alignment`'s tier; `BL-14.md`'s status
line). **Stage 5 is this feature's acceptance sortie.** Stages 6–7 (tier 2, projected position) are
correctly absent — `render_alignment`'s `tier` parameter is now `Literal[1]` at the type level, and
`decide()` still hardcodes `tier=1` with no caller ever able to pass `2`.

### Address

Reviewed at `feature/bl14-attack-run` tip `67d08f45dab18022212f08c96e91b9cbbe2475c6`. Worktree HEAD
(`f25c57c…`, from an unrelated prior task — forest-occlusion Stages 1–2) was a strict ancestor of
the named tip with a clean tree; fast-forwarded with `git merge --ff-only 67d08f4`, confirmed by
`git rev-parse HEAD` afterward.

### Verification — run myself

**body-layer/** (resolving `body-layer/.venv/bin/{ruff,mypy,pytest}` by absolute path from the main
checkout, confirmed resolving to *this* worktree's `src` via `pytest --collect-only` before running
anything for real):

- `ruff format --check src tests`: pass (126 files already formatted)
- `ruff check src tests`: pass
- `mypy src`: `Success: no issues found in 58 source files`
- `pytest tests -q`: **1820 passed, 4 xfailed** — matches the implementer's report exactly

**audio-adapter/** (same pattern):

- `ruff format --check src tests`: pass (29 files)
- `ruff check src tests`: pass
- `mypy src`: `Success: no issues found in 15 source files`
- `pytest tests -q`: **277 passed, 1 skipped** — matches the implementer's report exactly

### The six specific checks — findings

**1. `step` recomputes from ownship's present position, every press — confirmed by mutation, not
reading.** `_handle_step` reads `facts["relative_now"]` (world-anchored belief) fresh via
`describe_contact` on every call, for both the current target and every candidate; nothing is
sorted or cached outside the call. I mutated `_handle_step` to memoize the scored ordering in an
instance-level cache keyed on `(current_id, direction)` — exactly the "sort once, index into it"
bug the task names — and re-ran
`test_step_recomputes_order_from_ownships_present_position`: it failed immediately
(`CONTACT_3 != CONTACT_2`, the cached ordering surviving ownship's move to the far side of the
formation). Reverted; suite green again. The test's own fixture construction (mirror-flip vantage
point, verified against `signed_angular_delta_deg` before the fixture was written per
`implementation.md`) is sound and matches the exact pylon-turn case the user's words describe.

**2. The suppression gate — both halves confirmed by mutation.** `CalloutScheduler.tick` suppresses
`_WATCHED_ONLY_KINDS` only for the event whose `contact_id` equals `attack_run_target_contact_id`,
via `_consumed.add` (lost, not deferred, matching `WATCH_REPORT_MIN_GAP_S`'s own treatment). I
verified both halves by mutation, not by reading the two existing pinned tests:
- Confirmed `test_attack_run_target_never_speaks_a_range_crossing` and
  `test_attack_run_suppression_is_narrow_to_the_one_contact_id` both pass as-is.
- Mutated the gate to `if attack_run_target_contact_id is not None:` (suppressing *every*
  watched-only event whenever a run is active, not just the named contact's) — the narrow test
  failed immediately (`['BMP-2.'] != ['Getting closer, BMP-2.']`), proving the narrow-scope claim is
  load-bearing rather than redundant. Reverted; suite green.

**3. Ordering/occupancy — one required fix found here, by direct reproduction.** `drain_attack_run`
runs immediately before `drain_events` in `_run_crew_text_poll_loop` (confirmed by reading
`logger.py`'s poll body directly, not the docstring's claim), and `drain_events`'s own
`CalloutScheduler.tick` returns `[]` without consuming anything when `now_sim < busy_until_sim` —
so a guidance line that wins the tick genuinely defers the scheduler's own candidates rather than
dropping them, matching Decision 1. **But the reverse direction is broken**: when the channel is
already busy *at the moment guidance itself wants to speak*, `drain_attack_run` correctly skips
`_print` (per `if speech is not None and now_sim >= self.scheduler.busy_until_sim`), but it still
`return`s `decide_attack_run`'s `new_state` unconditionally — and that state has already had
`last_spoken_azimuth_deg`/`last_spoken_elevation_deg`/`last_spoken_text` updated by `decide()`
*as if the line had been spoken*, because `_should_emit`'s change-driven baseline is computed before
the caller ever checks occupancy. The result: a guidance change that arrives while the channel is
busy is marked "spoken" without ever being printed, and `_should_emit` will not fire again unless
the geometry drifts *further* than the already-recorded (fictitious) baseline. **This is lost, not
deferred — the one failure mode Decision 1 explicitly claims cannot happen.**

Confirmed by direct reproduction, not by reading: built a `Contact` with a tier-1
`RelativeDirection` 100 m right of boresight (an azimuth error large enough to speak "a bit right"),
set `console.scheduler.busy_until_sim` ahead of `now_sim`, and called `drain_attack_run` twice —
once busy, once free with unchanged geometry:

```
after busy tick: state = AttackRunState(last_spoken_azimuth_deg=5.71, ..., last_spoken_text='A bit right.')
printed so far: []
after channel freed, unchanged geometry: state = AttackRunState(last_spoken_azimuth_deg=5.71, ..., last_spoken_text='A bit right.')
printed so far: []
```

The line is never spoken, in either call, even once the channel frees. No test in this diff
exercises `drain_attack_run` against a busy scheduler at all (`grep -n busy_until_sim
tests/test_attack_run.py tests/test_crew_console.py` finds nothing attack-run-shaped). This is not
a rare edge case: the `engage` readback itself (`"Attack run, armour, 2 o'clock, 1.5 kilometres."`)
occupies the channel for several seconds right as the aircraft is mid-turn-in — exactly when the
first azimuth correction is most likely to be due — so the very first guidance line after `engage`
is a realistic casualty, and the pilot gets silence where design A promises either a correction or
`"lined up"`.

**Required fix**: `drain_attack_run` must only commit `new_state`'s "spoken" fields when the line
was actually printed; when occupancy suppresses the print, it must keep the *previous* state (or an
equivalent "pending" marker) so the same change is re-offered once the channel frees, rather than
being silently absorbed into the baseline.

I found no corresponding problem on the "guidance starves the scheduler" direction: because emission
is change-driven (most polls produce no speech at all), and an injected urgent call
(`bypass_gate=True`) bypasses `drain_attack_run` entirely and calls `note_urgent`, which forcibly
resets `busy_until_sim` rather than reading it — an urgent callout cannot be starved by a guidance
line that is already in flight.

**4. The gaze claim is bounded to the run — one required fix found here, also by direct
reproduction.** `disengage` works correctly: `_handle_disengage` sets `attack_run_transition =
"disengage"`, and the poll loop applies it to `runner.attack_run_state = None` before the next
`_active_gaze` call, which reads `attack_run_engaged=self.attack_run_state is not None` fresh every
poll. Decision 13's vanished-contact path also works: `drain_attack_run` returns `None` directly
when the contact record has vanished.

**`drop target` (and the generic `cancel`/`stop` all-kinds path) do not.** `_handle_drop_target`
delegates to `_handle_cancel_task(kinds=("attack_target",))`, which cancels the `PendingIntent` in
the task store but never touches `attack_run_transition` or `runner.attack_run_state`. On the next
poll, `drain_attack_run`'s own guard —

```python
target_task = self._active_attack_target_task()
if target_task is None or target_task.contact_id is None:
    return state
```

— returns the **unchanged, still-non-`None`** `state` once the task is gone, rather than `None`.
`runner.attack_run_state` therefore stays permanently non-`None` after a bare `drop target` (no
`disengage`), and `attack_run_engaged` stays `True` on every subsequent poll. This does not strand
the gaze on a stale contact, because `_active_gaze`'s own branch re-resolves the *live* task from
`tasks.tasks` each call and falls through to the ordinary scan logic when none is found — so nothing
breaks immediately. But it means the engaged flag is now permanently stuck "on" for the rest of the
session (or until the next explicit `engage`), and the very next unrelated `select target` — issued
with no `engage` at all — inherits it.

Confirmed by direct reproduction: `engage`d `CONTACT_1`, confirmed `_active_gaze` returns a
`fixed_look`; `drop_target`; confirmed `attack_run_transition` stays `None` and `drain_attack_run`
returns the same non-`None` state; then created a *new* `attack_target` task for `CONTACT_2` with no
`engage` at all, and called `_active_gaze` again with the stale (never-cleared) `attack_run_engaged`
flag:

```
gaze plan after re-select WITHOUT engage (should be FREE_SCAN_PLAN, NOT fixed_look):
ScanPlan(..., fixed_look=Gaze(center_azimuth_deg=0.0, ...))
BUG? True
```

A `select target` the pilot never followed with `engage` claims the gaze and stops scanning
elsewhere — exactly the cost Decision 9 REVISED says is paid only "for the run's duration," now paid
for a selection that was never run. No test in this diff exercises the drop-target-then-reselect
sequence; the existing `_active_gaze` tests all pass `attack_run_engaged` as a literal bool directly,
never exercising whether `runner.attack_run_state` itself gets reset on this path.

**Required fix**: `drain_attack_run` should treat "the standing task is gone" the same way it
already treats "the contact record is gone" — return `None`, not the unchanged `state` — so
`drop target`/the all-kinds cancel path end the run's phase (and the gaze claim with it), not only
the selection.

**5. Tier 2 unreachable, and no-fresh-observation silence — confirmed.** `render_alignment`'s `tier`
parameter is `Literal[1]` (`speech.py:563`); `decide()`'s only call site passes the literal `1`
(`attack_run.py:231`); no other call site exists in either subproject except the one test that
pins the (now type-checked-away) `NotImplementedError`. `_tier1_alignment` returns `None` when
`contact.last_percept.relative_direction is None` or the percept has aged past
`ATTACK_RUN_RELATIVE_MAX_AGE_S`, and `decide()` returns `(state, None)` unchanged in that case —
holding the last spoken state and staying silent, with no exception path. Confirmed by reading the
full `_tier1_alignment`/`decide` bodies directly, not by trusting the docstring.

**6. Decision 13's end conditions.** `render_lost_contact` speaks once: `drain_attack_run`'s
`if state is None: return state` guard at the top means a second call after the contact vanished
returns immediately without re-entering the lost-contact branch, so the line cannot repeat across
polls. The task is genuinely cancelled (`cancel_task(self.store, self.tasks, target_task.id)` before
the print), confirmed directly by the existing
`test_drain_attack_run_ends_the_run_when_the_contact_record_vanishes`, which asserts
`target_task.status == "cancelled"` — read and additionally exercised (passes as-is).

### The flagged gap — judged

**Declining the `attack`/`attack-run` synonym was the right call, and the case for it is slightly
stronger than reported.** Independently recomputed: `difflib.SequenceMatcher(None, "tanks",
"attack").ratio() == 0.5454545454545454` and `...("trucks", "attack").ratio() == 0.5` — both
confirmed exactly as stated. One sharpening: `command_matcher.py`'s actual floor check is `if
best_ratio < VERB_FLOOR: ...` (strict less-than, `VERB_FLOOR = 0.5`), so `"trucks"` at *exactly*
`0.5` would **not** be rejected either — it is not merely "right on the floor" but on the side that
passes. There is no currently-pinned adversarial test for `"trucks"` the way there is for
`"the tanks are on the ridge"`, so this is not a second broken test today, but it means the
real collision surface admitting `attack`/`attack-run` would open is at least two ordinary common
nouns wide, not one. This is scope judgment, not a defect: `BL-14`'s own vocabulary (`engage`,
`engage target`, `disengage`, `stop attack`, `abort`) is unaffected, the gap against the spec
document is recorded in two places in the source (`vocabulary.PHRASES["engage"]`,
`command_matcher._ENGAGE_VERBS`) rather than silently dropped, and resolving it (a differently-worded
anchor, or accepting the adversarial-test regression) is exactly the kind of call `AGENTS.md`'s
Escalation Rules route to the user/Architect, not to an implementer mid-pass. **Correctly deferred,
not a required fix.**

### Specification rules traced against the direction document

- **Qualitative only, no degrees** — `render_engage_readback`/`render_attack_run_off` add no numeric
  interpolation; range in the engage readback uses `_format_range_km` (already qualitative-safe,
  rounds to 0.5 km) exactly once, per §1/the vocabulary table.
- **Silence is the signal** — unchanged from Stage 1–3; Stage 5 wires it into the live loop but adds
  no second emission path.
- **Range spoken once** — `render_engage_readback` is the only place range is spoken for an
  engage/select sequence; `render_target_readback` (used by `step`'s own readback) still omits it,
  confirmed by reading both templates directly.
- **Aligned is the conjunction** — unchanged mechanism from Stage 3; Stage 5 does not touch
  `render_alignment`.
- **Cadence baseline is the last spoken value** — `_should_emit` unchanged; the bug in finding 3
  above is precisely a violation of this contract's *precondition* (that "last spoken" means
  "actually printed"), not a change to the comparison logic itself.
- **Terrain reference stops at `"lined up"`** — unaffected by this stage (renderer-level, already
  verified Stage 1–3).
- **`silence` mutes guidance, no exemption, and a run cannot begin while muted** — confirmed
  directly: `handle_command` clears `self.silenced = False` for every token except `"silence"`
  itself, dispatched *before* `_handle_engage` sets `attack_run_transition = "engage"` — so `engage`
  always clears silence first, meaning a run genuinely cannot begin while muted (the only reachable
  case is muting mid-run, which `_print`'s existing `if self.speech_client is not None and not
  self.silenced` gate already handles with no special-casing, exactly as the plan claims).
- **Three constants are unchanged agreed guesses** — `ATTACK_RUN_LINED_UP_AZIMUTH_DEG = 5.0`,
  `ATTACK_RUN_ELEVATION_GATE_DEG = 10.0`, `ATTACK_RUN_CHANGE_THRESHOLD_DEG = 3.0`,
  `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` — all re-confirmed by grep against their declarations; none
  retuned in this pass.
- **The speech log carries target/tier/both axis errors per utterance** — confirmed end to end:
  `drain_attack_run` passes `attack_run_fields` into `_print`; `_print` forwards it to
  `speech_log_sink`; `logger._speech_log_sink`'s closure forwards the four fields into
  `BeliefTruthLogWriter.write_speech`'s new keyword arguments, which conditionally add each to the
  written row only when not `None`. Traced the whole chain by reading every hop, not just the two
  endpoints.

### Verification of the implementer's `mypy tests` characterisation — partially inaccurate

The claim ("every reported line in `test_speech.py`/`test_crew_console.py`/`test_logger.py`/
`test_callouts.py` that is not one of this pass's own new lines was already failing before this
branch") was checked by diffing `mypy tests` output against the pre-Stage-5 commit (`5d96d62`), not
accepted. For the four files it names, the claim holds: the three new `# type: ignore[attr-defined]`
lines (`test_crew_console.py:4402,4410,4845`) produce the same "Unused type: ignore comment" noise
the pre-existing precedent (`test_callouts.py:651`) already produces in the base commit too — not a
new category of problem.

**But the claim's own file list is incomplete.** `mypy tests` reports one genuinely new error not
present in the base commit and not in any of the four named files:

```
tests/test_attack_run.py:361: error: Argument "tier" to "render_alignment" has incompatible type
"Literal[2]"; expected "Literal[1]"  [arg-type]
```

This is a direct, mechanical consequence of this pass's own `Literal[1]` narrowing (the carried-over
Stage 1–3 refinement) — `test_attack_run.py` itself has no diff in this range
(`git diff 5d96d62..67d08f4 -- body-layer/tests/test_attack_run.py` is empty), so the line didn't
change; the type of what it calls did. Low-stakes (`mypy tests` is not a mandated gate per
`body-layer/CLAUDE.md`'s Commands section, same footing the Stage 1–3 review already noted), and the
test itself still passes under `pytest` (it is asserting a runtime `NotImplementedError`, which the
type narrowing does not prevent at runtime — only at the type-checker level). Not a required fix,
but the self-report should have said "the four files above, plus one new tier-2 type error in
`test_attack_run.py` from this pass's own `Literal[1]` change" rather than implying completeness.

### Required Fixes

- **`drain_attack_run` commits "spoken" state even when occupancy suppresses the actual print**
  (finding 3) — a guidance change arriving while the channel is busy is marked spoken and never
  re-offered, which is lost, not deferred, directly contradicting Decision 1's own stated guarantee.
  Confirmed by direct reproduction (busy tick → state updated, nothing printed; freed tick, unchanged
  geometry → still nothing printed). Fix: only commit the "last spoken" fields when the line was
  actually printed; otherwise carry the previous state forward so the same change is re-offered once
  the channel frees.
- **`drop target` (and the generic all-kinds `cancel`/`stop` path) cancel the standing task but
  never clear `runner.attack_run_state`**, so the engaged flag survives and a subsequent
  `select target` with no `engage` wrongly inherits the gaze claim (finding 4). Confirmed by direct
  reproduction (engage CONTACT_1 → drop target → select CONTACT_2 with no engage → `_active_gaze`
  still returns a `fixed_look`). Fix: `drain_attack_run` should return `None`, not the unchanged
  `state`, when the standing task is gone (cancelled), the same treatment it already gives a
  vanished contact record.

### Optional Refinements

- The `mypy tests` self-report should name `test_attack_run.py`'s one new tier-2 type error
  alongside the four files it already lists, rather than implying the characterisation is complete
  for the whole diff. Not required — `mypy tests` is not a mandated gate.
- `attack`/`attack-run` synonym gap: no action needed now; correctly deferred to the user/Architect
  per the Escalation Rules, with the collision surface now confirmed slightly wider (two ordinary
  nouns, not one) than the implementer's own note stated.

### Verdict

**NEEDS REVISION** — two required fixes, both confirmed by direct reproduction against this
worktree's own code, not by reading. Everything else in Stage 4–5's scope (the `step` ordering
primitive, the suppression gate's narrow scope, tier-2 unreachability, Decision 13's end conditions,
the spoken-vocabulary/spec trace, the three constants, the speech-log wiring, and the
`attack`/`attack-run` deferral) checked out clean under the same standard. Given `AGENTS.md`'s
"A change request ... re-enters the loop" rule, these two fixes should go back through
Implementer → Reviewer (of the fix) → DoD, not straight to DoD or to the user's acceptance sortie —
the acceptance sortie flown before the busy-gate fix would risk measuring a run with an intermittently
silent guidance channel and attributing it to the tuned constants rather than this mechanism.

### Review Confidence (Stage 4–5)

Full read of the plan's Stage 4/5 sections, the direction document, `implementation.md`'s own
Stage 4/5 summary, and every changed source file in both subprojects (`crew_console.py`'s new
`_step_candidates`/`_handle_step`/`_handle_engage`/`_handle_disengage`/`drain_attack_run`,
`callouts.py`'s suppression gate, `logger.py`'s `_active_gaze` branch and poll-loop wiring,
`tasks.py`/`tools.py`'s `descriptor` threading, `voice_commands.py`'s cancel-token additions,
`belief_truth_log.py`'s new fields, and both audio-adapter files). All four verification gates run
directly from inside each subproject against this worktree's own `src`. Both required fixes were
found and confirmed by **direct reproduction against the real code** (not by reading, and not by
trusting the implementer's tests, which do not exercise either scenario) — a standalone script built
a real `Contact`/`CrewConsole`/`TaskStore` and drove `drain_attack_run`/`_active_gaze` through the
exact sequences described, with printed output showing the defect each time. The `step`-recomputation
claim and the suppression gate's narrow scope were both confirmed by mutation of the source, with
each mutation reverted afterward (`git status --porcelain` on `crew_console.py`/`callouts.py` is
clean). The `mypy tests` characterisation was checked by diffing the full tool output against the
pre-Stage-5 commit, not accepted at face value.

---

## Stage 4-5 fix review (2026-10-14)

Reviewed the two required-fix commits at `feature/bl14-attack-run` `1b62a3b10826fab1a087cb4ef1192db000c61a34`
(fast-forwarded cleanly from this worktree's stale base `f25c57c`, which was a strict ancestor — no
divergence, no cherry-pick needed). Diff scope: `body-layer/src/belief/crew_console.py`
(`drain_attack_run` only), `body-layer/tests/test_crew_console.py` (4 new tests + one local helper),
`plans/attack-run/implementation.md` (an appended "Stage 4-5 review fixes" section). No other file
touched.

### Both findings, re-reproduced against the fixed code

**Finding 1 (occupancy falsely committed `last_spoken_*`).** Reproduced the original busy-then-free
sequence directly (no test harness) against the fixed `drain_attack_run`: a contact 100m right of
boresight at 1000m, `busy_until_sim` set ahead of `now_sim`. Fixed behaviour: nothing printed, the
returned state is `AttackRunState()` (unchanged baseline) rather than the falsely-advanced one the
pre-fix code returned. Confirmed the fix, not just the test.

**Finding 2 (`drop target`/generic `cancel` left the gaze claim set).** Read the single-guard fix at
`crew_console.py:2219-2232`: the "task is gone" branch now returns `None` (was `return state`),
routing through the same `runner.attack_run_state = None` assignment the vanished-contact branch and
`disengage` already used. Confirmed via mutation (below) rather than by reading alone.

### Mutation testing (not reading, not trusting the new tests)

Reverted each fix in turn on this worktree's own checkout, ran the full `drain_attack_run` test
selection, then restored (`git status --porcelain` on `crew_console.py` clean after each revert):

- **Fix 1 reverted** (`return state` → `return new_state` on the occupancy path): both
  `test_drain_attack_run_reoffers_the_line_once_the_channel_frees` and
  `test_drain_attack_run_first_utterance_after_engage_survives_a_busy_channel` failed exactly as
  claimed — `busy_state` carried `last_spoken_azimuth_deg=5.710593137499642`,
  `last_spoken_text='A bit right.'` though nothing was printed. The other 4 `drain_attack_run`
  tests (both Fix 2 tests included) stayed green: **2 failed, 4 passed**, matching the
  implementer's own account exactly.
- **Fix 2 reverted** (top-of-function guard `return None` → `return state`): both
  `test_drain_attack_run_ends_the_run_after_drop_target` and
  `test_drain_attack_run_ends_the_run_after_the_generic_cancel_task` failed on
  `assert result is None`, returning the stale non-`None` `AttackRunState` instead. Same split:
  **2 failed, 4 passed**.

Both reversions matched the implementer's "Fail-then-pass evidence" section verbatim. The
fail-then-pass claim is verified, not merely accepted.

### Check 2 — "dropped, not queued"

Confirmed against `decide()` (`attack_run.py`): `decide` returns `(state, None)` unchanged — never a
partially-advanced state — whenever either tier 1 has no fresh alignment (`_tier1_alignment` is
`None`) or `_should_emit` says no. It only ever returns a *new* state together with non-`None`
speech. So `drain_attack_run`'s `speech is None` branch (`return new_state`) is always a no-op
returning the same object as `state`, and the occupancy branch's `return state` is the only place
that needed fixing — there is no third path that could leak an advanced-but-unspoken state. Dropping
rather than queuing is correct given the stated constraint (no deferral machinery on the reply lane);
since `decide` re-derives from live geometry every tick with no memory of "what it meant to say," a
dropped line is always re-offered the instant the channel frees, provided the input data is still
fresh — which is exactly where the real risk turns out to live (see "Readback-occupancy interaction"
below), not in the drop/queue choice itself.

### Check 3 — soundness across every path

Traced `AttackRunState | None` through all five return points: `state is None` guard (early
`return state`, a `None` stays `None`); the task-gone guard (now `return None`); the vanished-contact
guard (`return None`, unchanged by this fix); `speech is None` (`return new_state`, always `≡ state`
per Check 2); the occupancy split (`return new_state` when printed, `return state` when suppressed).
No two of these can both apply to the same call — each is a distinct `if`/`elif`-shaped branch,
mutually exclusive by construction, not an ordering question. No state value is reachable that mixes
"task gone" with "advanced-but-unspoken": the task-gone guard returns before `decide_attack_run` is
even called. Sound.

### Readback-occupancy interaction — superseded by user direction mid-review

The brief asked me to test the implementer's "harmless live, fixture-only" framing of the ~5s
readback vs. 2.0s `ATTACK_RUN_RELATIVE_MAX_AGE_S` gap. User direction landed during this review
(2026-10-14) settling part of that question and raising a new required item. Recording both what I
found and what changed:

**What I confirmed by direct reproduction (not by reading).** Built a real `Contact`/`TaskStore`/
`CrewConsole` with the percept frozen at `t_sim=0.0` and `busy_until_sim=6.0` (standing in for a
readback plus the new 1s gap, see below), then called `drain_attack_run(AttackRunState(), now_sim=6.0,
...)`. Result: nothing printed, state returned as `AttackRunState()` — correctly silent, not falsely
marked spoken. This is **not** the same defect class as Finding 1: Finding 1 was a state wrongly
advanced past what was actually heard; this is `decide()`'s documented Stage-3/5 behaviour ("silence,
holding the last spoken state... exactly as Stage 5 describes for a run flown before tier 2 exists")
correctly doing nothing when it has nothing fresh to guide on. Separately confirmed that as long as
gaze/LOS/FOV hold continuously, `NakedEyePerceptionSource` refreshes `Contact.last_percept.t_sim` on
every 1Hz poll regardless of how long the speech channel stays busy (`runner.run_once()` in
`_run_crew_text_poll_loop` runs unconditionally, not gated on `busy_until_sim`) — so the percept's
*age* at the moment the channel frees depends on whether LOS broke at some point during the busy
window, not on how long that window was. The implementer's "re-observes every poll" claim holds for
the continuously-visible case; the gap is specifically an LOS blip during the busy window with no
recovery before the next poll, which produces one tick of (correct, self-correcting) silence rather
than a lost callout — the run is not ended and the next successful observation is spoken immediately
against the still-unmoved `None` baseline. **Not a required fix**: it is an accepted, pre-existing
tier-1-only limitation (tier 2/"obstructed" is Stage 6), not something this patch introduced or
worsened in kind — though the new 1s delay below does widen the exposure window somewhat, since it
lengthens how long an LOS blip has to occur within to matter. Worth one line in the plan's Risks
section so a flight that hears nothing on the first callout is read correctly rather than as a
mystery; not worth gating this fix on.

**What changed under me: a pre-existing mechanism already does most of what the new instruction
asks.** `CalloutScheduler.note_reply` (`callouts.py:817-839`) already extends `busy_until_sim` by
`estimate_speech_duration_s(text) + INTER_UTTERANCE_GAP_S` (0.75s) for *every* reply, including
`engage`'s own readback (`handle_command` calls `self._print(lines, now_sim)` unconditionally at its
end, and `_print`'s non-`bypass_gate` branch calls `note_reply` for every line). `drain_attack_run`'s
existing `now_sim >= self.scheduler.busy_until_sim` gate therefore **already** waits for "readback
done, plus a breathing gap" before the first guidance line — this is not new mechanism to build, it
is already wired, and already general (every reply, not attack-run-specific). The user's "add a 1s
delay after that also" is a ~0.25s calibration gap above what already exists, not a missing feature.

**My read on placement, since I was asked for it.** Keep it general, in `callouts.py` beside
`INTER_UTTERANCE_GAP_S`/`SPEECH_RATE_WPS`/`MIN_UTTERANCE_S` — not attack-run-local, and not a new
constant in `attack_run.py` alongside its three deliberately-unset *geometry* constants (those are
about alignment/cadence, not channel pacing; mixing a scheduling constant in would blur the module
boundary `docs/STRUCTURE.md` draws between the two). Two ways to land it, in order of preference:

1. **Bump `INTER_UTTERANCE_GAP_S` from 0.75 to 1.0.** One constant, no new mechanism, "mechanism and
   calibration never share a commit" stays satisfied (this *is* a calibration-only change). Changes
   spacing after *every* reply, not only `engage`'s — which matches the user's own stated reasoning
   ("Petrovich can only speak one thing at a time... add a 1s delay after that *also*", read as a
   general pacing statement about how a crewman talks, not an attack-run carve-out) and costs
   nothing architecturally. This is what I'd recommend absent a stated reason to keep the general
   gap at 0.75 and add an attack-run-specific extra second on top.
2. **A second, attack-run-specific constant** (lives beside #1 in `callouts.py`, not in
   `attack_run.py`) only if the user wants ordinary replies to keep their current 0.75s spacing while
   guidance specifically waits longer. This needs the scheduler to expose *why* it is busy (a
   reply vs. a routine callout) to let `drain_attack_run` apply the extra second only after a reply —
   `busy_until_sim` alone does not currently carry that distinction, so this path is strictly more
   mechanism than #1, not just a bigger number.

Not reviewing the 1s-delay change itself here — it has not been implemented yet; this is input for
the implementer/architect on where it belongs, per the dispatch.

### Verdict (Stage 4-5 fix review)

**APPROVED**, for the two required fixes as implemented. Both are correct, both were confirmed by
reproduction and mutation (not by reading the new tests and not by trusting the implementer's
account), and nothing outside the stated scope moved — no constant tuned, no tier-2 work, no queue,
no vocabulary edit. The readback-occupancy interaction raised in my brief is not a required fix on
this commit; it surfaces a separate, not-yet-implemented required change (the 1s post-readback delay)
that the user has already decided to dispatch regardless of my verdict here.

### What Performance Reviewer / Security should look at specifically

- **Performance Reviewer**: nothing new on the hot path from this fix itself (one extra `if`,
  returning an existing object rather than constructing one). If the 1s-delay follow-up lands as
  option 2 above (scheduler exposing busy-reason), that is the piece worth a performance look —
  it adds a field read on every `_print` call, trivial, but worth confirming it stays trivial.
- **Security**: nothing in this diff touches I/O, parsing, or trust boundaries — pure in-process
  state transitions over already-validated `AttackRunState`/`Contact` objects. No new surface.

### Review Confidence (Stage 4-5 fix review)

Full read of both changed source files and the implementer's own account in `implementation.md`.
Both required fixes verified by direct reproduction and by mutation-testing each fix independently
(reverted, re-ran, restored, confirmed clean). All four verification gates (ruff format/check, mypy
--strict, pytest) run directly from inside each subproject's own venv against this worktree's `src`
(confirmed by import-path check, not assumed from `pythonpath` config alone) — body-layer **1824
passed, 4 xfailed**; audio-adapter **277 passed, 1 skipped** (untouched, run to confirm no
regression). The readback-occupancy interaction was tested by direct reproduction of the LOS-blip
scenario (frozen percept, `busy_until_sim=6.0`), not accepted from the implementer's fixture-note
framing.

---

## Security fix review — BL-14's stale `attack_target` task on reselection (2026-10-14)

Reviewed `9475af80af7c899bc23e857d483694733ac53ea4` on `feature/bl14-attack-run`. Worktree base
(`f25c57c`) was a strict ancestor of the named tip with a clean tree — fast-forwarded, no
divergence. `git diff 296fa81..9475af8`: `body-layer/src/belief/tools.py` (32 lines),
`body-layer/tests/test_crew_console.py` (6 new tests, 250 lines), `plans/attack-run/
implementation.md` (135 lines), one implementer agent-memory file. Read against `plans/attack-run/
security-review.md`'s "Required fix in detail" and `docs/acceptance/2026-10-14-attack-run-guidance-
direction.md`.

### Findings, each checked by running or mutating rather than by reading alone

1. **The fix itself — closes the finding.** `attack_target_task` now confirms `contact_id` exists
   (no side effect) before cancelling every still-active `attack_target` task and promoting the new
   one. Confirmed by running the six new tests (`pytest -k "reselect or stale"`, 7 passed) and, since
   the task said not to rely on tests written by the fix's own pass, by an independent reproduction
   script against `CrewConsole.drain_attack_run`/`_active_attack_target_task` directly (not kept in
   the tree). **Verified by running.**

2. **The cancel-before-promote ordering claim — verified by mutation, and it is exactly as fragile
   as the implementer says.** Reordered the two operations in `tools.py` (promote, then cancel) and
   reran `test_reselecting_the_same_target_does_not_demote_its_own_attention`: it failed,
   `armor.attention == 'normal'` where the test asserts `'priority'` — a same-contact reselect
   transiently demotes the contact it just promoted, exactly the regression the implementer's note
   describes. Reverted immediately after confirming the failure; current ordering (cancel first,
   confirmed clean) restored and reran to confirm green. **Verified by mutation.**

3. **Every `attack_target` mint point is closed.** Grepped for `kind="attack_target"`/
   `kind='attack_target'`/`tasks.create(` outside `tools.py` — none found; `belief.console`'s dev
   `attack-target <id>` command (line ~401) calls `tools.attack_target_task` itself, the same shared
   primitive. No test helper constructs an `attack_target` `PendingIntent` directly either (the new
   tests all go through `attack_target_task` or `handle_command`). **Verified by grep.**

4. **Attention demotion — pre-existing, not a new leak, confirmed by reading the unchanged code
   path.** `cancel_task`'s demote-to-`"normal"` is untouched by this diff. The group-mate "re-raise
   to `watch`" the implementer describes (`_handle_engage`'s/`_handle_select_target`'s tagging loop,
   `crew_console.py` ~2143–2153) is also untouched by this diff and runs unconditionally after every
   select/engage, independent of whether a reselection happened — so it is accurately described as
   existing behaviour, not something this fix introduces. No path leaves a contact stuck at
   `"priority"` after its task is cancelled: `cancel_task` demotes unconditionally on every
   cancellation, including the ones this fix newly triggers. **Verified by reading** (the code
   this bullet concerns is outside the diff, so there was nothing to usefully mutate).

5. **Mid-run reselection — re-point is the right call for task identity, but it exposes a real,
   separate staleness bug in `AttackRunState` that neither the plan, the security review, nor this
   fix's own implementation note catches.** `AttackRunState.last_known_target_alt_m` (`attack_run.py`)
   is a single run-level field, not per-contact, and `decide()`'s tier-2 fallback
   (`_tier2_alignment`) reads it from the *state passed in*, falling open to "no elevation word"
   only when that field is `None` — which the docstring frames as "no tier-1 look has ever
   succeeded for this contact," but the implementation has no contact identity attached to the
   value at all. Reselecting mid-run (exactly the path this security fix makes a sanctioned,
   silent re-point rather than a refusal) carries the *old* target's remembered altitude into the
   *new* target's first tier-2 tick, if tier 1 has not yet produced a fresh look for it.

   **Confirmed by direct reproduction, not by reading the docstring's claim.** Built two contacts —
   one with a fresh `relative_direction` (tier 1 succeeds, remembered altitude = ownship alt + 500m),
   one with none at all (tier 1 can never succeed for it). Ran `drain_attack_run` on the first,
   captured the returned state (`last_known_target_alt_m=1500.0`), re-pointed the task to the second
   contact, then called `belief.attack_run.decide` directly with the carried-forward state against
   the second contact: it returned `tier=2`, `elevation_deg` computed from `1500.0` — the *first*
   contact's altitude — rendering `"Higher, obstructed."` for a target whose own altitude belief
   has never been observed. The docstring's "`None` only before the very first tier-1 look this
   contact has ever had" is false as implemented; it is "`None` only before the very first tier-1
   look *this run* has ever had," which silently becomes wrong the moment a run survives a
   reselection. (In my own `console.drain_attack_run` call — as opposed to calling `decide()`
   directly — the scheduler's busy-gate happened to suppress the print on the tick I tested, which
   would have hidden this from a test that only exercised the public method at that exact `now_sim`;
   calling `decide()` directly bypassed that and is what actually surfaces the bug.) **Verified by
   mutation/reproduction**, not accepted from the docstring.

   This is **not a defect in this security-fix diff** — `attack_run.py` is untouched by it, and the
   bug predates this round. It is called out here because item 5 of the dispatch asked specifically
   whether re-pointing mid-run leaves anything stale, and the honest answer is yes, in a way the
   implementer's own "Mid-run reselection decision" note does not mention (that note covers task
   identity/attention only). The security fix's own choice — re-point rather than refuse — is what
   makes this latent bug reachable from an ordinary command sequence rather than only from a
   contrived direct call to `attack_run.decide`.

6. **Nothing else moved.** `git diff 296fa81..9475af8 --stat` is four files; no constant, no
   vocabulary, no `CalloutScheduler` change. The optional `field(repr=False)` refinement was
   correctly not taken. **Verified by reading the diff.**

### Verification — run myself

- `ruff format --check src tests`: pass (126 files)
- `ruff check src tests`: pass
- `mypy src` (from `cd body-layer`): `Success: no issues found in 58 source files`
- `pytest -q`: **1838 passed, 4 xfailed** — matches the implementer's reported count exactly
- audio-adapter untouched by this diff (confirmed by file list); not rerun

### Required Fixes

None.

### Suggestions (optional)

- Consider widening `AttackRunState.last_known_target_alt_m`'s fail-open condition so it cannot
  outlive the contact it was observed for — either reset it to `None` whenever the active
  `attack_target` task's `contact_id` changes (the natural hook, since `drain_attack_run` already
  resolves that task every tick), or key the remembered value by contact id. Not required here: the
  bug is pre-existing, outside this diff's files, and not part of the finding this round fixes.

### Verdict

**APPROVE.**

The one required finding from the deep security review is fixed at the correct single mint point,
the fix's own subtle ordering requirement is verified by mutation (not just by reading), every
other reader of "the current target" is confirmed to route through the same now-correct resolution,
and nothing outside the fix's stated scope moved. This clears the Implementer → Reviewer loop for
the security change request; proceed to Definition of Done.

### Flag for Definition of Done

**Put the Finding 5 staleness bug in front of DoD before or alongside the Stage 5/6/7 acceptance
sortie.** It is not a blocker for merging this security fix — it predates this round and is outside
the diff — but DoD is explicitly arranging a sortie covering Stages 5, 6, and 7 together, and this
bug is reachable from an ordinary in-cockpit sequence: `select target X` → `engage` → (while
engaged) `select target Y` → if Y has no fresh naked-eye/HelperAI look within
`ATTACK_RUN_RELATIVE_MAX_AGE_S` (2.0s) of the reselect, the very next guidance tick can speak an
elevation word ("Higher."/"A little lower.") derived from X's altitude, not Y's. On a real sortie
this would most often show up as a wrong-feeling elevation call for one or two ticks right after
switching targets mid-run, before tier 1 catches up — worth either reproducing in the sortie or
filing as a dated backlog item (`BL-B<n>`) rather than letting it surface only as "that callout felt
wrong" with no record of why.

### Review Confidence (security fix review)

Full read of the diff's two source-affecting files plus the console dispatch paths the finding
touches (`crew_console.py`'s `_handle_select_target`/`_handle_engage`/`_active_attack_target_task`/
`drain_attack_run`, `belief/console.py`'s dev command). Both the fix's required ordering and the
mid-run staleness finding were verified by direct mutation/reproduction, not accepted from the
implementer's report or the new tests' passing. `attention`/group-tagging finding (4) was verified
by reading only, since the code it concerns is outside this diff and there was nothing load-bearing
to mutate.

## Staleness fix review (2026-10-14) — `AttackRunState` reset on contact identity change

Reviewed `git diff 4a20b83..aa1e0cf` on `feature/bl14-attack-run` (tip `cf23246`, one capture-only
commit beyond the fix, not part of it). Worktree base (`f25c57c`, forest-occlusion merge) was a
strict ancestor of the named tip with a clean tree — fast-forwarded, no divergence. Files touched:
`body-layer/src/belief/attack_run.py` (+39/-9), `body-layer/src/belief/tools.py` (docstring only,
+13/-1), `body-layer/tests/test_attack_run.py` (+155, three new tests), `plans/attack-run/
implementation.md` (+134), one implementer agent-memory file. Read against this review's own
finding 5 and `docs/acceptance/2026-10-14-attack-run-guidance-direction.md` §25.

### Findings

1. **The fix closes finding 5 — verified by independent reproduction, not the new tests.** Built a
   fresh repro script against `decide()` directly (contact A: tier-1 look, remembered altitude
   1000.0; re-point to contact B: no relative observation at all). Against the fixed code: `new_state.
   last_known_target_alt_m is None`, `speech_b.text == "Lined up, obstructed."` — no elevation word.
   Reverted just the `if state.last_contact_id != contact.id: state = AttackRunState(...)` line (a
   two-line patch, restored afterwards, confirmed by `git status --short` showing no diff) and
   reran the identical script: `new_state.last_known_target_alt_m == 1000.0` carried from A,
   `speech_b.text == "Higher, obstructed."` — a wrong elevation call for a target never observed.
   Fail-then-pass confirmed against the actual bug, independently of the implementer's own tests.
   **Verified by running/mutating.**

2. **The reset's completeness — right shape, and nothing on the dataclass needs preserving across a
   re-point.** All five fields (`last_spoken_azimuth_deg`, `last_spoken_elevation_deg`,
   `last_spoken_text`, `last_spoken_tier`, `last_known_target_alt_m`) are per-contact by the
   implementation note's own audit, and reading each one's use in `decide`/`_should_emit`/
   `_tier2_alignment` confirms none of them describes anything run-level (ownship state, group
   membership, mission phase) rather than this-contact's-last-look. The wholesale-replace shape
   (`AttackRunState(last_contact_id=contact.id)` rather than clearing named fields) is right for
   today, but it is a trap waiting for the next field added to this dataclass: a future field that
   *is* run-level (e.g. a cumulative "ticks spent on this attack run" counter, should one ever be
   added) would be silently discarded by this reset with no test catching it, because the reset's
   correctness is currently accidental (every field happens to be per-contact) rather than
   structural (nothing enforces that a future field must be). Worth a one-line docstring note on
   `AttackRunState` itself ("adding a field here means auditing whether `decide`'s identity-change
   reset should still discard it") — not required now, since no such field exists, but cheap
   insurance against the exact failure mode this finding was. **Verified by reading** (there is
   nothing to mutate against a field that does not exist).

3. **The `last_spoken_tier` structural claim — confirmed true today, confirmed fragile, exactly as
   flagged.** Mutated `belief/speech.py`'s `render_alignment` to drop the `if tier == 2: text =
   f"{text}, obstructed"` line (the one place that guarantees tier-1/tier-2 text never collides).
   Result: `test_last_spoken_tier_cannot_silently_carry_a_wrong_value_across_a_retarget` failed
   immediately (`'Lined up.' != 'Lined up.'`), along with ten other tests across the same file —
   the claim is real and the dedicated test does pin it. Restored the file, confirmed all 29 tests
   in `test_attack_run.py` pass again. **This confirms the argument is true by construction today,
   not by luck** — the dedicated test would catch a future renderer change that reintroduced a
   collision, which is exactly what the implementer's note claims it is for. Note for the record
   (not a fix): this structural guarantee is a property of `render_alignment`, not of the
   identity-change reset — with the reset in place, `last_spoken_tier` is reset to `None` on every
   re-point regardless of whether tiers collide, so the two protections are independent and either
   alone would currently hold the field correct across a re-point. The audit's own framing ("not
   because a distinct reachable bug required it") is accurate. **Verified by mutation.**

4. **The reset point versus `logger.py`'s `engage`-transition reset — not redundant, not
   contradictory, but broader than `decide`'s own trigger in one case worth naming.** Read
   `logger.py`'s poll loop (`crew_console.attack_run_transition == "engage"` branch,
   `runner.attack_run_state = AttackRunState()`) against `_handle_engage`
   (`crew_console.py` ~2104–2167): a **bare** `"engage"` with no target slots — i.e. re-confirming
   the *already-selected, unchanged* target — still falls through to `self.attack_run_transition =
   "engage"` unconditionally at the end of that handler. That means the call-site reset fires on
   every explicit `engage` command, including one that names no new contact at all, whereas
   `decide`'s own reset fires only when `contact.id` actually changes. The two are not
   contradictory (both produce a fresh `AttackRunState` on the overlapping case — an actual
   re-point) and the call-site reset is not dead code (it is the only thing that resets state on a
   same-target re-confirm, a case `decide`'s identity check cannot and should not fire on). But it
   does mean a bare re-`"engage"` on the same target throws away the cadence baseline and spoken
   altitude memory even when nothing about the target changed — read as intentional ("restate the
   current alignment on every explicit engage") rather than a bug, since it predates this diff
   entirely (`logger.py` is untouched by `git diff 4a20b83..aa1e0cf`) and is not part of this
   finding. Flagging per the task's own question: two reset paths for one state is exactly the
   shape that goes wrong later if either is changed without checking the other's trigger condition.
   **Verified by reading**, both handlers, not mutated — this is a pre-existing path outside the
   diff.

5. **Spurious firing — checked, not found.** `ContactStore._new_contact_id` mints a contact id once
   at `Contact.from_percept` creation (`contacts.py` ~1176); `association_over_time`'s spatial gate
   resolves a later poll's observation of the *same* physical entity back onto the *same* existing
   contact id rather than minting a new one, so `contact.id` is stable across a continuously-tracked
   contact's life. The one case where a contact's id does change under the pilot's nose is a genuine
   loss-and-reacquisition (`CONTACT_LOST` then a fresh `CONTACT_DETECTED`, minting a new id) — and
   resetting the cadence/altitude memory there is the *correct* behaviour, not a spurious fire: a
   reacquired contact's belief state starts over regardless, so there is nothing stale to preserve.
   No path was found where the same physical target keeps a stable identity in belief while
   `attack_run.decide` sees a changing `contact.id`. **Verified by reading** (grepped `_new_
   contact_id`'s call sites and `association_over_time`'s resolution path; no mutation attempted,
   since there is no live DCS session available to generate a reachable counter-example and the
   store's own invariant — one id per continuously-tracked entity — is enforced structurally by the
   association gate, not by a check this round touches).

6. **The singleton invariant (§25) — confirmed by grep, not accepted from the implementer's
   report.** `belief.tasks.PendingIntent.contact_id: str | None` (`tasks.py:168`) — a single
   identifier, never a collection, confirmed by reading the field declaration directly.
   `attack_target_task` (`tools.py` ~1157–1161) cancels every still-`!= "cancelled"` `attack_target`
   task before minting the new one — unchanged by this diff, confirmed against the actual loop, not
   the docstring describing it. `CrewConsole._handle_step` (`crew_console.py` ~2089–2092) walks a
   group one contact at a time by `target_task.contact_id = next_id` — a direct attribute mutation
   on the existing `PendingIntent`, never a second `tasks.create(...)` call — confirmed by reading
   the actual assignment, not the docstring's claim that it does. The docstring sentence added to
   `attack_target_task` ("The attack target is always exactly one contact (user direction,
   2026-10-14)") states the invariant as a standing fact with its direction attributed, not merely a
   description of what the code happens to do today. **Verified by grep/reading**, each of the
   three claims checked against its own call site rather than taken from the implementation note.

7. **Nothing else moved.** `git diff 4a20b83..aa1e0cf --stat`: five files, matching the task's own
   description exactly (`attack_run.py`, `tools.py` docstring-only, the new tests, the
   implementation note, one memory file). No constant retuned
   (`ATTACK_RUN_LINED_UP_AZIMUTH_DEG`/`ATTACK_RUN_ELEVATION_GATE_DEG`/
   `ATTACK_RUN_CHANGE_THRESHOLD_DEG`/`ATTACK_RUN_RELATIVE_MAX_AGE_S` all untouched), no vocabulary
   change, no `CalloutScheduler` change, no group-as-target mechanism or tightness test built.
   **Verified by reading the diff stat and grepping the constant names.**

### Verification — run myself

Both subprojects, all four gates, from inside each subproject directory with its own `.venv`
(this worktree has none of its own; borrowed the main checkout's by absolute path — confirmed
`mypy src` resolves against *this* tree's `src` since config discovery and `mypy_path` are
CWD-relative and the CWD was this worktree's `body-layer/`):

- **body-layer**: `ruff format --check src tests` — 126 files, pass. `ruff check src tests` —
  pass. `mypy src` (from `cd body-layer`) — `Success: no issues found in 58 source files`.
  `pytest -q` — **1841 passed, 4 xfailed**, matching the implementer's reported count exactly.
- **audio-adapter** (untouched by this diff; run anyway to confirm no regression): `ruff format
  --check src tests` — 29 files, pass. `ruff check src tests` — pass. `mypy src` — `Success: no
  issues found in 15 source files`. `pytest -q` — **277 passed, 1 skipped**, matching exactly.

### Required Fixes

None.

### Suggestions (optional)

- A one-line docstring note on `AttackRunState` flagging that the identity-change reset's
  completeness is currently accidental (every field happens to be per-contact today) rather than
  structural, so a future field addition gets checked against it explicitly (finding 2). Cheap,
  not required.
- No action needed on finding 4 (the broader `logger.py` reset) unless the "restate on bare
  re-engage" behaviour is ever found to be unwanted in a sortie — it predates this diff and is not
  part of this finding.

### Verdict

**APPROVE.**

The fix closes finding 5, confirmed by an independent reproduction built from scratch and a
fail-then-pass against the actual two-line patch (not the implementer's own tests). The one
load-bearing structural claim (`last_spoken_tier` cannot silently collide) was tested by mutating
the renderer it depends on, not accepted from the audit's prose. The singleton-target invariant
(§25) was confirmed by reading each of the three call sites the implementer named, not from the
report. Nothing outside the stated scope moved. All four gates pass in both subprojects with
counts matching the implementer's report exactly. This clears the Implementer → Reviewer loop for
the staleness fix; proceed to Definition of Done.

### What Definition of Done should carry into the acceptance sortie

Two things already known for the card, per the dispatch: a possibly-sluggish `step` against a
large group (`BL-B49`'s enrichment cost, not the recogniser) and `engage`'s readback occupying the
channel before the first guidance callout (correct behaviour per user direction, not a stall).

One more thing worth telling the pilot to expect, from reading this fix closely: **a bare `"engage"`
re-confirm on the already-selected target will re-speak the current alignment line, even if
nothing about the target or geometry has changed** (finding 4 above) — this predates the fix, is
unrelated to it, and is very likely intentional, but on a sortie it will sound like "why did he say
that again" the first time it's heard with the fix now also silently resetting on every genuine
re-point. Worth the pilot being told both reset triggers exist so a repeated callout right after
saying "engage" again reads as expected, not as a glitch.

### Review Confidence (staleness fix review)

Full read of both source-affecting files (`attack_run.py`, `tools.py`'s docstring) plus the three
call sites the singleton-invariant claim rests on (`tasks.py`'s `PendingIntent.contact_id`,
`tools.py`'s cancel-then-promote loop, `crew_console.py`'s `_handle_step`). The fix itself, the
tier-collision structural claim, and `logger.py`'s overlapping reset path were each verified by
running, mutating, or reading against the actual code — not accepted from the implementation note.
Finding 5 (spurious reset triggers) was verified by reading the contact-id minting/resolution path
only, since no live DCS session was available to construct a reachable counter-example; the
store's own invariant (one id per continuously-tracked entity) is structural rather than a check
this round touches, so there was nothing distinctive to mutate.
