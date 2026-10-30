"""BL-B104 Stage 7 -- manoeuvre-based scenario mock flights
(`plans/bl-b104-ground-contacts-on-ground/plan.md` Stage 7,
`explore-notes.md`'s "Scenario mock flights"). User, on whether this
project can exercise a scenario like a real sortie without DCS: *"2 is
too cumbersome... 1 yes. Simple mock flights that still contain some
aircraft manoeuvre."* Record-and-replay (option 2) is rejected, not
backlogged; this file is option 1 -- scripted scenarios on the existing
mock-flight harness (`tests/support/mock_aircraft_layer.
MockAircraftLayerServer`, `tests/test_mock_flight_chain.py`'s own wiring),
each built from `tests/support/mock_flight_scenario.build_scenario_frames`
rather than hand-written JSON.

**Driven through the real threaded crew-text loop**
(`body._run_crew_text_poll_loop` on a background thread), but command
injection ("engage") is **not** issued via `CrewConsole.handle_line` as
the plan's own prose suggested -- confirmed by running it: `handle_line`
routes free text through `_handle_utterance`'s contact-reference grammar
(`belief.utterance.parse_utterance`), which has no bare-verb entry for
"engage target" with no antecedent contact reference, so the typed line
`"engage target"` is read as unmatched and escalated to the brain layer,
never reaching `_handle_engage` at all. This is a plan-prose inaccuracy
about which `CrewConsole` method to call, not a `body-layer/src` defect
-- `CrewConsole.handle_command("engage", now_sim, slots={...})` is the
dispatcher `_handle_utterance`'s own "handled" branch and the real voice
`"act"` disposition both bottom out at (`_act_on_voice_decision`), and is
the call every existing `engage` test in `test_crew_console.py` already
uses. Scenarios below call `handle_command` directly for that reason.

Each scenario builds its own frame list, a flat world-model big enough to
cover its own geometry (`mock_world_model.build_flat_world_model` --
`mock_world_model.build_mock_world_model`'s small, fixed-bounds canonical
rectangle does not cover a 5 km closing run), starts a
`MockAircraftLayerServer`, and drives the real pipeline with a persistent
`scan_area` "ahead" task (the same device `test_mock_flight_chain.py`'s
single-threaded test uses) so the naked-eye channel looks forward every
poll rather than cycling 11->12->1 and missing two-thirds of them --
cycling would make "range error shrinks poll-over-poll" and "one look
founds the contact" both untestable by starving the channel of looks, not
by any property of the estimator under test."""

from __future__ import annotations

import io
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from support.mock_aircraft_layer import MockAircraftLayerServer
from support.mock_flight_scenario import (
    Descend,
    FlightLeg,
    Level,
    OwnshipStart,
    PlacedUnit,
    Turn,
    build_scenario_frames,
)
from support.mock_world_model import build_flat_world_model

from aircraft_client import AircraftLayerClient
from belief.attention import AttentionArea
from belief.contacts import Contact, ContactStore
from belief.crew_console import CrewConsole
from belief.enrichment import EnrichmentContext
from belief.tasks import TaskStore
from belief.tools import describe_contact, get_contacts
from body import ConsolePerceptionRunner, _run_crew_text_poll_loop
from perception.geometry import GeoPosition, horizontal_range_m, open_world_model

_THEATRE = "Syria"
#: Generous but bounded -- a hard failure, not a skip, if the background
#: poll thread hasn't reached the fixture's final frame within this
#: window (`test_mock_flight_chain.py`'s own convention/rationale).
_THREAD_JOIN_TIMEOUT_S = 10.0
#: Fast enough that a 20-poll scenario finishes in well under a second,
#: slow enough (relative to the 0.005s wait-loop poll below) that a
#: foreground `handle_command` call reliably lands within the intended
#: poll tick rather than racing the next one.
_POLL_INTERVAL_S = 0.15
_WAIT_POLL_S = 0.005


def _world_model_path(
    tmp_path: Path, *, half_extent_x_m: float, half_extent_z_m: float
) -> Path:
    db_path = tmp_path / "region.sqlite"
    build_flat_world_model(
        db_path,
        region_name="bl-b104-scenario",
        theatre=_THEATRE,
        centre_x=0.0,
        centre_z=0.0,
        half_extent_x_m=half_extent_x_m,
        half_extent_z_m=half_extent_z_m,
        origin_x=-half_extent_x_m,
        origin_z=-half_extent_z_m,
        spacing_m=500.0,
        n_rows=max(3, round(2 * half_extent_x_m / 500.0) + 1),
        n_cols=max(3, round(2 * half_extent_z_m / 500.0) + 1),
    )
    return db_path


