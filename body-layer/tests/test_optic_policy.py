"""The binocular decision: when Petrovich raises them and when he stops.

`plans/binocular-optic/plan.md` Stage 2. Everything here is pure -- no
store, no telemetry, no clock -- which is the property that keeps a replay
identical and the reason the policy takes `LookTarget`s rather than
`Contact`s.
"""

from __future__ import annotations

import math
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from belief.optic_policy import (
    GUIDANCE_OPTIC_HYSTERESIS_FRACTION,
    GUIDANCE_OPTIC_MIN_INTERVAL_S,
    HANDS_BUSY_DURATION_S,
    MAX_LOOK_S,
    OPTIC_RETRY_INTERVAL_S,
    POINT_SWEEP_COUNT,
    RETRY_RANGE_FRACTION,
    SEARCH_STEP_S,
    SIGHT_GLANCE_AWAY_S,
    SIGHT_MAX_DWELL_S,
    SIGHT_SEARCH_NEAR_M,
    SIGHT_SEARCH_WIDE_MID_M,
    SIGHT_STALL_COOLDOWN_S,
    SIGHT_STEADY_RATE_LIMIT_DEG_S,
    STEADY_RATE_LIMIT_DEG_S,
    BoundedSightLook,
    LookTarget,
    OpticDecision,
    OpticPhase,
    OpticState,
    advance_sight_aim,
    choose_look,
    choose_sighting_look,
    decide,
    guidance_request_for,
    improvement_window_m,
    is_steady,
    is_worth_a_look,
    least_capable_sufficient_optic,
    lower_binoculars,
    search_pattern,
    sight_can_still_improve,
    sight_look_optic,
)
from perception.optics import (
    BINOCULAR_OPTIC,
    SIGHT_NARROW_OPTIC,
    SIGHT_WIDE_OPTIC,
    UNAIDED_OPTIC,
    Optic,
    within_field_of_regard,
)

_CYCLE_S = 16.0


