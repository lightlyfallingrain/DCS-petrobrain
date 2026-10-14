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