def _run_scenario(
    tmp_path: Path,
    *,
    ownship_start: OwnshipStart,
    legs: list[FlightLeg],
    placed_units: list[PlacedUnit],
    half_extent_x_m: float,
    half_extent_z_m: float,
    on_tick: object = None,
    world_model_db: Path | None = None,
) -> tuple[ConsolePerceptionRunner, CrewConsole, io.StringIO, Path]:
    """Builds, starts, and fully drains one scenario through the real
    threaded crew-text loop, calling `on_tick(runner, crew_console)` (if
    given) after every poll the foreground thread observes -- the hook a
    scenario test uses to issue `engage`/sample believed position at an
    exact point in the run, and to record per-poll series for monotonic
    assertions. Returns once the final frame has been reached and the
    poll thread has stopped. The fourth element is the world-model
    `.sqlite` path used for this scenario, built here unless the caller
    already built one (needed by a scenario that opens its own
    foreground-thread-local connection, `_ForegroundEnrichment` below,
    before `on_tick` can use it -- this function's own return value
    arrives too late for that)."""
    frames = build_scenario_frames(ownship_start, legs, placed_units, theatre=_THEATRE)
    if world_model_db is None:
        world_model_db = _world_model_path(
            tmp_path, half_extent_x_m=half_extent_x_m, half_extent_z_m=half_extent_z_m
        )
    server = MockAircraftLayerServer(frames)
    url = server.start()
    try:
        aircraft_client = AircraftLayerClient(base_url=url)
        tasks = TaskStore()
        tasks.create(
            "scan_area",
            AttentionArea(
                id="AREA_AHEAD",
                center=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
                radius_m=None,
                level="watch",
                source="scan_area",
                relative_sector="ahead",
            ),
            created_sim=1_000_000.0,
            deadline_sim=1_000_000_000.0,
            reason="test-fixture-ahead-scan",
        )
        runner = ConsolePerceptionRunner(aircraft_client=aircraft_client, tasks=tasks)
        output = io.StringIO()
        crew_console = CrewConsole(
            store=runner.store,
            output=output,
            aircraft_client=aircraft_client,
            tasks=tasks,
        )
        stop_event = threading.Event()
        poll_thread = threading.Thread(
            target=_run_crew_text_poll_loop,
            args=(
                runner,
                crew_console,
                aircraft_client,
                _THEATRE,
                world_model_db,
                _POLL_INTERVAL_S,
                stop_event,
            ),
            daemon=True,
        )
        poll_thread.start()
        try:
            final_t_sim = frames[-1]["telemetry"]["dcs_model_time_s"]
            seen_t_sims: set[float] = set()
            deadline = time.monotonic() + _THREAD_JOIN_TIMEOUT_S
            while time.monotonic() < deadline:
                current = runner.last_t_sim
                if current is not None and current not in seen_t_sims:
                    seen_t_sims.add(current)
                    if on_tick is not None:
                        on_tick(runner, crew_console)  # type: ignore[operator]
                if current == final_t_sim:
                    break
                time.sleep(_WAIT_POLL_S)
            assert runner.last_t_sim == final_t_sim, (
                "poll thread did not reach the scenario's final frame within "
                f"{_THREAD_JOIN_TIMEOUT_S}s"
            )
        finally:
            stop_event.set()
            poll_thread.join(timeout=_THREAD_JOIN_TIMEOUT_S)
        assert not poll_thread.is_alive()
        return runner, crew_console, output, world_model_db
    finally:
        server.stop()


class _ForegroundEnrichment:
    """Lets the test (foreground) thread call `CrewConsole.handle_command`
    for a command that needs `self.enrichment` (`"engage"` with a
    descriptor/clock/sector slot, via `_resolve_attack_target` ->
    `_report_scope` -> `get_contacts`) without touching
    `ConsolePerceptionRunner.enrichment` -- that object's
    `sqlite3.Connection` was opened on the background poll thread, and
    `sqlite3.Connection`s are thread-affine (`check_same_thread=True`),
    so a foreground read raises `sqlite3.ProgrammingError`. Confirmed by
    running it, not assumed: this exact bug, same mechanism, is already
    documented and fixed for the real REPL thread in
    `body._run_crew_text_repl`'s own docstring/BL-B96 fix -- "build a
    REPL-thread-local `sqlite3.Connection`/`EnrichmentContext`... rather
    than reading `runner.enrichment` at all." This class is that same
    fix, applied here because this test's foreground thread plays the
    REPL thread's role when it calls `handle_command` directly instead of
    through `_run_crew_text_repl`."""

    def __init__(self, world_model_db: Path) -> None:
        self._conn = open_world_model(world_model_db)

    def install(
        self, runner: ConsolePerceptionRunner, crew_console: CrewConsole
    ) -> None:
        if runner.world_model_store is None or runner.last_ownship_state is None:
            return
        theatre, _path = runner.world_model_store
        crew_console.enrichment = EnrichmentContext(
            conn=self._conn, theatre=theatre, ownship=runner.last_ownship_state
        )

    def close(self) -> None:
        self._conn.close()


