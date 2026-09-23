"""The binocular decision: when Petrovich raises them and when he stops.

`plans/binocular-optic/plan.md` Stage 2. Everything here is pure -- no
store, no telemetry, no clock -- which is the property that keeps a replay
identical and the reason the policy takes `LookTarget`s rather than
`Contact`s.
"""

from __future__ import annotations

from belief.optic_policy import (
    MAX_LOOK_S,
    RETRY_RANGE_FRACTION,
    STEADY_RATE_LIMIT_DEG_S,
    LookTarget,
    OpticPhase,
    OpticState,
    choose_look,
    decide,
    improvement_window_m,
    is_steady,
    is_worth_a_look,
    lower_binoculars,
)
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC

_CYCLE_S = 16.0


def _target(
    contact_id: str = "CONTACT_1",
    *,
    azimuth_deg: float = 0.0,
    elevation_deg: float = 0.0,
    range_m: float = 1_000.0,
    object_type: str = "T-72",
    current_level: str = "presence",
) -> LookTarget:
    return LookTarget(
        contact_id=contact_id,
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
        range_m=range_m,
        object_type=object_type,
        current_level=current_level,
    )


class TestImprovementWindow:
    """The trigger is computed from the calibration the eye itself uses,
    not from a tuned threshold."""

    def test_a_presence_contact_is_glassed_to_classify_it(self) -> None:
        """The common case, and the wide one: 500 m unaided against
        1750 m glassed for a 7 m vehicle."""
        lower_m, upper_m = improvement_window_m("T-72", current_level="presence")
        assert lower_m < upper_m
        assert upper_m > 1_000.0

    def test_a_classed_contact_is_glassed_to_identify_it(self) -> None:
        """A narrower band, because type needs resolved shape detail."""
        _, class_upper_m = improvement_window_m("T-72", current_level="presence")
        _, type_upper_m = improvement_window_m("T-72", current_level="class")
        assert type_upper_m < class_upper_m

    def test_an_identified_contact_has_no_window_at_all(self) -> None:
        """Nothing left to learn -- and the empty window is what makes
        that fall out of the same predicate rather than a special case."""
        assert improvement_window_m("T-72", current_level="type") == (0.0, 0.0)

    def test_binoculars_always_reach_further_than_the_eye(self) -> None:
        for object_type in ("T-72", "Ural-375", "Infantry"):
            lower_m, upper_m = improvement_window_m(
                object_type, current_level="presence"
            )
            assert upper_m > lower_m, object_type


class TestIsWorthALook:
    def test_a_contact_inside_the_window_is_worth_it(self) -> None:
        assert is_worth_a_look(_target(range_m=1_000.0), OpticState())

    def test_a_contact_too_close_is_not(self) -> None:
        """The naked eye reaches that tier on the next dwell anyway, so a
        look there spends the budget to learn nothing."""
        lower_m, _ = improvement_window_m("T-72", current_level="presence")
        assert not is_worth_a_look(_target(range_m=lower_m - 1.0), OpticState())

    def test_a_contact_too_far_is_not(self) -> None:
        """Binoculars would not reach the next tier either."""
        _, upper_m = improvement_window_m("T-72", current_level="presence")
        assert not is_worth_a_look(_target(range_m=upper_m + 1.0), OpticState())

    def test_an_already_identified_contact_is_never_worth_it(self) -> None:
        assert not is_worth_a_look(_target(current_level="type"), OpticState())

    def test_a_failed_look_is_not_retried_at_the_same_range(self) -> None:
        """The contact has not become more identifiable, so re-asking
        spends a look another contact could have used."""
        state = OpticState(attempted_at_range_m={"CONTACT_1": 1_000.0})
        assert not is_worth_a_look(_target(range_m=1_000.0), state)

    def test_a_failed_look_is_retried_once_it_has_closed(self) -> None:
        state = OpticState(attempted_at_range_m={"CONTACT_1": 1_000.0})
        closed_m = 1_000.0 * RETRY_RANGE_FRACTION - 1.0
        assert is_worth_a_look(_target(range_m=closed_m), state)


