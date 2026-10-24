### Review Summary

Reviewed `feature/switch-reference-values` at tip `d544f23d8f1` (HEAD matched the expected tip
on checkout), focused on the cherry-picked `f1ff3424` (BL-B90 follow-on: `mission-start`/
`mission-start-in-air` triggers, air-start no longer firing `takeoff`). Read the full diff, the
explore-notes "Two new triggers: mission start" section, `implementation.md`'s new section, plan
R14, `body-layer/CLAUDE.md`'s BL-B90 entry, and the production `logger.py`/`effector_sequences.py`
code the diff touches, including the parts of `_check_for_new_mission`/`reset_for_new_mission`/
`crew_console.py`'s `on_ground` field it depends on but does not itself change.

Independently re-ran the implementer's own mutation (`mission_start_resolving = False`) against
the six new tests: 5 of 6 failed red for the stated reasons, the sixth
(`test_body_layer_start_mid_mission_fires_neither_mission_start_trigger`) stayed green for the
stated reason (that scenario never arms the pending flags). Matches `implementation.md`'s
account exactly. Restored the mutation and confirmed `git diff` was empty afterward.

Ran `ruff format --check`, `ruff check`, `mypy src`, `mypy tools` (all from inside `body-layer/`,
per that subproject's own `CLAUDE.md`), and `pytest -q`: all pass, matching the implementer's
reported 2602 passed / 4 xfailed.

One required fix found: the `takeoff` trigger's own documentation — in three separate places —
still asserts the exact behaviour this change removes.

### Required Fixes

- **`takeoff`'s own documentation says a warm air start re-fires it — this change makes that
  false, and nothing in the diff touched it.** Three places, all now wrong:
  - `body-layer/src/belief/effector_sequences.py`, `TRIGGER_INFO[EffectorTrigger.TAKEOFF]
    .description`: *"No per-mission latch: a repeat takeoff or a warm air start re-fires it..."*
  - The **rendered** `body-layer/config/sequences/triggers.md` (generated verbatim from the
    description above) — the review brief specifically asked to check the rendered file, not
    the source comment, and this is exactly the gap that check exists for: the `takeoff` row
    repeats the same now-false claim, unchanged by this commit.
  - `body-layer/config/sequences/mi-24p/copilot-takeoff.md`'s own header comment: *"...and what
    lets a hot/air start finish the power-up on its own, by comparing each row's own effector
    against its already-observed readback..."* — also describes an air start reaching the
    `takeoff` trigger's rows, which this change makes untrue (an air start now fires
    `mission-start`/`mission-start-in-air` instead, and no sequence ships for either, so nothing
    writes on an air start at all).

  This is not cosmetic: anyone reading `triggers.md` or `copilot-takeoff.md` to decide which
  trigger to attach their own sequence file to — which is exactly what the acceptance card's
  block 4 now tells the user to do for `mission-start-in-air` — is told the wrong thing about
  `takeoff`. Fix: update the `TriggerInfo` description to drop the "warm air start re-fires it"
  clause (or state the new behaviour explicitly), regenerate `triggers.md`
  (`tools/render_triggers.py --write`), and prune/update `copilot-takeoff.md`'s header comment to
  match. `test_switch_reference_matches_the_generator`/`test_render_triggers.py` will not catch
  this on their own — they check the rendered file matches its generator's *current* input, and
  the input itself is what is stale, so both stay green while repeating the error.

### Optional Refinements