def _single_surface_contact(store: ContactStore) -> Contact | None:
    """Every single-unit scenario below expects at most one contact, and
    the naked-eye channel's raw classification for a lone group at range
    is `OP_GROUPSOMETHING` (presence-only), never the placed unit's own
    `object_type` string -- confirmed by running the harness, not
    assumed from `object_type`/`fold_classification`'s level table.
    `on_surface` (not the raw text) is what actually distinguishes "the
    scenario's one ground contact" from anything else that could in
    principle appear."""
    surface_contacts = [c for c in store.contacts if c.on_surface]
    if len(surface_contacts) != 1:
        return None
    return surface_contacts[0]


# --- Scenario 1: Run 1 shape -- seen high, ~400 m descent, overflight ------


def test_run1_overflight_believed_altitude_never_exceeds_ownship(
    tmp_path: Path,
) -> None:
    """Mirrors the 2026-10-30 sortie's Run 1: ownship sees a group from
    above, descends ~400 m while closing, and overflies it. Asserts the
    believed point is never above ownship at any poll -- the sortie's own
    defect (alignment finding 2: believed elevation tracking the true
    depression, never climbing to an impossible +72 deg as range closes
    toward zero under the old flat-projection model).

    **Stage 7 amendment (review.md Finding 2)**: a shallow `Turn` onto
    the final bearing precedes the `Descend`, per the user's plural
    "mock flights that still contain some aircraft manoeuvre" -- this
    scenario's own invariant (believed altitude never above ownship) is
    general, not geometry-specific, so adding a real heading change
    ahead of the descent does not weaken what it tests."""
    ground_alt_m = 0.0
    unit = PlacedUnit(
        object_id=201,
        unit_name="unit_201",
        object_type="T-72",
        x=0.0,
        z=0.0,
        ground_alt_m=ground_alt_m,
    )
    ownship_start = OwnshipStart(
        x=-1800.0,
        z=-130.0,
        heading_deg=15.0,
        altitude_msl_m=400.0,
        altitude_agl_m=400.0,
    )
    legs: list[FlightLeg] = [
        Turn(
            duration_s=10.0,
            speed_mps=51.0,
            end_heading_deg=0.0,
            altitude_msl_m=400.0,
            altitude_agl_m=400.0,
            bank_deg=15.0,
        ),
        Descend(
            duration_s=70.0,
            speed_mps=51.0,
            heading_deg=0.0,
            end_altitude_msl_m=20.0,
            end_altitude_agl_m=20.0,
            pitch_deg=-5.0,
        ),
    ]
    believed_alt_over_ownship_alt: list[tuple[float, float]] = []

    def on_tick(runner: ConsolePerceptionRunner, crew_console: CrewConsole) -> None:
        contact = _single_surface_contact(runner.store)
        if contact is None:
            return
        ownship = runner.last_ownship_state
        if ownship is None:
            return
        believed_alt_over_ownship_alt.append(
            (contact.last_position.alt_m, ownship.alt_m)
        )

    _run_scenario(
        tmp_path,
        ownship_start=ownship_start,
        legs=legs,
        placed_units=[unit],
        half_extent_x_m=2500.0,
        half_extent_z_m=1000.0,
        on_tick=on_tick,
    )

    assert believed_alt_over_ownship_alt, (
        "the group was never detected across this run -- cannot test the "
        "overflight defect without at least one poll of belief"
    )
    for believed_alt_m, ownship_alt_m in believed_alt_over_ownship_alt:
        assert believed_alt_m <= ownship_alt_m, (
            f"believed altitude {believed_alt_m} above ownship altitude "
            f"{ownship_alt_m} -- the overflight defect this scenario guards "
            "against"
        )


# --- Scenario 2: Run 2 shape -- shallow approach from 5 km -----------------


