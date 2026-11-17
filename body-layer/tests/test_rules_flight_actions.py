"""`config/rules/flight.lua` -- Stage 2's `turn_heading_relative` plus
Stage 4's full flight-control port (`plans/speech-rules/plan.md`
D18/D16, `[[BL-17]]`). Loads the **real**, shipped rule file (not a
fixture copy), and differentially pins every ported command's readback/
transition against the pre-rules handler it replaced (deleted in the
same stage) for every case that handler's own tests covered -- left/
right, a wrap past 0 and 360, `NOT_READY`/`NOT_FLYING`, the speed-max
sentinel, the altitude reference-resolution cases, and the HVRT hover
precondition.

Recorded **before** the old handlers were deleted (`git show` on the
commits that removed `tests/test_crew_console_ai_pilot_wheel.py`'s own
`TestLevelFlight`/`TestTurnHeading`/`TestSetSpeed`/`TestSpeedStep`/
`TestSetAltitude`/`TestAltitudeStep`/`TestHoldAltitude`/`TestLevelOff`/
`TestHvrtTranslate`/`TestHvrtHold`/`TestHvrtStep` classes has the exact
pre-rules assertions this file reproduces) -- see `plans/speech-rules/
implementation.md` for the pointer, since those classes no longer exist
in the working tree to diff against directly.

**Stage 4's own gate split** (review-stage3b.md Required Fix 1,
`rules.gates`): the single `"flight_control"` category from Stage 3b
split into `"flight_control"` (has-controls only) plus
`"flight_control_heading"`/`"_speed"`/`"_altitude"`/`"_any"` (also
holding for their own particular `held_*` value) -- every dispatch test
below sets exactly the held fields its own rule's category needs, not a
blanket "flying and settled" fixture, so a wrong category assignment
would show up as a spurious hold/unable rather than passing by
coincidence."""

from __future__ import annotations

from dataclasses import replace

from belief.ai_pilot_wheel import (
    AiPilotGoalRequest,
    AiPilotWheelGoal,
    ParkedFlightState,
)
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from rules.actions import ACTION_NAMESPACES, ActionContext
from rules.engine import RuleSet, run_rule
from rules.loader import DEFAULT_RULES_DIR
from rules.sandbox import RuleSandbox


def _console(**state_fields: object) -> CrewConsole:
    console = CrewConsole(store=ContactStore())
    console.parked_flight_state = replace(ParkedFlightState(), **state_fields)
    return console


def _dispatching_console(**state_fields: object) -> CrewConsole:
    """Like `_console`, but wired for the **real** dispatch path
    (`handle_command` -> `_handle_rule`/`drain_pending_rule_dispatch` ->
    the category gate -> `_dispatch_rule` -> the real `run_rule` against
    the real shipped `flight.lua`) -- every Stage 4 gate/differential
    test below goes through this, not a direct `run_rule` call, so the
    category gate is genuinely exercised rather than bypassed."""
    console = _console(**state_fields)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)

    def runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = runner
    console.set_enabled_rule_ids(
        frozenset(rule_set.rules),
        {rid: r.category for rid, r in rule_set.rules.items()},
    )
    return console


def test_shipped_rule_files_load_with_zero_failures() -> None:
    """Body-layer's own loader never runs the adapter's collision check
    (D1: that is audio-adapter's job, over `PUT /rules`) -- every one of
    the 19 rules `flight.lua` declares loads cleanly here regardless of
    which ones the real adapter would later reject for a wording
    collision (five, as of this stage -- see `plans/speech-rules/
    implementation.md`'s own Stage 4 section for the full account)."""
    sandbox = RuleSandbox()
    ctx = ActionContext(console=CrewConsole(store=ContactStore()))
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    assert rule_set.failures == ()
    assert set(rule_set.rules) == {
        "turn_heading_relative",
        "turn_heading",
        "level_flight",
        "set_speed",
        "speed_step",
        "set_altitude",
        "altitude_step",
        "hold_altitude",
        "level_off",
        "straight",
        "hvrt_translate_left",
        "hvrt_translate_right",
        "hvrt_translate_forward",
        "hvrt_translate_back",
        "hvrt_hold",
        "hvrt_step_up",
        "hvrt_step_down",
        "you_have_controls",
        "i_have_controls",
    }