def _target(
    contact_id: str = "CONTACT_1",
    *,
    azimuth_deg: float = 0.0,
    elevation_deg: float = 0.0,
    range_m: float = 1_000.0,
    object_type: str = "T-72",
    current_level: str = "presence",
    watched: bool = False,
) -> LookTarget:
    return LookTarget(
        contact_id=contact_id,
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
        range_m=range_m,
        object_type=object_type,
        current_level=current_level,
        watched=watched,
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


class TestChooseSightingLook:
    """`plans/9k113-scan-procedure/plan.md` Stage 1's priority ordering --
    the explore notes, verbatim: *"first units not yet identified that
    might be inside identification range... same thing for class"*."""

    def test_a_class_level_target_beats_a_presence_level_one_regardless_of_range(
        self,
    ) -> None:
        """A contact already at `"class"` (one look from `"type"`) is
        visited before a `"presence"`-level one even though the latter is
        closer -- the outer priority bucket overrides `choose_look`'s own
        range-based tie-break."""
        near_presence = _target(
            "CONTACT_NEAR", azimuth_deg=-30.0, range_m=600.0, current_level="presence"
        )
        far_class = _target(
            "CONTACT_FAR", azimuth_deg=30.0, range_m=1_500.0, current_level="class"
        )
        chosen = choose_sighting_look([near_presence, far_class])
        assert chosen is not None
        assert chosen.contact_id == "CONTACT_FAR"

    def test_within_one_bucket_choose_looks_own_ordering_is_reproduced(self) -> None:
        """Two `"class"`-level targets: the usual coverage/watched/range
        ordering still applies unchanged within the bucket."""
        near = _target(
            "CONTACT_NEAR", azimuth_deg=-30.0, range_m=600.0, current_level="class"
        )
        far = _target(
            "CONTACT_FAR", azimuth_deg=30.0, range_m=1_500.0, current_level="class"
        )
        assert choose_sighting_look([near, far]) == choose_look([near, far])

    def test_no_targets_chooses_nothing(self) -> None:
        assert choose_sighting_look([]) is None


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
        glassed again immediately.

        Checks `pending_attempted_at_range_m`, not `attempted_at_range_m`
        (`plans/sortie-2026-09-26-fixes/plan.md` Stage 2, Fix B1): a look
        that has only just started has not yet delivered its benefit, so
        its marks are pending, not committed -- see that field's own
        docstring."""
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
        assert set(state.pending_attempted_at_range_m) == {"CONTACT_1", "CONTACT_2"}

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
        assert "CONTACT_FAR_OFF" not in state.pending_attempted_at_range_m


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
    continuing one are different questions about the same contact.

    Checks `pending_attempted_at_range_m` (`plans/sortie-2026-09-26-fixes/
    plan.md` Stage 2, Fix B1's committed/pending split) -- the look has
    only just started, so its mark is pending, not yet committed. `is_
    worth_a_look` itself still correctly reads `False` regardless, via its
    own `pending_attempted_at_range_m` check."""
    state, _ = decide(
        OpticState(phase_started_sim=0.0),
        now_sim=_CYCLE_S,
        scan_cycle_period_s=_CYCLE_S,
        targets=[_target()],
        steady=True,
    )
    assert state.pending_attempted_at_range_m  # the look marked it
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

    def test_elevation_accounts_for_pitch(self) -> None:
        """F5 (`docs/acceptance/2026-10-20-sortie-feedback.md`): a look
        target's own elevation must rotate with pitch exactly as a live
        detection's does (`perception.visibility.check_visibility`'s own
        `body_relative_direction` call), or the sight's field-of-regard
        check means two different things depending on whether it is
        testing a believed contact or a search-pattern step. A target
        exactly along a 20-degree-nose-up aircraft's own boresight must
        read as elevation 0, the same case `test_geometry.py`'s
        `test_body_relative_direction_target_along_pitched_nose_is_dead_
        ahead` pins at the lower level."""
        from belief.optic_policy import look_target_for
        from perception.geometry import GeoPosition

        horizontal_range = 1_000.0
        pitch_deg = 20.0
        target = look_target_for(
            "CONTACT_1",
            observer=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
            target_position=GeoPosition(
                x=horizontal_range,
                z=0.0,
                alt_m=horizontal_range * math.tan(math.radians(pitch_deg)),
            ),
            heading_true_deg=0.0,
            pitch_deg=pitch_deg,
            object_type="T-72",
            current_level="presence",
        )

        assert target.azimuth_deg == pytest.approx(0.0)
        assert target.elevation_deg == pytest.approx(0.0, abs=1e-6)

    def test_elevation_and_azimuth_account_for_bank(self) -> None:
        """A target dead below the aircraft reads as elevation -90 when
        wings-level, but rolled 90 degrees right it reads as straight out
        the right side -- `test_geometry.py`'s own bank test, reproduced
        here through `look_target_for` to confirm it is not bypassed by a
        second, un-rotated derivation."""
        from belief.optic_policy import look_target_for
        from perception.geometry import GeoPosition

        observer = GeoPosition(x=0.0, z=0.0, alt_m=1_000.0)
        target_position = GeoPosition(x=0.0, z=0.0, alt_m=0.0)

        level = look_target_for(
            "CONTACT_1",
            observer=observer,
            target_position=target_position,
            heading_true_deg=0.0,
            object_type="T-72",
            current_level="presence",
        )
        banked_right = look_target_for(
            "CONTACT_1",
            observer=observer,
            target_position=target_position,
            heading_true_deg=0.0,
            bank_deg=90.0,
            object_type="T-72",
            current_level="presence",
        )

        assert level.elevation_deg == pytest.approx(-90.0)
        assert banked_right.azimuth_deg == pytest.approx(90.0)
        assert banked_right.elevation_deg == pytest.approx(0.0, abs=1e-6)

    def test_no_position_estimate_keeps_the_fixed_default_sweep(self) -> None:
        """`plans/precise-position-belief/plan.md` Stage 5: omitting
        `position` entirely must leave `bearing_uncertainty_deg` at
        `LookTarget`'s own pre-Stage-5 default (`CLOCK_BUCKET_DEG / 2.0`),
        not some other number -- the two tests above call `look_target_for`
        this way and must keep working."""
        from belief.enrichment import CLOCK_BUCKET_DEG
        from belief.optic_policy import look_target_for
        from perception.geometry import GeoPosition

        target = look_target_for(
            "CONTACT_1",
            observer=GeoPosition(x=0.0, z=0.0, alt_m=500.0),
            target_position=GeoPosition(x=1_000.0, z=0.0, alt_m=500.0),
            heading_true_deg=0.0,
            object_type="T-72",
            current_level="presence",
        )

        assert target.bearing_uncertainty_deg == CLOCK_BUCKET_DEG / 2.0

    def test_a_real_position_estimate_narrows_the_sweep_to_a_measured_number(
        self,
    ) -> None:
        """A single fresh look's own `PositionEstimate` (no fusion yet)
        must produce a `bearing_uncertainty_deg` of `LOOK_SWEEP_SIGMA *
        BEARING_SIGMA_DEG` -- narrower than the old fixed +/-15 default,
        the plan's own worked example (~9 degrees at `BEARING_SIGMA_DEG=
        3.0`, `LOOK_SWEEP_SIGMA=3.0`)."""
        from belief.optic_policy import LOOK_SWEEP_SIGMA, look_target_for
        from belief.position_belief import estimate_from_look
        from perception.estimation import BEARING_SIGMA_DEG
        from perception.geometry import GeoPosition
        from perception.source import PositionUncertainty

        observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
        target_position = GeoPosition(x=3_000.0, z=0.0, alt_m=500.0)
        sigma_cross_m = 3_000.0 * 0.05236  # radians(BEARING_SIGMA_DEG) * range
        estimate = estimate_from_look(
            x=3_000.0,
            z=0.0,
            uncertainty=PositionUncertainty(
                sigma_cross_m=sigma_cross_m, sigma_down_m=510.0
            ),
            look_bearing_deg=0.0,
            t_sim=0.0,
        )

        target = look_target_for(
            "CONTACT_1",
            observer=observer,
            target_position=target_position,
            heading_true_deg=0.0,
            object_type="T-72",
            current_level="presence",
            position=estimate,
        )

        assert target.bearing_uncertainty_deg == pytest.approx(
            LOOK_SWEEP_SIGMA * BEARING_SIGMA_DEG, abs=0.05
        )
        assert target.bearing_uncertainty_deg < 15.0  # narrower than the old default

    def test_a_well_refined_contact_collapses_the_look_to_a_single_step(self) -> None:
        """The plan's own Stage 5 verify item: a well-observed contact must
        produce a sweep of exactly one step -- a stare, not a search --
        once its `bearing_uncertainty_deg` narrows inside half a binocular
        field of view.

        **A real, non-obvious finding surfaced getting this test to pass
        honestly**: repeated looks from *crossing* bearings (real
        triangulation -- the scenario `test_position_belief.py`'s own
        `test_fold_position_from_two_crossing_looks_triangulates_tighter_
        than_either` covers, and which shrinks the estimate's *overall*
        radius the most) do **not** reliably collapse *this specific
        query's* `bearing_uncertainty_deg` to single-step, even fully
        converged to the systematic-bias floor -- cross-bearing fusion
        smears the tightened covariance's orientation away from being
        aligned with any one observer's own cross-range axis, and a query
        against a covariance that has become more isotropic can read
        *worse* along one particular axis than a single, luckily-aligned
        look would. Repeated looks from **the same bearing** (re-glassing
        the same contact without much relative-bearing change -- at least
        as plausible a "well-observed" scenario as an orbiting one)
        instead **preserve** the naturally favourable down-range-heavy
        anisotropy while still shrinking magnitude toward the floor, and
        do reach single-step reliably -- confirmed numerically before
        writing this test, not assumed. Recorded in `plans/
        precise-position-belief/implementation.md` as a genuine finding
        about the plan's own worked claim, not silently smoothed over."""
        from belief.optic_policy import look_sweep, look_target_for
        from belief.position_belief import fold_position
        from perception.geometry import GeoPosition
        from perception.source import PositionUncertainty

        observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
        target_position = GeoPosition(x=3_000.0, z=0.0, alt_m=500.0)
        uncertainty = PositionUncertainty(sigma_cross_m=157.08, sigma_down_m=510.0)

        # All folded at the same t_sim (elapsed_s=0 throughout) so the
        # elapsed-motion inflation term never fights the tightening --
        # this test is about how much fusion itself narrows the estimate,
        # not about a stale contact re-widening between looks. Same
        # bearing every time -- see the docstring above for why crossing
        # bearings do not reliably reach single-step here.
        estimate = None
        for _ in range(10):
            estimate = fold_position(
                estimate,
                x=3_000.0,
                z=0.0,
                uncertainty=uncertainty,
                look_bearing_deg=0.0,
                t_sim=0.0,
            )
        assert estimate is not None

        target = look_target_for(
            "CONTACT_1",
            observer=observer,
            target_position=target_position,
            heading_true_deg=0.0,
            object_type="T-72",
            current_level="class",
            position=estimate,
        )
        steps = look_sweep(
            centre_azimuth_deg=target.azimuth_deg,
            centre_elevation_deg=target.elevation_deg,
            bearing_uncertainty_deg=target.bearing_uncertainty_deg,
            fov_full_width_deg=(BINOCULAR_OPTIC.fov_half_angle_deg or 0.0) * 2.0,
        )

        assert len(steps) == 1


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

    def test_center_azimuth_deg_shifts_every_step_by_exactly_that_amount(
        self,
    ) -> None:
        """`plans/9k113-narrow-search/plan.md` Stage 2 -- `0.0` (the
        default, exercised by every other test in this class) is a true
        no-op; a non-zero centre shifts every generated azimuth by exactly
        that amount, and the sector cap still applies around it rather
        than around `0.0`."""
        centered = search_pattern(
            sector_half_width_deg=15.0,
            near_m=2_333.0,
            far_m=5_647.0,
            altitude_agl_m=120.0,
            fov_full_width_deg=8.5,
        )
        shifted = search_pattern(
            center_azimuth_deg=-45.0,
            sector_half_width_deg=15.0,
            near_m=2_333.0,
            far_m=5_647.0,
            altitude_agl_m=120.0,
            fov_full_width_deg=8.5,
        )
        for (centered_az, centered_el), (shifted_az, shifted_el) in zip(
            centered, shifted
        ):
            assert shifted_az == pytest.approx(centered_az - 45.0)
            assert shifted_el == centered_el

    def test_max_half_width_deg_overrides_the_binocular_cap(self) -> None:
        """`plans/9k113-narrow-search/plan.md` Stage 2 -- the sight's own
        search legs pass the sight's much wider field of regard here
        instead of the binocular convention's 30 deg cap."""
        from belief.optic_policy import MAX_SEARCH_SECTOR_HALF_WIDTH_DEG

        wide = search_pattern(
            sector_half_width_deg=60.0,
            near_m=2_333.0,
            far_m=5_647.0,
            altitude_agl_m=120.0,
            fov_full_width_deg=11.5,
            max_half_width_deg=60.0,
        )
        assert (
            max(abs(azimuth) for azimuth, _ in wide) > MAX_SEARCH_SECTOR_HALF_WIDTH_DEG
        )


class TestLookSweep:
    """`plans/binocular-optic/stage3b.md` D2: the sweep a binocular
    identification look works through, distinct from `search_pattern`
    (unknown ground, range-derived elevation) even though both share the
    same step-centre arithmetic."""

    def test_narrow_uncertainty_stays_a_single_step(self) -> None:
        """`N == 1` reproduces today's stare exactly -- the short-range
        common case needs no special handling, it falls out of the
        formula."""
        from belief.optic_policy import look_sweep

        sweep = look_sweep(
            centre_azimuth_deg=10.0,
            centre_elevation_deg=-5.0,
            bearing_uncertainty_deg=3.0,
            fov_full_width_deg=8.5,
        )
        assert sweep == [(10.0, -5.0)]

    def test_the_default_uncertainty_needs_four_steps(self) -> None:
        """The worked example from the plan: U = 15 deg against an 8.5 deg
        field gives N = 4, not 1 -- the default clock-bucket uncertainty
        does not degenerate to a stare."""
        from belief.optic_policy import look_sweep

        sweep = look_sweep(
            centre_azimuth_deg=0.0,
            centre_elevation_deg=0.0,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=8.5,
        )
        assert len(sweep) == 4

    def test_elevation_never_moves(self) -> None:
        """The down-range bucket also perturbs elevation, but at
        helicopter geometry it is well under a degree against a binocular
        half-angle -- a second swept axis would only cost steps."""
        from belief.optic_policy import look_sweep

        sweep = look_sweep(
            centre_azimuth_deg=0.0,
            centre_elevation_deg=-12.5,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=8.5,
        )
        assert {elevation for _, elevation in sweep} == {-12.5}

    def test_steps_are_ordered_centre_outward(self) -> None:
        """The believed bearing is the most likely direction, so it is
        looked at first -- and stays first even if the poll rate
        under-samples the rest of the sweep."""
        from belief.optic_policy import look_sweep

        sweep = look_sweep(
            centre_azimuth_deg=20.0,
            centre_elevation_deg=0.0,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=8.5,
        )
        offsets = [azimuth - 20.0 for azimuth, _ in sweep]
        assert offsets == sorted(offsets, key=lambda offset: (abs(offset), offset))

    def test_offsets_stay_within_the_uncertainty(self) -> None:
        from belief.optic_policy import look_sweep

        sweep = look_sweep(
            centre_azimuth_deg=0.0,
            centre_elevation_deg=0.0,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=8.5,
        )
        assert all(abs(azimuth) <= 15.0 for azimuth, _ in sweep)
        # And the sweep genuinely covers the span, not just its centre.
        assert max(abs(azimuth) for azimuth, _ in sweep) > 8.5 / 2.0

    def test_no_regard_optic_is_a_true_no_op(self) -> None:
        """The default (`regard_optic=None`, every pre-existing caller
        including `GLASSING`'s binocular sweep) must produce the exact
        same steps as before this parameter existed."""
        from belief.optic_policy import look_sweep

        with_default = look_sweep(
            centre_azimuth_deg=55.0,
            centre_elevation_deg=0.0,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=6.0,
        )
        explicit_none = look_sweep(
            centre_azimuth_deg=55.0,
            centre_elevation_deg=0.0,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=6.0,
            regard_optic=None,
        )
        assert with_default == explicit_none
        # And unfiltered, this sweep genuinely does reach past a 60 deg
        # boundary -- the premise the next test's truncation checks.
        assert max(azimuth for azimuth, _ in with_default) > 60.0

    def test_an_optic_with_no_regard_data_filters_nothing(self) -> None:
        """`BINOCULAR_OPTIC`'s `regard_*` fields are all `None`, so passing
        it through `regard_optic` must filter exactly as much as passing
        `None` itself -- the no-op is `within_field_of_regard`'s own
        unrestricted convention, not a special case in `look_sweep`."""
        from belief.optic_policy import look_sweep
        from perception.optics import BINOCULAR_OPTIC

        unfiltered = look_sweep(
            centre_azimuth_deg=55.0,
            centre_elevation_deg=0.0,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=6.0,
        )
        filtered_by_binoculars = look_sweep(
            centre_azimuth_deg=55.0,
            centre_elevation_deg=0.0,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=6.0,
            regard_optic=BINOCULAR_OPTIC,
        )
        assert unfiltered == filtered_by_binoculars

    def test_a_regard_optic_truncates_steps_past_its_boundary(self) -> None:
        """The residual leak `BL-B64`'s security follow-up flagged: a
        target 5 deg inside the sight's 60 deg azimuth limit, swept at the
        default 15 deg bearing uncertainty, would otherwise reach 67 deg --
        7 deg past the mount's own limit. `regard_optic=SIGHT_WIDE_OPTIC`
        drops those steps rather than clamping them to the boundary."""
        from belief.optic_policy import look_sweep
        from perception.optics import SIGHT_WIDE_OPTIC

        sweep = look_sweep(
            centre_azimuth_deg=55.0,
            centre_elevation_deg=0.0,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=6.0,
            regard_optic=SIGHT_WIDE_OPTIC,
        )
        assert all(abs(azimuth) <= 60.0 for azimuth, _ in sweep)
        # Truncated, not narrowed: the unconstrained (leftward) side keeps
        # its full-width steps rather than the whole envelope shrinking.
        assert min(azimuth for azimuth, _ in sweep) < 55.0 - 8.5

    def test_the_centre_step_always_survives_the_filter(self) -> None:
        """The chosen target's own (already-validated) direction is never
        itself dropped, even when every other step is."""
        from belief.optic_policy import look_sweep
        from perception.optics import SIGHT_WIDE_OPTIC

        sweep = look_sweep(
            centre_azimuth_deg=59.9,
            centre_elevation_deg=0.0,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=6.0,
            regard_optic=SIGHT_WIDE_OPTIC,
        )
        assert (59.9, 0.0) in sweep

    def test_elevation_truncation_follows_the_same_rule(self) -> None:
        """`look_sweep` never moves elevation itself, but a `regard_optic`
        whose elevation bound the centre is close to must still be
        honoured consistently -- here the centre sits just inside the
        down limit, and because elevation never varies across the sweep,
        every step shares the same (in-bounds) elevation and none is
        dropped on that axis alone."""
        from belief.optic_policy import look_sweep
        from perception.optics import SIGHT_WIDE_OPTIC

        sweep = look_sweep(
            centre_azimuth_deg=0.0,
            centre_elevation_deg=-14.9,
            bearing_uncertainty_deg=15.0,
            fov_full_width_deg=6.0,
            regard_optic=SIGHT_WIDE_OPTIC,
        )
        assert sweep  # not emptied
        assert all(elevation == -14.9 for _, elevation in sweep)


class TestSweepStepsWithTime:
    """`decide`'s `GLASSING` branch is step-indexed the way `SEARCHING`
    already is (`plans/binocular-optic/stage3b.md` D3): `step_s =
    MAX_LOOK_S / N`, no new constant."""

    def test_the_look_advances_through_its_own_sweep(self) -> None:
        target = _target(azimuth_deg=0.0, range_m=500.0, current_level="class")
        state, first = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[target],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING
        step_count = len(state.search_pattern_steps)
        assert step_count == 4  # the default 15 deg / 8.5 deg case
        step_s = MAX_LOOK_S / step_count

        state, second = decide(
            state,
            now_sim=_CYCLE_S + step_s * 1.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[target],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING
        assert second.look_azimuth_deg != first.look_azimuth_deg
        assert (second.look_azimuth_deg, second.look_elevation_deg) == (
            state.search_pattern_steps[1]
        )

    def test_running_out_of_steps_ends_the_look_at_max_look_s(self) -> None:
        """The cap and the sweep's own exhaustion become one event: with
        `step_s * N == MAX_LOOK_S`, there is no truncation mid-sweep."""
        target = _target(azimuth_deg=0.0, range_m=500.0, current_level="class")
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[target],
            steady=True,
        )
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + MAX_LOOK_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[target],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC


class TestSweepEnvelope:
    """`look_is_finished` widens from the field of view to the sweep's
    envelope (`plans/binocular-optic/stage3b.md` D4) -- without this, a
    sweep would end on its own first step, every time."""

    def test_the_first_step_does_not_end_the_look_early(self) -> None:
        """A target deliberately outside step 0's field of view, but
        inside the sweep envelope, must keep the look running -- the
        premise the whole fix rests on."""
        # Believed azimuth 12 deg off the target's own reported azimuth
        # (0.0), comfortably outside the 4.25 deg binocular half-angle but
        # inside the 15 deg envelope.
        target = _target(azimuth_deg=12.0, range_m=500.0, current_level="class")
        state, decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[target],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING
        assert decision.look_azimuth_deg is not None

        # One poll later, still mid-sweep: the look must still be running,
        # not ended by "nothing in the (first step's) field of view".
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + 0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[target],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING


class TestSweepFindsAnOffsetContact:
    """The real Stage 3b tripwire (`plans/binocular-optic/stage3b.md` step
    5): a believed bearing offset from the truth by most of a half-bucket,
    outside the binocular field of view. This is the test that must go red
    if the sweep is reverted to a stare -- the mock-flight fixture cannot
    play that role, since its only contact never enters `GLASSING` at all
    (see `test_mock_flight_chain.py`'s own comment)."""

    def test_the_sweep_reaches_the_true_bearing_a_stare_would_miss(self) -> None:
        true_azimuth_deg = 0.0
        believed_azimuth_deg = 12.0  # most of a 15 deg half-bucket
        fov_half_angle_deg = BINOCULAR_OPTIC.fov_half_angle_deg
        assert fov_half_angle_deg is not None

        # The premise: a single stare at the believed bearing misses.
        assert abs(believed_azimuth_deg - true_azimuth_deg) > fov_half_angle_deg

        target = _target(
            azimuth_deg=believed_azimuth_deg,
            range_m=500.0,  # inside the T-72 class -> type window
            current_level="class",
        )
        state, decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[target],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING

        directions = [decision.look_azimuth_deg]
        now = _CYCLE_S
        while state.phase is OpticPhase.GLASSING:
            now += 0.5
            state, decision = decide(
                state,
                now_sim=now,
                scan_cycle_period_s=_CYCLE_S,
                targets=[target],
                steady=True,
            )
            if state.phase is OpticPhase.GLASSING:
                directions.append(decision.look_azimuth_deg)

        assert any(
            direction is not None
            and abs(direction - true_azimuth_deg) <= fov_half_angle_deg
            for direction in directions
        ), directions


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


def test_choose_look_prefers_a_watched_contact_over_more_unwatched_ones() -> None:
    """User, 2026-09-25: identify by glass "for all contacts, but even more
    so watched contacts".

    The prior rule was coverage alone -- point where the binocular field
    covers the most unresolved contacts, since one look resolves all of
    them. That still holds among equally-watched directions, but a contact
    the pilot explicitly asked about now outranks raw count: he asked for a
    reason, and spending the next look elsewhere answers a question nobody
    posed."""
    # One watched contact off to the left, alone in its field.
    watched = _target("CONTACT_W", azimuth_deg=-40.0, range_m=2_000.0, watched=True)
    # Three unwatched contacts clustered together to the right -- under the
    # old coverage-only rule this direction wins 3 to 1.
    cluster = [
        _target("CONTACT_A", azimuth_deg=40.0, range_m=1_500.0),
        _target("CONTACT_B", azimuth_deg=41.0, range_m=1_500.0),
        _target("CONTACT_C", azimuth_deg=42.0, range_m=1_500.0),
    ]

    chosen = choose_look([watched, *cluster])

    assert chosen is not None
    assert chosen.contact_id == "CONTACT_W"


def test_choose_look_still_prefers_coverage_among_equally_watched() -> None:
    """The coverage rule is unchanged where watched-ness does not separate
    the options -- this is an added tie-break, not a replacement."""
    lone = _target("CONTACT_LONE", azimuth_deg=-40.0, range_m=1_500.0)
    cluster = [
        _target("CONTACT_A", azimuth_deg=40.0, range_m=2_000.0),
        _target("CONTACT_B", azimuth_deg=41.0, range_m=2_000.0),
    ]

    chosen = choose_look([lone, *cluster])

    assert chosen is not None
    assert chosen.contact_id in {"CONTACT_A", "CONTACT_B"}


def test_watched_ness_does_not_gate_whether_a_look_happens() -> None:
    """Ordering only. An unwatched contact inside its improvement window is
    still worth identifying -- otherwise "even more so watched" would have
    quietly become "only watched"."""
    only_unwatched = [_target("CONTACT_U", azimuth_deg=10.0, range_m=2_000.0)]

    chosen = choose_look(only_unwatched)

    assert chosen is not None
    assert chosen.contact_id == "CONTACT_U"


def test_a_command_interrupted_look_is_not_permanently_burned() -> None:
    """`plans/sortie-2026-09-26-fixes/diagnosis.md` (Defect 2). `decide`
    marks every contact a look covers as attempted the moment the look
    *starts* (`is_worth_a_look`'s own docstring: "they all get its
    benefit, so they all bear the retry rule") -- correct for a look that
    runs to a natural end (`look_is_finished`), but `lower_binoculars` can
    also end a look early, on every single player command
    (`CrewConsole.lower_binoculars`'s own docstring: "new command from
    player lowers binoculars... not per command type"). An early-ended
    look delivered less than a full look's worth of dwell, yet it burns
    the same `RETRY_RANGE_FRACTION` (0.8) budget as a completed one.

    A watched contact under real observation (not being closed on -- an
    orbit, a stand-off watch) may never close 20% further for the rest of
    the encounter, so one command landing during the very first look
    permanently forecloses ever raising binoculars on that contact again.
    This reproduces the flown finding ("binoculars... not even for
    watched") against the belief-truth log's own measured dwell times --
    several contacts sat inside `improvement_window_m`'s presence->class
    band (500-1750 m) for 200-1200+ simulated seconds and never advanced
    past PRESENCE.

    Currently fails: the interrupted look is never retried, for any number
    of further completed scan cycles, because the range never closes."""
    target = _target(range_m=1_700.0)  # inside the presence -> class window
    state, _decision = decide(
        OpticState(phase_started_sim=0.0),
        now_sim=_CYCLE_S,
        scan_cycle_period_s=_CYCLE_S,
        targets=[target],
        steady=True,
    )
    assert state.phase is OpticPhase.GLASSING  # the look started

    # One second later, an ordinary player command (not a deliberate
    # cancellation of the look) lowers the binoculars, well before
    # `look_is_finished` would ever end this look on its own.
    state = lower_binoculars(state, now_sim=_CYCLE_S + 1.0)
    assert state.phase is OpticPhase.SCANNING

    # The contact is being watched/orbited, not closed on: its range never
    # drops by RETRY_RANGE_FRACTION (0.8) for the rest of a long encounter.
    stalled_target = _target(range_m=1_700.0)
    ever_glassed_again = False
    for cycle in range(1, 40):  # ~640 s of further completed scan cycles
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + 1.0 + cycle * _CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[stalled_target],
            steady=True,
        )
        if decision.optic is BINOCULAR_OPTIC:
            ever_glassed_again = True
            break

    assert ever_glassed_again, (
        "an interrupted (not naturally concluded) look should not "
        "permanently exhaust the retry budget for a contact that never "
        "closes further"
    )