@dataclass
class _EngageState:
    """Mutable, properly-typed state the `on_tick` closure below writes
    and the test body reads after `_run_scenario` returns -- a typed
    alternative to a `dict[str, object]`, which `mypy --strict` cannot
    narrow back to each field's own type."""

    done: bool = False
    lines: list[str] | None = None
    pre_engage_count: int | None = None


def test_run2_shallow_approach_range_error_converges_and_bounded(
    tmp_path: Path,
) -> None:
    """Mirrors Run 2: a level closing approach from 5 km at 400 m AGL,
    preceded by a shallow `Turn` onto the run-in heading (Stage 7
    amendment, review.md Finding 2 -- the user's plural "mock flights
    that still contain some aircraft manoeuvre"). Naked-eye detection
    only begins once true range crosses the angular-size gate for a 7 m
    (T-72-sized) object (~2.3 km at the default `UNAIDED_OPTIC`/
    `LOWRES_ANGULAR_RADIUS_RAD`) -- this scenario is long enough to run
    well past that point. Asserts: range error (believed vs. true
    horizontal ground range) stays inside the plan's own ~700 m budget
    (300 m AGL / 4 km row) at every observed poll, and is no worse at
    the end of the run than at the first poll the contact was observed
    (the fused estimator's declared "tighter at steep geometry"
    convergence, not merely "ends up small by luck"). Also engages the
    target mid-run (`handle_command`, see module docstring) and asserts
    the engage readback is spoken.

    **Not asserted here, by scope**: the plan's own "`render_tracking()`'s
    line appears ... exactly once" claim, which needs a `weapon=
    "missiles"` run. Confirmed by running it: `_handle_engage` gates
    `"missiles"` on `self.sight_ready`, which this harness never sets
    True -- it is refreshed every poll from `belief.sight_effector.
    sight_ready(GuidanceUnitState())`, and this scenario wires no
    `--slew-trace`/effector-sequences infrastructure to ever move that
    state off its all-`False` default (confirmed directly: that call
    returns `False`). Simulating a ready guidance unit is effector-engine
    scope, not this scenario builder's; a `weapon="missiles"`-capable
    scenario is a later addition here, not a silent downgrade of this
    one -- this scenario engages with the guns/rockets-equivalent bare
    `weapon=None` instead, which `_handle_engage` does not gate.

    **review.md's Finding 3/Optional Refinement (sight tracking across
    the engage-time jump) was investigated, not added as an assertion
    here -- confirmed by running it, not assumed.** `runner.sight_head.
    mode` stays `"off"` for this scenario's entire run, before and after
    `engage`: the same reason `"missiles"` is gated above --
    `sight_ready`/the effector-engine wiring this harness never builds
    is also what moves the head out of `"off"` in the first place
    (`body.py`'s own sight-tier activation reads the guidance unit's
    readiness). So `aim_source` is `"belief"` throughout regardless of
    `engage`, by construction of this harness, not because the sight
    fails to lock -- asserting `aim_source != "belief"` here would be a
    tautological failure the harness can never pass, not a check of the
    real mechanism. A scenario that actually exercises sight tracking
    across `engage` needs the effector-engine wiring `weapon="missiles"`
    above already flags as a later addition, not a change to this one."""
    ground_alt_m = 0.0
    unit = PlacedUnit(
        object_id=202,
        unit_name="unit_202",
        object_type="T-72",
        x=0.0,
        z=0.0,
        ground_alt_m=ground_alt_m,
    )
    ownship_start = OwnshipStart(
        x=-5000.0,
        z=-220.0,
        heading_deg=10.0,
        altitude_msl_m=400.0,
        altitude_agl_m=400.0,
    )
    legs: list[FlightLeg] = [
        # Shallow turn onto the run-in heading (Stage 7 amendment) --
        # the offset start/heading above are not yet aimed at the unit.
        Turn(
            duration_s=10.0,
            speed_mps=51.0,
            end_heading_deg=0.0,
            altitude_msl_m=400.0,
            altitude_agl_m=400.0,
            bank_deg=10.0,
        ),
        # Stops around 900 m true ground range, short of point-blank --
        # the plan's own envelope table is itself scoped to "300 m AGL /
        # 4 km", not point-blank range, so this scenario deliberately
        # does not run all the way to overflight. **Corrected comment
        # (review.md's Optional Refinement)**: the original version of
        # this comment claimed a single-look `1/tan` sensitivity makes
        # absolute range error "grow again" close in -- checked directly
        # against `surface_range_estimate` (a numeric sweep at fixed
        # AGL=400 m, distance 5000->1 m): `sigma_down_m` decreases
        # monotonically as true distance shrinks; there is no single-
        # look blow-up near 900 m. Any apparent growth close in is a
        # *fused-belief* lag effect (several past looks averaged while
        # closing fast), not a per-look estimator defect -- the scoping
        # decision to stop at ~900 m stands on its own (outside the
        # plan's tested envelope, whose nearest grid point is 500 m),
        # not on the original, incorrect mechanism claim.
        Level(
            duration_s=68.0,
            speed_mps=51.0,
            heading_deg=0.0,
            altitude_msl_m=400.0,
            altitude_agl_m=400.0,
        ),
    ]
    range_errors: list[float] = []
    engaged = _EngageState()
    world_model_db = _world_model_path(
        tmp_path, half_extent_x_m=6000.0, half_extent_z_m=1000.0
    )
    # Built on this (foreground/test) thread, deliberately never
    # `runner.enrichment` -- see `_ForegroundEnrichment`'s own docstring
    # for the cross-thread `sqlite3.ProgrammingError` this avoids.
    foreground_enrichment = _ForegroundEnrichment(world_model_db)

    def on_tick(runner: ConsolePerceptionRunner, crew_console: CrewConsole) -> None:
        contact = _single_surface_contact(runner.store)
        ownship = runner.last_ownship_state
        if contact is not None and ownship is not None:
            observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
            true_range_m = horizontal_range_m(
                observer, GeoPosition(x=unit.x, z=unit.z, alt_m=ground_alt_m)
            )
            believed_range_m = horizontal_range_m(observer, contact.last_position)
            range_errors.append(abs(believed_range_m - true_range_m))
            if not engaged.done and true_range_m < 1800.0:
                # Set to `len(range_errors)` at the poll "engage" is
                # issued -- see the convergence assertion below for why
                # the comparison is scoped to this prefix, not the whole
                # series.
                engaged.pre_engage_count = len(range_errors)
                foreground_enrichment.install(runner, crew_console)
                engaged.lines = crew_console.handle_command(
                    "engage",
                    runner.last_t_sim or 0.0,
                    slots={"clock": 12},
                )
                engaged.done = True

    try:
        _runner, _crew_console, output, _world_model_db = _run_scenario(
            tmp_path,
            ownship_start=ownship_start,
            legs=legs,
            placed_units=[unit],
            half_extent_x_m=6000.0,
            half_extent_z_m=1000.0,
            on_tick=on_tick,
            world_model_db=world_model_db,
        )
    finally:
        foreground_enrichment.close()

    assert range_errors, "the group was never detected across this run"
    for error_m in range_errors:
        assert error_m <= 700.0, f"range error {error_m} m exceeds the ~700 m budget"
    # Convergence is checked only up to the poll "engage" was issued, not
    # across the whole series. Confirmed by running it: once
    # `attack_target_task` registers a "priority" attention task,
    # subsequent naked-eye looks at this contact no longer follow the
    # scan-ahead task's own 11->12->1 cycle the same way, so the specific
    # set of per-look hash draws contributing to the believed position
    # after "engage" differs from the pre-engage, cycling-only series --
    # a real, intended attention effect (Petrovich looks more
    # attentively at an engaged target), not a position-writing defect.
    # Isolated by running the engage call's own pieces individually: a
    # read-only `get_contacts`, `set_attention` alone, and
    # `attack_target_task` alone each left the post-call series
    # unchanged from the no-engage baseline; only going through
    # `_handle_engage` itself (which also flips `attack_run_transition`,
    # activating `body.py`'s attack-run/gaze machinery each subsequent
    # poll) changed it. Budget compliance above already covers the
    # post-engage portion; this assertion covers the "tighter while
    # closing" claim for the span where nothing but closing range has
    # changed.
    pre_engage_count = engaged.pre_engage_count
    assert pre_engage_count is not None and pre_engage_count >= 1
    pre_engage_errors = range_errors[:pre_engage_count]
    assert pre_engage_errors[-1] <= pre_engage_errors[0], (
        f"pre-engage range error {pre_engage_errors[-1]} m is worse than the "
        f"first observed poll's {pre_engage_errors[0]} m -- expected "
        "convergence while closing, not merely a small final value"
    )
    assert engaged.done, "never got close enough to issue 'engage' in this run"
    engage_lines = engaged.lines
    assert engage_lines, f"'engage' produced no readback at all: {output.getvalue()!r}"
    assert "no target selected" not in engage_lines[0]
    assert "no such contact" not in engage_lines[0]


