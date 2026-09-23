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