def test_turns_right_from_the_held_heading() -> None:
    console = _console(held_heading=10.0)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    outcome = run_rule(
        rule_set,
        "turn_heading_relative",
        {"direction": "right", "degrees": 20},
        sandbox,
    )
    assert outcome.lines == ["20 right."]
    assert outcome.error is False
    assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
        param="heading", heading_deg=30.0
    )


def test_turns_left_from_the_held_heading() -> None:
    console = _console(held_heading=10.0)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    outcome = run_rule(
        rule_set,
        "turn_heading_relative",
        {"direction": "left", "degrees": 20},
        sandbox,
    )
    assert outcome.lines == ["20 left."]
    assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
        param="heading", heading_deg=350.0
    )


def test_wraps_past_360() -> None:
    console = _console(held_heading=350.0)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    outcome = run_rule(
        rule_set,
        "turn_heading_relative",
        {"direction": "right", "degrees": 20},
        sandbox,
    )
    assert outcome.lines == ["20 right."]
    assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
        param="heading", heading_deg=10.0
    )


def test_wraps_past_0() -> None:
    console = _console(held_heading=10.0)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    outcome = run_rule(
        rule_set,
        "turn_heading_relative",
        {"direction": "left", "degrees": 20},
        sandbox,
    )
    assert outcome.lines == ["20 left."]
    assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
        param="heading", heading_deg=350.0
    )


def test_gate_refuses_not_flying_before_the_action_ever_runs() -> None:
    """`[[BL-17]]` Stage 3b (D16) supersedes the old direct-`run_rule`
    "unable without a known current heading" case above: `increment_ai_
    heading`'s own `current is None` check is gone (dead code once the
    `flight_control` gate owns the precondition), so the only way to see
    "unable" for this rule now is through the real dispatch path
    (`CrewConsole._handle_rule`/`handle_command`), which the gate refuses
    *before* the action is ever called -- `parked_active=False` here, so
    `held_heading` never even matters."""
    console = _console(parked_active=False)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)

    def runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = runner
    console.set_enabled_rule_ids(
        frozenset(rule_set.rules),
        {rid: r.category for rid, r in rule_set.rules.items()},
    )
    lines = console.handle_command(
        "turn_heading_relative", now_sim=0.0, slots={"direction": "left", "degrees": 20}
    )
    assert lines == ["Unable, not flying."]
    assert console.ai_pilot_goal_transition is None


def test_gate_holds_then_flies_once_settling_resolves() -> None:
    """The takeover-settle window (`CrewState.settling`): `parked_active`
    is already `True` but `held_heading` has not arrived yet -- the gate
    holds (speaks nothing), and once a later poll's `parked_flight_state`
    carries a `held_heading`, `drain_pending_rule_dispatch` flies the
    held command exactly as if it had just been said (Q12, "hold and fly
    when ready")."""
    console = _console(parked_active=True, held_heading=None)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)

    def runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = runner
    console.set_enabled_rule_ids(
        frozenset(rule_set.rules),
        {rid: r.category for rid, r in rule_set.rules.items()},
    )
    lines = console.handle_command(
        "turn_heading_relative", now_sim=0.0, slots={"direction": "left", "degrees": 20}
    )
    assert lines == []
    assert console.pending_rule_dispatch is not None
    assert console.ai_pilot_goal_transition is None

    # Settling resolves: a later poll's `parked_flight_state` carries a
    # held heading. `drain_pending_rule_dispatch` runs the handler now.
    console.parked_flight_state = replace(
        console.parked_flight_state, held_heading=10.0
    )
    lines = console.drain_pending_rule_dispatch(now_sim=1.0)
    assert lines == ["20 left."]
    assert console.pending_rule_dispatch is None
    assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
        param="heading", heading_deg=350.0
    )