- **Baseline-collision stall, documented here but not mitigated or tested.** The freshness check
  (`runner.last_ownship_state.t_sim != mission_start_fresh_sample_baseline_t_sim`) resolves on
  *any* difference from the pre-reset baseline, which is correct against the stale-cache hazard
  it was designed for (confirmed: `aircraft-layer`'s `TelemetryCache.push`/`latest` only replaces
  `_latest` wholesale on a genuine new sample, so a stale read is bit-identical in value, never
  merely similar). But the inverse case — the *first genuinely fresh* post-restart sample
  happening to carry the exact same `t_sim` value as the baseline — is not addressed by `!=` any
  better than it would be by `<`. This is not far-fetched: the baseline is `runner.last_t_sim`
  from immediately before the reset, which is `None` only if no ownship sample was ever read
  this process; otherwise it is a real captured value, and a mission restarted very soon after
  its own start (a realistic pattern when iterating a test mission in the editor) can easily have
  a small baseline (e.g. `0.0`–`0.5`) that a freshly-started replacement mission's own early
  samples can coincidentally re-hit, since DCS model time for most missions starts near zero too.
  Consequence if it happens: `pending_mission_start_fire`/`pending_mission_start_in_air_check`
  stay `True` indefinitely for that mission (re)start, `MISSION_START`/`MISSION_START_IN_AIR`
  never fire, and — more visibly — `TAKEOFF` stays suppressed for the rest of that mission, with
  no recovery until the *next* restart (whose own baseline is freshly captured and very unlikely
  to collide a second time in a row). None of the six new tests exercise this, and none of
  `implementation.md`'s discussion of `!=` vs. `<` mentions it — that discussion is about which
  direction the clock moves, not about an exact-value coincidence, which is a different failure
  mode from the one it was written to rule out. Not required to fix now, because: it self-heals on
  the next restart, it needs no code change to become safe to ship as-is (no sequence file ships
  for either new trigger yet, so the only visible symptom today is a suppressed `TAKEOFF`), and a
  robust fix (e.g. a monotonic per-sample generation counter from the aircraft-layer collector,
  rather than inferring freshness from a telemetry value) is bigger than this cut's scope. Worth
  one sentence in `implementation.md`'s existing `!=`-vs-`<` section, next to the rationale it
  already carries, so a future reader does not have to re-derive the gap; and worth considering
  for BL-15's own backlog whenever the collector gains a cheap monotonic frame counter for other
  reasons.
- **Look-command gating during the resolving window uses whatever the current sample says,
  stale or fresh, same as it always has.** `crew_console.on_ground` is reassigned unconditionally
  from `runner.last_ownship_state.alt_agl_m` every poll regardless of `mission_start_resolving`
  (the assignment sits before the new mission-start block), so during the stale-cache window a
  look command is gated on the *previous* mission's last known altitude, not the safe `True`
  default `reset_for_new_mission` just set. This is pre-existing behaviour (unrelated to this
  diff, which does not touch that line) and is almost certainly a fine approximation in practice,
  but it means the stale window briefly answers look-command refusals from the wrong mission's
  state. Not asked for by the plan and not a regression — flagging only because the review brief
  asked specifically about `on_ground`'s default and look-command refusals before the first
  sample, and the actual answer is "it's not the default that decides it during the stale window,
  it's the stale sample" — worth knowing, not worth building around this cut.

### Other checklist items verified clean