# --- Scenario 3: two groups on one bearing stay two contacts ---------------


def test_two_groups_one_bearing_stay_two_contacts(tmp_path: Path) -> None:
    """Mirrors Stage 4's own association scenario geometry (two groups at
    3 km/4.5 km, same bearing) -- **Stage 7 amendment (review.md
    Finding 1/2)**: a genuine closing run with a `Turn`, not the
    fully-stationary redesign review.md found was built specifically to
    dodge the E5 fold this scenario exists to test. Shape: `Level` on an
    offset heading (approaching from the near/far groups' side, not
    already on their bearing), `Turn` onto heading 0 deg (the groups'
    own bearing from the x-axis), then a long closing `Level` at 300 m
    AGL -- the same AGL Stage 4's own closing-run sub-case (c) and the
    plan's own forward-mask figures (`743 m = 300 / tan(22 deg)`) use.
    The lateral offset (`z=-500` once the turn completes, held for the
    rest of the run) is chosen, by direct numeric integration of this
    module's own trajectory (not guessed), so the closest *true-geometry*
    approach to the near group (3000 m) is ~508 m -- inside the 743 m
    forward-mask threshold, so the near group's true range does cross
    into masking range during this run, not merely close on it.

    **Outcome, checked empirically against the real pipeline, not
    assumed from true-geometry ranges or from Stage 8's own
    order-of-magnitude argument**: confirmed by running this scenario
    (`implementation.md`'s own recorded measurement) -- the near group
    founds its own contact once admitted (~t=85s of this run), the far
    group founds its own, second contact once *it* is admitted
    (~t=135s), and the count never drops back from 2 to 1 anywhere in
    the run. No fold. Per the dispatch's own stop condition, if a future
    change to this scenario or to the gate ever makes this run fold to
    one contact, that is the stop-and-report case -- do not retune the
    gate or re-flatten the scenario; escalate instead."""
    near_unit = PlacedUnit(
        object_id=301,
        unit_name="unit_301",
        object_type="T-72",
        x=3000.0,
        z=0.0,
        ground_alt_m=0.0,
    )
    far_unit = PlacedUnit(
        object_id=302,
        unit_name="unit_302",
        object_type="T-72",
        x=4500.0,
        z=0.0,
        ground_alt_m=0.0,
    )
    # Start offset to the south-west of the groups' bearing line, heading
    # 35 deg (not yet aimed at either group) -- a real approach-then-turn
    # shape, not a disguised straight-line closing run.
    ownship_start = OwnshipStart(
        x=-3000.0,
        z=-1237.6,
        heading_deg=35.0,
        altitude_msl_m=300.0,
        altitude_agl_m=300.0,
    )
    legs: list[FlightLeg] = [
        Level(
            duration_s=20.0,
            speed_mps=51.0,
            heading_deg=35.0,
            altitude_msl_m=300.0,
            altitude_agl_m=300.0,
        ),
        Turn(
            duration_s=15.0,
            speed_mps=51.0,
            end_heading_deg=0.0,
            altitude_msl_m=300.0,
            altitude_agl_m=300.0,
            bank_deg=25.0,
        ),
        Level(
            duration_s=130.0,
            speed_mps=51.0,
            heading_deg=0.0,
            altitude_msl_m=300.0,
            altitude_agl_m=300.0,
        ),
    ]
    contact_counts: list[int] = []

    def on_tick(runner: ConsolePerceptionRunner, crew_console: CrewConsole) -> None:
        if runner.store.contacts:
            contact_counts.append(len(runner.store.contacts))

    runner, _crew_console, _output, _world_model_db = _run_scenario(
        tmp_path,
        ownship_start=ownship_start,
        legs=legs,
        placed_units=[near_unit, far_unit],
        half_extent_x_m=6500.0,
        half_extent_z_m=2000.0,
        on_tick=on_tick,
    )

    assert contact_counts, "neither group was ever detected across this run"
    # Confirmed by running this scenario (see `implementation.md`'s own
    # recorded measurement): the near group founds first (count 1, ~t=85s
    # in this run -- the far group is not yet in range), then the far
    # group founds its own, second contact (count 2, ~t=135s) once it
    # enters the naked-eye channel's angular-size gate -- a real
    # single-contact *prefix*, not a fold. The actual E5 fold would show
    # as the count **dropping back to 1** after reaching 2 (the far
    # group's first look merging into the near group's own masked,
    # decay-widened contact) -- never observed in this run. So the
    # invariant this stage actually tests is "non-decreasing, and 2 by
    # the end of the run", not "always 2 from the first poll"; the
    # earlier single-contact prefix is expected, not a defect.
    assert contact_counts == sorted(contact_counts), (
        f"contact count dropped during the run ({contact_counts}) -- this "
        "is the E5 fold Stage 8 exists to prevent (two founded contacts "
        "collapsing into one) if it ever happens. Per the plan's own "
        "Stage 4 stop condition and the dispatch's own instruction, do "
        "not retune the gate or re-flatten this scenario if this fails "
        "-- escalate instead"
    )
    assert contact_counts[-1] == 2, (
        f"expected exactly two contacts by the end of this run, got "
        f"{contact_counts[-1]} -- the far group was never founded as its "
        "own contact"
    )
    # Exactly one `CONTACT_DETECTED` per group, never a third founding
    # event -- the actual "no spurious merge or re-split" signature.
    # A `CONTACT_CLASSIFICATION_CHANGED` does occur (confirmed by running
    # it: CONTACT_1 refines its classification after more looks) and is
    # not itself evidence of a merge -- the plan's own "no spurious-merge
    # event" was read, before running this, as "ban the event kind
    # outright"; running it shows that reading was wrong, since a benign
    # refinement fires the same event kind a merge would.
    assert [event.kind for event in runner.store.events].count("CONTACT_DETECTED") == 2

    final_t_sim = runner.last_t_sim
    assert final_t_sim is not None
    contacts = get_contacts(runner.store, final_t_sim)
    assert len(contacts) == 2
    for contact_result in contacts:
        contact_id = contact_result["facts"]["id"]
        assert isinstance(contact_id, str)
        described = describe_contact(runner.store, contact_id, final_t_sim)
        assert described is not None
        contact_obj = next(c for c in runner.store.contacts if c.id == contact_id)
        assert contact_obj.contributing_observation_ids, (
            f"contact {contact_id} carries no observations"
        )


