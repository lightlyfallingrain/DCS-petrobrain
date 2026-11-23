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

import pytest

from belief.ai_pilot_wheel import (
    AiPilotGoalRequest,
    AiPilotWheelGoal,
    ParkedFlightState,
)
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.flight_authority import PendingFlightReadback
from belief.speech import render_unable
from rules.actions import ACTION_NAMESPACES, ActionContext
from rules.engine import RuleSet, run_rule
from rules.loader import DEFAULT_RULES_DIR
from rules.sandbox import RuleSandbox


def _console(**state_fields: object) -> CrewConsole:
    console = CrewConsole(store=ContactStore())
    console.parked_flight_state = replace(ParkedFlightState(), **state_fields)
    # BL-16 Stage 2 (`plans/flight-desired-state/plan.md`): `flight_
    # mode()`/`current_crew_state()` read `flight_authority_state` now,
    # not `parked_flight_state` -- mirror `parked_active`/`held_*` onto
    # it too, so every existing `parked_active=True` fixture here still
    # reads as "flying through the overlay" to the gate/dispatch path.
    if state_fields.get("parked_active"):
        held_heading = state_fields.get("held_heading")
        console.flight_authority_state = replace(
            console.flight_authority_state,
            fd_mode="m2",
            hdg_mode="heading" if held_heading is not None else None,
            heading_deg=held_heading,  # type: ignore[arg-type]
            alt_m=state_fields.get("held_altitude"),  # type: ignore[arg-type]
            alt_ref=state_fields.get("held_altitude_ref"),  # type: ignore[arg-type]
            ias_kmh=state_fields.get("held_speed"),  # type: ignore[arg-type]
        )
    return console


def _set_mode1_active(
    console: CrewConsole, *, measured_heading: float | None = None
) -> None:
    """Companion to `_console`'s own `parked_active` mapping, for the
    mode-1 call sites below that need `flight_mode()` to read `"axes"` --
    `flight_mode()`/`current_crew_state()` need `flight_authority_
    state.fd_mode == "m1"`; `FlightControlState` carries no mode of its
    own since BL-16 Stage 3."""
    console.flight_authority_state = replace(
        console.flight_authority_state,
        fd_mode="m1",
        hdg_mode="heading" if measured_heading is not None else None,
        heading_deg=measured_heading,
    )


def _dispatching_console(
    *, speech_client: object | None = None, **state_fields: object
) -> CrewConsole:
    """Like `_console`, but wired for the **real** dispatch path
    (`handle_command` -> `_handle_rule`/`drain_pending_rule_dispatch` ->
    the category gate -> `_dispatch_rule` -> the real `run_rule` against
    the real shipped `flight.lua`) -- every Stage 4 gate/differential
    test below goes through this, not a direct `run_rule` call, so the
    category gate is genuinely exercised rather than bypassed.

    `speech_client` (D19/U22's own tests, below) is optional and `None`
    by default -- every pre-existing call site is unaffected."""
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
    if speech_client is not None:
        console.speech_client = speech_client  # type: ignore[assignment]
    return console


class _RecordingSpeechClient:
    """A minimal `push_speech`-only double for D19/U22's own tests below
    -- this file's own copy of `test_crew_console.py`'s
    `FakeSpeechClient`, kept local rather than imported across test
    files (no existing precedent for that in this subproject). Records
    `(text, urgent)` pairs so a test can assert `bypass_gate` reached
    `push_speech`'s `urgent` argument."""

    def __init__(self) -> None:
        self.pushed: list[tuple[str, bool]] = []

    def push_speech(
        self, text: str, urgent: bool, correlation_id: str | None = None
    ) -> None:
        self.pushed.append((text, urgent))

    def stop(self) -> None:
        pass


def test_shipped_rule_files_load_with_zero_failures() -> None:
    """Body-layer's own loader never runs the adapter's collision check
    (D1: that is audio-adapter's job, over `PUT /rules`) -- every one of
    the 23 rules `flight.lua` declares loads cleanly here regardless of
    which ones the real adapter would later reject for a wording
    collision (two, after the 2026-11-17 recalibration -- see
    `plans/speech-rules/implementation.md`'s "Stage 4 follow-ups" section
    for the full account). The four `cbtm_*` rules are BL-16 mode 2
    Stage P3+P4's own addition (`plans/flight-control/plan.md`, "Revised
    2026-11-18 -- Stages P3+P4 ready to build")."""
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
        "cbtm_align",
        "cbtm_align_for_launch",
        "cbtm_break",
        "cbtm_break_away",
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
    # BL-16 Stage 2: `current_crew_state()` reads `flight_authority_
    # state` now, not `parked_flight_state` -- mirror the same settle.
    console.flight_authority_state = replace(
        console.flight_authority_state, hdg_mode="heading", heading_deg=10.0
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

    def test_a_mode_1_command_s_readback_is_also_deferred(self) -> None:
        """BL-16 Stage 3b (section 3a, U1) -- the deferral is not scoped
        to mode 2: a mode-1 `axes_*` command queues `flight_control_
        goal_transition`, which `_flight_control_transition_queued`
        covers, so its own readback stages exactly the same way."""
        console = _dispatching_console(parked_active=False)
        _set_mode1_active(console, measured_heading=10.0)
        lines = console.handle_command(
            "turn_heading", now_sim=0.0, slots={"heading_deg": 315}
        )
        assert lines == ["Heading 3 1 5."]
        assert console.pending_flight_readback_lines == ["Heading 3 1 5."]

    def test_the_not_flying_refusal_is_never_deferred(self) -> None:
        """A local gate refusal never reaches Lua at all -- nothing is
        staged, and `handle_command`'s own immediate `_print` still
        speaks it (`test_an_unable_not_flying_readback_never_cuts_off_
        the_callout` below asserts the speech side of this same case)."""
        console = _dispatching_console(parked_active=False)
        console.handle_command("turn_heading", now_sim=0.0, slots={"heading_deg": 315})
        assert console.pending_flight_readback_lines is None


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
        # BL-16 Stage 2: `current_crew_state()` reads `flight_authority_
        # state` now, not `parked_flight_state` -- mirror the same settle.
        console.flight_authority_state = replace(
            console.flight_authority_state, ias_kmh=120.0
        )
        lines = console.drain_pending_rule_dispatch(now_sim=1.0)
        assert lines == ["Speed 1 5 0."]


class TestSetAltitude:
    """Differential pin against the deleted `TestSetAltitude`. Category
    `"flight_control"` -- no held value needed for the absolute form.

    `slots` below carries no `"verb"` key, matching `[[BL-B129]]` D1:
    `set_altitude`'s own `<verb:alt|altitude>` word-set is now the plain
    literal "altitude", so the real matcher never produces a `"verb"`
    slot for this rule any more (neither handler ever read it before D1
    either, which is why D1 could drop "alt" as a pure pattern edit)."""

    def test_a_reachable_radar_request_is_honoured(self) -> None:
        console = _dispatching_console(parked_active=True, held_altitude_ref="B")
        lines = console.handle_command(
            "set_altitude",
            now_sim=0.0,
            slots={"altitude_m": 300, "reference": "radar"},
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
            slots={"altitude_m": 900, "reference": "radar"},
        )
        assert lines == ["900 meters barometric."]

    def test_no_reference_spoken_keeps_the_current_one(self) -> None:
        console = _dispatching_console(parked_active=True, held_altitude_ref="R")
        lines = console.handle_command(
            "set_altitude", now_sim=0.0, slots={"altitude_m": 300}
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
    `"flight_control_altitude"`.

    `slots={}` below (`[[BL-B129]]` D1): `hold_altitude`'s pattern is
    now a plain two-literal phrase with no slot at all, so the real
    matcher never produces a `"verb"` key for this rule any more."""

    def test_freezes_at_the_held_value_and_reference(self) -> None:
        console = _dispatching_console(
            parked_active=True, held_altitude=300.0, held_altitude_ref="B"
        )
        lines = console.handle_command("hold_altitude", now_sim=0.0, slots={})
        assert lines == ["Holding 300 meters."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="altitude", altitude_m=300.0, altitude_ref="barometric"
        )


class TestLevelOff:
    """Differential pin against the deleted `TestLevelOff`. Category
    `"flight_control_heading"`. The legacy synonym "straight" was dropped
    by the user (2026-11-17, "Drop "straight"") -- its near-miss "right"
    is the HVRT bare word."""

    def test_level_off_holds_the_current_heading(self) -> None:
        console = _dispatching_console(parked_active=True, held_heading=120.0)
        lines = console.handle_command("level_off", now_sim=0.0)
        assert lines == ["Heading 1 2 0."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="heading", heading_deg=120.0
        )

    def test_holds_then_flies_once_held_heading_arrives(self) -> None:
        console = _dispatching_console(parked_active=True, held_heading=None)
        lines = console.handle_command("level_off", now_sim=0.0)
        assert lines == []
        assert console.pending_rule_dispatch is not None


class TestCbtmActions:
    """Review fix (`plans/flight-control/review-p3p4.md` Required Fix
    2): the four `cbtm_*` rules dispatched through the real `handle_
    command` -> gate -> `run_rule` path against the real shipped
    `flight.lua`, mirroring `TestHandoverActions`/`TestSeatNeverGates
    Mode1`'s own shape -- the overlay-mode readback/transition for each
    (category `"flight_control"`, has-controls only, U1: "no refusal
    branch -- CBTM is always reachable by one left press"), plus the
    permanently-gated mode-1 "unable" for align/align-for-launch
    (`_axes_cbtm_align_unready`'s `AI_OVERLAY`, E-P20). Mode-1 batch
    (`plans/flight-control/plan.md`, "Revised 2026-11-19"): `cbtm_
    break`/`cbtm_break_away`'s own mode-1 `NOT_READY` stub is gone --
    they now fly the real mode-1 break (`_axes_break_turn`/`_axes_
    break_away`), covered below. `test_shipped_rule_files_load_with_
    zero_failures` above only confirms the four rule ids exist in the
    loaded set; nothing else in this file previously called `handle_
    command` for any of them."""

    def test_align_speaks_aligning_and_sets_the_cbtm_transition(self) -> None:
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command("cbtm_align", now_sim=0.0)
        assert lines == ["Aligning."]
        assert console.ai_pilot_cbtm_transition == "align"

    def test_align_s_readback_is_not_deferred(self) -> None:
        """BL-16 Stage 3b (section 3a) -- CBTM is not dual-written onto
        the numbered `flight` channel this stage (`implementation.md`'s
        own deviation), so `_flight_control_transition_queued` excludes
        `ai_pilot_cbtm_transition`: the readback above speaks
        immediately, through the ordinary path, exactly as before this
        stage -- nothing is left staged for a `fd_acks` entry that will
        never arrive for it."""
        console = _dispatching_console(parked_active=True)
        console.handle_command("cbtm_align", now_sim=0.0)
        assert console.pending_flight_readback_lines is None

    def test_align_for_launch_speaks_aligning_for_launch(self) -> None:
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command("cbtm_align_for_launch", now_sim=0.0)
        assert lines == ["Aligning for launch."]
        assert console.ai_pilot_cbtm_transition == "align_for_launch"

    def test_break_left_speaks_breaking_left(self) -> None:
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command(
            "cbtm_break", now_sim=0.0, slots={"direction": "left"}
        )
        assert lines == ["Breaking left."]
        assert console.ai_pilot_cbtm_transition == "break_left"

    def test_break_right_speaks_breaking_right(self) -> None:
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command(
            "cbtm_break", now_sim=0.0, slots={"direction": "right"}
        )
        assert lines == ["Breaking right."]
        assert console.ai_pilot_cbtm_transition == "break_right"

    def test_break_away_speaks_breaking_away(self) -> None:
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command("cbtm_break_away", now_sim=0.0)
        assert lines == ["Breaking away."]
        assert console.ai_pilot_cbtm_transition == "break_away"

    def test_not_flying_answers_unable_not_flying_before_any_mode_body_runs(
        self,
    ) -> None:
        """The coarse `"flight_control"` gate (has-controls only) runs
        before `_by_mode` ever picks an `overlay=`/`axes=` body --
        nobody flying answers "unable, not flying," never reaching
        either `cbtm_align`'s no-refusal body or either `_axes_cbtm_*_
        unready` refusal."""
        console = _dispatching_console(parked_active=False)
        lines = console.handle_command("cbtm_align", now_sim=0.0)
        assert lines == ["Unable, not flying."]
        assert console.ai_pilot_cbtm_transition is None

    def test_mode_1_align_is_permanently_unable_ai_overlay(self) -> None:
        """`_axes_cbtm_align_unready` -- E-P20, the user's own answer:
        "align"/"align for launch" are mode-2-only, permanently, since
        the 9K113 is gated behind the CPG view which is gated behind
        mode 2."""
        console = _dispatching_console(parked_active=False)
        _set_mode1_active(console)
        lines = console.handle_command("cbtm_align", now_sim=0.0)
        assert lines == [render_unable("AI_OVERLAY").text]
        assert console.ai_pilot_cbtm_transition is None

    def test_mode_1_align_for_launch_is_also_unable_ai_overlay(self) -> None:
        console = _dispatching_console(parked_active=False)
        _set_mode1_active(console)
        lines = console.handle_command("cbtm_align_for_launch", now_sim=0.0)
        assert lines == [render_unable("AI_OVERLAY").text]
        assert console.ai_pilot_cbtm_transition is None

    def test_mode_1_break_not_ready_without_a_known_heading(self) -> None:
        """`_axes_break_turn`'s own `current is None` -> `NOT_READY`
        guard, not an assert -- reachable because `cbtm_break`'s rule
        category is the plain `"flight_control"` (shared with mode 2's
        own no-refusal body), which needs no held/measured heading at
        all, unlike `increment_heading`'s own `"flight_control_
        heading"`."""
        console = _dispatching_console(parked_active=False)
        _set_mode1_active(console)
        lines = console.handle_command(
            "cbtm_break", now_sim=0.0, slots={"direction": "left"}
        )
        assert lines == [render_unable("NOT_READY").text]
        assert console.flight_control_goal_transition is None

    def test_mode_1_break_away_not_ready_without_a_known_heading(self) -> None:
        console = _dispatching_console(parked_active=False)
        _set_mode1_active(console)
        lines = console.handle_command("cbtm_break_away", now_sim=0.0)
        assert lines == [render_unable("NOT_READY").text]
        assert console.flight_control_goal_transition is None

    def test_mode_1_break_left_flies_the_real_break(self) -> None:
        """Mode-1 batch, Decision 27 -- "break turn left" flies the
        real mode-1 break: current heading - 90, with the rule's own
        `BREAK_TURN_RATE_DEG_S` (`config/rules/flight.lua`, 40) as the
        signed rate override. No `NOT_READY` stub left to answer."""
        console = _dispatching_console(parked_active=False)
        _set_mode1_active(console, measured_heading=100.0)
        lines = console.handle_command(
            "cbtm_break", now_sim=0.0, slots={"direction": "left"}
        )
        assert lines == ["Breaking left."]
        request = console.flight_control_goal_transition
        assert request is not None
        assert request.heading_deg == pytest.approx(10.0)
        assert request.turn_rate_deg_s == pytest.approx(-40.0)

    def test_mode_1_break_right_flies_the_real_break(self) -> None:
        console = _dispatching_console(parked_active=False)
        _set_mode1_active(console, measured_heading=100.0)
        lines = console.handle_command(
            "cbtm_break", now_sim=0.0, slots={"direction": "right"}
        )
        assert lines == ["Breaking right."]
        request = console.flight_control_goal_transition
        assert request is not None
        assert request.heading_deg == pytest.approx(190.0)
        assert request.turn_rate_deg_s == pytest.approx(40.0)

    def test_mode_1_break_away_flies_the_real_break(self) -> None:
        """Always a hard 180 to the left (E13) -- the rate override is
        negative regardless of a "direction" slot, there is none."""
        console = _dispatching_console(parked_active=False)
        _set_mode1_active(console, measured_heading=100.0)
        lines = console.handle_command("cbtm_break_away", now_sim=0.0)
        assert lines == ["Breaking away."]
        request = console.flight_control_goal_transition
        assert request is not None
        assert request.heading_deg == pytest.approx(280.0)
        assert request.turn_rate_deg_s == pytest.approx(-40.0)


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

    def test_the_readback_is_not_deferred(self) -> None:
        """BL-16 Stage 3b (section 3a) -- same exclusion as CBTM's own:
        HVRT is not dual-written onto the numbered `flight` channel this
        stage, so nothing is staged for an ack that will never come."""
        console = _dispatching_console(parked_active=True, ai_mode="HVR")
        console.handle_command("hvrt_translate_left", now_sim=0.0)
        assert console.pending_flight_readback_lines is None

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


class TestHandoverActions:
    """BL-16 mode 1 Decision 22 (`plans/flight-control/plan.md`,
    "Revised 2026-11-18") -- replaces the old `TestHaveControlsNoOp`:
    "you/i have controls" now really hand the controls over on the
    axes, category `"flight_handover"`. The *readback* text ("I have
    controls."/"You have controls.") is deferred for both a successful
    take and a successful release (spoken only once `Export.lua`
    confirms, via `drain_flight_control` -- neither rule body calls
    `say()` at all, debug-2026-11-23 problem 1), so `handle_command`'s
    own immediate return stays `[]` even when either acts; the
    belief-state side effect is immediate and asserted here instead.

    `_dispatching_console`'s `**state_fields` only ever sets `Parked
    FlightState` fields (its own docstring) -- `on_ground`/`ias_kmh`/
    `attack_run_engaged`/`flight_control_state` are set directly on the
    returned console in the tests below that need them."""

    def test_you_have_controls_is_silent_while_overlay_flying(self) -> None:
        """The 2026-11-17 no-op: Petrovich already has the controls
        through the AI overlay, so nothing happens and nothing is
        said -- `acted=False`, not a refusal."""
        console = _dispatching_console(parked_active=True)
        lines = console.handle_command("you_have_controls", now_sim=0.0)
        assert lines == []
        assert console.flight_control_transition is None

    def test_you_have_controls_takes_when_clear_to_fly(self) -> None:
        console = _dispatching_console(parked_active=False)
        console.on_ground = False
        console.ias_kmh = 150.0
        console.attack_run_engaged = False
        lines = console.handle_command("you_have_controls", now_sim=0.0)
        assert lines == []
        assert console.flight_control_transition == "take"
        assert console.pending_take_says == "I have controls."

    def test_you_have_controls_refuses_on_the_ground(self) -> None:
        console = _dispatching_console(parked_active=False)
        console.on_ground = True
        console.ias_kmh = 150.0
        lines = console.handle_command("you_have_controls", now_sim=0.0)
        assert lines == [render_unable("ON_GROUND").text]
        assert console.flight_control_transition is None

    def test_you_have_controls_refuses_too_slow(self) -> None:
        console = _dispatching_console(parked_active=False)
        console.on_ground = False
        console.ias_kmh = 10.0
        lines = console.handle_command("you_have_controls", now_sim=0.0)
        assert lines == [render_unable("TOO_SLOW").text]

    def test_i_have_controls_is_unable_while_overlay_flying(self) -> None:
        """U9, answered 2026-11-18: "unable", not remembered -- the
        player's escape is to unpark, then say it again."""
        console = _dispatching_console(parked_active=True, held_heading=10.0)
        lines = console.handle_command("i_have_controls", now_sim=0.0)
        assert lines == [render_unable("AI_OVERLAY").text]

    def test_i_have_controls_releases_while_flying_on_the_axes(self) -> None:
        """Debug-2026-11-23, problem 1 -- the readback is deferred the
        same way `you_have_controls`'s "I have controls." is: nothing
        is spoken until `Export.lua` acks the release."""
        console = _dispatching_console(parked_active=False)
        _set_mode1_active(console)
        lines = console.handle_command("i_have_controls", now_sim=0.0)
        assert lines == []
        assert console.flight_control_transition == "release"
        assert console.pending_release_says == "You have controls."

    def test_i_have_controls_is_a_silent_no_op_with_nobody_flying(self) -> None:
        """The player already has the controls -- `acted=False`, same
        silent shape as the overlay no-op above, not a refusal."""
        console = _dispatching_console(parked_active=False)
        lines = console.handle_command("i_have_controls", now_sim=0.0)
        assert lines == []
        assert console.flight_control_transition is None


class TestSeatNeverGatesMode1:
    """BL-16 mode 1 Decision 25 -- "mode 1 is never gated on seat":
    `flight_mode()`/`take_controls`'s own result must be identical
    whether `player_seat` reads `"pilot"`, `"operator"`, or `None`
    (unknown) -- both read `parked_active`/`on_ground`/`ias_kmh`/
    `attack_run_engaged` only."""

    @pytest.mark.parametrize("seat", ["pilot", "operator", None])
    def test_flight_mode_is_the_same_whichever_seat(self, seat: str | None) -> None:
        flying_console = _dispatching_console(parked_active=False, player_seat=seat)
        _set_mode1_active(flying_console)
        assert flying_console.flight_mode() == "axes"

        overlay_console = _dispatching_console(parked_active=True, player_seat=seat)
        assert overlay_console.flight_mode() == "overlay"

        nobody_console = _dispatching_console(parked_active=False, player_seat=seat)
        assert nobody_console.flight_mode() is None

    @pytest.mark.parametrize("seat", ["pilot", "operator", None])
    def test_take_controls_succeeds_the_same_whichever_seat(
        self, seat: str | None
    ) -> None:
        console = _dispatching_console(parked_active=False, player_seat=seat)
        console.on_ground = False
        console.ias_kmh = 150.0
        console.attack_run_engaged = False
        lines = console.handle_command("you_have_controls", now_sim=0.0)
        assert lines == []
        assert console.flight_control_transition == "take"


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


class TestFlightReadbackUrgency:
    """`[[BL-17]]` D19/U22 -- a flight-category rule's own readback may
    cut off an in-flight routine callout (`CalloutScheduler.note_urgent`,
    reused rather than a new mechanism), scoped to flight-category rules
    while he actually has controls. `busy_until_sim` is pre-set to a
    value far in the future to stand in for "a routine callout believed
    still playing": `note_urgent` *resets* it down (the cutoff);
    `note_reply` only ever *extends* it (`max`), so a dispatch that must
    stay on the ordinary path leaves the pre-set value exactly as high,
    never lower -- the negative-space half of each test below, proving
    the mechanism can tell the two paths apart rather than merely not
    crashing."""

    _FAR_FUTURE_BUSY_UNTIL = 1000.0

    def test_a_flight_rule_readback_cuts_off_the_callout_while_flying(self) -> None:
        """BL-16 Stage 3b (section 3a, U1) -- the dispatch itself no
        longer speaks the readback (it queued a numbered-channel
        transition, so `handle_command` stages the line rather than
        printing it); the cutoff only happens once the staged line is
        actually spoken, on the later poll `fd_acks` accepts it
        (`drain_flight_control`'s own `has_controls`-gated bypass,
        D19/U22 unchanged by the deferral)."""
        speech_client = _RecordingSpeechClient()
        console = _dispatching_console(
            speech_client=speech_client, parked_active=True, held_heading=10.0
        )
        console.scheduler.busy_until_sim = self._FAR_FUTURE_BUSY_UNTIL
        console.handle_command(
            "turn_heading_relative",
            now_sim=0.0,
            slots={"direction": "left", "degrees": 20},
        )
        assert speech_client.pushed == []
        assert console.pending_flight_readback_lines == ["20 left."]
        assert console.scheduler.busy_until_sim == self._FAR_FUTURE_BUSY_UNTIL
        # `body.py`'s own wire-send claims the staged line and queues it
        # against the `seq` it just minted -- simulated here directly,
        # since this file dispatches through the real rule engine but
        # not through `body.py`'s poll loop.
        readback_lines = console.take_pending_flight_readback_lines()
        assert readback_lines is not None
        console.pending_flight_readbacks.append(
            PendingFlightReadback(seq=1, lines=tuple(readback_lines), sent_at_sim=0.0)
        )
        console.flight_authority_state = replace(
            console.flight_authority_state, acks="1:a:m2"
        )
        console.drain_flight_control(now_sim=1.0)
        assert speech_client.pushed == [("20 left.", True)]
        assert console.scheduler.busy_until_sim < self._FAR_FUTURE_BUSY_UNTIL

    def test_a_static_command_readback_never_cuts_off_the_callout(self) -> None:
        """Counterfactual: `radio_check` is not a rule at all, so it must
        keep the pre-existing `note_reply`/`max()` behaviour -- the
        pre-set busy time is never lowered."""
        speech_client = _RecordingSpeechClient()
        console = _dispatching_console(speech_client=speech_client, parked_active=True)
        console.scheduler.busy_until_sim = self._FAR_FUTURE_BUSY_UNTIL
        console.handle_command("radio_check", now_sim=0.0)
        assert speech_client.pushed[0][1] is False
        assert console.scheduler.busy_until_sim >= self._FAR_FUTURE_BUSY_UNTIL

    def test_the_always_category_have_controls_rule_never_cuts_off_the_callout(
        self,
    ) -> None:
        """`you_have_controls`/`i_have_controls` are rule ids too, but
        category `"always"` -- excluded by the `.startswith("flight_
        control")` check, not by an accident of dispatch order."""
        speech_client = _RecordingSpeechClient()
        console = _dispatching_console(speech_client=speech_client, parked_active=True)
        console.scheduler.busy_until_sim = self._FAR_FUTURE_BUSY_UNTIL
        lines = console.handle_command("you_have_controls", now_sim=0.0)
        # Q7's own no-op: the handler speaks nothing, so there is no push
        # to inspect -- the scheduler's own budget, untouched either way,
        # is the only observable here.
        assert lines == []
        assert speech_client.pushed == []
        assert console.scheduler.busy_until_sim >= self._FAR_FUTURE_BUSY_UNTIL

    def test_an_unable_not_flying_readback_never_cuts_off_the_callout(self) -> None:
        """A flight-category rule dispatched while he does *not* have
        controls answers `UNABLE` -- still excluded, since the scoping
        is "while `has_controls`," not "any flight-category rule.\""""
        speech_client = _RecordingSpeechClient()
        console = _dispatching_console(speech_client=speech_client, parked_active=False)
        console.scheduler.busy_until_sim = self._FAR_FUTURE_BUSY_UNTIL
        lines = console.handle_command(
            "turn_heading_relative",
            now_sim=0.0,
            slots={"direction": "left", "degrees": 20},
        )
        assert lines == ["Unable, not flying."]
        assert speech_client.pushed == [("Unable, not flying.", False)]
        assert console.scheduler.busy_until_sim >= self._FAR_FUTURE_BUSY_UNTIL

    def test_a_held_timeout_unable_readback_cuts_off_the_callout(self) -> None:
        """`drain_pending_rule_dispatch`'s own hold-timeout-elapsed
        "unable" line gets the same scoping as the immediate dispatch
        path -- `has_controls` was true throughout the hold (the gate
        never holds otherwise, `rules.gates._require_controls`'s own
        docstring), so this counts as "while flying" too."""
        speech_client = _RecordingSpeechClient()
        console = _dispatching_console(
            speech_client=speech_client, parked_active=True, held_heading=None
        )
        console.handle_command(
            "turn_heading_relative",
            now_sim=0.0,
            slots={"direction": "left", "degrees": 20},
        )
        assert console.pending_rule_dispatch is not None
        speech_client.pushed.clear()
        console.scheduler.busy_until_sim = self._FAR_FUTURE_BUSY_UNTIL
        lines = console.drain_pending_rule_dispatch(now_sim=100.0)
        assert lines == ["Unable, not ready."]
        assert speech_client.pushed == [("Unable, not ready.", True)]
        assert console.scheduler.busy_until_sim < self._FAR_FUTURE_BUSY_UNTIL