def test_gate_holds_then_times_out_to_unable() -> None:
    """Still `HOLD` once `RULE_GATE_HOLD_TIMEOUT_S` has elapsed -- the
    player unparked, or `held_heading` genuinely never arrives (a real
    fault, not a settle delay) -- speaks "unable" once and clears the
    field."""
    console = _console(parked_active=True, held_heading=None)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)

    def runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = runner
    console.set_enabled_rule_ids(
        frozenset(rule_set.rules),
        {rid: r.category for rid, r in rule_set.rules.items()},
    )
    console.handle_command(
        "turn_heading_relative", now_sim=0.0, slots={"direction": "left", "degrees": 20}
    )
    assert console.pending_rule_dispatch is not None

    # Still settling, well past the default 5.0 s hold timeout.
    lines = console.drain_pending_rule_dispatch(now_sim=100.0)
    assert lines == ["Unable, not ready."]
    assert console.pending_rule_dispatch is None


class TestTurnHeadingAbsolute:
    """Differential pin against the deleted `TestTurnHeading` (`_handle_
    turn_heading`). Category `"flight_control"` -- has-controls only, no
    held value needed."""

    def test_speaks_the_resolved_heading_digit_by_digit(self) -> None:
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command(
            "turn_heading", now_sim=0.0, slots={"heading_deg": 315}
        )
        assert lines == ["Heading 3 1 5."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="heading", heading_deg=315.0
        )

    def test_not_flying_answers_unable_not_flying(self) -> None:
        """Today's defect, fixed by the gate (BL-17.md Finding 2/E13):
        before this stage the old handler had *no* precondition check at
        all, so issuing this command while unparked silently set a
        transition `body.py` would later drop with no spoken feedback."""
        console = _dispatching_console(parked_active=False)
        lines = console.handle_command(
            "turn_heading", now_sim=0.0, slots={"heading_deg": 315}
        )
        assert lines == ["Unable, not flying."]
        assert console.ai_pilot_goal_transition is None


class TestLevelFlight:
    """Differential pin against the deleted `TestLevelFlight`. Category
    `"flight_control_any"` -- holds only while *none* of the three held
    values is known, exactly the deleted handler's own "partial
    knowledge still freezes what is known" rule, now owned by the gate."""

    def test_freezes_all_three_known_values(self) -> None:
        console = _dispatching_console(
            parked_active=True,
            held_heading=90.0,
            held_altitude=300.0,
            held_speed=150.0,
        )
        lines = console.handle_command("level_flight", now_sim=0.0)
        assert lines == ["Level flight."]
        assert console.ai_pilot_level_flight_transition is True

    def test_partial_knowledge_still_passes(self) -> None:
        """Only `held_speed` known -- the gate passes (any one of three
        is enough), matching the deleted handler's own rule exactly."""
        console = _dispatching_console(parked_active=True, held_speed=150.0)
        lines = console.handle_command("level_flight", now_sim=0.0)
        assert lines == ["Level flight."]
        assert console.ai_pilot_level_flight_transition is True

    def test_holds_then_times_out_when_nothing_is_known_yet(self) -> None:
        """The deleted handler spoke "Unable, not ready." synchronously;
        the gate now holds-and-retries instead (Q12), only answering
        unable once `RULE_GATE_HOLD_TIMEOUT_S` elapses."""
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command("level_flight", now_sim=0.0)
        assert lines == []
        assert console.pending_rule_dispatch is not None
        lines = console.drain_pending_rule_dispatch(now_sim=100.0)
        assert lines == ["Unable, not ready."]


class TestSetSpeed:
    """Differential pin against the deleted `TestSetSpeed`. Category
    `"flight_control"` -- no held value needed for the absolute form."""

    def test_snaps_a_numeric_request_for_the_readback(self) -> None:
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command(
            "set_speed",
            now_sim=0.0,
            slots={"speed_target": {"kind": "number", "value": 140}},
        )
        assert lines == ["Speed 1 5 0."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="speed", speed_kmh=140.0
        )

    def test_the_literal_max_speaks_max(self) -> None:
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command(
            "set_speed", now_sim=0.0, slots={"speed_target": {"kind": "max"}}
        )
        assert lines == ["Speed max."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="speed", speed_kmh="max"
        )