class TestSteadiness:
    def test_level_flight_is_steady(self) -> None:
        samples = [(0.0, 1.0, 0.0, 90.0), (1.0, 1.0, 0.0, 90.0)]
        assert is_steady(samples)

    def test_a_hard_bank_is_not(self) -> None:
        samples = [
            (0.0, 0.0, 0.0, 90.0),
            (1.0, 0.0, STEADY_RATE_LIMIT_DEG_S + 5.0, 90.0),
        ]
        assert not is_steady(samples)

    def test_a_fast_heading_change_is_not(self) -> None:
        samples = [(0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, STEADY_RATE_LIMIT_DEG_S + 5.0)]
        assert not is_steady(samples)

    def test_crossing_north_is_not_a_manoeuvre(self) -> None:
        """359 -> 1 degrees is two degrees of turn, not 358. Without the
        wrap every northerly heading would forbid binoculars."""
        samples = [(0.0, 0.0, 0.0, 359.0), (1.0, 0.0, 0.0, 1.0)]
        assert is_steady(samples)

    def test_no_history_is_treated_as_steady(self) -> None:
        """At startup there is no evidence of manoeuvring, and refusing to
        look until proven calm would make the instrument unusable for the
        first seconds of every mission."""
        assert is_steady([])
        assert is_steady([(0.0, 0.0, 0.0, 0.0)])

    def test_a_duplicate_timestamp_does_not_divide_by_zero(self) -> None:
        samples = [(5.0, 0.0, 0.0, 0.0), (5.0, 0.0, 40.0, 0.0)]
        assert is_steady(samples)


class TestChooseLook:
    def test_the_direction_covering_the_most_contacts_wins(self) -> None:
        """The optic is a property of the look, not of a target, so one
        look resolves everything in the cone -- pointing at the nearest
        contact instead would spend the same look on one of them."""
        clustered = [
            _target("CONTACT_1", azimuth_deg=40.0, range_m=1_200.0),
            _target("CONTACT_2", azimuth_deg=41.0, range_m=1_200.0),
            _target("CONTACT_3", azimuth_deg=42.0, range_m=1_200.0),
        ]
        lone_but_closer = _target("CONTACT_4", azimuth_deg=-60.0, range_m=600.0)

        chosen = choose_look([*clustered, lone_but_closer])

        assert chosen is not None
        assert chosen.contact_id in {"CONTACT_1", "CONTACT_2", "CONTACT_3"}

    def test_ties_break_toward_the_closer_contact(self) -> None:
        near = _target("CONTACT_NEAR", azimuth_deg=-30.0, range_m=600.0)
        far = _target("CONTACT_FAR", azimuth_deg=30.0, range_m=1_500.0)
        chosen = choose_look([near, far])
        assert chosen is not None
        assert chosen.contact_id == "CONTACT_NEAR"

    def test_nothing_to_look_at_chooses_nothing(self) -> None:
        assert choose_look([]) is None


class TestPhaseCycle:
    """The lockout is structural: a glass phase is only reachable from the
    end of a completed scan phase, so "at least one naked eye scan between
    uses" cannot be violated."""

    def test_binoculars_are_not_raised_mid_scan(self) -> None:
        """The user's clarification: finish the pass first, so it gathers
        as many naked-eye detections as it can."""
        state = OpticState(phase_started_sim=0.0)
        state, decision = decide(
            state,
            now_sim=_CYCLE_S / 2,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC

    def test_binoculars_come_up_at_the_end_of_a_completed_scan(self) -> None:
        state, decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING
        assert decision.optic is BINOCULAR_OPTIC
        assert decision.look_azimuth_deg is not None

    def test_a_faster_scan_plan_brings_them_round_sooner(self) -> None:
        """ "Depends on scan mode" -- a commanded sector cycles faster than
        a free scan, so binoculars come round more often, and nothing in
        the policy computes that."""
        fast_period_s = 4.0
        state, _decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=fast_period_s,
            scan_cycle_period_s=fast_period_s,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING

    def test_nothing_worth_looking_at_restarts_the_scan(self) -> None:
        """Otherwise a completed phase with no work would sit forever and
        never complete again."""
        state, decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING
        assert state.phase_started_sim == _CYCLE_S
        assert decision.optic is UNAIDED_OPTIC

    def test_a_look_ends_when_nothing_in_the_cone_can_improve(self) -> None:
        """The user's stop condition, which is sharper than the timer: the
        contact resolved, so there is nothing left to learn from staring."""
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING

        resolved = _target(current_level="type")
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + 1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[resolved],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC

    def test_a_look_ends_at_the_cap_when_recognition_never_comes(self) -> None:
        """The case the cap exists for: still in the window, still
        unresolved, and staring longer is not going to help."""
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        state, _decision = decide(
            state,
            now_sim=_CYCLE_S + MAX_LOOK_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING

    def test_a_look_holds_while_there_is_still_something_to_learn(self) -> None:
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + 1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING
        assert decision.optic is BINOCULAR_OPTIC

    def test_the_scan_must_complete_again_before_the_next_look(self) -> None:
        """The lockout, demonstrated end to end: a finished look cannot be
        followed immediately by another."""
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        # The look ends.
        state, _ = decide(
            state,
            now_sim=_CYCLE_S + MAX_LOOK_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target("CONTACT_2")],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING

        # Immediately afterwards, with something still worth seeing.
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + MAX_LOOK_S + 1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target("CONTACT_2")],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC


class TestSteadinessGate:
    def test_manoeuvring_prevents_a_look_starting(self) -> None:
        state, decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=False,
        )
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC

    def test_manoeuvring_lowers_a_look_already_in_progress(self) -> None:
        """ "jittery flying and hard manouvering lowers binoculars" -- they
        come down mid-look, not only at the next decision point."""
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + 1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=False,
        )
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC


class TestPlayerCommand:
    def test_a_command_lowers_them(self) -> None:
        """Not per command type: the pilot asking for something is itself
        evidence that what Petrovich is doing matters less."""
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING

        state = lower_binoculars(state, now_sim=_CYCLE_S + 1.0)

        assert state.phase is OpticPhase.SCANNING
        assert state.look_azimuth_deg is None

    def test_lowering_while_already_scanning_changes_nothing(self) -> None:
        """Including the scan's own start time -- a command must not reset
        the cycle and delay the next look."""
        scanning = OpticState(phase_started_sim=3.0)
        assert lower_binoculars(scanning, now_sim=9.0) is scanning


class TestEveryContactInTheConeIsAttempted:
    def test_a_look_marks_all_the_contacts_it_covers(self) -> None:
        """They all get the benefit of the look, so they all bear the
        retry rule -- otherwise the ones that were merely nearby would be
        glassed again immediately."""
        targets = [
            _target("CONTACT_1", azimuth_deg=40.0, range_m=1_200.0),
            _target("CONTACT_2", azimuth_deg=41.0, range_m=1_200.0),
        ]
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=targets,
            steady=True,
        )
        assert set(state.attempted_at_range_m) == {"CONTACT_1", "CONTACT_2"}

    def test_a_contact_outside_the_cone_is_not_marked(self) -> None:
        targets = [
            _target("CONTACT_1", azimuth_deg=40.0, range_m=1_200.0),
            _target("CONTACT_FAR_OFF", azimuth_deg=-80.0, range_m=1_200.0),
        ]
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=targets,
            steady=True,
        )
        assert "CONTACT_FAR_OFF" not in state.attempted_at_range_m


def test_decide_is_pure() -> None:
    """Same inputs, same outputs, and the input state is never mutated --
    the property that keeps a replay identical, as `gaze_at`'s own purity
    does for the scan."""
    state = OpticState(phase_started_sim=0.0)
    targets = [_target()]

    first_state, first_decision = decide(
        state,
        now_sim=_CYCLE_S,
        scan_cycle_period_s=_CYCLE_S,
        targets=targets,
        steady=True,
    )
    second_state, second_decision = decide(
        state,
        now_sim=_CYCLE_S,
        scan_cycle_period_s=_CYCLE_S,
        targets=targets,
        steady=True,
    )

    assert first_state == second_state
    assert first_decision == second_decision
    assert state.phase is OpticPhase.SCANNING
    assert state.attempted_at_range_m == {}


def test_a_look_is_not_ended_by_its_own_attempt_marking() -> None:
    """The defect a test caught during Stage 2, pinned so it cannot
    return: a look marks every contact it covers as attempted the instant
    it begins, so a stop condition phrased as "is this still *worth* a
    look" ends every look on the very next poll. Starting a look and
    continuing one are different questions about the same contact."""
    state, _ = decide(
        OpticState(phase_started_sim=0.0),
        now_sim=_CYCLE_S,
        scan_cycle_period_s=_CYCLE_S,
        targets=[_target()],
        steady=True,
    )
    assert state.attempted_at_range_m  # the look marked it
    assert not is_worth_a_look(_target(), state)  # so a *new* look is not due

    state, decision = decide(
        state,
        now_sim=_CYCLE_S + 0.5,
        scan_cycle_period_s=_CYCLE_S,
        targets=[_target()],
        steady=True,
    )

    assert state.phase is OpticPhase.GLASSING  # ...but this one continues
    assert decision.optic is BINOCULAR_OPTIC


