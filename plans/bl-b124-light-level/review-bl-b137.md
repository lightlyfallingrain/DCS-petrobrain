### Review Summary

Reviewed the security-requested fix `[[BL-B137]]` (commit `90484ea9`, `feature/bl-b124-light-
level`) against `plans/bl-b124-light-level/security.md` Finding 1 and `body-layer/ROADMAP/
BL-B137.md`.

The fix itself is correct, minimal, and matches the finding exactly: `MissionClockSample.
from_wire` now rejects a non-finite `abs_time_s` at the wire (`math.isfinite`, raises
`FiringParseError`, dropped to `mission_clock=None` by the existing `except FiringParseError`
posture); `body._parse_mission_clock_dict` rejects the same shape a second time for the
locally-extrapolated value that never passes back through the wire parser; `perception.
light_level.sun_elevation_deg` raises `ValueError` before the clamp that was silently resolving
NaN to 90.0 (full daylight), and `body._resolve_sun_elevation_deg` catches that and falls
through to the existing forced-dark/logged-error path. I independently re-ran one of the three
mutations the implementer's log describes (removed the wire-boundary `math.isfinite` guard in
`firing.py`, confirmed all 5 of the targeted tests go red for the stated reason — a `nan`-
bearing `MissionClockSample` reaching the `FiringEventBatch` instead of `None` — restored, and
confirmed `shasum` matches before/after). I did not independently re-run the other two
mutations (`sun_elevation_deg`'s dual guard, `_resolve_sun_elevation_deg`'s `try`/`except`) but
read the implementer's account of them in `implementation.md`, which is specific about method,
outcome and the one correction found along the way (Infinity was already caught by Python's own
`math.sin`/`cos` domain check; NaN was the only value neither guard nor existing code caught
before this fix) — detail that reads as actually having been run, not asserted.

A bad sample does not break the firing-events batch (confirmed: `test_non_finite_abs_time_s_
is_dropped_not_raised_at_batch_level` and the mutation above both exercise this), and healthy
behaviour is unchanged (targeted + smoke tests pass, full-suite comparison below).

**One finding outside the fix's own diff, found while carrying out the task's own instruction
to check the 5 `test_bl_b104_scenario_mock_flights.py` failures against `main`: they are not
pre-existing on `main`, and not solely an artifact of a mock-server gap — they are a regression
introduced by this same branch's own Stage 4 commit (`f3d922eb`), undetected by every review
pass in this batch (Stages 1-3, Stages 4-5, performance, security) because none of them ran the
full suite — only `-m "not slow"`.** See Required Fix 1.

### Required Fixes

