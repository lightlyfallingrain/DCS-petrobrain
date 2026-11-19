"""BL-16 mode 1, Stage M2 (the controller) -- the toy-plant suite the
plan asks for (`plans/flight-control/plan.md`, "Offline tests run
under luajit against a deliberately crude toy plant"), against
`Petrobrain/flight_control.lua`'s own `law_init_at_take`/`law_apply_
goal`/`law_update`/`law_outputs` -- five pure functions over an
explicit state table, with no DCS global and no module-level local in
sight (the module exports them for exactly this: "the law above, as
pure functions over a state table so luajit can test them").

**Technique**: unlike `test_flight_control_lua.py`'s whole-module IIFE
(needed there because `handle_flight_control_command`/`run_flight_
control` close over the module's own flat `fc_*` locals), the five law
functions take every input as an explicit parameter, so this file loads
the *whole file* too (simplest, always-correct way to get a consistent
chunk) but never has to mock a single DCS global -- none of the law
functions ever calls one.

**The toy plant** is a point mass with first-order attitude lags, per
the plan's own wording, one scenario per channel: bank/roll-rate first-
order toward `phi_d` with heading integrating the resulting coordinated
turn rate (`law_turn_rate_at_bank`, the same helper the law itself
uses); vertical speed driven by collective deflection from a trim
value; forward acceleration driven by pitch deflection from trim. The
plant's own gains are picked to produce a plausible, stable closed
loop -- they are not a measurement and are not shared with the law's
own placeholder gains (`plans/flight-control/plan.md`: "the toy plant
proves the shaper and the wiring. The flights tune.")."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_FLIGHT_CONTROL_LUA = (
    Path(__file__).resolve().parent.parent
    / "dcs-export"
    / "Petrobrain"
    / "flight_control.lua"
)

_EXEC_TOOLS: tuple[str, ...] = ("luajit", "lua5.5", "lua5.1", "lua")


def _lua_executable() -> str | None:
    for tool in _EXEC_TOOLS:
        found = shutil.which(tool)
        if found is not None:
            return found
    return None


#: The default `limits` table every scenario starts from -- the same
#: field names `flight_control_limits()` (body-layer) sends on the
#: wire, with values picked only to exercise the law, not to match any
#: tuned default.
#: **No `max_bank_deg` entry** (mode-1 batch, F-M1: "remove the 30
#: degree limit") -- the field is gone from the wire entirely, not
#: widened. The five mode-1 batch additions (`rotor_rpm_floor_pct`/
#: `retreating_blade_stall_ias_kmh`/`break_max_height_loss_m`/
#: `vrs_ias_threshold_kmh`/`vrs_max_descent_mps`) are picked generous
#: enough that no pre-existing scenario below trips a guard it is not
#: testing.
#: `floor_agl_m` is new to `law_update` this batch too (Decision 29's
#: break floor) -- previously sent on the wire but never read inside
#: the law itself.
_LIMITS = """
local LIMITS = {
    takeover_level_bank_deg = 5.0,
    max_turn_bank_deg = 20.0,
    max_climb_vs_mps = 5.0,
    max_accel_mps2 = 1.0,
    heading_band_deg = 5.0,
    alt_band_frac = 0.10,
    alt_band_min_m = 10.0,
    speed_band_frac = 0.10,
    turn_rate_band_frac = 0.10,
    floor_agl_m = 40.0,
    rotor_rpm_floor_pct = 85.0,
    retreating_blade_stall_ias_kmh = 250.0,
    break_max_height_loss_m = 100.0,
    vrs_ias_threshold_kmh = 50.0,
    vrs_max_descent_mps = 4.0,
}
"""


def _run(driver: str) -> list[str]:
    """Loads the whole module (no mocks -- the law functions touch no
    DCS global) and runs `driver`, returning stdout split into
    non-empty lines. Skips cleanly without a Lua interpreter on
    `PATH`."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    module_source = _FLIGHT_CONTROL_LUA.read_text(encoding="utf-8")
    script = (
        "local flight_control = (function()\n"
        + module_source
        + "\nend)()\n"
        + _LIMITS
        + "\n"
        + driver
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".lua", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(script)
        script_path = handle.name
    try:
        result = subprocess.run(
            [exe, script_path], capture_output=True, text=True, check=False
        )
    finally:
        Path(script_path).unlink(missing_ok=True)

    assert result.returncode == 0, f"Lua harness failed (exe={exe}): {result.stderr}"
    return [line for line in result.stdout.splitlines() if line != ""]


def _measured(**overrides: float) -> str:
    base = {
        "pitch_deg": 0.0,
        "bank_deg": 0.0,
        "psi_deg": 0.0,
        "ias_mps": 40.0,
        "v_t_mps": 42.0,
        "w_mps": 0.0,
        "h_m": 200.0,
        "asl_m": 200.0,
        "p_deg_s": 0.0,
        "q_deg_s": 0.0,
        "r_deg_s": 0.0,
        # Mode-1 batch -- well clear of `LIMITS.rotor_rpm_floor_pct`
        # (85.0) by default, so no pre-existing scenario trips the
        # rotor-RPM guard it is not testing.
        "rotor_rpm_pct": 100.0,
    }
    base.update(overrides)
    fields = ", ".join(f"{k} = {v}" for k, v in base.items())
    return "{ " + fields + " }"


class TestBitExactAtTake:
    def test_output_equals_the_captured_command_with_nonzero_body_rates(self) -> None:
        """Decision 24: "the output is continuous at take, bit-exact".
        `T_p`/`T_r` are solved against the *measured* body rates at
        take (`command.pitch + K_Q*q`, `command.roll + K_P*p`), so this
        must hold even when `p`/`q` are nonzero at the instant of
        capture -- the degenerate all-zero case the full-module harness
        already exercises would not catch a sign error in that solve."""
        driver = f"""
local measured = {_measured(pitch_deg=2.0, bank_deg=-3.0, q_deg_s=1.5, p_deg_s=-0.8)}
local command = {{ pitch = 0.321, roll = -0.154, pedals = 0.05, collective = 0.2 }}
local state = flight_control.law_init_at_take(measured, LIMITS, command)
local outputs = flight_control.law_outputs(state, measured)
print(string.format("%.9f", outputs.pitch))
print(string.format("%.9f", outputs.roll))
print(string.format("%.9f", outputs.pedals))
print(string.format("%.9f", outputs.collective))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - 0.321) < 1e-6
        assert abs(float(lines[1]) - (-0.154)) < 1e-6
        assert abs(float(lines[2]) - 0.05) < 1e-6
        assert abs(float(lines[3]) - 0.2) < 1e-6

    def test_disabled_collective_defaults_to_zero_not_a_captured_value(self) -> None:
        """`axis_command` on an axis absent from the captured set
        (today's disabled collective) returns `0.0`, never `nil` --
        `law_init_at_take` needs a number for every axis even though
        nothing will ever be written for it."""
        driver = f"""
local measured = {_measured()}
local command = {{ pitch = 0.0, roll = 0.0, pedals = 0.0, collective = 0.0 }}
local state = flight_control.law_init_at_take(measured, LIMITS, command)
print(state.u_c)
"""
        lines = _run(driver)
        assert float(lines[0]) == 0.0


class TestTakeoverModeSelection:
    def test_4_9_degrees_picks_heading_mode(self) -> None:
        driver = f"""
local measured = {_measured(bank_deg=4.9)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0 }})
print(tostring(state.turn_mode))
"""
        lines = _run(driver)
        assert lines[0] == "false"

    def test_5_1_degrees_picks_turn_mode(self) -> None:
        driver = f"""