def test_time_based_reeligibility_fires_for_a_naturally_completed_look_on_a_stalled_contact() -> (
    None
):
    """Fix B2 (Stage 3) companion to the test above: this time the look
    runs to its own *natural* end (`look_is_finished` via `MAX_LOOK_S`,
    recognition never having come), so it genuinely commits the attempt --
    unlike the interrupted case above, `RETRY_RANGE_FRACTION` alone is the
    correct gate here in principle, except the contact never closes range
    at all (a stand-off watch, not a close). `OPTIC_RETRY_INTERVAL_S`
    (`plans/sortie-2026-09-26-fixes/decisions.md` Decision 2's own named
    gap in D5: "not even for watched") is what eventually unlocks it
    instead, alongside (not replacing) the existing range-based retry."""
    target = _target(range_m=1_700.0)  # inside the presence -> class window
    state, _ = decide(
        OpticState(phase_started_sim=0.0),
        now_sim=_CYCLE_S,
        scan_cycle_period_s=_CYCLE_S,
        targets=[target],
        steady=True,
    )
    assert state.phase is OpticPhase.GLASSING

    # The look runs to MAX_LOOK_S with recognition never having come --
    # a natural end, so this commits the attempt (unlike lower_binoculars
    # above, which drops it).
    state, decision = decide(
        state,
        now_sim=_CYCLE_S + MAX_LOOK_S,
        scan_cycle_period_s=_CYCLE_S,
        targets=[target],
        steady=True,
    )
    assert state.phase is OpticPhase.SCANNING
    assert decision.optic is UNAIDED_OPTIC
    assert state.attempted_at_range_m == {"CONTACT_1": 1_700.0}

    # The contact never closes range and never advances classification for
    # the rest of a long encounter -- RETRY_RANGE_FRACTION alone would lock
    # it out forever, exactly Decision 2's own named gap.
    stalled_target = _target(range_m=1_700.0)
    ever_glassed_again = False
    for cycle in range(
        1, 10
    ):  # up to ~144 s -- comfortably past OPTIC_RETRY_INTERVAL_S
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + MAX_LOOK_S + cycle * _CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[stalled_target],
            steady=True,
        )
        if decision.optic is BINOCULAR_OPTIC:
            ever_glassed_again = True
            break

    assert ever_glassed_again, (
        "a naturally completed look on a contact that never closes range "
        "and never advances classification should still become eligible "
        "again once OPTIC_RETRY_INTERVAL_S has elapsed"
    )


class TestAdvanceSightAim:
    """`plans/9k113-sight/plan.md` §15a -- the perception stage's own body
    is a pure pass-through; the effector stage (`[[BL-B66]]`) replaces it
    with a rate-limited controller without moving the call site."""

    def test_actual_becomes_desired_instantly(self) -> None:
        actual_azimuth, actual_elevation = advance_sight_aim(
            10.0, -2.0, 45.0, 6.0, dt_s=1.0
        )

        assert actual_azimuth == 45.0
        assert actual_elevation == 6.0

    def test_actual_becomes_desired_even_with_no_prior_actual(self) -> None:
        """The first poll of a look has no prior actual aim at all
        (`OpticState.actual_aim_azimuth_deg` defaults to `None`) -- the
        pass-through must not require one."""
        actual_azimuth, actual_elevation = advance_sight_aim(
            None, None, 45.0, 6.0, dt_s=0.0
        )

        assert actual_azimuth == 45.0
        assert actual_elevation == 6.0

    def test_dt_s_is_accepted_but_does_not_change_the_result(self) -> None:
        """Reserved for the effector stage's controller -- the perception
        stage's own body ignores it entirely."""
        at_zero = advance_sight_aim(10.0, -2.0, 45.0, 6.0, dt_s=0.0)
        at_large = advance_sight_aim(10.0, -2.0, 45.0, 6.0, dt_s=100.0)

        assert at_zero == at_large


class TestOpticStateActualAimCarriesForward:
    """`OpticState.actual_aim_azimuth_deg`/`actual_aim_elevation_deg` are
    not part of `decide`'s own phase bookkeeping, so a phase transition
    must never reset them -- a future controller needs continuity across
    polls to converge at all (the field's own docstring)."""

    def test_entering_glassing_carries_the_prior_actual_aim_forward(self) -> None:
        state, decision = decide(
            OpticState(
                phase_started_sim=0.0,
                actual_aim_azimuth_deg=12.0,
                actual_aim_elevation_deg=-3.0,
            ),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING
        assert decision.optic is BINOCULAR_OPTIC
        assert state.actual_aim_azimuth_deg == 12.0
        assert state.actual_aim_elevation_deg == -3.0

    def test_entering_searching_carries_the_prior_actual_aim_forward(self) -> None:
        sweep = [(-10.0, -2.0), (0.0, -2.0)]
        state, decision = decide(
            OpticState(
                phase_started_sim=0.0,
                actual_aim_azimuth_deg=12.0,
                actual_aim_elevation_deg=-3.0,
            ),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            search=sweep,
        )
        assert state.phase is OpticPhase.SEARCHING
        assert decision.optic is BINOCULAR_OPTIC
        assert state.actual_aim_azimuth_deg == 12.0
        assert state.actual_aim_elevation_deg == -3.0


class TestObservOffIsBitIdentical:
    """`BL-B64` Stage 2, plan §13's own claim: `home_phase`'s default is
    `SCANNING`, so every caller that never sets it (every pre-existing
    caller) must exercise exactly the code this project already had.
    `TestPhaseCycle`/`TestSteadinessGate`/`TestOpticStateActualAimCarries
    Forward` above already pin that path byte-for-byte unchanged (they
    pass with no edits); this class pins the two *new* parameters'
    no-op contract specifically, which nothing above exercises."""

    def test_sight_steady_is_ignored_while_observ_is_off(self) -> None:
        """`sight_steady` is only ever read inside the `SIGHTING` branch
        (`_decide_sighting`) -- a `False` value must not perturb the
        ordinary scanning-at-home cycle at all."""
        state, decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
            sight_steady=False,
        )
        assert state.phase is OpticPhase.GLASSING
        assert decision.optic is BINOCULAR_OPTIC
        assert state.home_phase is OpticPhase.SCANNING

    def test_hands_busy_until_sim_default_never_suppresses(self) -> None:
        state, decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S / 2,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert decision.suppressed is False
        assert state.hands_busy_until_sim is None

    def test_first_poll_optic_is_still_unaided_when_home_phase_defaults(
        self,
    ) -> None:
        state, decision = decide(
            OpticState(),
            now_sim=0.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
        )
        assert decision.optic is UNAIDED_OPTIC
        assert state.phase is OpticPhase.SCANNING


class TestObservOn:
    """`BL-B64` Stage 2, direction §6 -- entering OBSERV never jumps the
    *current* phase straight into `SIGHTING`; it only changes `home_phase`,
    and the phase itself moves there at its own next boundary
    (`_back_to_home`) -- the structural rule that makes "abandon a scan
    mid-sweep to sight up" inexpressible, exactly as it already does for
    binoculars."""

    def test_setting_home_phase_mid_glassing_does_not_interrupt_the_look(
        self,
    ) -> None:
        state, decision = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING

        # OBSERV commanded on mid-look (the poll loop would do this via
        # `replace(runner.optic_state, home_phase=OpticPhase.SIGHTING)`).
        state = replace(state, home_phase=OpticPhase.SIGHTING)
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + 1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        # Still glassing -- the look is not abandoned mid-sweep.
        assert state.phase is OpticPhase.GLASSING
        assert decision.optic is BINOCULAR_OPTIC

    def test_the_look_ending_hands_back_to_sighting_not_scanning(self) -> None:
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        state = replace(state, home_phase=OpticPhase.SIGHTING)
        resolved = _target(current_level="type")
        state, decision = decide(
            state,
            now_sim=_CYCLE_S + 1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[resolved],
            steady=True,
        )
        assert state.phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC


class TestSightingDwellCycle:
    """`SIGHTING`'s own body (`_decide_sighting`), direction §9's inverted
    dwell: always ready to pick a target (no scan boundary to wait for),
    narrow sight while actively looking, wide while idle, and a scheduled
    break (`SIGHT_MAX_DWELL_S`) regardless of whether anything is still
    worth looking at."""

    def _sighting_state(self, **overrides: object) -> OpticState:
        base = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        return replace(base, **overrides)  # type: ignore[arg-type]

    def test_idle_sighting_rests_with_an_aim_inside_regard_with_nothing_worth_looking_at(
        self,
    ) -> None:
        """Rewrites the old pinned bug (`decision.look_azimuth_deg is
        None`) -- `plans/9k113-narrow-search/plan.md` Stage 1/3: with
        Stage 3's active default search, the idle branch no longer rests
        at a single point at all, so this asserts the general invariant
        rather than a fixed `(0.0, 0.0)`."""
        state, decision = decide(
            self._sighting_state(),
            now_sim=1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
        )
        assert state.phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert decision.look_azimuth_deg is not None
        assert within_field_of_regard(
            SIGHT_WIDE_OPTIC,
            decision.look_azimuth_deg,
            decision.look_elevation_deg or 0.0,
        )

    def test_the_default_search_starts_at_the_wide_legs_first_step(self) -> None:
        """The default sweep's own first step, computed by `search_pattern`
        directly rather than assumed to be `(0.0, 0.0)` -- a symmetric
        +-60 deg sweep at the wide FOV in general has no step exactly at
        centre."""
        wide_search = search_pattern(
            center_azimuth_deg=0.0,
            sector_half_width_deg=60.0,
            near_m=SIGHT_SEARCH_NEAR_M,
            far_m=SIGHT_SEARCH_WIDE_MID_M,
            altitude_agl_m=120.0,
            fov_full_width_deg=(SIGHT_WIDE_OPTIC.fov_half_angle_deg or 0.0) * 2.0,
            max_half_width_deg=60.0,
        )
        state, decision = decide(
            self._sighting_state(),
            now_sim=1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            sight_wide_near_search=wide_search,
        )
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert (decision.look_azimuth_deg, decision.look_elevation_deg) == wide_search[
            0
        ]
        assert state.sight_search_leg == "wide_near"

    def test_a_worthwhile_target_is_picked_immediately_no_scan_boundary(
        self,
    ) -> None:
        """Unlike `GLASSING`, which waits for `scan_cycle_period_s` to
        elapse, `SIGHTING` has no boundary to wait for -- it is already
        home. `_target()`'s default range (1000 m) is inside `sight_look_
        optic`'s own wide threshold for a presence-level T-72 (3500 m), so
        the look starts on wide, not narrow (`plans/9k113-narrow-search/
        plan.md` Stage 4 Part A -- least capable optic that suffices)."""
        state, decision = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert decision.look_azimuth_deg is not None
        assert state.look_contact_id == "CONTACT_1"
        assert state.look_optic is SIGHT_WIDE_OPTIC
        assert state.look_started_sim == 0.5

    def test_the_look_continues_on_the_next_poll(self) -> None:
        state, _ = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        state, decision = decide(
            state,
            now_sim=1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert state.look_contact_id == "CONTACT_1"

    def test_a_resolved_look_commits_and_immediately_picks_the_next_target(
        self,
    ) -> None:
        state, _ = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target("CONTACT_1")],
            steady=True,
        )
        assert state.look_contact_id == "CONTACT_1"

        resolved = _target("CONTACT_1", current_level="type")
        other = _target("CONTACT_2", azimuth_deg=20.0)
        state, decision = decide(
            state,
            now_sim=1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[resolved, other],
            steady=True,
        )
        # CONTACT_1 resolved and left the window; the dwell does not end --
        # it picks CONTACT_2 immediately, without a forced break.
        assert state.phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert state.look_contact_id == "CONTACT_2"
        assert "CONTACT_1" in state.attempted_at_range_m

    def test_the_scheduled_break_fires_regardless_of_whether_something_is_worth_looking_at(
        self,
    ) -> None:
        """Direction §9: *"Maybe take eyes off it for a quick glance
        around"* -- a scheduled break, not only a last-resort timeout."""
        state, decision = decide(
            self._sighting_state(),
            now_sim=SIGHT_MAX_DWELL_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING
        assert state.home_phase is OpticPhase.SIGHTING
        assert decision.optic is UNAIDED_OPTIC

    def test_the_glance_away_returns_to_sighting_after_its_own_duration(
        self,
    ) -> None:
        state, _ = decide(
            self._sighting_state(),
            now_sim=SIGHT_MAX_DWELL_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING

        state, decision = decide(
            state,
            now_sim=SIGHT_MAX_DWELL_S + SIGHT_GLANCE_AWAY_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        # `_back_to_home` itself rests idle-wide for the poll that resolves
        # the glance -- there is no scan-complete gate (unlike `SCANNING`-
        # at-home) to wait out before the *next* poll picks a target.
        assert state.phase is OpticPhase.SIGHTING
        assert state.home_phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC

        state, decision = decide(
            state,
            now_sim=SIGHT_MAX_DWELL_S + SIGHT_GLANCE_AWAY_S + 0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC

    def test_the_glance_away_holds_naked_eye_before_its_duration_elapses(
        self,
    ) -> None:
        state, _ = decide(
            self._sighting_state(),
            now_sim=SIGHT_MAX_DWELL_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        state, decision = decide(
            state,
            now_sim=SIGHT_MAX_DWELL_S + SIGHT_GLANCE_AWAY_S / 2,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC


class TestSightLookOptic:
    """`sight_look_optic` in isolation -- `plans/9k113-narrow-search/
    plan.md` Stage 4 Part A, "least capable optic that suffices". Direct
    unit tests of the function, not through `_decide_sighting`'s own
    candidate gate (`is_worth_a_look`/`sight_can_still_improve`, `plans/
    9k113-narrow-search/review.md`'s required fix) -- these exercise the
    function on its own terms, independent of what admits a target as a
    candidate in the first place."""

    def test_a_close_presence_target_uses_wide(self) -> None:
        target = LookTarget(
            contact_id="CONTACT_1",
            azimuth_deg=0.0,
            elevation_deg=0.0,
            range_m=1_000.0,
            object_type="T-72",
            current_level="presence",
        )
        assert sight_look_optic(target) is SIGHT_WIDE_OPTIC

    def test_a_presence_target_beyond_wides_class_threshold_uses_narrow(self) -> None:
        _, class_upper_m = improvement_window_m("T-72", current_level="presence")
        target = LookTarget(
            contact_id="CONTACT_1",
            azimuth_deg=0.0,
            elevation_deg=0.0,
            range_m=class_upper_m + 5_000.0,
            object_type="T-72",
            current_level="presence",
        )
        assert sight_look_optic(target) is SIGHT_NARROW_OPTIC

    def test_a_classed_target_is_judged_against_the_type_threshold_not_class(
        self,
    ) -> None:
        """A `"class"`-level target's next tier is type, not class -- the
        threshold `sight_look_optic` compares against must move with it,
        not stay pinned to the presence->class figure."""
        target = LookTarget(
            contact_id="CONTACT_1",
            azimuth_deg=0.0,
            elevation_deg=0.0,
            range_m=1_000.0,
            object_type="T-72",
            current_level="class",
        )
        assert sight_look_optic(target) is SIGHT_WIDE_OPTIC


class TestSightCanStillImprove:
    """`sight_can_still_improve` in isolation -- the required fix from
    `plans/9k113-narrow-search/review.md`: an upper-bound check against
    `SIGHT_NARROW_OPTIC`'s own class/type threshold, with no lower bound."""

    def test_a_presence_target_beyond_binoculars_own_reach_can_still_improve(
        self,
    ) -> None:
        """5000 m is beyond `BINOCULAR_OPTIC`'s own class threshold
        (1750 m for a T-72) but inside `SIGHT_NARROW_OPTIC`'s (6875 m) --
        exactly the gap the review's required fix closes."""
        target = _target(range_m=5_000.0)
        assert sight_can_still_improve(target)

    def test_a_target_beyond_narrows_own_reach_cannot(self) -> None:
        target = _target(range_m=10_000.0)
        assert not sight_can_still_improve(target)

    def test_a_very_close_target_still_can_improve_no_lower_bound(self) -> None:
        """Unlike `improvement_window_m`, there is no lower bound: nothing
        dwells in parallel to resolve a close contact for free while
        `SIGHTING`, so a target well inside wide's own reach is still a
        valid sight candidate."""
        target = _target(range_m=10.0)
        assert sight_can_still_improve(target)

    def test_an_already_identified_target_cannot(self) -> None:
        target = _target(current_level="type")
        assert not sight_can_still_improve(target)

    def test_a_classed_target_is_judged_against_the_type_threshold(self) -> None:
        target = _target(range_m=4_000.0, current_level="class")
        assert not sight_can_still_improve(
            target
        )  # beyond narrow's own type_m (3750 m)
        target = _target(range_m=3_000.0, current_level="class")
        assert sight_can_still_improve(target)


class TestFarSightCandidateIsAdmittedAndSurvives:
    """The review's required test (`plans/9k113-narrow-search/review.md`):
    a contact beyond binocular's own reach, but within the sight's, must
    both (1) be picked for a sight look and (2) survive past the poll
    that started it -- not be ended one poll later by `look_is_finished`
    still judging it against the eye/binocular window."""

    def _sighting_state(self, **overrides: object) -> OpticState:
        base = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        return replace(base, **overrides)  # type: ignore[arg-type]

    def test_a_far_contact_is_picked_for_a_sight_look(self) -> None:
        """5000 m: beyond `BINOCULAR_OPTIC`'s own 1750 m class threshold,
        within `SIGHT_NARROW_OPTIC`'s 6875 m -- and beyond `SIGHT_WIDE_
        OPTIC`'s own 3500 m, so `sight_look_optic` must pick narrow."""
        state, decision = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target(range_m=5_000.0)],
            steady=True,
        )
        assert state.look_contact_id == "CONTACT_1"
        assert decision.optic is SIGHT_NARROW_OPTIC
        assert decision.look_azimuth_deg is not None

    def test_the_look_survives_past_the_poll_that_started_it(self) -> None:
        """The second poll must not find the look already finished --
        before the fix, `look_is_finished` judged the in-progress look
        against the eye/binocular window, found the target already past
        it (it was only ever admitted by the sight's own wider window),
        and ended the look one poll after it started."""
        target = _target(range_m=5_000.0)
        state, decision = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[target],
            steady=True,
        )
        assert state.look_contact_id == "CONTACT_1"
        assert decision.optic is SIGHT_NARROW_OPTIC

        state, decision = decide(
            state,
            now_sim=1.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[target],
            steady=True,
        )
        assert state.look_contact_id == "CONTACT_1"
        assert decision.optic is SIGHT_NARROW_OPTIC


class TestFieldOfRegardEnforcement:
    """`BL-B64` security finding (`plans/9k113-sight/security.md`): the
    sight's physical +-60 deg azimuth / +20/-15 deg elevation pointing
    envelope was declared as data (`Optic.regard_*`) but never enforced --
    `_decide_sighting` could and did pick a look target past the sight's
    own mechanical limit. These pin the fix: a target outside the
    envelope is excluded from `choose_look`'s candidates before selection,
    never committed as `look_azimuth_deg`/`look_elevation_deg`."""

    def _sighting_state(self, **overrides: object) -> OpticState:
        base = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        return replace(base, **overrides)  # type: ignore[arg-type]

    def test_the_security_agents_own_reproduction_is_rejected(self) -> None:
        """The exact scenario from `plans/9k113-sight/security.md`: a
        contact at 85 deg body-relative azimuth, 25 deg past the sight's
        own 60 deg limit. Before the fix this was picked and pointed at
        directly -- confirmed by direct execution in that report.

        **`decision.look_azimuth_deg is None` no longer holds** (`plans/
        9k113-narrow-search/plan.md` Stage 1/3): the idle branch always
        has an aim now, from the active default search -- the fix this
        pins is narrower than "no aim at all": the rejected target is
        never the *source* of the committed aim."""
        state, decision = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target(azimuth_deg=85.0)],
            steady=True,
        )
        assert state.look_contact_id is None
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert decision.look_azimuth_deg is not None
        assert decision.look_azimuth_deg != 85.0

    def test_a_target_just_inside_the_azimuth_limit_is_still_picked(self) -> None:
        state, decision = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target(azimuth_deg=59.0)],
            steady=True,
        )
        assert state.look_contact_id == "CONTACT_1"
        assert decision.optic is SIGHT_WIDE_OPTIC

    def test_elevation_above_the_up_limit_is_rejected(self) -> None:
        """+20 deg up limit."""
        state, decision = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target(elevation_deg=25.0)],
            steady=True,
        )
        assert state.look_contact_id is None
        assert decision.optic is SIGHT_WIDE_OPTIC

    def test_elevation_below_the_down_limit_is_rejected(self) -> None:
        """-15 deg down limit -- the one most likely to bite in practice
        (a close ground contact sits well below the horizon). A
        symmetric +-15 implementation would wrongly accept this at the
        same magnitude the up-limit test rejects at +25, which is exactly
        the bug a symmetric bound would hide."""
        state, decision = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target(elevation_deg=-20.0)],
            steady=True,
        )
        assert state.look_contact_id is None
        assert decision.optic is SIGHT_WIDE_OPTIC

    def test_a_target_at_minus_14_degrees_elevation_is_still_picked(self) -> None:
        """Just inside the -15 deg down limit -- confirms the asymmetric
        bound is not a symmetric +-20 in disguise (which would also pass
        this, but for the wrong reason)."""
        state, decision = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target(elevation_deg=-14.0)],
            steady=True,
        )
        assert state.look_contact_id == "CONTACT_1"
        assert decision.optic is SIGHT_WIDE_OPTIC

    def test_a_target_at_plus_19_degrees_elevation_is_still_picked(self) -> None:
        """Just inside the +20 deg up limit."""
        state, decision = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target(elevation_deg=19.0)],
            steady=True,
        )
        assert state.look_contact_id == "CONTACT_1"
        assert decision.optic is SIGHT_WIDE_OPTIC

    def test_an_in_regard_target_is_still_picked_when_an_out_of_regard_one_exists(
        self,
    ) -> None:
        """Rejection removes only the offending target from consideration
        -- it does not make the sight pick nothing at all when something
        reachable is also worth a look."""
        state, decision = decide(
            self._sighting_state(),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[
                _target("OUT_OF_REGARD", azimuth_deg=85.0),
                _target("IN_REGARD", azimuth_deg=10.0),
            ],
            steady=True,
        )
        assert state.look_contact_id == "IN_REGARD"
        assert decision.optic is SIGHT_WIDE_OPTIC

    def test_the_swept_look_never_commits_an_aim_past_the_boundary(self) -> None:
        """The residual leak flagged in `plans/9k113-sight/implementation.md`'s
        Notable Discoveries: a target 5 deg inside the 60 deg azimuth
        limit, with a fresh contact's default 15 deg bearing uncertainty,
        would sweep steps out to 67 deg -- 7 deg past the mount's own
        limit -- each committed as `look_azimuth_deg` on some poll. Stepped
        through every poll of a full dwell and asserts every committed
        azimuth stays inside the boundary, not just the first one."""
        state = self._sighting_state()
        target = _target(azimuth_deg=55.0)
        max_committed_azimuth = 0.0
        for poll_index in range(30):
            state, decision = decide(
                state,
                now_sim=float(poll_index),
                scan_cycle_period_s=_CYCLE_S,
                targets=[target],
                steady=True,
            )
            if decision.look_azimuth_deg is not None:
                max_committed_azimuth = max(
                    max_committed_azimuth, abs(decision.look_azimuth_deg)
                )
        assert max_committed_azimuth <= 60.0
        # And the look still happened -- this is truncation, not rejection
        # of the whole target (that is the required fix's own test above).
        assert max_committed_azimuth > 0.0

    def test_binocular_cycle_is_unaffected_by_field_of_regard(self) -> None:
        """`GLASSING` (binoculars, `regard_* is None`) never calls through
        `_decide_sighting` at all -- this pins that an out-of-regard-for-
        the-sight azimuth is nonetheless glassed normally via the ordinary
        `SCANNING`-at-home -> `GLASSING` path, confirming the fix changed
        nothing outside `SIGHTING`."""
        state = OpticState(phase=OpticPhase.SCANNING, phase_started_sim=0.0)
        state, decision = decide(
            state,
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target(azimuth_deg=85.0)],
            steady=True,
        )
        assert state.phase is OpticPhase.GLASSING
        assert decision.optic is BINOCULAR_OPTIC
        assert state.look_contact_id == "CONTACT_1"

    def test_a_target_repeatedly_out_of_regard_is_never_marked_attempted(
        self,
    ) -> None:
        """F5's own reacquire requirement: a contact rejected as a *candidate*
        (pitch has put it out of regard this poll) is never selected, so it
        is never written into `pending_attempted_at_range_m`/`attempted_at_
        level` -- a look that never started cannot have "ended", and
        `SIGHT_STALL_COOLDOWN_S` only ever reads those dicts. Run several
        polls with the target held out of regard throughout: it must never
        once be recorded."""
        state = self._sighting_state()
        target = _target(elevation_deg=-16.0)  # just past the -15 deg down limit
        for poll_index in range(10):
            state, decision = decide(
                state,
                now_sim=float(poll_index),
                scan_cycle_period_s=_CYCLE_S,
                targets=[target],
                steady=True,
            )
            assert state.look_contact_id is None
            assert target.contact_id not in state.pending_attempted_at_range_m
            assert target.contact_id not in state.attempted_at_range_m
            assert target.contact_id not in state.attempted_at_level
        assert decision.optic is SIGHT_WIDE_OPTIC

    def test_the_same_target_is_picked_immediately_once_back_in_regard(
        self,
    ) -> None:
        """The other half: once the same contact is back in regard (the
        nose came down), it is picked on the very next poll -- nothing
        carried over from the out-of-regard polls holds it out, because
        nothing was ever recorded for it (the test above)."""
        state = self._sighting_state()
        out_of_regard = _target(elevation_deg=-16.0)
        for poll_index in range(3):
            state, _ = decide(
                state,
                now_sim=float(poll_index),
                scan_cycle_period_s=_CYCLE_S,
                targets=[out_of_regard],
                steady=True,
            )
        assert state.look_contact_id is None

        back_in_regard = _target(elevation_deg=-10.0)
        state, decision = decide(
            state,
            now_sim=3.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[back_in_regard],
            steady=True,
        )
        assert state.look_contact_id == "CONTACT_1"
        assert decision.optic is SIGHT_WIDE_OPTIC