- **The 5 `test_bl_b104_scenario_mock_flights.py` failures are `BL-B124`'s own regression, not
  a pre-existing/unrelated issue, and must be fixed or explicitly accepted by the user before
  DoD, not waved through on the implementer's "pre-existing" framing.** The task asked me to
  confirm this against `main`; I bisected further than that single check:
  - `git checkout d565c5ed` (current `main`, i.e. before `BL-B124` existed at all): all 5 tests
    **pass** (confirmed, ran twice for consistency, ~118s each).
  - `git checkout b1978652` ("BL-B124 Stages 1-3 re-review", the last commit before Stage 4):
    all 5 tests **pass** (confirmed, ran twice for consistency).
  - `git checkout f3d922eb` ("BL-B124 Stage 4: wire the real light factor into body.py's poll
    loop", the very next commit): all 5 tests **fail**, same symptom every time —
    `aircraft_client.AircraftLayerError: ... /command/look_direction failed: HTTP Error 501:
    Unsupported method ('POST')`, because `tests/support/mock_aircraft_layer.py`'s `_Handler`
    implements `do_GET` only, no `do_POST`.
  - `git checkout 4525ebcd` (the commit directly before the `BL-B137` fix, i.e. the
    implementer's own "unmodified base"): same 5 failures, matching `implementation.md`'s
    account — so the implementer's claim that these reproduce at that specific commit is true,
    but "pre-existing" in `implementation.md`'s prose reads as "pre-existing on `main`" /
    "unrelated to `BL-B124`", which is not what the evidence shows.

  **Root cause, as far as I traced it**: Stage 4 wired `_resolve_sun_elevation_deg`/`light_
  factor` into the poll loop and reworked `optic_policy.py`'s threading of the (renamed)
  `sun_elevation_deg` parameter. `post_look_direction` itself is pre-existing, unrelated code
  (`body.py`'s gaze-driven hour push, line ~1106-1114) — grepping Stage 4's diff shows no new
  call site. The most likely mechanism is that Stage 4's added per-poll computation shifted the
  scenario's real-time/sim-time relationship enough that the gaze's scan-plan hour crosses a
  boundary within the test's bounded loop where it previously didn't, newly exercising a
  `POST /command/look_direction` call that the mock server was always missing `do_POST` for —
  a latent test-infrastructure gap made reachable by this feature, not a logic bug in the light-
  level code itself. I did not chase this further (outside this task's scope, which was the
  `BL-B137` fix specifically), but the mechanism matters less than the fact: **this branch's
  full test suite is not green, the cause is `BL-B124`'s own Stage 4, and three review passes
  plus this one's own targeted run would not have caught it** because `tests/test_bl_b104_
  scenario_mock_flights.py` is `pytest.mark.slow` and every one of those passes' own check
  commands used `-m "not slow"` (fast-tests.sh's own documented scope, by design — DoD's job is
  the full suite). Fix options, either is acceptable: add `do_POST` (even a minimal 200-ack
  stub) to `MockAircraftLayerServer`'s `_Handler`, or confirm with the user that these 5 tests
  should be `xfail`ed/skipped with a tracking note until that mock gap is closed on its own
  ticket. **Do not let DoD's full-suite run be the first time anyone sees this** — the task that
  dispatched this review explicitly asked for the main-branch comparison so DoD would have an
  accurate answer; the accurate answer is "regression, not pre-existing," and that needs to
  reach DoD's report as such.

### Optional Refinements

- `security.md`'s Finding 1 also named `year`/`month`/`day`'s unbounded `int()` conversion
  (`OverflowError` reachable from an absurdly-large digit string, caught by `body.py`'s poll-
  cycle `except Exception`, self-healing) as "optionally also range-check" — correctly left
  unfixed here, matching the finding's own "cosmetic by comparison" disposition and `BL-B137`'s
  own closed-status note. Not a blocker; flagging only so it isn't lost — `BL-B135`'s own "a
  scan... would be a reasonable scope" note already covers it as a future dedicated pass.
- The implementer's mutation log is detailed and specific (method, exact failure signature,
  shasum before/after) for all three mutations; I only re-ran one independently given time
  constraints. If the user wants every mutation independently re-verified rather than read, say
  so and I'll run the other two.

### Verdict

**APPROVED WITH MINOR FIXES** — the `BL-B137` fix itself (commit `90484ea9`) is correct, tested,
and verified by mutation (one independently re-run here, matching the log's claim); it is not
blocked by the Required Fix above, which is about a separate regression this review's own
instructed main-branch check surfaced, already present before the `BL-B137` commit and not
touched by it. **Do not let DoD proceed on the "pre-existing/unrelated" framing without
confirming that characterization with the user first** — it understates what the evidence
shows.

### Checks run

- `git rev-parse HEAD` was `d565c5ed` (tip of `main`); `90484ea9` is a strict descendant
  (`git merge-base --is-ancestor HEAD 90484ea9`), tree was clean, so `git merge --ff-only
  90484ea9` — fast-forwarded cleanly, no conflict, no divergence to reconcile.
- `body-layer`: `ruff format --check src tests` clean (232 files); `ruff check src tests` clean;
  `cd body-layer && .venv/bin/mypy src` clean (94 source files, via the real `body-layer/.venv`
  since this worktree carries none of its own); smoke (`pytest tests -q --collect-only`) 3812
  collected; targeted (`pytest tests/test_light_level.py tests/test_body.py -q -m "not slow"`)
  274 passed.
- `aircraft-layer`: `ruff format --check src tests` clean (86 files); `ruff check src tests`
  clean; `cd aircraft-layer && .venv/bin/mypy src` clean (28 source files); smoke (`pytest
  tests -q --collect-only`) 1070 collected; targeted (`pytest tests/test_firing_schema.py
  tests/test_firing_receiver.py -q -m "not slow"`) 50 passed.
- Mutation re-run (independent of the implementer's own log): removed `MissionClockSample.
  from_wire`'s `math.isfinite` guard, confirmed all 5 targeted `test_firing_schema.py` tests
  failed for the stated reason (a NaN-bearing sample reaching `FiringEventBatch.mission_clock`
  instead of being dropped to `None`), restored, `shasum` matched exactly before and after
  (`f8a6633880c45d1561c30742719dd6f270bc2f9d`).
- Full-suite comparison for the pre-existing-failures question (see Required Fix 1): ran
  `test_bl_b104_scenario_mock_flights.py` at `main` (`d565c5ed`, pass), `b1978652` (pass),
  `f3d922eb` (fail), `4525ebcd` (fail) — each in a disposable worktree under the scratchpad
  directory, removed after use.

### Review Confidence

Full read of the `BL-B137` diff, security finding, ROADMAP entry, and implementation.md's
account of the fix and its mutation log; one of three documented mutations independently re-run
and confirmed. The full-suite-regression finding was chased by bisection beyond what the task
strictly asked for (it asked only for a main-branch comparison) because the main-branch result
alone (passes) made the implementer's "pre-existing" claim worth running down further before
reporting it as settled.