class TestFixedLookPlan:
    """A glass phase overrides the scan by handing the source a plan that
    answers with one direction -- so nothing downstream has to learn that
    binoculars exist."""

    def test_a_fixed_look_ignores_the_clock(self) -> None:
        from perception.gaze import ScanPlan, gaze_at

        plan = ScanPlan.fixed_look_at(azimuth_deg=-45.0, elevation_deg=-7.0)

        for t_sim in (0.0, 3.0, 11.5, 900.0):
            gaze = gaze_at(t_sim, plan)
            assert gaze.center_azimuth_deg == -45.0
            assert gaze.center_elevation_deg == -7.0

    def test_a_free_scan_plan_still_cycles(self) -> None:
        """The regression that matters: adding the fixed look must not
        freeze the ordinary scan."""
        from perception.gaze import FREE_SCAN_PLAN, gaze_at

        labels = {gaze_at(float(t), FREE_SCAN_PLAN).label for t in range(0, 16, 2)}
        assert len(labels) > 1

    def test_a_scan_gaze_is_level(self) -> None:
        """Elevation exists for aiming an optic; the scan sweeps
        horizontally and must be unaffected."""
        from perception.gaze import FREE_SCAN_PLAN, gaze_at

        assert gaze_at(0.0, FREE_SCAN_PLAN).center_elevation_deg == 0.0


class TestLookTargetGeometry:
    def test_a_contact_below_is_a_negative_elevation(self) -> None:
        """The sign convention the whole aiming fix depends on: ground
        contacts are *below*, and getting this backwards would point the
        binoculars at the sky."""
        from belief.optic_policy import look_target_for
        from perception.geometry import GeoPosition

        target = look_target_for(
            "CONTACT_1",
            observer=GeoPosition(x=0.0, z=0.0, alt_m=500.0),
            target_position=GeoPosition(x=1_000.0, z=0.0, alt_m=380.0),
            heading_true_deg=0.0,
            object_type="T-72",
            current_level="presence",
        )

        assert target.elevation_deg < 0.0
        assert -10.0 < target.elevation_deg < -5.0  # ~120 m down over ~1 km

    def test_azimuth_is_body_relative(self) -> None:
        """A contact due north with the nose due east is off the left
        side, not at 0 degrees."""
        from belief.optic_policy import look_target_for
        from perception.geometry import GeoPosition

        target = look_target_for(
            "CONTACT_1",
            observer=GeoPosition(x=0.0, z=0.0, alt_m=500.0),
            target_position=GeoPosition(x=1_000.0, z=0.0, alt_m=500.0),
            heading_true_deg=90.0,
            object_type="T-72",
            current_level="presence",
        )

        assert target.azimuth_deg == -90.0