- **Mid-mission body-layer start vs. a real restart**: correctly distinguished.
  `_check_for_new_mission`'s pre-existing first-poll rule (`runner.last_mission_start_sequence is
  None` → record and return `False`, no reset) runs *before* the new pending-flag arming code, so
  a process that attaches mid-mission never arms `pending_mission_start_fire`/
  `pending_mission_start_in_air_check` at all — confirmed by reading the function and by the
  passing `test_body_layer_start_mid_mission_fires_neither_mission_start_trigger`.
- **Mission restart while a sequence is running**: `effector_state` is not in
  `ConsolePerceptionRunner.reset_for_new_mission`'s preserved-field list, so a restart mid-run
  drops any queued/running trigger (including a queued `takeoff`) with nothing carried over —
  this is pre-existing documented behaviour (D11), unchanged and uncontradicted by this diff.
- **Takeoff suppression covers exactly the resolving window, including the resolving poll
  itself** (the `if`/`elif` structure means the takeoff-edge check never runs at all while
  `mission_start_resolving` was true on entry to that poll), and `on_ground`'s baseline for the
  *next* poll's takeoff-edge check is the real value established on the resolving poll — so a
  ground start later takeoff, an air start later land-then-takeoff, and a second mission restart
  all behave as the plan intends. Verified by reading the code and by the passing
  `test_air_start_then_land_then_takeoff_fires_takeoff_once` and
  `test_second_mission_restart_fires_both_triggers_again`.
- **Scope**: touches exactly `effector_sequences.py`, `logger.py`, their tests, the generated
  `triggers.md`, the acceptance card, and the plan/implementation docs — matches plan R14, no
  drift into unrelated modules.
- **Module boundary**: the new logic lives entirely in `logger.py`'s poll loop (where
  `takeoff`/`on_ground` already lived) and `effector_sequences.py`'s trigger enum/registry —
  correct placement, no new module needed.
- **Comment pruning**: the one durable-looking line removed (`TriggerInfo.cardinality`'s
  docstring, "no shipped trigger is `once` yet") was a now-false implementation note, not a dated
  decision or user quote, and its replacement states the current truth — fine to have gone,
  not a required-fix case under the pruning rule.

### Verdict

NEEDS REVISION

### Review Confidence

Full read of the diff and the surrounding production code it depends on (`_check_for_new_mission`,
`reset_for_new_mission` on both `ConsolePerceptionRunner` and `CrewConsole`, `on_ground`'s field
docstring, `aircraft-layer`'s `TelemetryCache`). Mutation re-verified independently, not taken on
the implementer's word. Full subproject check suite run and passing.

---

## Fix re-review (2026-10-23)

Re-reviewed fix commit `8fd8fc38` (tip, confirmed via `git rev-parse HEAD` against the dispatched
sha) on `feature/switch-reference-values`, diffed against the previously-reviewed `b61bf3e6`.
Addresses this review's required fix (stale "warm air start re-fires takeoff" documentation) and
its first optional refinement (baseline-collision stall during mission-start resolving).

**Stale documentation**: confirmed gone everywhere — grepped `src/`, `config/sequences/`,
`plans/effector-sequences/`, `body-layer/CLAUDE.md`, and
`docs/acceptance/2026-10-23-bl-b90-sequences-reflight.md` for "air start". Every remaining hit
states the *new*, correct behaviour (air start fires `mission-start`/`mission-start-in-air`, never
`takeoff`); the implementer's own grep caught two spots this review's three-item list missed
(`logger.py`'s `elif` comment, two in `plan.md`) and fixed those too. The rendered
`config/sequences/triggers.md` and `copilot-takeoff.md`'s header both read correctly — checked the
rendered files, not the source comments, as this review's own brief requires.

**Rendered `defaults.toml`**: the new `[logger] MISSION_START_RESOLVE_FALLBACK_S` entry's rendered
comment is the `#:` block's full first sentence, verbatim, no truncation and no corrupted
backtick/space span — compared byte-for-byte against the source. `status: judgement | range: 5.0
.. 120.0` matches the declaration's `lo=5.0, hi=120.0, status="judgement"`.

**New test fails on pre-fix code**: independently re-verified, not taken on the implementer's
report. Copied the fixed `src/logger.py` aside, restored the `b61bf3e6` version, ran
`test_baseline_collision_resolves_via_bounded_fallback` alone — `ImportError: cannot import name
'MISSION_START_RESOLVE_FALLBACK_S' from 'logger'`, red for the stated reason (the mechanism does
not exist on the reviewed tip). Restored the fixed file; `git diff` on it came back empty.

**`implementation.md` overwrite claim**: confirmed nothing lost. `git show b61bf3e6:plans/
effector-sequences/implementation.md` is byte-identical to the first 261 lines of the new 389-line
file — the new section is a pure append, not a rewrite.

**Checks**: `ruff format --check`, `ruff check` (`src tests tools`), `mypy src` (74 files clean),
`mypy tools` (10 files clean), `pytest -q` — 2603 passed, 4 xfailed, from inside this worktree's
`body-layer/`, matching the implementer's reported counts.

### Required Fix

