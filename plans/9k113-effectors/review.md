# Review: BL-B66 (9K113 effectors), Stages 1-4

Reviewed against `plans/9k113-effectors/plan.md` (text above the `# Superseded text below`
divider), `explore-notes.md`, `security-plan-review.md`, `docs/acceptance/
2026-10-17-9k113-procedures-direction.md`, and `plans/9k113-effectors/implementation.md`.

**Base note (process, not a finding on the implementation):** the worktree assigned to this
review (`.claude/worktrees/agent-afab5f7cbdd00061e`) was created from a stale/unrelated base
(`origin/HEAD`-ish, diverged from `feature/9k113-effectors` — neither commit was an ancestor of
the other). The expected tip `ce6a81babb47ac75fcf0ae0940360be684fe3d7d` could not be reached by
`git merge --ff-only` from that HEAD. A second worktree already existed at
`/Users/sg/Code/DCS-petrobrain-9k113-effectors`, checked out exactly at that tip on
`feature/9k113-effectors` with a clean tree — all verification below (reading, running checks,
mutation testing) was done there. This review file and this worktree's own commit are written
here, in the worktree I was given, per the handoff instructions.

## What was checked

- Full read of the plan, explore notes, security plan review (REJECTED on the allow-list finding,
  explicitly overridden by user Decision 4 — not re-litigated here), and the procedures-direction
  acceptance doc.
- Full diff read: `Export.lua` (new op, readback push, version bump), aircraft-layer
  schema/collector/API/tests, `body-layer/src/belief/sight_effector.py` (new),
  `body-layer/src/logger.py`'s poll-loop wiring, `crew_console.py`, `speech.py`,
  `audio-adapter/src/vocabulary.py` and its test changes, `tuning.py`/`defaults.toml`.
- Ran `ruff format --check`, `ruff check`, `mypy src` (from inside each subproject), and `pytest`
  for all three touched subprojects (aircraft-layer, body-layer, audio-adapter) against freshly
  built `.venv`s (none existed in either worktree) pinned to Python 3.12. All green, matching
  `implementation.md`'s own claims exactly (aircraft-layer 407 passed; body-layer 2383 passed, 4
  xfailed; audio-adapter 346 passed, 2 skipped).
- `luac5.1 -p Export.lua` (syntax) and `luac5.1 -l -p` + a `GETGLOBAL` scan (global-leak check) —
  clean; every `GETGLOBAL` resolves to an existing DCS/Lua API name or stdlib, none of the three
  new functions (`handle_cockpit_switch_command`, `push_cockpit_switch_state`,
  `extract_json_number_field`) leaks a name.
- Verified the rendered `body-layer/config/defaults.toml` entry for
  `GUIDANCE_UNIT_SWITCH_DELAY_S` directly (not the source `#:` comment) — first sentence renders
  intact, status/range correct, no markup corruption, arithmetic matches the source constants.