# --- Scenario 4: cockpit-mask boundary cases -------------------------------


def test_cockpit_mask_forward_boundary_suppresses_then_recovers_callout(
    tmp_path: Path,
) -> None:
    """Forward-mask boundary (`perception.cockpit_mask`'s forward
    breakpoint, 22 deg max depression out to 60 deg azimuth): at 300 m
    AGL level flight the threshold range is `300 / tan(22 deg) ~= 743 m`
    (plan's own "~740 m forward" figure, read off the mask table rather
    than re-derived here -- placed generously either side per the plan's
    own Risks note). Closes a forward unit through that threshold and
    asserts `Contact.last_observable_sim` stops advancing once inside it
    (masked, not spoken about) while the contact's believed position is
    still being updated -- the "masked, not guided at a point behind the
    mask" distinction the plan draws.

    **Stage 7 amendment (review.md Finding 2)**: a short `Turn` onto the
    final run-in heading precedes the long closing `Level` leg, per the
    user's plural "mock flights that still contain some aircraft
    manoeuvre" -- the mask-boundary geometry below is unaffected (the
    turn happens far outside the mask radius, at slow speed, and ends on
    the same heading 0 deg the rest of this test already assumed)."""
    unit = PlacedUnit(
        object_id=401,
        unit_name="unit_401",
        object_type="T-72",
        x=0.0,
        z=0.0,
        ground_alt_m=0.0,
    )
    # Generous margins either side of the ~743 m computed threshold, per
    # this plan's own Risks note on the exact boundary not being re-derived
    # here: closes from 2000 m (well outside) down to well inside it.
    ownship_start = OwnshipStart(
        x=-2000.0,
        z=-60.0,
        heading_deg=8.0,
        altitude_msl_m=300.0,
        altitude_agl_m=300.0,
    )
    legs: list[FlightLeg] = [
        Turn(
            duration_s=10.0,
            speed_mps=10.0,
            end_heading_deg=0.0,
            altitude_msl_m=300.0,
            altitude_agl_m=300.0,
            bank_deg=8.0,
        ),
        Level(
            duration_s=155.0,
            speed_mps=10.0,
            heading_deg=0.0,
            altitude_msl_m=300.0,
            altitude_agl_m=300.0,
        ),
    ]
    observable_series: list[tuple[float, bool, float]] = []

    def on_tick(runner: ConsolePerceptionRunner, crew_console: CrewConsole) -> None:
        contact = _single_surface_contact(runner.store)
        ownship = runner.last_ownship_state
        if contact is None or ownship is None or runner.last_t_sim is None:
            return
        true_range_m = horizontal_range_m(
            GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m),
            GeoPosition(x=unit.x, z=unit.z, alt_m=0.0),
        )
        observable = contact.last_observable_sim == runner.last_t_sim
        observable_series.append((true_range_m, observable, runner.last_t_sim))

    _run_scenario(
        tmp_path,
        ownship_start=ownship_start,
        legs=legs,
        placed_units=[unit],
        half_extent_x_m=2500.0,
        half_extent_z_m=1000.0,
        on_tick=on_tick,
    )

    assert observable_series, "the unit was never detected across this run"
    far_observable = [obs for range_m, obs, _ in observable_series if range_m > 900.0]
    near_observable = [obs for range_m, obs, _ in observable_series if range_m < 600.0]
    assert far_observable, "no polls recorded outside the mask threshold"
    assert near_observable, "no polls recorded inside the mask threshold"
    assert any(far_observable), (
        "expected the unit observable while still forward of the mask"
    )
    assert not any(near_observable), (
        "expected the unit masked (last_observable_sim stale) once inside "
        "the ~743 m forward cockpit-mask threshold"
    )