- **The fallback's own comments claim a narrower trigger condition than the code actually has, and
  the gap matters because the two cases behave differently.** Both `MISSION_START_RESOLVE_FALLBACK_S`'s
  declaration comment (`src/logger.py:318-337`) and `mission_start_resolving_since_wall`'s field
  docstring frame the 30 s fallback as covering exactly one case: *"the restart happens near `t_sim
  = 0` **and** the first fresh sample lands on the exact same float as the baseline"* — a
  coincidence that "self-heals on the next restart." The code cannot tell that case apart from a
  second, more mundane one: **no fresh sample has arrived at all yet** when the 30 s elapses —
  e.g. a long mission-load screen, or (common in DCS) a mission that starts paused and the pilot
  takes their time un-pausing. `fresh_sample_confirmed` and `fallback_due` are both computed purely
  from `t_sim` equality and wall-clock elapsed time; neither can distinguish "a fresh sample
  coincidentally matches the baseline" from "there has been no fresh sample at all," because
  body-layer's only signal is the value it reads over HTTP — there is no cheaper signal available
  today (a monotonic per-sample generation counter from the collector, which the original review
  already flagged as future BL-15 backlog, is the only thing that would actually distinguish them).
  In the second case the fallback fires `MISSION_START`/`MISSION_START_IN_AIR` against
  `crew_console.on_ground` computed from the genuinely stale, previous-mission sample — not "the
  first real ownship sample after the mission start" as the call site's own comment claims
  (`logger.py:3628-3632`), and unlike the coincidence case **this does not self-heal**:
  `pending_mission_start_in_air_check` is cleared unconditionally once the fallback fires, so a
  wrong classification stands for the rest of that mission, with no second chance at the next
  genuinely fresh sample. The committed comments assert "short enough to self-heal within the same
  sortie" and "only reachable if a real restart happens near `t_sim = 0` **and** ..." — both read as
  confident claims about *when* the fallback fires and are each only half true. Required because
  these are exactly the kind of load-bearing "X, so Y" claims this project's own review discipline
  asks to be checked, not because the underlying design choice is wrong: given body-layer's actual
  telemetry contract, there is no cheaper correct signal, and the task scoped this as a minimal
  fallback, not a redesign. **Fix is documentation-only, no behaviour change needed to close this
  finding**: state plainly, in both comments, that the fallback also fires whenever no fresh sample
  has arrived within the window (paused sim, slow load) and not only on a `t_sim` coincidence, and
  that in that case the `MISSION_START_IN_AIR` classification may be wrong for previous-mission
  reasons and will not self-correct until the next restart.

### Optional Refinement

- **Whether that residual misclassification risk is worth mitigating now is a product question,
  not purely a reviewer judgement call** — flagging for the user rather than deciding it here,
  per CLAUDE.md's escalation rule for genuine ambiguity about expected behaviour. Today's actual
  consequence is zero: no sequence file ships for either new trigger yet, so nothing reads whether
  `MISSION_START_IN_AIR` fired correctly (same reasoning the original review used to leave the
  coincidence case unmitigated). The moment a sequence file is attached to `mission-start-in-air`,
  this stops being free — a pilot who starts a mission paused and un-pauses after 30+ seconds could
  get a wrong one-shot classification with no recovery. Worth a decision at that point, not
  necessarily before.

### Verdict

APPROVED WITH MINOR FIXES

### Review Confidence (fix re-review)

Full read of the diff against `b61bf3e6`. Mutation-verified the new test independently. Full
subproject check suite run and passing. Did not re-verify the untouched parts of the mission-start
mechanism already covered by the first review pass (the mid-mission-start distinction, the
takeoff-suppression window, the module/scope checks) — no code in that surface changed in this
commit.

---

## Fix re-review 2 (2026-10-23)

Re-reviewed fix commit `e39408f8535481c71f7defd413d677e265bd2cab` (tip, confirmed via
`git rev-parse HEAD` against the dispatched sha before checkout) on `feature/switch-reference-values`,
diffed against the previously-reviewed `4b00a955`. Addresses the "Fix re-review (2026-10-23)"
required fix above: the fallback could not tell a `t_sim`-coincidence apart from no fresh sample
having arrived at all, and both cases fired `MISSION_START_IN_AIR` off stale, previous-mission
`on_ground` data.

**Behaviour change, read from the code, not the commit message**: on fallback expiry,
`MISSION_START` still fires unconditionally (`src/logger.py`'s poll block, `if runner.
pending_mission_start_fire:` under `if fresh_sample_confirmed or fallback_due:`). `MISSION_START_
IN_AIR` is now gated on `fresh_sample_confirmed and not crew_console.on_ground` — never on
`fallback_due` alone — so a fallback forced by "no fresh sample at all" drops the air/ground
classification instead of guessing, logs a warning naming why
(`"...dropping the MISSION_START_IN_AIR check..."`), and still clears `pending_mission_start_
in_air_check`/`mission_start_resolving_since_wall` the same poll, which ends `TAKEOFF` suppression
the same way a normal resolution does. No code changed to make that last part true: the pre-existing
`if mission_start_resolving: ... elif was_on_ground ...` structure already skips the takeoff-edge
check for the resolving poll itself regardless of path, and the *next* poll's `was_on_ground` is
taken from whatever `on_ground` value that resolving poll established — confirmed by reading the
code, not assumed from the commit message's account of it.

**2 new tests — only one is a mutation-kill test for this fix, and that is correct, not a gap.**
Re-ran the mutation independently: swapped `src/logger.py` back to the `4b00a955` version (tests
left at `e39408f8`) and ran both new tests.
- `test_no_fresh_sample_fallback_fires_mission_start_only_then_real_takeoff` — **failed red** for
  the stated reason: the old code's unconditional `if not crew_console.on_ground:` fires
  `MISSION_START_IN_AIR`'s write off the stale airborne sample, which the new test's exact
  write-list assertion catches (`assert aircraft_client.cockpit_switch_writes == [*writes_before_
  restart, _MISSION_START_WRITE]` — extra tuple `(6, 3020, 1.0)` present on old code).
- `test_takeoff_suppression_ends_cleanly_after_no_fresh_sample_fallback` — **passed on the
  unfixed code too.** This is not a hidden gap: its own docstring says it is a *companion*
  isolating two claims the first test does not assert on directly (the stale sample right after
  resolution is not itself read as a `TAKEOFF` edge, and a later genuine ground→air transition
  still fires `TAKEOFF` exactly once) — both of which were already true before this fix, since
  they depend on the unchanged `if`/`elif` takeoff-suppression structure, not on the
  `MISSION_START_IN_AIR` gating this commit changes. `implementation.md`'s own account says the
  same thing ("isolating the two claims the test above doesn't assert on directly"). So: the
  commit's premise that "2 new tests" verify this fix is true only of the first; the second earns
  its place as regression coverage for an adjacent property, not as a second mutation-kill test —
  worth stating precisely rather than letting "2 tests, 2 kills" stand unchecked.
Restored the fixed `src/logger.py` from a saved copy; `git status --porcelain` on it came back
empty afterward.

**Rendered files and TRIGGER_INFO**: `triggers.md`'s `mission-start-in-air` row,
`TRIGGER_INFO[MISSION_START_IN_AIR].description`, `EffectorTrigger.MISSION_START_IN_AIR`'s own
`#:` comment, and the rendered `defaults.toml` entry for `logger.MISSION_START_RESOLVE_FALLBACK_S`
all now state both cases (the rare `t_sim` coincidence, which self-heals, and "no fresh sample at
all," which does not and instead drops the check) — read the **rendered** `defaults.toml`, not
just the source `#:` block, and confirmed the generator emitted the *whole* first sentence intact,
including the `plans/effector-sequences/review-mission-start.md` backtick path split across two
source lines, joined with no inserted or dropped space. All four of the places this review's
previous pass could name are now internally consistent with the code and with each other.

**`implementation.md` append-only**: `git show 4b00a955:plans/effector-sequences/
implementation.md` is byte-identical to the first 389 lines of the new 467-line file — confirmed
by diffing those 389 lines directly, not by line count alone.

**Edge case asked for by the dispatching task — a paused mission start where the first fresh
sample arrives *after* the fallback expired, with the aircraft on the ground**: traced by hand and
confirmed by `test_takeoff_suppression_ends_cleanly_after_no_fresh_sample_fallback`'s own
"land, then take off for real" step. After the fallback fires (stale sample still airborne),
`crew_console.on_ground` keeps reflecting that stale sample every poll (the unconditional
reassignment above the mission-start block, unchanged by this diff and already flagged as a
pre-existing, out-of-scope quirk in the first review's optional refinements) until a genuinely
fresh sample lands. The moment it does — altitude dropped to the grounded threshold in the test —
`crew_console.on_ground` is reassigned from *that* sample and becomes `True`, with no `TAKEOFF`
write in between (asserted via `writes_right_after_fallback` staying unchanged across ten polls,
then the landing transition itself producing no write, since `TAKEOFF`'s edge condition requires
leaving the ground, not reaching it). A subsequent real takeoff from that correctly-grounded state
then fires `TAKEOFF` exactly once, counted against the pre-restart flight's own four writes landing
twice in total. So: yes, `on_ground` comes from the fresh sample once it arrives, and no false
`TAKEOFF` fires on the stale→fresh transition into "on the ground" — confirmed, not merely asserted
by the test's own pass.

**Checks** (from inside this worktree's `body-layer/`, using the main checkout's `.venv` since
none exists in this worktree): `ruff format --check src tests tools` — 183 files already
formatted; `ruff check src tests tools` — all checks passed; `mypy src` — success, 74 source
files; `mypy tools` — success, 10 source files; `pytest -q` — 2605 passed, 4 xfailed, matching the
implementer's reported counts.

### Required Fixes

None.

### Optional Refinements

- **Two adjacent docstrings still describe `pending_mission_start_in_air_check`'s clearing path as
  single-cause, and this fix did not touch either** — not introduced by this commit, and not worse
  than before it, but now slightly more wrong given what the code does. `ConsolePerceptionRunner.
  pending_mission_start_in_air_check`'s own field docstring (`src/logger.py:628-636`) says
  "Cleared the poll a fresh (non-stale) ownship sample is found," and `_check_for_new_mission`'s
  docstring (`src/logger.py:2483-2485`) says the poll block fires both new triggers "once it has
  an ownship sample it trusts is not the previous mission's stale cached one" — both describe only
  the fresh-sample path, not the fallback-without-a-fresh-sample path this very fix adds a second,
  documented way to resolve through. Low cost to close (one clause each, same pattern already used
  at the call site and in `MISSION_START_RESOLVE_FALLBACK_S`'s own comment) and not required now
  because neither claim is relied on by a test or another comment the way the three required-fix
  spots in the first pass were, and both predate this commit's own touched lines.
- **`body-layer/CLAUDE.md`'s `effector_sequences.py` module-map entry** ("`mission-start-in-air`
  fires immediately after it, same poll, only when that same sample is airborne") was not updated
  to mention the fallback-drop case either, and wasn't in the task's named list of files to check
  (comments, `TRIGGER_INFO`, rendered `triggers.md`/`defaults.toml`) — flagging only because a
  reader of that file alone would still expect an unconditional in-air classification.

### Verdict

APPROVED

### Review Confidence (fix re-review 2)

Full read of the diff against `4b00a955`. Mutation-verified both new tests independently (one
kills on old code, one correctly does not, matching its own stated scope). Full subproject check
suite run and passing. Traced the asked-for paused-mission-start edge case by hand against the
code and against the existing test that exercises it, rather than taking the test's green alone as
the answer. Did not re-verify the parts of the mechanism unchanged by this commit and already
covered by the first two passes (the mid-mission-start distinction, scope, module boundary).