- Verified by mutation, not just reading, per this role's standing instruction:
  - Construction-site grep tests (`test_guidance_unit_state_is_constructed_in_exactly_one_place_
    in_logger_py`, `test_sight_effector_never_constructs_guidance_unit_state_directly`) — read, not
    mutated (mechanical regex checks, low risk of a false guard).
  - `advance_power_up`'s retry-on-failure path — unit test exercises it correctly at the pure
    function level (confirmed by reading the fake clients and assertions, not separately mutated,
    since the security-plan-review finding 3 this answers is already a `replace()`-based idempotent
    design and the test shape is standard).
  - **The `_run_crew_text_poll_loop` integration wiring added for Stages 2-4** (takeoff rising-edge
    detection, `start_guidance_unit_power_up`/`advance_guidance_unit_power_up`/
    `refresh_cockpit_switch_readback` calls, the `sight_ready` refresh, `drain_guidance_unit_ready`,
    and the OBSERV/weapons-safety cockpit-write-through with its try/except) — mutated twice:
    1. Forced the takeoff rising-edge `if` to `False` (disabling the entire power-up trigger).
       Ran `pytest tests/test_logger.py` — **160/160 still passed.**
    2. Removed the `announced` guard from `CrewConsole.drain_guidance_unit_ready` (so "Guidance
       unit ready." would be spoken every poll once ready, not once). Ran the full body-layer
       suite — **2383/2383 still passed.**
    Both mutations were reverted; the worktree's tree is clean (confirmed below).
  - The three pre-existing `test_crew_console.py` tests the implementer modified
    (`test_non_look_command_on_ground_dispatches_normally`,
    `test_observ_on_signals_the_poll_loop_and_speaks`,
    `test_observ_transition_is_reset_at_the_top_of_every_dispatch`) — read in full; each addition
    (`console.sight_ready = True`) is the minimal, correctly-targeted change the Stage 3 readiness
    gate requires, and the two new tests
    (`test_observ_on_refused_when_guidance_unit_not_ready`/`test_observ_off_needs_no_readiness`)
    cover exactly the dimension the three predate.
  - Audio-adapter's "weapons"/"tanks" `VERB_FLOOR`-boundary claim — checked against
    `command_matcher.py`'s actual comparison (`if best_ratio < VERB_FLOOR:`, strict `<`), so a ratio
    exactly at `0.5` does anchor, matching the test's asserted `verb_anchored is True`. Confirmed,
    not just read.
- Queried `.claude/scripts/gq.sh` for prior practice on whether this project's poll-loop wiring
  needs an integration test beyond the effector module's own unit tests — turned up
  `test_observ_off_command_stops_the_sight_through_the_real_poll_loop` (this same file,
  pre-existing), whose own docstring states the precedent directly: *"the gap the review found was
  invisible precisely because no existing test drove this path end to end."* Also found
  `test_crew_text_poll_loop_resets_belief_on_mission_restart`/`...switches_theatre_on_mission_
  restart`, which do drive `_run_crew_text_poll_loop` on a real thread for a comparably
  wiring-shaped feature (BL-15). Neither precedent is honoured for this entry's own new wiring.

## Required Fixes

- **The `_run_crew_text_poll_loop` wiring for the entire guidance-unit power-up (takeoff
  detection → sequencer advance → readback refresh → `sight_ready` → "Guidance unit ready."
  spoken exactly once) and the OBSERV/weapons-safety cockpit-write-through has no test coverage at
  the point it is actually wired into the poll loop**, only at the pure-function level inside
  `sight_effector.py`/`crew_console.py` in isolation. This is not a theoretical gap: disabling the
  takeoff trigger outright, and separately breaking "spoken exactly once" into "spoken every poll
  once ready," both left the full body-layer suite green (160/160 and 2383/2383 respectively — see
  above). The implementation.md's own text claims the fake client's new
  `cockpit_switch_writes` recorder exists "so a test can assert on the guidance-unit power-up
  sequence's actual writes" — no test in the diff does. This is exactly the project's own stated
  failure mode for this file (`test_observ_off_command_stops_the_sight_through_the_real_poll_loop`'s
  docstring, quoted above), recurring on the same file in the same feature family. Two of the
  checklist items the task brief named directly — "takeoff detection edge cases" and
  "'Guidance unit ready' spoken exactly once" — are unverifiable from the test suite as it stands.
  **Fix**: add at least one test that drives the real poll-loop path (either on a thread, per
  `test_crew_text_poll_loop_resets_belief_on_mission_restart`'s pattern, or reproduced verbatim per
  `test_observ_off_command_stops_the_sight_through_the_real_poll_loop`'s pattern) across an
  on-ground→airborne transition, asserting: the four switches are written in order via
  `cockpit_switch_writes`/the fake's recorder; `sight_ready` becomes `True` only after the fourth;
  "Guidance unit ready." is printed exactly once across several subsequent polls, not once per
  poll. A second, smaller test should exercise the OBSERV-on/weapons-armed write-through
  (`write_observ_switch`/`write_weapon_safety_switch` actually firing from an accepted transition
  inside the loop, not just from the handler that sets the transition field).

No other required fixes. The security-plan-review's rejection (missing allow-list) is addressed by
an explicit, named user override (plan Decision 4), not silently dropped — correctly not treated as
outstanding.

## Optional Refinements

- `test_logger.py`'s `FakeConsoleAircraftClient.get_cockpit_switch_state_latest` always returns
  `None`. Once the required fix above adds a real driving test, consider letting it also return a
  synthesized `CockpitSwitchState`-shaped dict after the sequence completes, so `refresh_readback`'s
  wiring (currently only unit-tested in isolation) gets at least one integration-level exercise too.
  Optional — `refresh_readback`'s result is explicitly unread by this entry (plan §3, carried for
  `BL-B67`), so this is a nice-to-have, not a gap in anything this entry's own behaviour depends on.
- The `870`/`956`/`L166V POWER` naming cross-check in `implementation.md`'s Deviations §1 (device/
  cmd numbers resolved from three separate research docs rather than one table) would be cheaper to
  verify for a future reader if `sight_effector.py`'s own `_POWER_UP_SWITCHES` comment named the
  source document inline next to each row, not just at the top of the block — it already does
  this reasonably well; a line-by-line citation would be marginally better. Cosmetic.

## Verdict

**NEEDS REVISION** — one required fix (test coverage for the poll-loop integration wiring,
Stages 2-4). Everything else — scope fit, module boundaries (`sight_effector.py`'s single
device/arg-number boundary), the construction-site discipline, the tuning pattern and its rendered
output, the deliberate no-allow-list departure, the ARMED-never-automatic invariant, the voice-phrase
false-anchor mitigation and its own test, and all format/lint/type/test gates across all three
touched subprojects — is sound and needs no change.

## Review Confidence

Full read of the diff and all five linked plan/explore/security/acceptance/implementation
documents; all three subprojects' format/lint/type/test commands run directly (not taken on
report); the one required fix was confirmed by actual mutation + re-run, not by inspection alone.