def test_cockpit_mask_pitch_down_recovers_masked_forward_target(
    tmp_path: Path,
) -> None:
    """The mask angle moves with pitch (`perception.cockpit_mask.
    is_visible` works in body-relative, not ownship-relative, angles): a
    target masked in level flight comes back into view once the nose
    pitches down toward it, without ever having been reported while
    masked. Three legs: approach (closes from well outside the mask
    radius so the contact is founded while still visible), a level hold
    well inside it (masked throughout -- confirmed by running it:
    `Contact.last_observable_sim` stops advancing by true range ~850 m,
    not exactly the ~743 m computed threshold, because the mask gate
    reads the *believed* position, not true range -- `_run1_overflight`'s
    own docstring makes the same point from the other direction), then a
    pitch-down leg at the same holding point. Asserts observability
    never resumes during the hold, and does resume once the nose pitches
    down."""
    unit = PlacedUnit(
        object_id=402,
        unit_name="unit_402",
        object_type="T-72",
        x=0.0,
        z=0.0,
        ground_alt_m=0.0,
    )
    ownship_start = OwnshipStart(
        x=-2000.0, z=0.0, heading_deg=0.0, altitude_msl_m=300.0, altitude_agl_m=300.0
    )
    #: Confirmed by running it: masked from true range ~850 m through the
    #: end of the level hold (t=115..200), observable again from the
    #: first pitch-down poll (t=205) onward.
    _HOLD_ENDS_T_SIM = 200.0
    _MASK_ESTABLISHED_T_SIM = 115.0
    legs: list[FlightLeg] = [
        # Approach from well outside the mask radius (visible, founds the
        # contact) down to a fixed holding point well inside it.
        Level(
            duration_s=160.0,
            speed_mps=10.0,
            heading_deg=0.0,
            altitude_msl_m=300.0,
            altitude_agl_m=300.0,
        ),
        # Hold at that point, still level/nose-level -- masked throughout.
        Level(
            duration_s=40.0,
            speed_mps=0.0,
            heading_deg=0.0,
            altitude_msl_m=300.0,
            altitude_agl_m=300.0,
        ),
        # Pitch down hard toward the now-close target without closing
        # further (near-zero groundspeed) -- isolates the pitch effect on
        # the mask from any further range change.
        Descend(
            duration_s=20.0,
            speed_mps=0.1,
            heading_deg=0.0,
            end_altitude_msl_m=300.0,
            end_altitude_agl_m=300.0,
            pitch_deg=-30.0,
        ),
    ]
    masked_during_hold = {"value": True}
    observable_after_pitch_down = {"value": False}

    def on_tick(runner: ConsolePerceptionRunner, crew_console: CrewConsole) -> None:
        contact = _single_surface_contact(runner.store)
        if contact is None or runner.last_t_sim is None:
            return
        observable = contact.last_observable_sim == runner.last_t_sim
        if _MASK_ESTABLISHED_T_SIM <= runner.last_t_sim < _HOLD_ENDS_T_SIM:
            if observable:
                masked_during_hold["value"] = False
        elif runner.last_t_sim >= _HOLD_ENDS_T_SIM and observable:
            observable_after_pitch_down["value"] = True

    _run_scenario(
        tmp_path,
        ownship_start=ownship_start,
        legs=legs,
        placed_units=[unit],
        half_extent_x_m=2500.0,
        half_extent_z_m=1000.0,
        on_tick=on_tick,
    )

    assert masked_during_hold["value"], (
        "expected the target masked (never observable) throughout the "
        "level-flight holding leg"
    )
    assert observable_after_pitch_down["value"], (
        "expected the target observable again once the nose pitched down toward it"
    )