class TestIdleAimInvariant:
    """Stage 1's whole claim in one place (`plans/9k113-narrow-search/
    plan.md`): whenever the sight is handed out as the decided optic, it
    carries an aim already inside its own field of regard -- across every
    path that can produce a `SIGHTING` decision with nothing yet chosen to
    look at (closes F5, `docs/acceptance/2026-10-20-sortie-feedback.md`).
    The four transitions named by Stage 1's own "Fix shape": idle rest,
    resume-from-interruption, resume-from-search, and a guidance override
    arriving during the glance-away."""

    def _assert_invariant(self, decision: OpticDecision) -> None:
        if decision.optic in (SIGHT_WIDE_OPTIC, SIGHT_NARROW_OPTIC):
            assert decision.look_azimuth_deg is not None
            assert within_field_of_regard(
                decision.optic,
                decision.look_azimuth_deg,
                decision.look_elevation_deg or 0.0,
            )

    def test_idle_rest(self) -> None:
        _, decision = decide(
            OpticState(
                phase=OpticPhase.SIGHTING,
                phase_started_sim=0.0,
                home_phase=OpticPhase.SIGHTING,
            ),
            now_sim=1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
        )
        self._assert_invariant(decision)

    def test_resume_from_interruption(self) -> None:
        """A player command (`lower_binoculars`) lands mid-glance-away."""
        state = OpticState(
            phase=OpticPhase.SCANNING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        resumed = lower_binoculars(state, now_sim=1.0)
        _, decision = decide(
            resumed,
            now_sim=1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
        )
        self._assert_invariant(decision)

    def test_resume_from_search(self) -> None:
        """The binocular excursion's own pattern runs out and `_back_to_
        home` resumes `SIGHTING` -- the aim must be the sight's own last
        position, not nulled (the "stays at last position" claim, not only
        the generic invariant)."""
        state = OpticState(
            phase=OpticPhase.SEARCHING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
            search_pattern_steps=((10.0, -2.0),),
            look_azimuth_deg=20.0,
            look_elevation_deg=-3.0,
        )
        _, decision = decide(
            state,
            now_sim=SEARCH_STEP_S + 0.1,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
        )
        self._assert_invariant(decision)
        assert decision.look_azimuth_deg == 20.0
        assert decision.look_elevation_deg == -3.0

    def test_guidance_override_during_glance_away(self) -> None:
        """Stage 1's fourth path: the glance-away's own decision is bare
        `OpticDecision(optic=UNAIDED_OPTIC)` (no aim, because the naked
        eye never needs one) -- a concurrent guidance request must be
        capped to `BINOCULAR_OPTIC` rather than handing back a sight optic
        with the glance's own `look_azimuth_deg=None` untouched."""
        state = OpticState(
            phase=OpticPhase.SCANNING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        _, decision = decide(
            state,
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            guidance_request=SIGHT_NARROW_OPTIC,
        )
        assert decision.optic is BINOCULAR_OPTIC
        self._assert_invariant(decision)


class TestSightSearchLegs:
    """The three-leg cycle itself (`plans/9k113-scan-procedure/plan.md`
    Stage 1) -- `_decide_sighting`'s own mechanism, driven here with
    small synthetic sequences rather than `body.py`'s real geometry (that
    geometry has its own tests in `test_body.py`)."""

    def _sighting_state(self, **overrides: object) -> OpticState:
        base = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        return replace(base, **overrides)  # type: ignore[arg-type]

    _WIDE_NEAR_STEPS = ((0.0, -1.0),)
    _WIDE_FAR_STEPS = ((10.0, -2.0),)
    _NARROW_FAR_SWEEP_STEPS = ((20.0, -3.0),)

    def _decide(
        self,
        state: OpticState,
        now_sim: float,
        *,
        out_of_regard: Sequence[tuple[float, float]] = (),
    ) -> tuple[OpticState, OpticDecision]:
        return decide(
            state,
            now_sim=now_sim,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            sight_wide_near_search=self._WIDE_NEAR_STEPS,
            sight_wide_far_search=self._WIDE_FAR_STEPS,
            sight_narrow_far_sweep_search=self._NARROW_FAR_SWEEP_STEPS,
            sight_out_of_regard_search=out_of_regard,
        )

    def test_the_cycle_steps_wide_near_wide_far_narrow_far_sweep_in_order(
        self,
    ) -> None:
        """Steps `now_sim` by `1.0`, not `SEARCH_STEP_S` (0.8) --
        comfortably past each leg's own one-step boundary without landing
        on it, since repeated float addition of 0.8 drifts enough
        (`2.4000000000000004`) to occasionally read as just *under* a
        step's own `SEARCH_STEP_S` width and miss the advance by one
        poll."""
        state = self._sighting_state()
        seen: list[tuple[Optic, tuple[float, float] | None]] = []
        now_sim = 0.0
        for _ in range(3):
            state, decision = self._decide(state, now_sim)
            seen.append(
                (
                    decision.optic,
                    (decision.look_azimuth_deg, decision.look_elevation_deg),
                )
            )
            assert state.phase is OpticPhase.SIGHTING
            now_sim += 1.0
        assert [optic for optic, _ in seen] == [
            SIGHT_WIDE_OPTIC,
            SIGHT_WIDE_OPTIC,
            SIGHT_NARROW_OPTIC,
        ]
        assert [aim for _, aim in seen] == [
            self._WIDE_NEAR_STEPS[0],
            self._WIDE_FAR_STEPS[0],
            self._NARROW_FAR_SWEEP_STEPS[0],
        ]
        assert state.sight_search_leg == "narrow_far_sweep"

    def test_completing_a_lap_forces_the_glance_away_not_a_fresh_wide_near(
        self,
    ) -> None:
        """Stage 1 item 5: stepping off `narrow_far_sweep` (the cycle's
        last leg) is a completed lap -- the mandatory naked-eye pause
        fires *instead of* restarting `wide_near`, independent of
        `SIGHT_MAX_DWELL_S` -- proven here by `now_sim - phase_started_
        sim` being far under that constant's default (30 s) when the
        pause starts, which is only possible if the *other* trigger
        fired."""
        state = self._sighting_state()
        now_sim = 0.0
        for _ in range(3):  # wide_near, wide_far, narrow_far_sweep
            state, _decision = self._decide(state, now_sim)
            now_sim += 1.0
        assert state.phase is OpticPhase.SIGHTING

        # The poll after narrow_far_sweep's own single step runs out.
        state, decision = self._decide(state, now_sim)
        assert state.phase is OpticPhase.SCANNING
        assert state.home_phase is OpticPhase.SIGHTING  # a pause, not OBSERV off
        assert decision.optic is UNAIDED_OPTIC
        assert now_sim - state.phase_started_sim < SIGHT_MAX_DWELL_S

    def test_the_cycle_resumes_a_fresh_wide_near_pass_after_the_glance_away(
        self,
    ) -> None:
        """No out-of-regard remainder: once `SIGHT_GLANCE_AWAY_S` elapses,
        `_back_to_home` resumes `SIGHTING` at the sight's own last
        position -- `narrow_far_sweep`'s own step, since `[[BL-B98]]`'s
        fix has `_start_glance_away` carry the aim through rather than
        nulling it -- and the poll after that starts `wide_near` over
        from its own first step -- never entering `OpticPhase.SEARCHING`
        at all."""
        state = self._sighting_state()
        now_sim = 0.0
        for _ in range(4):  # wide_near, wide_far, narrow_far_sweep, glance-away starts
            state, _decision = self._decide(state, now_sim)
            now_sim += 1.0
        assert state.phase is OpticPhase.SCANNING

        now_sim = state.phase_started_sim + SIGHT_GLANCE_AWAY_S
        state, decision = self._decide(state, now_sim)
        assert state.phase is OpticPhase.SIGHTING  # resumed, at last position
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert (
            decision.look_azimuth_deg,
            decision.look_elevation_deg,
        ) == self._NARROW_FAR_SWEEP_STEPS[0]
        assert state.sight_search_leg == "wide_near"

        now_sim += 1.0
        state, decision = self._decide(state, now_sim)
        assert state.phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert decision.look_azimuth_deg == self._WIDE_NEAR_STEPS[0][0]
        assert decision.look_elevation_deg == self._WIDE_NEAR_STEPS[0][1]

        now_sim += 1.0
        state, decision = self._decide(state, now_sim)
        assert state.phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert decision.look_azimuth_deg == self._WIDE_FAR_STEPS[0][0]

    def test_an_out_of_regard_remainder_is_swept_once_the_glance_away_ends(
        self,
    ) -> None:
        """The out-of-regard binocular excursion is entered from the
        glance-away's own resume point, not as a fourth leg of this
        cycle (`_enter_binocular_search`'s own docstring) -- so it never
        appears mid-lap, only right after the mandatory pause."""
        out_of_regard = ((70.0, -1.0), (-70.0, -1.0))
        state = self._sighting_state()
        now_sim = 0.0
        for _ in range(4):  # wide_near, wide_far, narrow_far_sweep, glance-away starts
            state, _decision = self._decide(state, now_sim, out_of_regard=out_of_regard)
            now_sim += 1.0
        assert state.phase is OpticPhase.SCANNING

        now_sim = state.phase_started_sim + SIGHT_GLANCE_AWAY_S
        state, decision = self._decide(state, now_sim, out_of_regard=out_of_regard)
        assert state.phase is OpticPhase.SEARCHING
        assert decision.optic is BINOCULAR_OPTIC
        assert (
            decision.look_azimuth_deg,
            decision.look_elevation_deg,
        ) == out_of_regard[0]
        assert state.sight_search_leg == "wide_near"
        # The mandatory glance-away this excursion was entered from no
        # longer nulls the sight's own aim (`[[BL-B98]]`'s fix to
        # `_start_glance_away`) -- `_enter_binocular_search` carries the
        # pre-lap position through unchanged, it does not null it.
        assert state.look_azimuth_deg == self._NARROW_FAR_SWEEP_STEPS[0][0]
        assert state.look_elevation_deg == self._NARROW_FAR_SWEEP_STEPS[0][1]

        # The excursion's own pattern (two steps) runs out and resumes
        # SIGHTING at exactly that last sight position, ready to start a
        # fresh `wide_near` pass.
        now_sim += 1.0
        state, decision = self._decide(state, now_sim, out_of_regard=out_of_regard)
        assert state.phase is OpticPhase.SEARCHING
        assert decision.optic is BINOCULAR_OPTIC
        assert (
            decision.look_azimuth_deg,
            decision.look_elevation_deg,
        ) == out_of_regard[1]

        now_sim += 1.0
        state, decision = self._decide(state, now_sim, out_of_regard=out_of_regard)
        assert state.phase is OpticPhase.SIGHTING  # resumed, at last position
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert (
            decision.look_azimuth_deg,
            decision.look_elevation_deg,
        ) == self._NARROW_FAR_SWEEP_STEPS[0]
        assert state.sight_search_leg == "wide_near"

        now_sim += 1.0
        state, decision = self._decide(state, now_sim, out_of_regard=out_of_regard)
        assert state.phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert decision.look_azimuth_deg == self._WIDE_NEAR_STEPS[0][0]
        assert decision.look_elevation_deg == self._WIDE_NEAR_STEPS[0][1]


class TestSightStallCooldown:
    """`BL-B85` -- a contact stuck at `presence` forever can fully starve
    the sight's search cycle (`docs/acceptance/2026-10-20-sortie-
    feedback.md` F4, `plans/9k113-narrow-search/review.md`'s 900 s/
    three-contact reproduction: busy 792/900 polls, `sight_search_leg`
    never advancing past `"wide"`). `SIGHT_STALL_COOLDOWN_S` extends
    `is_worth_a_look`'s existing retry bookkeeping rather than adding a
    second mechanism -- see that constant's own docstring."""

    def _sighting_state(self, **overrides: object) -> OpticState:
        base = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        return replace(base, **overrides)  # type: ignore[arg-type]

    _WIDE_NEAR_STEPS = ((0.0, -1.0),)
    _WIDE_FAR_STEPS = ((10.0, -2.0),)
    _NARROW_FAR_SWEEP_STEPS = ((20.0, -3.0),)

    def _decide(
        self, state: OpticState, now_sim: float, targets: Sequence[LookTarget]
    ) -> tuple[OpticState, OpticDecision]:
        return decide(
            state,
            now_sim=now_sim,
            scan_cycle_period_s=_CYCLE_S,
            targets=targets,
            steady=True,
            sight_wide_near_search=self._WIDE_NEAR_STEPS,
            sight_wide_far_search=self._WIDE_FAR_STEPS,
            sight_narrow_far_sweep_search=self._NARROW_FAR_SWEEP_STEPS,
        )

    def test_a_stalled_contact_is_not_retried_before_the_sight_cooldown(
        self,
    ) -> None:
        """Surgical unit test on `is_worth_a_look` directly: a contact
        whose level has not moved since its last committed attempt is held
        out for `SIGHT_STALL_COOLDOWN_S`, longer than the pre-`BL-B85`
        `OPTIC_RETRY_INTERVAL_S` that let it straight back in."""
        assert OPTIC_RETRY_INTERVAL_S < SIGHT_STALL_COOLDOWN_S
        state = OpticState(
            attempted_at_range_m={"CONTACT_1": 80.0},
            attempted_at_time_sim={"CONTACT_1": 0.0},
            attempted_at_level={"CONTACT_1": "presence"},
        )
        stalled_target = _target(range_m=80.0, current_level="presence")

        # Past the short GLASSING-era interval, but short of the sight's
        # own longer cooldown.
        assert not is_worth_a_look(
            stalled_target,
            state,
            now_sim=OPTIC_RETRY_INTERVAL_S + 1.0,
            can_improve=sight_can_still_improve,
            stall_cooldown_s=SIGHT_STALL_COOLDOWN_S,
        )

    def test_glassing_keeps_the_pre_existing_short_interval(self) -> None:
        """`GLASSING`'s own call never passes `stall_cooldown_s` -- a
        stalled contact under binoculars is unaffected by this feature,
        by construction rather than by a second code path. 1_700.0 m, not
        the close ranges the other tests in this class use, because
        `can_still_improve` (the naked-eye/binocular pair `GLASSING` asks)
        excludes anything the naked eye would resolve for free on its own
        next dwell -- the same range `TestIsWorthALook`'s own GLASSING
        tests use."""
        state = OpticState(
            attempted_at_range_m={"CONTACT_1": 1_700.0},
            attempted_at_time_sim={"CONTACT_1": 0.0},
            attempted_at_level={"CONTACT_1": "presence"},
        )
        stalled_target = _target(range_m=1_700.0, current_level="presence")
        assert is_worth_a_look(
            stalled_target, state, now_sim=OPTIC_RETRY_INTERVAL_S + 1.0
        )

    def test_a_stalled_contact_is_retried_once_the_sight_cooldown_elapses(
        self,
    ) -> None:
        state = OpticState(
            attempted_at_range_m={"CONTACT_1": 80.0},
            attempted_at_time_sim={"CONTACT_1": 0.0},
            attempted_at_level={"CONTACT_1": "presence"},
        )
        stalled_target = _target(range_m=80.0, current_level="presence")
        assert is_worth_a_look(
            stalled_target,
            state,
            now_sim=SIGHT_STALL_COOLDOWN_S,
            can_improve=sight_can_still_improve,
            stall_cooldown_s=SIGHT_STALL_COOLDOWN_S,
        )

    def test_progress_since_the_last_attempt_keeps_the_fast_retry(self) -> None:
        """A contact whose level *did* move since the last committed
        attempt is not penalised by the longer cooldown -- only a
        genuinely stuck one is."""
        state = OpticState(
            attempted_at_range_m={"CONTACT_1": 80.0},
            attempted_at_time_sim={"CONTACT_1": 0.0},
            attempted_at_level={"CONTACT_1": "presence"},
        )
        progressed_target = _target(range_m=80.0, current_level="class")
        assert is_worth_a_look(
            progressed_target,
            state,
            now_sim=OPTIC_RETRY_INTERVAL_S + 1.0,
            can_improve=sight_can_still_improve,
            stall_cooldown_s=SIGHT_STALL_COOLDOWN_S,
        )

    def test_three_contacts_stuck_at_presence_still_let_the_search_cycle_run(
        self,
    ) -> None:
        """The pessimistic reproduction from `plans/9k113-narrow-search/
        review.md`: three simultaneous close contacts held at `presence`
        forever (a stuck/stalled belief-layer case, not modelled
        behaviour). Before `BL-B85` the sight was busy 792/900 polls (88%)
        and `sight_search_leg` never advanced past `"wide"` for the whole
        run -- end to end against this exact scenario, measured at 58%
        busy with every leg visited and every contact re-looked four
        times over a 600 s run, once both halves of the fix are in place
        (`_start_glance_away` now committing a timed-out look instead of
        discarding it, and `SIGHT_STALL_COOLDOWN_S` then bounding the
        re-grant once there is something committed to bound)."""
        targets = [
            _target("CONTACT_1", azimuth_deg=0.0, range_m=50.0),
            _target("CONTACT_2", azimuth_deg=40.0, range_m=80.0),
            _target("CONTACT_3", azimuth_deg=-40.0, range_m=120.0),
        ]
        state = self._sighting_state()
        busy_polls = 0
        total_polls = 0
        legs_seen: set[str] = set()
        look_starts: dict[str, int] = {t.contact_id: 0 for t in targets}
        now_sim = 0.0
        step_s = 1.0
        duration_s = 600.0
        while now_sim < duration_s:
            state, _decision = self._decide(state, now_sim, targets)
            total_polls += 1
            legs_seen.add(state.sight_search_leg)
            if state.look_contact_id is not None:
                busy_polls += 1
                if state.look_started_sim == now_sim:
                    look_starts[state.look_contact_id] += 1
            now_sim += step_s

        busy_fraction = busy_polls / total_polls
        assert busy_fraction < 0.75, (
            "the sight should not stay busy on identification looks the "
            f"whole run (pre-BL-B85 measured 88%); measured "
            f"{busy_fraction:.2%}"
        )
        assert legs_seen >= {"wide_near", "wide_far", "narrow_far_sweep"}, (
            "the idle search cycle should advance through every leg once "
            f"the cooldown gives it room; only saw {legs_seen}"
        )
        assert all(count >= 2 for count in look_starts.values()), (
            "every contact should still be re-looked more than once over "
            f"a 600 s run, not abandoned forever: {look_starts}"
        )

    def test_three_progressing_contacts_all_reach_type_and_search_resumes(
        self,
    ) -> None:
        """The "realistic case" `plans/9k113-narrow-search/review.md`'s
        "Review -- F5 boresight + BL-B85 refinement" required as a committed
        test rather than a one-off narrative number -- `BL-B85.md`'s own
        "Realistic case" paragraph must describe what this test measures,
        not a figure nobody can re-derive.

        **"The poll after its look ends" is ambiguous -- the review's own
        words -- so the exact convention used here is**: a contact's level
        advances one tier (`presence -> class -> type`) the instant its own
        look stops being `state.look_contact_id` for any reason (the
        scheduled `SIGHT_MAX_DWELL_S` dwell boundary, in practice, for a
        target close enough that `sight_can_still_improve` never excludes
        it below `type`) -- i.e. the bumped level is what the *next* poll's
        `targets` carries, never the poll that ended the look itself. Two
        independent reproductions of this exact scenario disagreed in the
        prior review round (10.4% busy/exits at 97/262/427 s vs. this
        module's own 19.4%/130/163/196 s) -- this test pins the real
        code's own answer under one precise, reproducible convention, so
        there is no second narrative to disagree with."""
        contacts = (
            ("CONTACT_1", 0.0, 50.0),
            ("CONTACT_2", 40.0, 80.0),
            ("CONTACT_3", -40.0, 120.0),
        )
        level_after = {"presence": "class", "class": "type", "type": "type"}
        levels = {contact_id: "presence" for contact_id, _az, _range_m in contacts}
        reached_type_at_sim: dict[str, float] = {}
        look_starts: dict[str, int] = {
            contact_id: 0 for contact_id, _az, _range_m in contacts
        }

        state = self._sighting_state()
        busy_polls = 0
        total_polls = 0
        legs_seen: set[str] = set()
        now_sim = 0.0
        step_s = 1.0
        duration_s = 900.0
        while now_sim < duration_s:
            targets = [
                _target(
                    contact_id,
                    azimuth_deg=azimuth_deg,
                    range_m=range_m,
                    current_level=levels[contact_id],
                )
                for contact_id, azimuth_deg, range_m in contacts
            ]
            previous_look_contact_id = state.look_contact_id
            state, _decision = self._decide(state, now_sim, targets)
            total_polls += 1
            legs_seen.add(state.sight_search_leg)
            if state.look_contact_id is not None:
                busy_polls += 1
                if state.look_started_sim == now_sim:
                    look_starts[state.look_contact_id] += 1

            # The look that was active just ended this poll (for any
            # reason) -- advance that contact's level one tier, to take
            # effect from the *next* poll's `targets` onward.
            if (
                previous_look_contact_id is not None
                and state.look_contact_id != previous_look_contact_id
            ):
                old_level = levels[previous_look_contact_id]
                new_level = level_after[old_level]
                if new_level != old_level:
                    levels[previous_look_contact_id] = new_level
                    if new_level == "type":
                        reached_type_at_sim[previous_look_contact_id] = now_sim

            now_sim += step_s

        busy_fraction = busy_polls / total_polls
        assert look_starts == {
            "CONTACT_1": 2,
            "CONTACT_2": 2,
            "CONTACT_3": 2,
        }, (
            "each contact needs exactly two completed looks to reach "
            f"type (presence->class, class->type); measured {look_starts}"
        )
        assert reached_type_at_sim == {
            "CONTACT_1": 129.0,
            "CONTACT_2": 162.0,
            "CONTACT_3": 195.0,
        }, (
            "exact, reproducible exit times under this test's bump "
            f"convention; measured {reached_type_at_sim}"
        )
        assert busy_polls == 175 and total_polls == 900, (
            f"measured busy_polls={busy_polls}, total_polls={total_polls} "
            f"({busy_fraction:.1%}); expected 175/900 (19.4%)"
        )
        assert legs_seen == {"wide_near", "wide_far", "narrow_far_sweep"}, (
            "every search leg should be visited once all three contacts "
            f"have exited candidacy; only saw {legs_seen}"
        )

    def test_a_progressing_contact_is_relooked_near_the_pre_bl_b85_cadence(
        self,
    ) -> None:
        """`plans/9k113-narrow-search/review.md`'s "Review -- BL-B85"
        required fix: the first round's `_start_glance_away` committed
        every pending mark unconditionally, which also throttled a contact
        whose classification was genuinely advancing, not only a stalled
        one -- measured there at a re-look cadence of ~94 s (dwell +
        `OPTIC_RETRY_INTERVAL_S`) instead of the pre-`BL-B85` ~33 s
        (`SIGHT_MAX_DWELL_S` + `SIGHT_GLANCE_AWAY_S`).

        Here the contact advances `presence` -> `class` at t=10 s, *during*
        its first look's dwell (which runs t=0-30) -- so that look's
        pending mark is dropped (progress since the look started), not
        committed, leaving the contact immediately eligible again once the
        glance-away ends, rather than waiting out `OPTIC_RETRY_INTERVAL_S`
        from a stale commit. `class` then holds for the rest of the
        window, so this test only pins the first re-look gap, which is
        the one the required fix changes -- the second look's own dwell
        sees no further progress and commits normally (`SIGHT_STALL_
        COOLDOWN_S` taking over from there is already covered by the
        stalled-contact tests above)."""
        contact_id = "CONTACT_1"
        level_changes_at_s = 10.0

        def targets_at(now_sim: float) -> list[LookTarget]:
            level = "presence" if now_sim < level_changes_at_s else "class"
            return [_target(contact_id, range_m=80.0, current_level=level)]

        state = self._sighting_state()
        look_starts: list[float] = []
        now_sim = 0.0
        step_s = 1.0
        duration_s = 120.0
        while now_sim < duration_s:
            state, _decision = self._decide(state, now_sim, targets_at(now_sim))
            if state.look_contact_id is not None and state.look_started_sim == now_sim:
                look_starts.append(now_sim)
            now_sim += step_s

        assert len(look_starts) >= 2, (
            f"expected at least two look-starts in {duration_s:.0f} s, got "
            f"{look_starts}"
        )
        pre_bl_b85_cadence_s = SIGHT_MAX_DWELL_S + SIGHT_GLANCE_AWAY_S
        second_look_gap_s = look_starts[1] - look_starts[0]
        assert second_look_gap_s < OPTIC_RETRY_INTERVAL_S, (
            "a contact that progressed during its look should not wait out "
            f"OPTIC_RETRY_INTERVAL_S ({OPTIC_RETRY_INTERVAL_S:.0f} s) before "
            f"its next look; measured a {second_look_gap_s:.0f} s gap "
            f"(pre-BL-B85 cadence: {pre_bl_b85_cadence_s:.0f} s)"
        )
        assert second_look_gap_s <= pre_bl_b85_cadence_s + 5.0, (
            "expected the re-look gap to stay close to the pre-BL-B85 "
            f"cadence of {pre_bl_b85_cadence_s:.0f} s, measured "
            f"{second_look_gap_s:.0f} s"
        )

    def test_an_inverting_override_imports_cleanly_and_floors_to_the_retry_interval(
        self, tmp_path: Path
    ) -> None:
        """`plans/9k113-narrow-search/review.md`'s "Review -- F5 boresight +
        BL-B85 refinement" required fix: the old bare `assert
        OPTIC_RETRY_INTERVAL_S < SIGHT_STALL_COOLDOWN_S` at import time
        crashed the whole process on a single, realistic, in-bounds
        override -- `SIGHT_STALL_COOLDOWN_S = 40.0` sits comfortably inside
        its own declared `lo=30.0, hi=400.0` and still inverts the pair
        against the default `OPTIC_RETRY_INTERVAL_S` of 64.0. Fresh process,
        not an in-process reimport, for the same reason `test_tuning.py`'s
        `test_a_real_constant_resolves_an_override_in_a_fresh_process` is:
        `belief.optic_policy` has already bound its constants by the time
        this test file's own imports ran.

        Behavioural, not just a value check: a stalled contact must become
        eligible again at the *floored* 64.0 s (the ordinary retry
        interval), not at the overridden 40.0 s -- using the raw override
        would silently reintroduce the throttle gap `SIGHT_STALL_COOLDOWN_S`
        exists to close."""
        tuning_file = tmp_path / "tuning.toml"
        tuning_file.write_text(
            "[belief.optic_policy]\nSIGHT_STALL_COOLDOWN_S = 40.0\n",
            encoding="utf-8",
        )
        body_layer_src = Path(__file__).resolve().parent.parent / "src"
        world_model_src = (
            Path(__file__).resolve().parent.parent.parent / "world-model" / "src"
        )
        env = {
            "PETROBRAIN_TUNING": str(tuning_file),
            "PYTHONPATH": f"{body_layer_src}:{world_model_src}",
            "PATH": "/usr/bin:/bin",
        }
        script = (
            "from belief.optic_policy import (\n"
            "    OPTIC_RETRY_INTERVAL_S,\n"
            "    SIGHT_STALL_COOLDOWN_S,\n"
            "    LookTarget,\n"
            "    OpticState,\n"
            "    _EFFECTIVE_SIGHT_STALL_COOLDOWN_S,\n"
            "    is_worth_a_look,\n"
            "    sight_can_still_improve,\n"
            ")\n"
            "assert SIGHT_STALL_COOLDOWN_S == 40.0, SIGHT_STALL_COOLDOWN_S\n"
            "assert OPTIC_RETRY_INTERVAL_S == 64.0, OPTIC_RETRY_INTERVAL_S\n"
            "assert _EFFECTIVE_SIGHT_STALL_COOLDOWN_S == OPTIC_RETRY_INTERVAL_S, (\n"
            "    _EFFECTIVE_SIGHT_STALL_COOLDOWN_S\n"
            ")\n"
            "state = OpticState(\n"
            "    attempted_at_range_m={'CONTACT_1': 80.0},\n"
            "    attempted_at_time_sim={'CONTACT_1': 0.0},\n"
            "    attempted_at_level={'CONTACT_1': 'presence'},\n"
            ")\n"
            "stalled_target = LookTarget(\n"
            "    contact_id='CONTACT_1', azimuth_deg=0.0, elevation_deg=0.0,\n"
            "    range_m=80.0, object_type='T-72', current_level='presence',\n"
            ")\n"
            "assert not is_worth_a_look(\n"
            "    stalled_target, state, now_sim=45.0,\n"
            "    can_improve=sight_can_still_improve,\n"
            "    stall_cooldown_s=_EFFECTIVE_SIGHT_STALL_COOLDOWN_S,\n"
            "), 'must not use the raw 40.0 s override as the real cooldown'\n"
            "assert is_worth_a_look(\n"
            "    stalled_target, state, now_sim=65.0,\n"
            "    can_improve=sight_can_still_improve,\n"
            "    stall_cooldown_s=_EFFECTIVE_SIGHT_STALL_COOLDOWN_S,\n"
            "), 'must become eligible again once the floored 64.0 s elapses'\n"
        )
        # `check=True` is the point: this call must not raise -- the bug
        # being fixed here is an uncaught `AssertionError` at import, which
        # `subprocess.run` surfaces as a non-zero exit and this would turn
        # into a `CalledProcessError`.
        subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )


class TestManoeuvreForcesObservOff:
    """Direction §8: *"Gyros are sensitive to violent manouvres and OBSERV
    must be swithced OFF is pilot manouvres violently."* Unlike a normal
    binocular interruption (which only ends the current dwell),
    `sight_steady=False` drops `home_phase` back to `SCANNING` -- OBSERV
    itself ends, not just the current look."""

    def test_an_unsteady_poll_while_sighting_turns_observ_off_entirely(
        self,
    ) -> None:
        state = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
            look_contact_id="CONTACT_1",
            look_started_sim=0.0,
        )
        state, decision = decide(
            state,
            now_sim=1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
            sight_steady=False,
        )
        assert state.home_phase is OpticPhase.SCANNING
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC
        # The interrupted look's pending marks are dropped, not committed.
        assert state.pending_attempted_at_range_m == {}

    def test_binoculars_steadiness_is_unaffected_by_sight_steady(self) -> None:
        """`steady`/`sight_steady` answer different questions -- a violent
        manoeuvre on the sight's own gate must not interrupt an ordinary
        binocular look that is otherwise steady."""
        state, _ = decide(
            OpticState(phase_started_sim=0.0),
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
            sight_steady=False,
        )
        assert state.phase is OpticPhase.GLASSING