local measured = {_measured(bank_deg=5.1)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0 }})
print(tostring(state.turn_mode))
"""
        lines = _run(driver)
        assert lines[0] == "true"


#: Shared toy-plant driver body for the heading channel: bank is a
#: first-order lag toward `phi_d` (`tau` s), heading integrates the
#: coordinated-turn rate at the current bank (`law_turn_rate_at_bank`,
#: the law's own helper -- reused so the plant's kinematics are at
#: least internally consistent with what the law assumes a turn does).
_HEADING_PLANT_DRIVER = """
local measured = {measured}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
state = flight_control.law_apply_goal(state, {{ heading_deg = {goal} }}, LIMITS)
local dt = 0.05
local tau = 1.0
local errs = {{}}
local signs = {{}}
for i = 1, {steps} do
    state = flight_control.law_update(state, dt, measured, LIMITS)
    local outputs = flight_control.law_outputs(state, measured)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    measured.p_deg_s = (state.phi_d - measured.bank_deg) / tau
    local r = flight_control.law_turn_rate_at_bank(measured.bank_deg, measured.v_t_mps)
    measured.psi_deg = (measured.psi_deg + r * dt) % 360.0
    measured.r_deg_s = r
    local err = ((measured.psi_deg - {goal} + 540) % 360) - 180
    errs[i] = err
    if err > 0 then signs[i] = 1 elseif err < 0 then signs[i] = -1 else signs[i] = 0 end