class TestSpeedStep:
    """Differential pin against the deleted `TestSpeedStep`. Category
    `"flight_control_speed"` -- holds until `held_speed` is known."""

    def test_steps_up_from_the_held_speed(self) -> None:
        console = _dispatching_console(parked_active=True, held_speed=120.0)
        lines = console.handle_command(
            "speed_step", now_sim=0.0, slots={"verb": "speed", "direction": "up"}
        )
        assert lines == ["Speed 1 5 0."]

    def test_steps_down_from_the_held_speed(self) -> None:
        console = _dispatching_console(parked_active=True, held_speed=120.0)
        lines = console.handle_command(
            "speed_step", now_sim=0.0, slots={"verb": "slow", "direction": "down"}
        )
        assert lines == ["Speed 6 0."]

    def test_holds_then_flies_once_held_speed_arrives(self) -> None:
        console = _dispatching_console(parked_active=True, held_speed=None)
        lines = console.handle_command(
            "speed_step", now_sim=0.0, slots={"verb": "speed", "direction": "up"}
        )
        assert lines == []
        assert console.pending_rule_dispatch is not None
        console.parked_flight_state = replace(
            console.parked_flight_state, held_speed=120.0
        )
        lines = console.drain_pending_rule_dispatch(now_sim=1.0)
        assert lines == ["Speed 1 5 0."]


class TestSetAltitude:
    """Differential pin against the deleted `TestSetAltitude`. Category
    `"flight_control"` -- no held value needed for the absolute form."""

    def test_a_reachable_radar_request_is_honoured(self) -> None:
        console = _dispatching_console(parked_active=True, held_altitude_ref="B")
        lines = console.handle_command(
            "set_altitude",
            now_sim=0.0,
            slots={"verb": "altitude", "altitude_m": 300, "reference": "radar"},
        )
        assert lines == ["300 meters."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="altitude", altitude_m=300.0, altitude_ref="radar"
        )

    def test_a_target_above_the_cap_speaks_barometric_not_radar(self) -> None:
        console = _dispatching_console(parked_active=True, held_altitude_ref="R")
        lines = console.handle_command(
            "set_altitude",
            now_sim=0.0,
            slots={"verb": "altitude", "altitude_m": 900, "reference": "radar"},
        )
        assert lines == ["900 meters barometric."]

    def test_no_reference_spoken_keeps_the_current_one(self) -> None:
        console = _dispatching_console(parked_active=True, held_altitude_ref="R")
        lines = console.handle_command(
            "set_altitude", now_sim=0.0, slots={"verb": "alt", "altitude_m": 300}
        )
        assert lines == ["300 meters."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="altitude", altitude_m=300.0, altitude_ref="radar"
        )


class TestAltitudeStep:
    """Differential pin against the deleted `TestAltitudeStep`. Category
    `"flight_control_altitude"` -- holds until `held_altitude` is known."""

    def test_climbs_from_the_held_altitude(self) -> None:
        console = _dispatching_console(
            parked_active=True, held_altitude=300.0, held_altitude_ref="B"
        )
        lines = console.handle_command(
            "altitude_step",
            now_sim=0.0,
            slots={"direction": "climb", "amount_m": 50},
        )
        assert lines == ["350 meters barometric."]

    def test_descends_from_the_held_altitude(self) -> None:
        console = _dispatching_console(
            parked_active=True, held_altitude=300.0, held_altitude_ref="R"
        )
        lines = console.handle_command(
            "altitude_step",
            now_sim=0.0,
            slots={"direction": "descend", "amount_m": 50},
        )
        assert lines == ["250 meters."]

    def test_holds_then_flies_once_held_altitude_arrives(self) -> None:
        console = _dispatching_console(parked_active=True, held_altitude=None)
        lines = console.handle_command(
            "altitude_step",
            now_sim=0.0,
            slots={"direction": "climb", "amount_m": 50},
        )
        assert lines == []
        assert console.pending_rule_dispatch is not None