class TestObservOffStopsTheSightImmediately:
    """`BL-B64` Stage 2 review, Pass 2 required fix. The pilot's "Observ
    off" command (`body.py`'s poll loop) drains into `state.home_phase`
    alone, one poll lagged -- the same shape `_force_observ_off` already
    uses for a violated `sight_steady`, just arriving from a pilot command
    instead of a manoeuvre. Every test here builds the *diverged* state
    directly (`phase=SIGHTING`, `home_phase=SCANNING`) -- the state no
    pre-existing test constructed, which is exactly why the gap survived
    46 new tests on the first implementation."""

    def test_observ_off_while_idle_sighting_exits_on_the_next_poll(self) -> None:
        state = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SCANNING,  # already diverged
        )
        state, decision = decide(
            state,
            now_sim=1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING
        assert state.home_phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC

    def test_observ_off_mid_look_drops_the_look_on_the_next_poll(self) -> None:
        """The reviewer's own reproduction: a look is active when the
        command lands, and it must not be allowed to finish."""
        state = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SCANNING,  # diverged: command already landed
            look_contact_id="CONTACT_1",
            look_started_sim=0.0,
            pending_attempted_at_range_m={"CONTACT_1": 3000.0},
        )
        state, decision = decide(
            state,
            now_sim=1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC
        assert state.look_contact_id is None
        # Dropped, same as any other interruption on this phase -- not
        # committed, so the contact is immediately eligible for a fresh
        # look if OBSERV comes back on.
        assert state.pending_attempted_at_range_m == {}

    def test_observ_off_never_reaches_sight_max_dwell_s(self) -> None:
        """Stepped for several polls, well short of `SIGHT_MAX_DWELL_S` --
        before the fix this stayed in `SIGHTING` throughout (the review's
        own eight-second reproduction); it must now leave on the very
        first poll after the command lands."""
        state = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
            look_contact_id="CONTACT_1",
            look_started_sim=0.0,
        )
        # The command lands: the poll loop sets home_phase alone.
        state = replace(state, home_phase=OpticPhase.SCANNING)
        for poll in range(1, 5):
            state, decision = decide(
                state,
                now_sim=float(poll),
                scan_cycle_period_s=_CYCLE_S,
                targets=[],
                steady=True,
            )
            assert state.phase is OpticPhase.SCANNING
            assert decision.optic is UNAIDED_OPTIC

    def test_observ_still_on_through_sighting_is_unaffected(self) -> None:
        """Counter-test: the ordinary agreeing-state cycle stays exactly
        as before this fix -- `home_phase is SIGHTING` throughout, so the
        new check is a no-op and `_decide_sighting` still runs."""
        state = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        state, decision = decide(
            state,
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SIGHTING
        assert decision.optic is SIGHT_WIDE_OPTIC


class TestHandsBusy:
    """`BL-B64` Stage 2, direction §6's 1 s hand movement -- `decide`
    suppresses every optic's observations while `hands_busy_until_sim` is
    active, rather than advancing any phase logic."""

    def test_suppressed_while_hands_are_busy(self) -> None:
        state = OpticState(phase_started_sim=0.0, hands_busy_until_sim=1.0)
        new_state, decision = decide(
            state,
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert decision.suppressed is True
        assert new_state.phase is OpticPhase.SCANNING
        assert new_state is state

    def test_no_longer_suppressed_once_the_duration_elapses(self) -> None:
        state = OpticState(phase_started_sim=0.0, hands_busy_until_sim=1.0)
        _, decision = decide(
            state,
            now_sim=1.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert decision.suppressed is False

    def test_hands_busy_duration_constant_is_positive(self) -> None:
        assert HANDS_BUSY_DURATION_S > 0.0


class TestLowerBinocularsPreservesObserv:
    """§13a's first named trap: `lower_binoculars` runs on every player
    command and must not drop OBSERV -- it is a pilot-commanded standing
    mode (direction §6), distinct from the current dwell this function
    ends."""

    def test_lowering_while_sighting_is_home_and_idle_is_a_no_op(self) -> None:
        """Mirrors today's "lowering while already naked-eye scanning is a
        no-op" exactly, with the roles swapped -- idle, no look chosen."""
        state = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        result = lower_binoculars(state, now_sim=5.0)
        assert result is state
        assert result.home_phase is OpticPhase.SIGHTING

    def test_lowering_while_sighting_is_home_drops_an_active_look(self) -> None:
        """Unlike `SCANNING`-at-home (which never has a look in progress
        while it is the current phase), `SIGHTING`-at-home is its own
        "closer look" -- so a command can still drop an *active* look back
        to idle without leaving `home_phase`, the same distinction §13a
        draws for the standing mode versus the current dwell."""
        state = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
            look_contact_id="CONTACT_1",
            look_started_sim=0.0,
        )
        result = lower_binoculars(state, now_sim=5.0)
        assert result.phase is OpticPhase.SIGHTING
        assert result.home_phase is OpticPhase.SIGHTING
        assert result.look_contact_id is None

    def test_lowering_mid_glance_away_returns_to_sighting_not_scanning_home(
        self,
    ) -> None:
        """The brief glance-away is `phase is SCANNING` with `home_phase is
        SIGHTING` -- lowering it must hand back to the sight, not drop
        OBSERV by accident."""
        state = OpticState(
            phase=OpticPhase.SCANNING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        result = lower_binoculars(state, now_sim=1.0)
        assert result.phase is OpticPhase.SIGHTING
        assert result.home_phase is OpticPhase.SIGHTING

    def test_lowering_a_sight_look_drops_pending_but_keeps_observ_on(
        self,
    ) -> None:
        state, _ = decide(
            OpticState(
                phase=OpticPhase.SIGHTING,
                phase_started_sim=0.0,
                home_phase=OpticPhase.SIGHTING,
            ),
            now_sim=0.5,
            scan_cycle_period_s=_CYCLE_S,
            targets=[_target()],
            steady=True,
        )
        assert state.phase is OpticPhase.SIGHTING
        assert state.look_contact_id == "CONTACT_1"

        result = lower_binoculars(state, now_sim=1.0)
        assert result.phase is OpticPhase.SIGHTING
        assert result.home_phase is OpticPhase.SIGHTING
        assert result.look_contact_id is None
        assert result.pending_attempted_at_range_m == {}


class TestSightSteadyRateLimitIsHigherThanBinoculars:
    """Cross-key coupling (not enforced at import, like `SIGHT_WIDE_RANGE_
    SIGMA_SCALE`/`SIGHT_NARROW_RANGE_SIGMA_SCALE`'s own ordering) -- a
    stabilised sight must tolerate at least as much attitude-rate as a
    pair of hands holding binoculars, per direction §8's own framing."""

    def test_sight_rate_limit_is_at_least_binocular_rate_limit(self) -> None:
        assert SIGHT_STEADY_RATE_LIMIT_DEG_S >= STEADY_RATE_LIMIT_DEG_S


# -- `BL-B71`: `least_capable_sufficient_optic` (Stage 1, naive) ---------

# Presence thresholds for "T-72" (`profile_for`), computed once here from
# the same `tier_ranges` formula the module itself uses, rather than
# re-measured per assertion: UNAIDED ~2333 m, BINOCULAR ~5647 m,
# SIGHT_WIDE ~8283 m, SIGHT_NARROW ~13557 m.
_T72_UNAIDED_M = 2333.3333333333335
_T72_BINOCULAR_M = 5646.666666666667
_T72_SIGHT_WIDE_M = 8283.333333333334
_T72_SIGHT_NARROW_M = 13556.666666666666


class TestLeastCapableSufficientOptic:
    def test_within_naked_eye_range_picks_the_least_capable_optic(self) -> None:
        """§6/§7: naked eye first, not the most capable instrument
        available -- the whole product argument (`BL-B71.md`: "more
        capable means narrower")."""
        assert (
            least_capable_sufficient_optic(
                1000.0, "T-72", floor=UNAIDED_OPTIC, ceiling=SIGHT_NARROW_OPTIC
            )
            is UNAIDED_OPTIC
        )

    def test_beyond_naked_eye_escalates_to_binoculars(self) -> None:
        assert (
            least_capable_sufficient_optic(
                _T72_UNAIDED_M + 1.0,
                "T-72",
                floor=UNAIDED_OPTIC,
                ceiling=SIGHT_NARROW_OPTIC,
            )
            is BINOCULAR_OPTIC
        )

    def test_beyond_binoculars_escalates_to_sight_wide(self) -> None:
        assert (
            least_capable_sufficient_optic(
                _T72_BINOCULAR_M + 1.0,
                "T-72",
                floor=UNAIDED_OPTIC,
                ceiling=SIGHT_NARROW_OPTIC,
            )
            is SIGHT_WIDE_OPTIC
        )

    def test_beyond_everything_falls_back_to_the_ceiling(self) -> None:
        """Even `SIGHT_NARROW_OPTIC` cannot resolve this -- the function
        returns the ceiling rather than raising; the caller's own
        remembered-sighting fallback (`TOO_FAR`) is what speaks in that
        case."""
        assert (
            least_capable_sufficient_optic(
                _T72_SIGHT_NARROW_M + 1.0,
                "T-72",
                floor=UNAIDED_OPTIC,
                ceiling=SIGHT_NARROW_OPTIC,
            )
            is SIGHT_NARROW_OPTIC
        )

    def test_ceiling_below_binoculars_never_returns_a_sight_optic(self) -> None:
        """The `BL-B71.md` hard gate's own shape, one layer down: a caller
        that passes `ceiling=BINOCULAR_OPTIC` (OBSERV off) can never get a
        sight optic back, no matter how close the range -- confirmed by
        mutation: removing the `ceiling_rank + 1` slice bound (replacing
        it with the whole `_LADDER`) makes this assert fail, since the
        function would then walk past the ceiling to `SIGHT_NARROW_OPTIC`
        at this range."""
        result = least_capable_sufficient_optic(
            50_000.0, "T-72", floor=UNAIDED_OPTIC, ceiling=BINOCULAR_OPTIC
        )
        assert result is BINOCULAR_OPTIC


# -- `BL-B71`: `guidance_request_for` (Stage 3, hysteresis) --------------


class TestGuidanceRequestFor:
    def test_no_previous_request_starts_from_the_floor(self) -> None:
        assert (
            guidance_request_for(
                1000.0, "T-72", None, floor=UNAIDED_OPTIC, ceiling=SIGHT_NARROW_OPTIC
            )
            is UNAIDED_OPTIC
        )

    def test_escalation_is_immediate_no_band(self) -> None:
        """§7: "Escalate when range_m > threshold(current)" -- crossing
        by one metre is enough, no margin."""
        result = guidance_request_for(
            _T72_UNAIDED_M + 1.0,
            "T-72",
            UNAIDED_OPTIC,
            floor=UNAIDED_OPTIC,
            ceiling=SIGHT_NARROW_OPTIC,
        )
        assert result is BINOCULAR_OPTIC

    def test_de_escalation_is_withheld_until_the_margin_is_crossed(self) -> None:
        """Guard 2: sitting just inside `BINOCULAR_OPTIC`'s own threshold
        is not enough to step back down to `UNAIDED_OPTIC` -- only once
        the range is comfortably past the unaided threshold by
        `GUIDANCE_OPTIC_HYSTERESIS_FRACTION`'s own margin. This is the
        counterfactual: with the margin removed (testable by asserting at
        exactly `_T72_UNAIDED_M - 1.0`, which sits on the wrong side of
        the margin but still inside the raw unaided threshold) the naive
        answer would already be `UNAIDED_OPTIC`, so the two cases below
        must disagree for the hysteresis to be doing anything at all."""
        just_inside_unaided_m = _T72_UNAIDED_M - 1.0
        comfortably_inside_m = (
            _T72_UNAIDED_M * (1.0 - GUIDANCE_OPTIC_HYSTERESIS_FRACTION) - 1.0
        )
        assert just_inside_unaided_m > comfortably_inside_m

        held = guidance_request_for(
            just_inside_unaided_m,
            "T-72",
            BINOCULAR_OPTIC,
            floor=UNAIDED_OPTIC,
            ceiling=SIGHT_NARROW_OPTIC,
        )
        assert held is BINOCULAR_OPTIC  # still held -- margin not crossed yet

        de_escalated = guidance_request_for(
            comfortably_inside_m,
            "T-72",
            BINOCULAR_OPTIC,
            floor=UNAIDED_OPTIC,
            ceiling=SIGHT_NARROW_OPTIC,
        )
        assert de_escalated is UNAIDED_OPTIC

    def test_de_escalation_steps_one_rung_at_a_time(self) -> None:
        """A contact that closes from well beyond `SIGHT_WIDE_OPTIC`'s own
        threshold straight to naked-eye range de-escalates to
        `SIGHT_WIDE_OPTIC` first, not straight to `UNAIDED_OPTIC` -- one
        rung per tick, matching how a real poll loop calls this (every
        tick, not once at the end of a long closure)."""
        very_close_m = 100.0
        result = guidance_request_for(
            very_close_m,
            "T-72",
            SIGHT_NARROW_OPTIC,
            floor=UNAIDED_OPTIC,
            ceiling=SIGHT_NARROW_OPTIC,
        )
        assert result is SIGHT_WIDE_OPTIC

    def test_previous_below_floor_is_clamped_up_to_the_floor(self) -> None:
        """A `floor` raised since the last request (the ATGM arm's own
        shape) must never leave a stale request sitting below it."""
        result = guidance_request_for(
            100.0,
            "T-72",
            UNAIDED_OPTIC,
            floor=SIGHT_WIDE_OPTIC,
            ceiling=SIGHT_NARROW_OPTIC,
        )
        assert result is SIGHT_WIDE_OPTIC


# -- `BL-B71`: `decide`'s `guidance_request` override --------------------


def _idle_scanning_state(**kwargs: object) -> OpticState:
    return OpticState(phase_started_sim=0.0, **kwargs)  # type: ignore[arg-type]


class TestGuidanceOverride:
    """`decide`'s post-dispatch override step (`_apply_guidance`) --
    `guidance_request=None` is a true no-op (exercised by every other
    test in this file, none of which pass it), so these only cover the
    new behaviour."""

    def test_guidance_request_none_is_a_true_no_op(self) -> None:
        state = _idle_scanning_state()
        state_without, decision_without = decide(
            state,
            now_sim=1.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
        )
        state_with, decision_with = decide(
            state,
            now_sim=1.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=None,
        )
        assert state_with == state_without
        assert decision_with == decision_without

    def test_a_granted_request_overrides_the_optic(self) -> None:
        state, decision = decide(
            _idle_scanning_state(),
            now_sim=1.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=BINOCULAR_OPTIC,
        )
        assert decision.optic is BINOCULAR_OPTIC
        assert state.guidance_optic is BINOCULAR_OPTIC
        assert state.guidance_optic_since_sim == 1.0
        # A real change from the SCANNING home optic -- hands-busy charged.
        assert state.hands_busy_until_sim == 1.0 + HANDS_BUSY_DURATION_S

    def test_the_hard_gate_the_9k113_is_never_reached_for_autonomously(
        self,
    ) -> None:
        """`BL-B71.md`'s hard gate: a sight-ranked request is capped to
        `BINOCULAR_OPTIC` whenever `home_phase` is not `SIGHTING` -- the
        pilot has not said "Observ on". Counterfactual: deleting the
        ceiling-clamp branch in `_apply_guidance` makes this assert
        `SIGHT_NARROW_OPTIC`, confirmed by temporarily removing the clamp
        and re-running (the clamp is the only code standing between a
        guidance request and the sight)."""
        state, decision = decide(
            _idle_scanning_state(home_phase=OpticPhase.SCANNING),
            now_sim=1.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=SIGHT_NARROW_OPTIC,
        )
        assert decision.optic is BINOCULAR_OPTIC
        assert state.guidance_optic is BINOCULAR_OPTIC

    def test_the_gate_lifts_once_observ_is_on(self) -> None:
        state, decision = decide(
            _idle_scanning_state(
                phase=OpticPhase.SIGHTING, home_phase=OpticPhase.SIGHTING
            ),
            now_sim=1.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=SIGHT_NARROW_OPTIC,
        )
        assert decision.optic is SIGHT_NARROW_OPTIC
        assert state.guidance_optic is SIGHT_NARROW_OPTIC

    def test_the_diverged_state_sight_granted_while_scanning_is_home_demotes_at_once(
        self,
    ) -> None:
        """The hand-built diverged state the plan explicitly calls for:
        `guidance_optic is SIGHT_WIDE_OPTIC` while `home_phase is
        OpticPhase.SCANNING` -- every natural path through `decide` keeps
        the two consistent, so this constructs the divergence directly
        (`BL-B64`'s own equivalent needed exactly this). A single poll
        must demote the standing grant to `BINOCULAR_OPTIC`, not merely
        refuse to escalate further."""
        diverged = OpticState(
            phase_started_sim=0.0,
            home_phase=OpticPhase.SCANNING,
            guidance_optic=SIGHT_WIDE_OPTIC,
            guidance_optic_since_sim=0.0,
        )
        state, decision = decide(
            diverged,
            now_sim=GUIDANCE_OPTIC_MIN_INTERVAL_S + 1.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=SIGHT_WIDE_OPTIC,
        )
        assert decision.optic is BINOCULAR_OPTIC
        assert state.guidance_optic is BINOCULAR_OPTIC

    def test_guard_3_refuses_a_change_before_the_minimum_interval(self) -> None:
        granted, decision1 = decide(
            _idle_scanning_state(),
            now_sim=0.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=BINOCULAR_OPTIC,
        )
        assert decision1.optic is BINOCULAR_OPTIC

        too_soon_s = GUIDANCE_OPTIC_MIN_INTERVAL_S - 1.0
        refused, decision2 = decide(
            granted,
            now_sim=too_soon_s,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=SIGHT_WIDE_OPTIC,
        )
        assert decision2.optic is BINOCULAR_OPTIC  # held, not SIGHT_WIDE_OPTIC
        assert refused.guidance_optic is BINOCULAR_OPTIC
        # Refusing costs no hands: the charge from the first grant stands
        # unchanged, not re-stamped.
        assert refused.hands_busy_until_sim == granted.hands_busy_until_sim
        assert refused.guidance_optic_since_sim == granted.guidance_optic_since_sim

    def test_guard_3_allows_the_change_once_the_interval_has_passed(self) -> None:
        """Observ is already on (`home_phase=SIGHTING`), so the only gate
        left standing between the two grants is guard 3's own clock --
        isolating this from the hard sight gate, which has its own tests
        above."""
        sighting = _idle_scanning_state(
            phase=OpticPhase.SIGHTING, home_phase=OpticPhase.SIGHTING
        )
        granted, _ = decide(
            sighting,
            now_sim=0.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=BINOCULAR_OPTIC,
        )
        state, decision = decide(
            granted,
            now_sim=GUIDANCE_OPTIC_MIN_INTERVAL_S + 1.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=SIGHT_WIDE_OPTIC,
        )
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert state.guidance_optic is SIGHT_WIDE_OPTIC

    def test_revocation_on_disengage(self) -> None:
        """Co-moving Fields: `disengage`/`drop_target`/run ends ->
        `guidance_request=None` the next poll -> `guidance_optic` and its
        clock both go back to `None` together."""
        granted, _ = decide(
            _idle_scanning_state(),
            now_sim=0.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=BINOCULAR_OPTIC,
        )
        assert granted.guidance_optic is BINOCULAR_OPTIC

        state, decision = decide(
            granted,
            now_sim=1.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=None,
        )
        assert state.guidance_optic is None
        assert state.guidance_optic_since_sim is None
        assert decision.optic is UNAIDED_OPTIC  # whatever the dispatch picked

    def test_suppressed_by_hands_busy_is_never_overridden(self) -> None:
        """A guidance request arriving during the 1 s hands-busy window
        must not be granted or charged -- `_apply_guidance` is never even
        called while `decision.suppressed`."""
        state = OpticState(phase_started_sim=0.0, hands_busy_until_sim=5.0)
        new_state, decision = decide(
            state,
            now_sim=1.0,
            scan_cycle_period_s=1000.0,
            targets=[],
            steady=True,
            guidance_request=BINOCULAR_OPTIC,
        )
        assert decision.suppressed is True
        assert decision.optic is UNAIDED_OPTIC
        assert new_state.guidance_optic is None

    def test_a_fresh_search_phase_entry_does_not_reset_a_standing_grant(
        self,
    ) -> None:
        """The fresh-`OpticState(...)` trap (`BL-B64` Stage 1's own
        review): entering `SEARCHING` from `SCANNING`-at-home constructs a
        new `OpticState` rather than `replace`-ing one, so a standing
        guidance grant's `guidance_optic`/`guidance_optic_since_sim` must
        be carried forward explicitly there, or an unrelated commanded
        search would silently reset the grant's clock and trigger a
        spurious second hands-busy charge. Counterfactual: dropping the
        two `guidance_optic*` kwargs from that construction site makes
        `hands_busy_until_sim` jump again here, since `_apply_guidance`
        would then see a freshly-`None`d clock and treat this as a first
        grant."""
        state = OpticState(
            phase=OpticPhase.SCANNING,
            phase_started_sim=0.0,
            guidance_optic=BINOCULAR_OPTIC,
            guidance_optic_since_sim=0.0,
            hands_busy_until_sim=0.0 + HANDS_BUSY_DURATION_S,
        )
        new_state, decision = decide(
            state,
            now_sim=_CYCLE_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            search=[(10.0, 0.0), (-10.0, 0.0)],
            guidance_request=BINOCULAR_OPTIC,
        )
        assert new_state.phase is OpticPhase.SEARCHING
        assert new_state.guidance_optic is BINOCULAR_OPTIC
        assert new_state.guidance_optic_since_sim == 0.0
        assert new_state.hands_busy_until_sim == 0.0 + HANDS_BUSY_DURATION_S
        assert decision.optic is BINOCULAR_OPTIC


class TestBoundedSightLook:
    """`look <o'clock>`/`look <compass>`'s own bounded search (`plans/
    9k113-scan-procedure/plan-stage2.md`'s "The sweep itself") -- driven
    here with small synthetic step sequences, the same posture
    `TestSightSearchLegs` takes for the three-leg cycle."""

    _POINT_STEPS = ((5.0, -1.0), (6.0, -1.0))

    def _sighting_state(self, **overrides: object) -> OpticState:
        base = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
            bounded_look=BoundedSightLook(
                center_azimuth_deg=5.5,
                half_width_deg=15.0,
                near_m=1_500.0,
                far_m=8_000.0,
                label="two o'clock",
            ),
        )
        return replace(base, **overrides)  # type: ignore[arg-type]

    def _decide(
        self, state: OpticState, now_sim: float, *, targets: Sequence[LookTarget] = ()
    ) -> tuple[OpticState, OpticDecision]:
        return decide(
            state,
            now_sim=now_sim,
            scan_cycle_period_s=_CYCLE_S,
            targets=targets,
            steady=True,
            sight_point_search=self._POINT_STEPS,
        )

    def test_bounded_look_is_checked_before_the_idle_cycle(self) -> None:
        """A `bounded_look` pre-empts the ordinary three-leg cycle --
        `sight_search_leg` stays untouched (still its default `wide_near`)
        while the bounded search runs, so the idle cycle resumes there
        once the bounded look clears."""
        state = self._sighting_state()
        state, decision = self._decide(state, 0.0)
        assert decision.optic is SIGHT_WIDE_OPTIC
        assert (decision.look_azimuth_deg, decision.look_elevation_deg) == (
            self._POINT_STEPS[0]
        )
        assert state.sight_search_leg == "wide_near"
        assert state.bounded_look is not None
        assert state.bounded_look.sweeps_completed == 0

    def test_two_sweeps_then_clear_and_resume(self) -> None:
        """`POINT_SWEEP_COUNT` (2) complete traversals of the two-step
        sequence with nothing found, then `point_clear_label` is set and
        the idle cycle takes over the same poll."""
        assert POINT_SWEEP_COUNT == 2
        state = self._sighting_state()
        now_sim = 0.0
        step_s = SEARCH_STEP_S
        # Each sweep is two steps; step past both to complete one sweep.
        for _ in range(2 * POINT_SWEEP_COUNT):
            state, decision = self._decide(state, now_sim)
            now_sim += step_s

        # One more poll steps past the second sweep's own last step.
        state, decision = self._decide(state, now_sim)
        assert state.bounded_look is None
        assert state.point_clear_label == "two o'clock"
        # Handed off to the idle cycle in the same poll -- no aim is left
        # unset.
        assert decision.look_azimuth_deg is not None

    def test_a_found_contact_does_not_consume_a_sweep(self) -> None:
        """Mid-sweep, a target becoming worth a look interrupts the
        bounded search (an ordinary look, chosen by `choose_sighting_
        look`) without incrementing `sweeps_completed` -- the interrupting
        report is not counted as a completed sweep."""
        state = self._sighting_state()
        state, _ = self._decide(state, 0.0)
        assert state.bounded_look is not None
        assert state.bounded_look.sweeps_completed == 0

        target = _target(
            "c1",
            azimuth_deg=5.0,
            elevation_deg=-1.0,
            range_m=3_000.0,
            current_level="class",
        )
        state, decision = self._decide(state, SEARCH_STEP_S, targets=[target])
        assert state.look_contact_id == "c1"
        assert decision.optic in (SIGHT_WIDE_OPTIC, SIGHT_NARROW_OPTIC)
        # The bounded look's own sweep count is untouched by the
        # interruption.
        assert state.bounded_look is not None
        assert state.bounded_look.sweeps_completed == 0

    def test_observ_off_clears_the_bounded_look(self) -> None:
        """`_back_to_home`'s OBSERV-off branch (`home_phase` leaving
        `SIGHTING`) tears a running bounded look down, same as the rest
        of the sighting state (`[[BL-B98]]`'s own rule)."""
        state = self._sighting_state()
        state, _ = self._decide(state, 0.0)
        assert state.bounded_look is not None
        state = replace(state, home_phase=OpticPhase.SCANNING)
        state, decision = decide(
            state,
            now_sim=SEARCH_STEP_S,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
        )
        assert state.bounded_look is None
        assert state.phase is OpticPhase.SCANNING
        assert decision.optic is UNAIDED_OPTIC

    def test_empty_steps_falls_back_to_idle_cycle_without_announcing(self) -> None:
        """A bounded wedge/band that generates no steps at all (e.g. a
        compass bearing wholly outside the sight's own field of regard)
        hands off to the idle cycle the same poll, with no "<where>
        clear." -- an empty search answered nothing, which is not the
        same claim as "searched it and it was clear."."""
        state = self._sighting_state()
        state, decision = decide(
            state,
            now_sim=0.0,
            scan_cycle_period_s=_CYCLE_S,
            targets=[],
            steady=True,
            sight_point_search=(),
            sight_wide_near_search=((0.0, -1.0),),
        )
        assert state.bounded_look is None
        assert state.point_clear_label is None
        assert decision.look_azimuth_deg is not None