end
print(string.format("%.6f", errs[#errs]))
print(tostring(state.in_band_heading))
-- zero-crossing count: a sign flip between consecutive nonzero samples
local crossings = 0
local last_sign = 0
for i = 1, #signs do
    if signs[i] ~= 0 then
        if last_sign ~= 0 and signs[i] ~= last_sign then crossings = crossings + 1 end
        last_sign = signs[i]
    end
end
print(crossings)
-- mean |error| over the first and last 10% of the run.
local window = math.floor(#errs * 0.1)
local first_sum, last_sum = 0.0, 0.0
for i = 1, window do first_sum = first_sum + math.abs(errs[i]) end
for i = #errs - window + 1, #errs do last_sum = last_sum + math.abs(errs[i]) end
print(string.format("%.6f", first_sum / window))
print(string.format("%.6f", last_sum / window))
"""


class TestHeadingChannel:
    def test_converges_into_band_mean_error_drops_and_turns_once(self) -> None:
        driver = _HEADING_PLANT_DRIVER.format(
            measured=_measured(psi_deg=0.0), goal=90.0, steps=2000
        )
        lines = _run(driver)
        final_err, in_band, crossings, first_mean, last_mean = lines
        assert abs(float(final_err)) <= 5.0  # within HEADING_BAND_DEG
        assert in_band == "true"
        # One roll-in, one settle -- never a reversal in direction of
        # travel once past the goal (ringing would show as >=2).
        assert int(crossings) <= 1
        assert float(last_mean) < float(first_mean)


#: Mode-1 batch, Decision 27 -- a break is the same heading channel,
#: with `turn_rate_deg_s` carried on the goal. Same bank-lag toy plant
#: as `_HEADING_PLANT_DRIVER`, tracking the peak bank reached as well
#: as the final settle, since the thing this batch changes is how
#: steep the bank gets, not just whether the heading converges.
_BREAK_PLANT_DRIVER = """
local measured = {measured}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
state = flight_control.law_apply_goal(
    state, {{ heading_deg = {goal}, turn_rate_deg_s = {rate} }}, LIMITS)
local dt = 0.05
local tau = 1.0
local max_bank = 0.0
for i = 1, {steps} do
    state = flight_control.law_update(state, dt, measured, LIMITS)
    local outputs = flight_control.law_outputs(state, measured)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    measured.p_deg_s = (state.phi_d - measured.bank_deg) / tau
    if math.abs(measured.bank_deg) > max_bank then max_bank = math.abs(measured.bank_deg) end
    local r = flight_control.law_turn_rate_at_bank(measured.bank_deg, measured.v_t_mps)
    measured.psi_deg = (measured.psi_deg + r * dt) % 360.0
    measured.r_deg_s = r
end
print(string.format("%.6f", max_bank))
print(tostring(state.in_band_heading))
print(tostring(state.rate_override_deg_s))
"""


class TestBreakTurnChannel:
    """Mode-1 batch, Decision 27 -- "no new state machine, a break is a
    heading goal flown at a steeper bank." Steep bank (60-80 deg) is
    the kinematic *consequence* of a fast rate at cruise speed, per the
    plan's own hand-derived worked example ("150 km/h, 40 deg/s -> ~71
    deg; 220 km/h, 40 deg/s -> ~76 deg").

    **Measured finding, not asserted as a bound here**: running this
    exact mechanism through the toy plant does not reach that 60-80 deg
    window -- 150 km/h settles around ~43 deg of bank, 220 km/h around
    ~54 deg (both measured against this suite's run). The plan's own
    hand-derivation assumes the commanded rate (`turn_rate_deg_s`, 40)
    is actually reached; it is not, here, because the heading-mode
    shaper's `OMEGA_HEADING` (0.3, an explicitly unmeasured placeholder)
    critically damps the rate well below that ceiling for a 90 deg
    error (a 2nd-order critically-damped step response peaks near
    `E*omega/e`, independent of `rate_limit` once `rate_limit` exceeds
    that natural peak) -- the override *raises the ceiling*, but
    nothing in this mechanism drives the rate up *to* it for an error
    this size. The bank reached is still well past the ordinary 20 deg
    turn-bank ceiling (`max_turn_bank_deg`), and part of the margin
    above the pure-kinematic rate prediction comes from `phi_i`'s own
    unclamped growth (the plan's own named Risk: "Integrator windup in
    `phi_i`... deliberately not fixed this batch"). So: these tests
    assert the qualitative properties Decision 27 promises (steeper
    than an ordinary turn, converges, settling clears the override),
    not the plan's specific 60-80 deg figure -- flagged for Flight M-A's
    retune, same as every other placeholder gain in this module."""

    def test_150_kmh_break_is_much_steeper_than_an_ordinary_turn_and_settles(
        self,
    ) -> None:
        driver = _BREAK_PLANT_DRIVER.format(
            measured=_measured(psi_deg=0.0, ias_mps=150.0 / 3.6, v_t_mps=150.0 / 3.6),
            goal=90.0,
            rate=40.0,
            steps=2000,
        )
        lines = _run(driver)
        max_bank, in_band, rate_override = lines
        # Well past the ordinary 20 deg turn-bank ceiling (LIMITS'
        # max_turn_bank_deg) -- "steep bank in any case."
        assert float(max_bank) > 35.0
        assert in_band == "true"
        # Settling clears the override (Decision 27's own "settling
        # clears it") -- by the time the break is in band, it is `nil`.
        assert rate_override == "nil"

    def test_220_kmh_break_is_steeper_than_150_kmh(self) -> None:
        """Higher cruise IAS -> more bank for the same commanded rate
        (`atan(V_t*r/g)` grows with `V_t`) -- the one directional claim
        the toy plant can confirm without pinning an exact figure."""
        driver_150 = _BREAK_PLANT_DRIVER.format(
            measured=_measured(psi_deg=0.0, ias_mps=150.0 / 3.6, v_t_mps=150.0 / 3.6),
            goal=90.0,
            rate=40.0,
            steps=2000,
        )
        driver_220 = _BREAK_PLANT_DRIVER.format(
            measured=_measured(psi_deg=0.0, ias_mps=220.0 / 3.6, v_t_mps=220.0 / 3.6),
            goal=90.0,
            rate=40.0,
            steps=2000,
        )
        max_bank_150 = float(_run(driver_150)[0])
        max_bank_220 = float(_run(driver_220)[0])
        assert max_bank_220 > max_bank_150

    def test_break_right_is_the_mirror_of_break_left(self) -> None:
        """A negative rate (break left, sign convention from `crew_
        console.axes_break_turn`) reaches the same peak bank magnitude
        as a positive one (break right), just the opposite heading
        direction."""
        left = _run(
            _BREAK_PLANT_DRIVER.format(
                measured=_measured(
                    psi_deg=90.0, ias_mps=150.0 / 3.6, v_t_mps=150.0 / 3.6
                ),
                goal=0.0,
                rate=-40.0,
                steps=2000,
            )
        )
        right = _run(
            _BREAK_PLANT_DRIVER.format(
                measured=_measured(
                    psi_deg=0.0, ias_mps=150.0 / 3.6, v_t_mps=150.0 / 3.6
                ),
                goal=90.0,
                rate=40.0,
                steps=2000,
            )
        )
        assert abs(float(left[0]) - float(right[0])) < 1.0


class TestRateOverrideClearing:
    """Mode-1 batch, Decision 27's own Co-moving Fields B1/B2/B3 --
    `rate_override_deg_s`/`break_entry_h_m` are set only on a heading
    goal that carries `turn_rate_deg_s`, and cleared by an ordinary
    heading/turn goal (B2) as well as by settling (B3, exercised above
    by `TestBreakTurnChannel`)."""

    def test_heading_goal_with_a_rate_sets_both_fields(self) -> None:
        driver = f"""
local measured = {_measured(h_m=300.0)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
state = flight_control.law_apply_goal(
    state, {{ heading_deg = 90.0, turn_rate_deg_s = -40.0 }}, LIMITS)
print(state.rate_override_deg_s)
print(state.break_entry_h_m)
"""
        lines = _run(driver)
        assert float(lines[0]) == -40.0
        assert float(lines[1]) == 300.0

    def test_an_ordinary_heading_goal_clears_a_standing_override(self) -> None:
        """F-M2: "a rate belongs to the command that set it" -- a plain
        `set_heading`/`increment_heading` (no `turn_rate_deg_s`) clears
        whatever override an earlier break left standing."""
        driver = f"""
local measured = {_measured(h_m=300.0)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
state = flight_control.law_apply_goal(
    state, {{ heading_deg = 90.0, turn_rate_deg_s = -40.0 }}, LIMITS)
state = flight_control.law_apply_goal(state, {{ heading_deg = 180.0 }}, LIMITS)
print(tostring(state.rate_override_deg_s))
print(tostring(state.break_entry_h_m))
"""
        lines = _run(driver)
        assert lines[0] == "nil"
        assert lines[1] == "nil"

    def test_a_continuous_turn_goal_also_clears_a_standing_override(self) -> None:
        driver = f"""
local measured = {_measured(h_m=300.0)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
state = flight_control.law_apply_goal(
    state, {{ heading_deg = 90.0, turn_rate_deg_s = -40.0 }}, LIMITS)
state = flight_control.law_apply_goal(state, {{ turn = 1 }}, LIMITS)
print(tostring(state.rate_override_deg_s))
print(tostring(state.break_entry_h_m))
"""
        lines = _run(driver)
        assert lines[0] == "nil"
        assert lines[1] == "nil"


class TestBreakHeightFloor:
    """Mode-1 batch, Decision 29 -- while a break's rate override is
    active, the shaper's effective altitude target is floored at
    `max(floor_agl_m, entry_h - break_max_height_loss_m)`; the stored
    `alt_goal_m` itself is never moved (a break never writes it)."""

    def test_h_ref_never_chases_below_the_break_floor_while_the_override_is_set(
        self,
    ) -> None:
        driver = """
local measured = {measured}
local state = flight_control.law_init_at_take(measured, LIMITS,
    { pitch = 0, roll = 0, pedals = 0, collective = 0.2 })
-- Force a far-below floor so the shaper would chase it if the break
-- floor did not intervene.
state.alt_goal_m = 0.0
state = flight_control.law_apply_goal(
    state, { heading_deg = 90.0, turn_rate_deg_s = 40.0 }, LIMITS)
local dt = 0.05
local min_h_ref = state.h_ref
for i = 1, 400 do
    state = flight_control.law_update(state, dt, measured, LIMITS)
    if state.h_ref < min_h_ref then min_h_ref = state.h_ref end
end
print(string.format("%.6f", min_h_ref))
print(string.format("%.6f", state.alt_goal_m))
""".replace("{measured}", _measured(h_m=300.0))
        lines = _run(driver)
        min_h_ref, alt_goal_m = lines
        # floor = max(floor_agl_m, entry_h - break_max_height_loss_m)
        # = max(0.0, 300 - 100) = 200.0 (LIMITS' own defaults above).
        assert float(min_h_ref) >= 200.0 - 1e-6
        # The break never rewrote the stored goal itself.
        assert float(alt_goal_m) == 0.0

    def test_chases_the_real_goal_again_once_the_break_settles(self) -> None:
        """Once the break settles (B3's own clearing), the floor stops
        applying and `h_ref` is free to continue toward `alt_goal_m`."""
        driver = """
local measured = {measured}
local state = flight_control.law_init_at_take(measured, LIMITS,
    { pitch = 0, roll = 0, pedals = 0, collective = 0.2 })
state.alt_goal_m = 0.0
state = flight_control.law_apply_goal(
    state, { heading_deg = 90.0, turn_rate_deg_s = 40.0 }, LIMITS)
local dt = 0.05
local tau = 1.0
for i = 1, 3000 do
    state = flight_control.law_update(state, dt, measured, LIMITS)
    local outputs = flight_control.law_outputs(state, measured)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    measured.p_deg_s = (state.phi_d - measured.bank_deg) / tau
    local r = flight_control.law_turn_rate_at_bank(measured.bank_deg, measured.v_t_mps)
    measured.psi_deg = (measured.psi_deg + r * dt) % 360.0
    measured.r_deg_s = r
end
print(tostring(state.rate_override_deg_s))
print(string.format("%.6f", state.h_ref))
""".replace("{measured}", _measured(h_m=300.0, psi_deg=0.0))
        lines = _run(driver)
        rate_override, final_h_ref = lines
        assert rate_override == "nil"
        # Free to chase the real (0.0) goal again, well below the
        # break floor (200.0) that applied while it was active.
        assert float(final_h_ref) < 200.0


class TestRotorEnvelopeGuards:
    """Mode-1 batch, Decision 30 -- the rotor-RPM floor and the
    retreating-blade-stall margin both widen the existing "collective
    is limited" flag reactively: only a further *increase* in
    collective is ever capped, a decrease is untouched."""

    def test_low_rotor_rpm_caps_a_rising_collective(self) -> None:
        driver = f"""
local measured = {_measured(h_m=100.0, w_mps=-5.0, rotor_rpm_pct=88.0)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
-- A big positive altitude error asks for a large rising c_dot.
state.alt_goal_m = 1000.0
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS)
print(string.format("%.6f", (next_state.u_c - state.u_c) / 0.05))
"""
        lines = _run(driver)
        # COLLECTIVE_RATE_CAP_NEAR_RPM_FLOOR = 0.0 -- a rising c_dot is
        # capped to zero (no further increase) once within 5 pct of
        # ROTOR_RPM_FLOOR_PCT (85.0), i.e. at or below 90.0.
        assert float(lines[0]) <= 1e-9

    def test_a_falling_collective_is_untouched_by_the_rpm_floor(self) -> None:
        driver = f"""
local measured = {_measured(h_m=1000.0, w_mps=5.0, rotor_rpm_pct=88.0)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
state.alt_goal_m = 0.0
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS)
print(string.format("%.6f", (next_state.u_c - state.u_c) / 0.05))
"""
        lines = _run(driver)
        assert float(lines[0]) < -1e-9

    def test_near_retreating_blade_stall_caps_a_rising_collective(self) -> None:
        driver = f"""
local measured = {_measured(h_m=100.0, w_mps=-5.0, ias_mps=235.0 / 3.6, v_t_mps=235.0 / 3.6)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
state.alt_goal_m = 1000.0
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS)
print(string.format("%.6f", (next_state.u_c - state.u_c) / 0.05))
"""
        lines = _run(driver)
        # RETREATING_BLADE_STALL_MARGIN_KMH = 20.0 -- capped at or
        # above 250.0 - 20.0 = 230.0 km/h; 235 km/h qualifies.
        assert float(lines[0]) <= 1e-9

    def test_well_clear_of_both_guards_collective_rises_freely(self) -> None:
        driver = f"""
local measured = {_measured(h_m=100.0, w_mps=-5.0)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
state.alt_goal_m = 1000.0
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS)
print(string.format("%.6f", (next_state.u_c - state.u_c) / 0.05))
"""
        lines = _run(driver)
        assert float(lines[0]) > 1e-9


class TestVrsDescentCap:
    """Mode-1 batch, Decision 31 -- below `VRS_IAS_THRESHOLD_KMH`
    (50.0), the descent-rate reference is capped at `VRS_MAX_DESCENT_
    MPS` (4.0), regardless of how large the altitude error driving it
    is, in every mode-1 state."""

    def test_slow_flight_descent_never_exceeds_the_vrs_cap(self) -> None:
        driver = """
local measured = {measured}
local state = flight_control.law_init_at_take(measured, LIMITS,
    { pitch = 0, roll = 0, pedals = 0, collective = 0.2 })
state.alt_goal_m = -10000.0
local dt = 0.05
local min_w_ref = 0.0
for i = 1, 400 do
    state = flight_control.law_update(state, dt, measured, LIMITS)
    if state.w_ref < min_w_ref then min_w_ref = state.w_ref end
end
print(string.format("%.6f", min_w_ref))
""".replace("{measured}", _measured(h_m=500.0, ias_mps=30.0 / 3.6, v_t_mps=30.0 / 3.6))
        lines = _run(driver)
        assert float(lines[0]) >= -4.0 - 1e-6

    def test_cruise_speed_descent_is_not_capped_by_vrs(self) -> None:
        driver = """
local measured = {measured}
local state = flight_control.law_init_at_take(measured, LIMITS,
    { pitch = 0, roll = 0, pedals = 0, collective = 0.2 })
state.alt_goal_m = -10000.0
local dt = 0.05
local min_w_ref = 0.0
for i = 1, 400 do
    state = flight_control.law_update(state, dt, measured, LIMITS)
    if state.w_ref < min_w_ref then min_w_ref = state.w_ref end
end
print(string.format("%.6f", min_w_ref))
""".replace(
            "{measured}",
            _measured(h_m=500.0, ias_mps=150.0 / 3.6, v_t_mps=150.0 / 3.6),
        )
        lines = _run(driver)
        # MAX_CLIMB_VS_MPS (LIMITS) = 5.0 -- without the VRS cap this
        # reaches -5.0, not -4.0.
        assert float(lines[0]) < -4.0 - 1e-6


class TestClimbTakeoverStoppingHeight:
    """Decision 24: "Altitude goal = the stopping height... So a climb
    levels off where it naturally stops, rather than reversing back to
    the height at capture." The toy plant: vertical speed responds to
    collective deflection from the trim value captured at take."""

    def test_stopping_height_goal_is_ahead_of_capture_in_the_climb_direction(
        self,
    ) -> None:
        driver = f"""
local measured = {_measured(w_mps=4.0, h_m=200.0)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
print(string.format("%.6f", state.alt_goal_m))
"""
        lines = _run(driver)
        # Climbing at 4 m/s: the stopping height must be above 200 m,
        # never the height at capture itself (that would be a reversal
        # the moment the loop starts decelerating).
        assert float(lines[0]) > 200.0

    def test_descending_takeover_goal_is_below_capture(self) -> None:
        driver = f"""
local measured = {_measured(w_mps=-3.0, h_m=200.0)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
print(string.format("%.6f", state.alt_goal_m))
"""
        lines = _run(driver)
        assert float(lines[0]) < 200.0

    def test_overshoot_past_the_stopping_height_stays_inside_the_band(self) -> None:
        """A fixed-gain second-order shaper chasing a goal that is
        itself velocity-dependent (the stopping-height formula) does
        not generally guarantee zero overshoot for every initial
        vertical speed -- confirmed by running this scenario during
        implementation, which is how `OMEGA_ALT` was tuned up from its
        first value. The plan names this as an alternative, equally
        valid pass criterion ("any overshoot stays inside the band"),
        so that is what this asserts, rather than a blanket "never
        reverses" that placeholder gains cannot promise."""
        driver = """
local measured = {measured}
local trim_collective = 0.2
local state = flight_control.law_init_at_take(measured, LIMITS,
    { pitch = 0, roll = 0, pedals = 0, collective = trim_collective })
local dt = 0.05
local plant_w_gain = 15.0  -- m/s^2 per unit collective deflection
local max_h_ref = state.h_ref
for i = 1, 4000 do
    state = flight_control.law_update(state, dt, measured, LIMITS)
    local outputs = flight_control.law_outputs(state, measured)
    local w_dot = plant_w_gain * (outputs.collective - trim_collective)
    measured.w_mps = measured.w_mps + w_dot * dt
    measured.h_m = measured.h_m + measured.w_mps * dt
    if state.h_ref > max_h_ref then max_h_ref = state.h_ref end
end
print(string.format("%.6f", state.alt_goal_m))
print(string.format("%.6f", max_h_ref))
print(string.format("%.6f", state.h_ref))
print(tostring(state.in_band_altitude))
""".replace("{measured}", _measured(w_mps=4.0, h_m=200.0))
        lines = _run(driver)
        goal_m, max_h_ref, final_h_ref, in_band = lines
        alt_band = max(0.10 * float(goal_m), 10.0)
        assert float(max_h_ref) - float(goal_m) <= alt_band
        assert abs(float(final_h_ref) - float(goal_m)) < 0.5
        assert in_band == "true"


class TestSpeedChannel:
    def test_converges_into_band(self) -> None:
        driver = """
local measured = {measured}
local trim_pitch = -3.0
local state = flight_control.law_init_at_take(measured, LIMITS,
    { pitch = 0.15, roll = 0, pedals = 0, collective = 0.2 })
state = flight_control.law_apply_goal(state, { ias_kmh = 180.0 }, LIMITS)  -- 50 m/s
local dt = 0.05
local plant_ax_gain = 2.0  -- m/s^2 per degree of nose-down pitch past trim
for i = 1, 6000 do
    state = flight_control.law_update(state, dt, measured, LIMITS)
    local outputs = flight_control.law_outputs(state, measured)
    local tau = 1.5
    measured.pitch_deg = measured.pitch_deg + (state.theta_d - measured.pitch_deg) * (dt / tau)
    measured.q_deg_s = (state.theta_d - measured.pitch_deg) / tau
    local ax = plant_ax_gain * (trim_pitch - measured.pitch_deg)
    measured.ias_mps = measured.ias_mps + ax * dt
    measured.v_t_mps = measured.ias_mps + 2.0
end
print(string.format("%.6f", measured.ias_mps))
print(tostring(state.in_band_speed))
""".replace("{measured}", _measured(pitch_deg=-3.0, ias_mps=40.0, v_t_mps=42.0))
        lines = _run(driver)
        final_ias, in_band = lines
        assert abs(float(final_ias) - 50.0) <= 0.1 * 50.0
        assert in_band == "true"


class TestLevelOffSettlesToHeadingMode:
    def test_level_off_switches_internally_once_the_turn_settles(self) -> None:
        """ "`level_off` goes through turn mode at 0. When `r_ref`
        reaches 0, Lua switches to heading mode with `psi_goal =
        psi_ref`" -- a continuing turn (`turn=1`), then `turn=0`
        (`level_off`'s own wire shape), run against the same bank-lag
        toy plant as `TestHeadingChannel` until the turn has visibly
        rolled out."""
        driver = f"""
local measured = {_measured(bank_deg=20.0, psi_deg=0.0)}
local state = flight_control.law_init_at_take(measured, LIMITS,
    {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }})
state = flight_control.law_apply_goal(state, {{ turn = 0 }}, LIMITS)
local dt = 0.05
local tau = 1.0
for i = 1, 3000 do
    state = flight_control.law_update(state, dt, measured, LIMITS)
    local outputs = flight_control.law_outputs(state, measured)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    measured.p_deg_s = (state.phi_d - measured.bank_deg) / tau
    local r = flight_control.law_turn_rate_at_bank(measured.bank_deg, measured.v_t_mps)
    measured.psi_deg = (measured.psi_deg + r * dt) % 360.0
    measured.r_deg_s = r
end
print(tostring(state.turn_mode))
print(string.format("%.6f", measured.bank_deg))
"""
        lines = _run(driver)
        turn_mode, final_bank = lines
        assert turn_mode == "false"
        assert abs(float(final_bank)) < 2.0


def test_file_parses_without_a_lua_interpreter_too() -> None:
    """`luac5.1` sanity, independent of whether a runtime interpreter is
    on `PATH` -- mirrors `test_flight_control_lua.py`'s own copy of
    this check."""
    exe = shutil.which("luac5.1")
    if exe is None:
        pytest.skip("no luac5.1 on PATH")
    result = subprocess.run(
        [exe, "-p", str(_FLIGHT_CONTROL_LUA)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