class TestHoldAltitude:
    """Differential pin against the deleted `TestHoldAltitude`. Category
    `"flight_control_altitude"`."""

    def test_freezes_at_the_held_value_and_reference(self) -> None:
        console = _dispatching_console(
            parked_active=True, held_altitude=300.0, held_altitude_ref="B"
        )
        lines = console.handle_command(
            "hold_altitude", now_sim=0.0, slots={"verb": "altitude"}
        )
        assert lines == ["Holding 300 meters."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="altitude", altitude_m=300.0, altitude_ref="barometric"
        )


class TestLevelOffAndStraight:
    """Differential pin against the deleted `TestLevelOff`. Category
    `"flight_control_heading"`. Two rule ids (`level_off`/`straight`)
    sharing one action -- both pinned."""

    def test_level_off_holds_the_current_heading(self) -> None:
        console = _dispatching_console(parked_active=True, held_heading=120.0)
        lines = console.handle_command("level_off", now_sim=0.0)
        assert lines == ["Heading 1 2 0."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="heading", heading_deg=120.0
        )

    def test_straight_holds_the_current_heading(self) -> None:
        console = _dispatching_console(parked_active=True, held_heading=120.0)
        lines = console.handle_command("straight", now_sim=0.0)
        assert lines == ["Heading 1 2 0."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="heading", heading_deg=120.0
        )

    def test_holds_then_flies_once_held_heading_arrives(self) -> None:
        console = _dispatching_console(parked_active=True, held_heading=None)
        lines = console.handle_command("level_off", now_sim=0.0)
        assert lines == []
        assert console.pending_rule_dispatch is not None


class TestHvrtTranslate:
    """Differential pin against the deleted `TestHvrtTranslate`. Category
    `"flight_control"` -- has-controls only; `_ai_pilot_hvrt_ready`'s own
    hover-mode check stays the action's own finer precondition (D16/D18),
    unaffected by the gate."""

    def test_dispatches_from_hover(self) -> None:
        console = _dispatching_console(parked_active=True, ai_mode="HVR")
        lines = console.handle_command("hvrt_translate_left", now_sim=0.0)
        assert lines == ["Left."]
        assert console.ai_pilot_hvrt_transition == "left"

    def test_dispatches_while_already_in_hvrt(self) -> None:
        console = _dispatching_console(parked_active=True, ai_mode="HVRT")
        lines = console.handle_command("hvrt_translate_forward", now_sim=0.0)
        assert lines == ["Forward."]
        assert console.ai_pilot_hvrt_transition == "forward"

    def test_unable_when_not_in_hover(self) -> None:
        console = _dispatching_console(parked_active=True, ai_mode="FLT")
        lines = console.handle_command("hvrt_translate_right", now_sim=0.0)
        assert lines == ["Unable, not ready."]
        assert console.ai_pilot_hvrt_transition is None

    def test_unable_before_any_mode_has_been_read(self) -> None:
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command("hvrt_translate_back", now_sim=0.0)
        assert lines == ["Unable, not ready."]

    def test_unable_not_flying_takes_priority_over_the_mode_check(self) -> None:
        """The coarse `"flight_control"` gate runs *before* the action's
        own `_ai_pilot_hvrt_ready` check -- not flying at all answers
        "unable, not flying," never "unable, not ready," even with
        `ai_mode="HVR"` already set from a previous activation."""
        console = _dispatching_console(parked_active=False, ai_mode="HVR")
        lines = console.handle_command("hvrt_translate_left", now_sim=0.0)
        assert lines == ["Unable, not flying."]