class TestSearchPattern:
    """`plans/binocular-optic/plan.md` D6/Stage 3. Range is the vertical
    axis, so "close to far" and "as high as there is ground ahead" are one
    instruction, and "do not scan at sky" is a property of the geometry
    rather than a clamp."""

    def _pattern(self, *, altitude_agl_m: float) -> list[tuple[float, float]]:
        from belief.optic_policy import search_pattern

        return search_pattern(
            sector_half_width_deg=15.0,
            near_m=2_333.0,
            far_m=5_647.0,
            altitude_agl_m=altitude_agl_m,
            fov_full_width_deg=8.5,
        )

    def test_nothing_is_ever_aimed_at_the_sky(self) -> None:
        for altitude in (60.0, 120.0, 500.0, 1_000.0):
            assert all(
                elevation <= 0.0
                for _, elevation in self._pattern(altitude_agl_m=altitude)
            ), altitude

    def test_the_sweep_collapses_to_one_band_at_helicopter_altitude(self) -> None:
        """The finding that stops this being a pointlessly slow vertical
        crawl at low level: the whole 2.3-5.6 km band spans under two
        degrees of depression at 120 m AGL, far inside a binocular's own
        field, so the S-shape has nothing to step through."""
        elevations = {elevation for _, elevation in self._pattern(altitude_agl_m=120.0)}
        assert len(elevations) == 1

    def test_it_becomes_a_real_raster_when_high(self) -> None:
        elevations = {
            elevation for _, elevation in self._pattern(altitude_agl_m=1_000.0)
        }
        assert len(elevations) > 1

    def test_successive_bands_sweep_in_opposite_directions(self) -> None:
        """The S in the S-shape -- sweeping back the way you came costs no
        extra movement, where restarting at the same edge every band
        does."""
        pattern = self._pattern(altitude_agl_m=1_000.0)
        first_band_elevation = pattern[0][1]
        first_band = [az for az, el in pattern if el == first_band_elevation]
        second_band = [az for az, el in pattern if el != first_band_elevation]
        assert first_band == sorted(first_band)
        assert second_band == sorted(second_band, reverse=True)

    def test_the_sector_is_capped_at_thirty_degrees(self) -> None:
        """User: "cap binocular scan at 30 deg azimuth, there's no wide
        area binocular scan". A wider commanded scan is swept across its
        middle rather than taking a minute to cover."""
        from belief.optic_policy import MAX_SEARCH_SECTOR_HALF_WIDTH_DEG, search_pattern

        wide = search_pattern(
            sector_half_width_deg=90.0,
            near_m=2_333.0,
            far_m=5_647.0,
            altitude_agl_m=120.0,
            fov_full_width_deg=8.5,
        )
        assert all(
            abs(azimuth) <= MAX_SEARCH_SECTOR_HALF_WIDTH_DEG for azimuth, _ in wide
        )

    def test_the_sweep_covers_the_sector(self) -> None:
        pattern = self._pattern(altitude_agl_m=120.0)
        azimuths = [azimuth for azimuth, _ in pattern]
        assert min(azimuths) < -7.0
        assert max(azimuths) > 7.0


class TestSearchPhase:
    def test_a_commanded_sector_is_swept_when_nothing_needs_resolving(self) -> None:
        from belief.optic_policy import OpticPhase

        sweep = [(-10.0, -2.0), (0.0, -2.0), (10.0, -2.0)]
        state, decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            search=sweep,
        )
        assert state.phase is OpticPhase.SEARCHING
        assert decision.optic is BINOCULAR_OPTIC
        assert (decision.look_azimuth_deg, decision.look_elevation_deg) == sweep[0]

    def test_resolving_a_contact_beats_searching_for_another(self) -> None:
        """The user's own sequencing: detected targets get the dwell
        behaviour. A contact already found and resolvable is worth more
        than looking for one that may not exist."""
        from belief.optic_policy import OpticPhase

        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
            search=[(-10.0, -2.0), (0.0, -2.0)],
        )
        assert state.phase is OpticPhase.GLASSING

    def test_the_sweep_advances_with_time(self) -> None:
        from belief.optic_policy import SEARCH_STEP_S

        sweep = [(-10.0, -2.0), (0.0, -2.0), (10.0, -2.0)]
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            search=sweep,
        )
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + SEARCH_STEP_S * 1.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            search=sweep,
        )
        assert (decision.look_azimuth_deg, decision.look_elevation_deg) == sweep[1]

    def test_the_sweep_ends_after_its_last_step(self) -> None:
        """One complete area scan, not a loop -- the user asked for a
        single pass, and a repeating sweep would never hand the naked eye
        back."""
        from belief.optic_policy import SEARCH_STEP_S, OpticPhase

        sweep = [(-10.0, -2.0), (0.0, -2.0)]
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            search=sweep,
        )
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + SEARCH_STEP_S * len(sweep),
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            search=sweep,
        )
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC

    def test_manoeuvring_ends_a_sweep_too(self) -> None:
        from belief.optic_policy import OpticPhase

        sweep = [(-10.0, -2.0), (0.0, -2.0)]
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            search=sweep,
        )
        state, _decision = decide(
            state,
            now_sim=_CYCLE_S + 0.1,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=False,
            search=sweep,
        )
        assert state.phase is OpticPhase.SCANNING

    def test_no_search_is_offered_for_a_free_scan(self) -> None:
        """Free scan has no sector to sweep, so the empty pattern simply
        restarts the scan -- no branch needed at the call site."""
        from belief.optic_policy import OpticPhase

        state, decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC
