---
name: project_cones_2c_scan_loop
description: Cones slice 2C (o'clock scan loop) implementation notes -- ScanPlan design decision, the "default gaze is now restrictive" test-migration pattern, and the TaskStore success-check trap for long fixtures.
metadata:
  type: project
---

Implemented `plans/detection-cones-slice2/plan.md`'s 2C on `feature/cones-2c-scan-loop`
(base `19180a0`, 2A/2A.5/2B already merged). Baseline 810 passed/4 xfailed -> 830 passed/4
xfailed.

**Design call beyond the plan's literal text, and why**: the Implementation Plan's step 12
only specifies ONE table (free scan's `12,11,10,9,12,1,2,3`), but hard part 1 says "a commanded
scan is a function of sim time relative to the command time" and hard part 2a's user quote says
"within a sector it is itself a smaller cone moving in a scan pattern." Read literally-narrow,
`ScanPlan.command_t_sim` would be dead data for a commanded sector (2B's static-wedge behaviour
kept). I chose the generalised reading: each `RelativeSector` decomposes into its own o'clock
legs (`ahead`->`(12,)`, `left`->`(11,10,9)`, `right`->`(1,2,3)`, `full`->the free-scan table),
cycled from `command_t_sim` instead of absolute `t_sim`. This makes `command_t_sim` load-bearing
and matches the user's own quoted framing. Flagged prominently in the implementation report as
the plan defect/underspecification this slice found (matching the pattern the last two slices
each found one).

**The single most disruptive downstream effect: the default gaze stops being "no restriction"
and becomes an always-on +/-15 deg cone.** Every existing `NakedEyePerceptionSource` test that
placed a candidate dead-ahead and polled at an arbitrary `t_sim` (mostly `100.0`) silently
depended on 2B's `None`-means-unrestricted default. Fix pattern used throughout: shift the
poll's `now_sim` argument (not the `OwnshipState.t_sim` field, which is separate and unused for
gaze) into the free-scan "12 o'clock" window (`t % 16 in [0,2)`), e.g. `100.0 -> 0.0`,
`100.2 -> 0.2`. For fixtures spanning multiple *seconds* across the whole flow (integration
tests, replay tests), a persistent commanded scan is the right tool instead of chasing the
free-scan phase — see below.

**Cross-offset fixtures need re-verification, not linear rescaling.** `_CAP_TEST_CROSS_OFFSETS_M`
(5 candidates at increasing range) had one candidate at 14.93 deg azimuth -- 0.07 deg inside the
new +/-15 deg gate, too tight to trust. Naively scaling every offset down by the same factor
made the fixture WORSE (candidates converge toward the zero-offset candidate's own bearing, the
exact same-bearing degenerate case Stage 3b-i rev.2 already warns about) — I had to search a
scale factor (0.85x) that keeps BOTH the gaze margin (>2 deg) and the clustering separability
margin (still >0.2 deg) real, verified against `perception.clustering.angular_separation_rad`/
`angular_size_rad` directly via a throwaway script, not by eye.

**Time-based acquisition dicts change what "leave and re-enter" tests need.** Both acquisition
sets went `frozenset[int]` (per-poll) -> `dict[int, float]` (object_id -> last-seen t_sim),
evicted after `SCAN_CYCLE_PERIOD_S` (16.0 s) — reusing `perception.gaze.SCAN_CYCLE_PERIOD_S`
directly, not an invented constant. Consequence: a candidate that "leaves and re-enters" within
one scan cycle no longer re-emits under `on_change` — it's still "known", by design (this is the
whole point: a cone sweeping off a sector and back must not read as "gone"). Any test asserting
re-emission after a brief absence needs its gap widened past 16 s, landing both polls in the
same free-scan leg so the gaze gate isn't itself the confound (I used `0.0` then `16.1`/`16.3`,
both `% 16` inside `[0,2)`).

**`TaskStore.tick`'s success check makes a "persistent commanded scan" via a real `scan_area`
task self-defeating for a long fixture.** A task succeeds (and stops being picked up by
`_active_gaze`, which requires `status=="pending"`) the very first poll a contact is confirmed
inside it — realistic for a real F10 command, wrong for a 20-poll integration fixture wanting
"ahead" the whole time. Fix: set `created_sim`/`deadline_sim` to something far past the
fixture's own sim-time range (I used `1_000_000.0`/`1_000_000_000.0`) so the success check
(`contact.last_seen_sim > task.created_sim`) can never fire. A direct `source.scan_plan = ...`
field assignment does NOT work for this either — `ConsolePerceptionRunner.run_once` calls
`_apply_active_gaze` (which re-resolves from `tasks`, defaulting to `FREE_SCAN_PLAN`) at the
START of every poll, before `source.poll()` runs, so any manual assignment gets clobbered on the
very next `run_once()` regardless of when you set it.

**Gate-outcome trace expectations move too.** Gaze is the first gate in `check_visibility`'s
chain (since 2B), and no o'clock cone's reach (max 90 deg center +/- 15 deg = 105 deg) extends to
a rear/astern candidate (180 deg) — so any trace-level test previously expecting
`GateOutcome.COCKPIT_MASK` for an astern candidate now gets `GateOutcome.GAZE` instead, under
*any* `ScanPlan`. This is the plan's own accepted, stated consequence (hard part 3), not a
regression to chase.

See also [[feedback_decouple_fixtures_from_tuned_defaults]] — same principle, reused here: give
integration fixtures whose actual subject is NOT the scan loop an explicit, stable `ScanPlan`
rather than depending on whichever cone the free-scan phase happens to be in at whatever `t_sim`
the fixture already used for unrelated reasons.