class TestHvrtHold:
    """Differential pin against the deleted `TestHvrtHold`."""

    def test_clears_the_translate(self) -> None:
        console = _dispatching_console(parked_active=True, ai_mode="HVRT")
        lines = console.handle_command("hvrt_hold", now_sim=0.0)
        assert lines == ["Holding."]
        assert console.ai_pilot_hvrt_transition == "hold"

    def test_unable_when_not_in_hover(self) -> None:
        console = _dispatching_console(parked_active=True, ai_mode="CBTM")
        lines = console.handle_command("hvrt_hold", now_sim=0.0)
        assert lines == ["Unable, not ready."]

    def test_cancels_unconditionally_when_a_translate_is_already_outstanding(
        self,
    ) -> None:
        """Review fix (BL-16 Stage P2): "Hold" must cancel an outstanding
        translate even when the aircraft has left hover -- `parked_active`
        must still be `True` for the gate to pass at all (physically, HVRT
        cannot be active while unparked), unlike the pre-rules unit test
        this pins, which never had to satisfy a gate."""
        console = _dispatching_console(
            parked_active=True,
            ai_mode="FLT",
            goal=AiPilotWheelGoal(hvrt_direction="left"),
        )
        lines = console.handle_command("hvrt_hold", now_sim=0.0)
        assert lines == ["Holding."]
        assert console.ai_pilot_hvrt_transition == "hold"

    def test_still_unable_when_nothing_outstanding_and_not_in_hover(self) -> None:
        console = _dispatching_console(parked_active=True, ai_mode="FLT", goal=None)
        lines = console.handle_command("hvrt_hold", now_sim=0.0)
        assert lines == ["Unable, not ready."]
        assert console.ai_pilot_hvrt_transition is None


class TestHvrtStep:
    """Differential pin against the deleted `TestHvrtStep`."""

    def test_taps_up(self) -> None:
        console = _dispatching_console(parked_active=True, ai_mode="HVRT")
        lines = console.handle_command("hvrt_step_up", now_sim=0.0)
        assert lines == ["Up."]
        assert console.ai_pilot_hvrt_step_transition == "up"

    def test_taps_down(self) -> None:
        console = _dispatching_console(parked_active=True, ai_mode="HVR")
        lines = console.handle_command("hvrt_step_down", now_sim=0.0)
        assert lines == ["Down."]
        assert console.ai_pilot_hvrt_step_transition == "down"

    def test_unable_when_not_in_hover(self) -> None:
        console = _dispatching_console(parked_active=True, ai_mode="FLT")
        lines = console.handle_command("hvrt_step_up", now_sim=0.0)
        assert lines == ["Unable, not ready."]
        assert console.ai_pilot_hvrt_step_transition is None


class TestHaveControlsNoOp:
    """Q7: a silent no-op in AI-overlay mode, category `"always"` --
    never gated by seat or flight state, dispatches identically whether
    or not Petrovich has controls."""

    def test_you_have_controls_is_silent(self) -> None:
        console = _dispatching_console(parked_active=False)
        lines = console.handle_command("you_have_controls", now_sim=0.0)
        assert lines == []

    def test_i_have_controls_is_silent_while_flying_too(self) -> None:
        console = _dispatching_console(parked_active=True, held_heading=10.0)
        lines = console.handle_command("i_have_controls", now_sim=0.0)
        assert lines == []


class TestTransitionsResetEachDispatch:
    """Differential pin against the deleted `TestTransitionsResetEachDispatch`
    -- the reset-at-top-of-`handle_command` convention applies to rule
    dispatch exactly as it always did to static tokens."""

    def test_a_later_unrelated_command_clears_the_goal_transition(self) -> None:
        console = _dispatching_console(parked_active=True)
        console.handle_command("turn_heading", now_sim=0.0, slots={"heading_deg": 90})
        assert console.ai_pilot_goal_transition is not None
        console.handle_command("radio_check", now_sim=0.1)
        assert console.ai_pilot_goal_transition is None

    def test_a_later_unrelated_command_clears_the_hvrt_transition(self) -> None:
        console = _dispatching_console(parked_active=True, ai_mode="HVRT")
        console.handle_command("hvrt_translate_left", now_sim=0.0)
        assert console.ai_pilot_hvrt_transition is not None
        console.handle_command("radio_check", now_sim=0.1)
        assert console.ai_pilot_hvrt_transition is None
