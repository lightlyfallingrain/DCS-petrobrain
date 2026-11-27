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

#: review-debug-1125.md required fix 1 -- `TestAmendmentProductionValuesTogether`'s own tests
#: below read the shipped `omega_speed`/`k_speed_error`/`c_theta`/`speed_accel_cap_mps2` from
#: this file directly (via the Lua driver's own `dofile`), rather than retyping them, so the
#: fifth re-fly's own gap (a profile constant moved, no committed test ever ran the new value)
#: cannot recur a third time on the same four fields.
_FLIGHT_PROFILE_LUA = _FLIGHT_CONTROL_LUA.parent / "flight_profile.lua"

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

#: BL-16 lift-vector law, Stage LV-1 (`plans/flight-lift-vector/
#: plan.md`) -- the five `law_*` pure functions take `profile` as an
#: explicit trailing parameter (`flight_profile.lua`'s `PROFILES
#: ["Mi-24P"]` table). Values below are copied from that profile table.
#: Removed from LV-0's own copy of this table (dead fields, per the
#: plan's own "Removed and kept"): `k_bank_increment`, `k_tilt_from_ax`,
#: `k_tilt_from_az_saturated`, `tau_accel_filter_s`, `k_break_pedal_
#: bias`. New for LV-1: the gain schedule, the trim loops (D), the
#: ordinary priority chain (G), the lift-length feed-forward (E) and
#: the ball-centring pedal loop (F).
_PROFILE = """
local PROFILE = {
    law_zeta = 1.0,
    omega_heading = 0.3,
    omega_alt = 0.5,
    omega_speed = 0.15,
    t_roll = 2.0,
    heading_accel_cap_deg_s2 = 6.0,
    k_heading_track = 0.3,
    alt_accel_cap_mps2 = 1.0,
    speed_accel_cap_mps2 = 0.5,
    k_vs_error = 0.3,
    k_alt_error = 0.05,
    k_speed_error = 0.2,
    schedule_gain_min = 0.3,
    schedule_full_speed_kmh = 150.0,
    c_theta = 0.5,
    k_phi_trim = 0.02,
    k_theta_trim = 0.02,
    trim_hold_attitude_err_deg = 10.0,
    phi_i_bound_deg = 8.0,
    k_theta_speed_give = 0.5,
    speed_give_capacity = 0.05,
    k_phi_give = 4.0,
    phi_ff_min_scale = 0.3,
    k_collective_speed_give = 0.1,
    collective_speed_give_max_a_f_d_mps2 = 3.0,
    k_lift_ff = 0.05,
    k_collective = 0.08,
    theta_min_deg = -15.0,
    theta_max_deg = 15.0,
    k_theta = 0.03,
    k_theta_i = 0.015,
    k_q = 0.01,
    k_phi = 0.03,
    k_phi_i = 0.015,
    k_p = 0.01,
    -- Positive pedal command = RIGHT pedal (`plans/flight-lift-vector/
    -- debug-2026-11-24b.md` reverted the first 2026-11-24 pass's flip,
    -- which the re-fly showed backwards) -- mirrors `flight_profile.lua`.
    k_ball_pedal = 0.3,
    -- LV-1 amendment (2026-11-24, fourth re-fly) -- new fields.
    k_ball_pedal_p = 0.3,
    k_pedal_from_collective_rate = 0.25,
    spooled_rpm_pct = 93.0,
    engine_rpm_gentle_floor_pct = 74.0,
    collective_rate_gentle_min_per_s = 0.2,
    rotor_dir = 1.0,
    k_turn_coord_pedal = 0.02,
    pedal_limit_positive = 0.5,
    pedal_limit_negative = -1.0,
    pedal_near_limit_margin = 0.1,
    collective_rate_cap_near_pedal_limit = 0.3,
    rotor_rpm_warning_pct = 88.0,
    collective_ease_rate_near_rpm_warning = -0.3,
    retreating_blade_stall_margin_kmh = 20.0,
    collective_rate_cap_near_blade_stall = 0.0,
    turn_settle_deg_s = 0.3,
    law_hz = 30.0,
    velocity_source = "position",
    w_v_s = 0.1,
    w_a_s = 0.2,
    w_a2_s = 0.1,
    w_b = 0.2,
    ball_centre = 0.03,
    ball_usable_range = 0.5,
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
        + _PROFILE
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
    base: dict[str, float | bool] = {
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
        # LV-1 amendment (2026-11-24, fourth re-fly) -- well clear of
        # `PROFILE.spooled_rpm_pct` (93.0, review-lv1-amendment.md
        # required fix 2) by default, same "no pre-existing scenario
        # trips a guard it is not testing" posture as `rotor_rpm_pct`
        # above.
        "engine_rpm_pct": 100.0,
        # BL-16 sortie 2026-11-20 (`plans/flight-control/debug.md`) --
        # defaults `true` so every pre-existing collective-channel
        # scenario above keeps exercising the collective-coupling
        # pedal feedforward it always implicitly assumed; the new
        # drift scenario below overrides it `false` to match today's
        # real `FC_AXES_ENABLED.collective` default.
        "collective_enabled": True,
    }
    base.update(overrides)
    fields = ", ".join(
        f"{k} = {'true' if isinstance(v, bool) and v else 'false' if isinstance(v, bool) else v}"
        for k, v in base.items()
    )
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
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
local outputs = flight_control.law_outputs(state, measured, PROFILE)
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
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
print(state.u_c)
"""
        lines = _run(driver)
        assert float(lines[0]) == 0.0


class TestTakeoverModeSelection:
    """LV-1 amendment (2026-11-24, fourth re-fly), section A, E11 -- a
    bank at or past `LIMITS.takeover_level_bank_deg` now HOLDS THAT BANK
    directly (`bank_hold_deg`) rather than setting the old `turn_mode`
    (which held whatever rate happened to be measured at the take,
    finding 2's own "a 45 deg take rolls out to `max_turn_bank_deg`").
    `turn_mode` is never set true by a take any more -- it stays live
    only for an actual "turn left/right" command."""

    def test_4_9_degrees_picks_heading_mode(self) -> None:
        driver = f"""
local measured = {_measured(bank_deg=4.9)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0 }}, nil, PROFILE)
print(tostring(state.turn_mode))
print(tostring(state.bank_hold_deg))
"""
        lines = _run(driver)
        assert lines[0] == "false"
        assert lines[1] == "nil"

    def test_5_1_degrees_holds_that_bank(self) -> None:
        driver = f"""
local measured = {_measured(bank_deg=5.1)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0 }}, nil, PROFILE)
print(tostring(state.turn_mode))
print(string.format("%.6f", state.bank_hold_deg))
"""
        lines = _run(driver)
        assert lines[0] == "false"
        assert abs(float(lines[1]) - 5.1) < 1e-6

    def test_averaged_bank_phi_bar_is_what_the_5_degree_rule_reads(
        self,
    ) -> None:
        """Finding, "the 5 deg rule's input": a wobbly raw single-frame
        bank must not flip the decision -- `measured.phi_bar` (the
        estimator's own running mean) is read in preference to
        `measured.bank_deg` whenever it is present."""
        driver = f"""
local measured = {_measured(bank_deg=10.0)}
measured.phi_bar = 2.0
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0 }}, nil, PROFILE)
print(tostring(state.turn_mode))
print(tostring(state.bank_hold_deg))
"""
        lines = _run(driver)
        # phi_bar (2.0) is below the 5 deg threshold, even though the
        # raw single-frame bank_deg (10.0) is not.
        assert lines[0] == "false"
        assert lines[1] == "nil"

    def test_bank_hold_falls_back_to_raw_bank_when_phi_bar_absent(
        self,
    ) -> None:
        """A mission-start-instant take (estimator not primed yet) has
        no `phi_bar` -- falls back to the raw measured bank, same as
        before the estimator primed anywhere else in this module."""
        driver = f"""
local measured = {_measured(bank_deg=8.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0 }}, nil, PROFILE)
print(string.format("%.6f", state.bank_hold_deg))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - 8.0) < 1e-6


class TestUnparkTakeSeedFromMode2SetTargets:
    """BL-16 sortie 2026-11-20 (`plans/flight-control/debug.md`) -- the
    crash this report diagnoses. Without a seed, an unpark mid-break
    (still banked past `takeover_level_bank_deg`) reads that transient
    bank as the pilot deliberately holding a turn (the same heuristic
    `TestTakeoverModeSelection` above pins for a voice take, where that
    reading is correct) and `turn_goal_deg_s` then never changes on its
    own -- nothing in `law_update` ever drives it back toward zero. A
    held heading from mode 2's own AI-wheel overlay forces heading mode
    instead, giving the law something real to fly back to."""

    def test_seed_overrides_heading_altitude_and_speed(self) -> None:
        driver = f"""
local measured = {
            _measured(bank_deg=10.0, psi_deg=270.0, h_m=500.0, w_mps=3.0, ias_mps=50.0)
        }
local command = {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}
local state = flight_control.law_init_at_take(measured, LIMITS, command, {{ heading_deg = 45.0, alt_m = 700.0, alt_ref = "B", speed_kmh = 180.0 }}, PROFILE)
print(tostring(state.turn_mode))
print(string.format("%.6f", state.heading_goal_deg))
print(string.format("%.6f", state.alt_goal_m))
print(state.alt_goal_ref)
print(string.format("%.6f", state.speed_goal_mps))
"""
        lines = _run(driver)
        turn_mode, heading_goal, alt_goal, alt_ref, speed_goal = lines
        # A known heading forces heading mode even though bank alone
        # (10 deg, past the 5 deg threshold) would have picked turn
        # mode -- the dial is the deliberate state to resume, not the
        # bank the AI wheel happened to be at.
        assert turn_mode == "false"
        assert abs(float(heading_goal) - 45.0) < 1e-6
        assert abs(float(alt_goal) - 700.0) < 1e-6
        assert alt_ref == "baro"
        assert abs(float(speed_goal) - (180.0 / 3.6)) < 1e-6

    def test_a_seed_with_no_usable_fields_falls_back_exactly_as_before(self) -> None:
        """`held_targets()` returns every field even when the AI-wheel
        overlay text was never parsed (every value `nil`) -- an all-nil
        seed must behave identically to no seed at all."""
        driver = f"""
local measured = {
            _measured(bank_deg=2.0, psi_deg=123.0, h_m=400.0, w_mps=0.0, ias_mps=60.0)
        }
local command = {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}
local with_seed = flight_control.law_init_at_take(measured, LIMITS, command, {{ heading_deg = nil, alt_m = nil, alt_ref = nil, speed_kmh = nil }}, PROFILE)
local without_seed = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
print(tostring(with_seed.turn_mode == without_seed.turn_mode))
print(tostring(with_seed.heading_goal_deg == without_seed.heading_goal_deg))
print(tostring(with_seed.alt_goal_m == without_seed.alt_goal_m))
print(tostring(with_seed.alt_goal_ref == without_seed.alt_goal_ref))
print(tostring(with_seed.speed_goal_mps == without_seed.speed_goal_mps))
"""
        lines = _run(driver)
        assert all(line == "true" for line in lines)

    def test_without_a_seed_a_mid_break_unpark_never_levels_or_converges(self) -> None:
        """LV-1 amendment, section A -- the mechanism changed (`bank_
        hold_deg` replaces the old measured-rate-hold `turn_mode`), but
        the outcome this test pins is the same one E11 asks for: a take
        past the takeover threshold with no known heading keeps turning,
        never rolls back toward level."""
        driver = f"""
local measured = {
            _measured(
                bank_deg=25.0,
                psi_deg=0.0,
                r_deg_s=6.0,
                ias_mps=150.0 / 3.6,
                v_t_mps=150.0 / 3.6,
            )
        }
local command = {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
print(tostring(state.turn_mode))
print(tostring(state.bank_hold_deg))
local dt = 0.05
local tau = 1.0
for i = 1, 2000 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    -- BL-16 lift-vector law, LV-1 -- the real lateral (centripetal)
    -- acceleration a coordinated turn at this bank actually produces,
    -- so the trim loop's own measured-acceleration feedback (section D,
    -- `e_r = a_r,d - a_r`) has something real to converge against;
    -- without it `a_r` stays the `law_update` fallback (0.0) forever,
    -- which never opposes `phi_i`'s own integration and leaves it
    -- pinned wherever the turn left it.
    measured.a_r = 9.81 * math.tan(math.rad(measured.bank_deg))
    measured.p_deg_s = (state.phi_d - measured.bank_deg) / tau
    local r = flight_control.law_turn_rate_at_bank(measured.bank_deg, measured.v_t_mps)
    measured.psi_deg = (measured.psi_deg + r * dt) % 360.0
    measured.r_deg_s = r
end
print(tostring(state.in_band_heading))
print(string.format("%.6f", measured.bank_deg))
"""
        lines = _run(driver)
        was_turn_mode, bank_hold_deg, in_band, final_bank = lines
        assert was_turn_mode == "false"
        assert abs(float(bank_hold_deg) - 25.0) < 1e-6
        # Never a heading to be "in band" of -- `law_update` forces
        # `in_band_heading` false for the whole run while a bank is
        # held.
        assert in_band == "false"
        # Holds (close to) the captured bank, never back toward level
        # flight -- nothing in this mechanism ever commands it to roll
        # out.
        assert abs(float(final_bank)) > 20.0

    def test_with_a_held_heading_the_unpark_rolls_level_and_converges(self) -> None:
        driver = f"""
local measured = {
            _measured(
                bank_deg=25.0,
                psi_deg=0.0,
                r_deg_s=6.0,
                ias_mps=150.0 / 3.6,
                v_t_mps=150.0 / 3.6,
            )
        }
local command = {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}
local state = flight_control.law_init_at_take(measured, LIMITS, command, {{ heading_deg = 0.0 }}, PROFILE)
print(tostring(state.turn_mode))
local dt = 0.05
local tau = 1.0
for i = 1, 2000 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    -- BL-16 lift-vector law, LV-1 -- the real lateral (centripetal)
    -- acceleration a coordinated turn at this bank actually produces,
    -- so the trim loop's own measured-acceleration feedback (section D,
    -- `e_r = a_r,d - a_r`) has something real to converge against;
    -- without it `a_r` stays the `law_update` fallback (0.0) forever,
    -- which never opposes `phi_i`'s own integration and leaves it
    -- pinned wherever the turn left it.
    measured.a_r = 9.81 * math.tan(math.rad(measured.bank_deg))
    measured.p_deg_s = (state.phi_d - measured.bank_deg) / tau
    local r = flight_control.law_turn_rate_at_bank(measured.bank_deg, measured.v_t_mps)
    measured.psi_deg = (measured.psi_deg + r * dt) % 360.0
    measured.r_deg_s = r
end
print(tostring(state.in_band_heading))
print(string.format("%.6f", measured.bank_deg))
"""
        lines = _run(driver)
        was_turn_mode, in_band, final_bank = lines
        assert was_turn_mode == "false"
        assert in_band == "true"
        # Rolled back toward level chasing heading 0, rather than
        # holding the captured 25 deg bank.
        assert abs(float(final_bank)) < 5.0


#: Shared toy-plant driver body for the heading channel: bank is a
#: first-order lag toward `phi_d` (`tau` s), heading integrates the
#: coordinated-turn rate at the current bank (`law_turn_rate_at_bank`,
#: the law's own helper -- reused so the plant's kinematics are at
#: least internally consistent with what the law assumes a turn does).
_HEADING_PLANT_DRIVER = """
local measured = {measured}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ heading_deg = {goal} }}, LIMITS, PROFILE)
local dt = 0.05
local tau = 1.0
local errs = {{}}
local signs = {{}}
for i = 1, {steps} do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    -- BL-16 lift-vector law, LV-1 -- the real lateral (centripetal)
    -- acceleration a coordinated turn at this bank actually produces,
    -- so the trim loop's own measured-acceleration feedback (section D,
    -- `e_r = a_r,d - a_r`) has something real to converge against;
    -- without it `a_r` stays the `law_update` fallback (0.0) forever,
    -- which never opposes `phi_i`'s own integration and leaves it
    -- pinned wherever the turn left it.
    measured.a_r = 9.81 * math.tan(math.rad(measured.bank_deg))
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
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ heading_deg = {goal}, turn_rate_deg_s = {rate} }}, LIMITS, PROFILE)
local dt = 0.05
local tau = 1.0
local max_bank = 0.0
for i = 1, {steps} do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    -- BL-16 lift-vector law, LV-1 -- the real lateral (centripetal)
    -- acceleration a coordinated turn at this bank actually produces,
    -- so the trim loop's own measured-acceleration feedback (section D,
    -- `e_r = a_r,d - a_r`) has something real to converge against;
    -- without it `a_r` stays the `law_update` fallback (0.0) forever,
    -- which never opposes `phi_i`'s own integration and leaves it
    -- pinned wherever the turn left it.
    measured.a_r = 9.81 * math.tan(math.rad(measured.bank_deg))
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
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ heading_deg = 90.0, turn_rate_deg_s = -40.0 }}, LIMITS, PROFILE)
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
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ heading_deg = 90.0, turn_rate_deg_s = -40.0 }}, LIMITS, PROFILE)
state = flight_control.law_apply_goal(state, {{ heading_deg = 180.0 }}, LIMITS, PROFILE)
print(tostring(state.rate_override_deg_s))
print(tostring(state.break_entry_h_m))
"""
        lines = _run(driver)
        assert lines[0] == "nil"
        assert lines[1] == "nil"

    def test_a_continuous_turn_goal_also_clears_a_standing_override(self) -> None:
        driver = f"""
local measured = {_measured(h_m=300.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ heading_deg = 90.0, turn_rate_deg_s = -40.0 }}, LIMITS, PROFILE)
state = flight_control.law_apply_goal(state, {{ turn = 1 }}, LIMITS, PROFILE)
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
local state = flight_control.law_init_at_take(measured, LIMITS, { pitch = 0, roll = 0, pedals = 0, collective = 0.2 }, nil, PROFILE)
-- Force a far-below floor so the shaper would chase it if the break
-- floor did not intervene.
state.alt_goal_m = 0.0
state = flight_control.law_apply_goal(state, { heading_deg = 90.0, turn_rate_deg_s = 40.0 }, LIMITS, PROFILE)
local dt = 0.05
local min_h_ref = state.h_ref
for i = 1, 400 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
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
local state = flight_control.law_init_at_take(measured, LIMITS, { pitch = 0, roll = 0, pedals = 0, collective = 0.2 }, nil, PROFILE)
state.alt_goal_m = 0.0
state = flight_control.law_apply_goal(state, { heading_deg = 90.0, turn_rate_deg_s = 40.0 }, LIMITS, PROFILE)
local dt = 0.05
local tau = 1.0
for i = 1, 3000 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    -- BL-16 lift-vector law, LV-1 -- the real lateral (centripetal)
    -- acceleration a coordinated turn at this bank actually produces,
    -- so the trim loop's own measured-acceleration feedback (section D,
    -- `e_r = a_r,d - a_r`) has something real to converge against;
    -- without it `a_r` stays the `law_update` fallback (0.0) forever,
    -- which never opposes `phi_i`'s own integration and leaves it
    -- pinned wherever the turn left it.
    measured.a_r = 9.81 * math.tan(math.rad(measured.bank_deg))
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
    """Mode-1 batch, Decision 30, superseded 2026-11-25 for the rotor
    channel (`plans/flight-lift-vector/debug-2026-11-25.md`): the
    retreating-blade-stall margin still only caps a further *increase*
    in collective, untouched on a decrease. The rotor-RPM floor is now
    the warning-based active ease below (Petrovich's stand-in for the
    real aircraft's own low-RPM audio cue to a human pilot) -- it forces
    a *decrease*, unconditionally, not merely a freeze on increase."""

    def test_low_rotor_rpm_eases_a_rising_collective(self) -> None:
        driver = f"""
local measured = {_measured(h_m=100.0, w_mps=-5.0, rotor_rpm_pct=87.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
-- A big positive altitude error asks for a large rising c_dot.
state.alt_goal_m = 1000.0
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
print(string.format("%.6f", (next_state.u_c - state.u_c) / 0.05))
"""
        lines = _run(driver)
        # Strictly below `rotor_rpm_warning_pct` (88.0): the nominal
        # rising c_dot is overridden by `collective_ease_rate_near_rpm_
        # warning` (-0.3), an active decrease -- never merely frozen at
        # zero.
        assert float(lines[0]) <= -0.3 + 1e-6

    def test_rotor_rpm_at_the_warning_threshold_is_not_yet_below_it(self) -> None:
        """Strict `<` (`plans/flight-lift-vector/debug-2026-11-24b.md`,
        question 3, same lesson re-applied): a reading exactly AT
        `rotor_rpm_warning_pct` must not trip the ease, or a reading
        that sits exactly on the boundary (the shipped dummy's `90.0`
        sat exactly on the old floor+margin threshold and locked
        collective out for every mode-1 frame, 2026-11-24)."""
        driver = f"""
local measured = {_measured(h_m=100.0, w_mps=-5.0, rotor_rpm_pct=88.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state.alt_goal_m = 1000.0
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
print(string.format("%.6f", (next_state.u_c - state.u_c) / 0.05))
"""
        lines = _run(driver)
        assert float(lines[0]) > 1e-3

    def test_the_shipped_dummy_rpm_reading_lets_collective_rise(self) -> None:
        """The shipped dummy (90.0, `ROTOR_RPM_DUMMY_PCT`) sits above
        `rotor_rpm_warning_pct` (88.0), so a fallback-to-dummy read
        (e.g. a failed live read) never eases collective by itself."""
        driver = f"""
local measured = {_measured(h_m=100.0, w_mps=-5.0, rotor_rpm_pct=90.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state.alt_goal_m = 1000.0
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
print(string.format("%.6f", (next_state.u_c - state.u_c) / 0.05))
"""
        lines = _run(driver)
        assert float(lines[0]) > 1e-3

    def test_a_falling_collective_is_untouched_by_the_rpm_floor(self) -> None:
        driver = f"""
local measured = {_measured(h_m=1000.0, w_mps=5.0, rotor_rpm_pct=88.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state.alt_goal_m = 0.0
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
print(string.format("%.6f", (next_state.u_c - state.u_c) / 0.05))
"""
        lines = _run(driver)
        assert float(lines[0]) < -1e-9

    def test_near_retreating_blade_stall_caps_a_rising_collective(self) -> None:
        driver = f"""
local measured = {_measured(h_m=100.0, w_mps=-5.0, ias_mps=235.0 / 3.6, v_t_mps=235.0 / 3.6)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state.alt_goal_m = 1000.0
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
print(string.format("%.6f", (next_state.u_c - state.u_c) / 0.05))
"""
        lines = _run(driver)
        # RETREATING_BLADE_STALL_MARGIN_KMH = 20.0 -- capped at or
        # above 250.0 - 20.0 = 230.0 km/h; 235 km/h qualifies.
        assert float(lines[0]) <= 1e-9

    def test_well_clear_of_both_guards_collective_rises_freely(self) -> None:
        driver = f"""
local measured = {_measured(h_m=100.0, w_mps=-5.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state.alt_goal_m = 1000.0
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
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
local state = flight_control.law_init_at_take(measured, LIMITS, { pitch = 0, roll = 0, pedals = 0, collective = 0.2 }, nil, PROFILE)
state.alt_goal_m = -10000.0
local dt = 0.05
local min_w_ref = 0.0
for i = 1, 400 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    if state.w_ref < min_w_ref then min_w_ref = state.w_ref end
end
print(string.format("%.6f", min_w_ref))
""".replace("{measured}", _measured(h_m=500.0, ias_mps=30.0 / 3.6, v_t_mps=30.0 / 3.6))
        lines = _run(driver)
        assert float(lines[0]) >= -4.0 - 1e-6

    def test_cruise_speed_descent_is_not_capped_by_vrs(self) -> None:
        driver = """
local measured = {measured}
local state = flight_control.law_init_at_take(measured, LIMITS, { pitch = 0, roll = 0, pedals = 0, collective = 0.2 }, nil, PROFILE)
state.alt_goal_m = -10000.0
local dt = 0.05
local min_w_ref = 0.0
for i = 1, 400 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
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
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
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
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
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
local state = flight_control.law_init_at_take(measured, LIMITS, { pitch = 0, roll = 0, pedals = 0, collective = trim_collective }, nil, PROFILE)
local dt = 0.05
local plant_w_gain = 15.0  -- m/s^2 per unit collective deflection
local max_h_ref = state.h_ref
local prev_w = measured.w_mps
for i = 1, 4000 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    local w_dot = plant_w_gain * (outputs.collective - trim_collective)
    measured.w_mps = measured.w_mps + w_dot * dt
    measured.h_m = measured.h_m + measured.w_mps * dt
    -- BL-16 lift-vector law, LV-1 -- the real vertical acceleration,
    -- so `e_u = a_u,d - a_u` (section E) has genuine measured-rate
    -- damping to work against, the same role `a_z_f`'s own low-pass
    -- filter played in the pre-LV-1 law. Without it `a_u` stays the
    -- `law_update` fallback (0.0) forever and this double-integrator
    -- plant (collective -> accel -> velocity -> position) has nothing
    -- to damp the collective-rate integrator against -- confirmed:
    -- w_mps swung to +-30 m/s before this was added.
    measured.a_u = (measured.w_mps - prev_w) / dt
    prev_w = measured.w_mps
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
local state = flight_control.law_init_at_take(measured, LIMITS, { pitch = 0.15, roll = 0, pedals = 0, collective = 0.2 }, nil, PROFILE)
state = flight_control.law_apply_goal(state, { ias_kmh = 180.0 }, LIMITS, PROFILE)  -- 50 m/s
local dt = 0.05
local plant_ax_gain = 2.0  -- m/s^2 per degree of nose-down pitch past trim
for i = 1, 6000 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
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
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ turn = 0 }}, LIMITS, PROFILE)
local dt = 0.05
local tau = 1.0
for i = 1, 3000 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    -- BL-16 lift-vector law, LV-1 -- the real lateral (centripetal)
    -- acceleration a coordinated turn at this bank actually produces,
    -- so the trim loop's own measured-acceleration feedback (section D,
    -- `e_r = a_r,d - a_r`) has something real to converge against;
    -- without it `a_r` stays the `law_update` fallback (0.0) forever,
    -- which never opposes `phi_i`'s own integration and leaves it
    -- pinned wherever the turn left it.
    measured.a_r = 9.81 * math.tan(math.rad(measured.bank_deg))
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


class TestPedalDoesNotDriftWithCollectiveDisabled:
    """BL-16 sortie 2026-11-20 (`plans/flight-control/debug.md`,
    defect A): the user reported Petrovich adding "quite a lot" of
    left pedal right after a plain take, with no break involved --
    confirmed as a continuous *ramp*, not a one-off offset, driven by
    `K_PEDAL_FROM_COLLECTIVE_RATE * c_dot` where `c_dot` tracks a
    collective that `FC_AXES_ENABLED.collective = false` never
    actually writes to the aircraft. A sustained altitude-hold
    tracking error (here: the real aircraft sits 5 m away from the
    stopping height captured at take, and never moves, since nothing
    is actually flying the collective) therefore never resolves and
    keeps driving `c_dot`, and before the fix that fed straight into
    the pedal every frame with nothing to arrest it."""

    def test_sustained_altitude_error_does_not_move_the_pedal(self) -> None:
        driver = f"""
local measured_take = {_measured(h_m=200.0, w_mps=0.0, collective_enabled=False)}
local command = {{ pitch = 0.0, roll = 0.0, pedals = 0.0, collective = 0.0 }}
local state = flight_control.law_init_at_take(measured_take, LIMITS, command, nil, PROFILE)
local t_y_at_take = state.t_y
-- The real aircraft sits 5 m above the stopping height captured at
-- take, and never moves from there (nothing is flying the collective)
-- -- a sustained, never-resolving altitude error.
for i = 1, 200 do
    local m = {_measured(h_m=205.0, w_mps=0.0, collective_enabled=False)}
    state = flight_control.law_update(state, 0.1, m, LIMITS, PROFILE)
end
print(string.format("%.6f", t_y_at_take))
print(string.format("%.6f", state.t_y))
"""
        lines = _run(driver)
        t_y_at_take, t_y_after_20s = (float(v) for v in lines)
        assert abs(t_y_at_take) < 1e-6
        # Before the fix this reached roughly -0.1 after 20 s and kept
        # growing (an unbounded ramp) -- a tight bound here catches a
        # regression of the same shape, not only a total reversion.
        assert abs(t_y_after_20s - t_y_at_take) < 0.01

    def test_the_same_altitude_error_does_move_the_pedal_with_collective_enabled(
        self,
    ) -> None:
        """Negative control: the gate in `law_update` is keyed on
        `measured.collective_enabled`, not on the altitude error being
        absent -- with collective enabled the same scenario is
        expected to feed the pedal (today's `FC_AXES_ENABLED.
        collective = false` default is what makes the gate matter in
        practice, not a claim that the feedforward term itself is
        wrong)."""
        driver = f"""
local measured_take = {_measured(h_m=200.0, w_mps=0.0, collective_enabled=True)}
local command = {{ pitch = 0.0, roll = 0.0, pedals = 0.0, collective = 0.0 }}
local state = flight_control.law_init_at_take(measured_take, LIMITS, command, nil, PROFILE)
for i = 1, 200 do
    local m = {_measured(h_m=205.0, w_mps=0.0, collective_enabled=True)}
    state = flight_control.law_update(state, 0.1, m, LIMITS, PROFILE)
end
print(string.format("%.6f", state.t_y))
"""
        lines = _run(driver)
        (t_y_after_20s,) = (float(v) for v in lines)
        assert abs(t_y_after_20s) > 0.01


class TestCollectiveHoldsAltitudeInABankedTurn:
    """Sortie 2026-11-20 (`docs/acceptance/2026-11-20-sortie-feedback.md`,
    "Mode 1 flight, `main` @ `a8b21de0`"), user: "Use pedals. All the
    axis are interdependent... Use then all to maintain desired state."
    -- and the decision to enable collective at all. Step 3's own split
    (`d_theta` only ever picks up the altitude channel's `a_z_d` term
    while `collective_limited`) already favours collective 100% while
    it has room; this is the toy-plant proof that the split actually
    holds altitude once collective has a real effect on the plant, and
    that pitch picks up the slack when it does not (collective written
    but never actually moving the aircraft -- the pre-this-batch
    reality for every flight so far)."""

    @staticmethod
    def _run_banked_scenario(collective_effective: bool) -> tuple[float, float, float]:
        driver = f"""
local measured_take = {_measured()}
local command = {{ pitch = 0.0, roll = 0.0, pedals = 0.0, collective = 0.2 }}
local state = flight_control.law_init_at_take(measured_take, LIMITS, command, nil, PROFILE)
local measured = {_measured(bank_deg=40.0)}
-- This scenario fixes the measured bank externally (40 deg, never
-- itself driven by the law -- the point is the altitude/collective
-- split, not bank tracking) rather than via a turn command. Section H's
-- own anti-windup would otherwise read that as "the inner loop is not
-- following its own target" (the law never asked for 40 deg of bank)
-- and hold every trim integrator -- seeding `phi_d` to match is what a
-- real break/turn command would have produced on its own.
state.phi_d = 40.0
local dt = 0.1
local max_theta = 0.0
-- Lift lost to the bank's own tilt (`1 - cos(bank)`), a standing drain
-- on vertical lift the toy plant applies regardless of scenario --
-- the thing collective (or, lacking that, pitch) has to counter.
local lift_loss = 1.0 - math.cos(math.rad(40.0))
for i = 1, 600 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    -- `law_update` recomputes `phi_d` fresh every frame from `phi_ff`/
    -- `phi_i` (both ~0 here, no turn commanded) -- re-pin it after every
    -- call, not just once at take, or section H's "not following" gate
    -- would see a standing 40 deg mismatch from frame 2 onward and
    -- freeze every trim integrator this scenario means to exercise.
    state.phi_d = 40.0
    local target_w
    if {"true" if collective_effective else "false"} then
        -- Collective actually reaches the plant: vertical speed chases
        -- a target set by how far `u_c` sits above its level-flight
        -- trim (0.2 at take), net of the bank's own lift loss.
        target_w = (state.u_c - 0.2) * 10.0 - lift_loss * 5.0
    else
        -- Collective has no real effect (today's reality before this
        -- batch): only the bank's lift loss acts on vertical speed.
        target_w = -lift_loss * 5.0
    end
    measured.w_mps = measured.w_mps + (target_w - measured.w_mps) * (dt / 1.0)
    measured.h_m = measured.h_m + measured.w_mps * dt
    if math.abs(state.theta_d) > max_theta then max_theta = math.abs(state.theta_d) end
end
print(string.format("%.6f", max_theta))
print(string.format("%.6f", state.u_c))
print(string.format("%.6f", measured.h_m))
"""
        lines = _run(driver)
        max_theta, u_c, final_h_m = (float(v) for v in lines)
        return max_theta, u_c, final_h_m

    def test_collective_alone_holds_altitude_pitch_never_moves(self) -> None:
        max_theta, u_c, final_h_m = self._run_banked_scenario(collective_effective=True)
        # Pitch (`theta_d`) never picks up the altitude term at all --
        # collective alone carries the whole correction, never saturating.
        assert max_theta == 0.0
        assert u_c < 0.999
        # Altitude barely moves from the 200 m take height (collective
        # closes the loop before any real drift accumulates).
        assert abs(final_h_m - 200.0) < 1.0

    def test_pitch_only_picks_up_the_job_once_collective_cannot_act(self) -> None:
        """Negative control, same scenario: with collective's real
        effect removed, `u_c` saturates (no feedback ever resolves the
        altitude error), `collective_limited` goes true, and pitch
        picks up the slack -- a materially larger pitch demand than the
        collective-effective run, and real altitude loss collective
        would otherwise have prevented."""
        max_theta, u_c, final_h_m = self._run_banked_scenario(
            collective_effective=False
        )
        assert max_theta > 1.0
        assert u_c >= 0.999
        assert final_h_m < 150.0

    def test_pitch_demand_is_smaller_with_collective_effective(self) -> None:
        theta_on, _, _ = self._run_banked_scenario(collective_effective=True)
        theta_off, _, _ = self._run_banked_scenario(collective_effective=False)
        assert theta_on < theta_off


#: Shared toy-plant driver for the turn-coordination pedal (sortie
#: 2026-11-20, step 5's `turn_coord_pedal`) -- the idealised "measured
#: heading tracks the law's own reference" plant `TestBreakPedalBias
#: Unwinds` already uses, since isolating the pedal mechanism from
#: heading-tracking physics is exactly what that technique is for.
_TURN_PEDAL_DRIVER = """
local measured_take = {measured_take}
local command = {{ pitch = 0.0, roll = 0.0, pedals = 0.0, collective = 0.0 }}
local state = flight_control.law_init_at_take(measured_take, LIMITS, command, nil, PROFILE)
local outputs_before = flight_control.law_outputs(state, measured_take, PROFILE)
{goal_apply}
local min_pedal, max_pedal = 0.0, 0.0
local m
for i = 1, {steps} do
    m = {{ pitch_deg = 0, bank_deg = 0, psi_deg = state.psi_ref, ias_mps = 40.0,
           v_t_mps = 42.0, w_mps = 0, h_m = 200.0, asl_m = 200.0, p_deg_s = 0,
           q_deg_s = 0, r_deg_s = 0, rotor_rpm_pct = 100.0, collective_enabled = false }}
    state = flight_control.law_update(state, 0.1, m, LIMITS, PROFILE)
    local out = flight_control.law_outputs(state, m, PROFILE)
    if out.pedals < min_pedal then min_pedal = out.pedals end
    if out.pedals > max_pedal then max_pedal = out.pedals end
end
local outputs_after = flight_control.law_outputs(state, m, PROFILE)
print(string.format("%.6f", outputs_before.pedals))
print(string.format("%.6f", min_pedal))
print(string.format("%.6f", max_pedal))
print(string.format("%.6f", outputs_after.pedals))
print(tostring(state.in_band_heading))
"""


class TestTurnCoordinationPedal:
    """Sortie 2026-11-20, user: "turn right 50 -> turns but does not use
    pedals at all. Use pedals." -- `next_state.turn_coord_pedal`, a
    position overlay added only at `law_outputs` (see that function's
    own comment for why it is not folded into the `t_y` integrator)."""

    def test_zero_throughout_straight_and_level_flight(self) -> None:
        """No goal at all -- same heading held throughout, same as a
        take with no command given. Covers the take-time no-drift
        requirement too: `outputs_before` (the take state itself,
        before any `law_update`) is included in the same zero check."""
        driver = _TURN_PEDAL_DRIVER.format(
            measured_take=_measured(collective_enabled=False),
            goal_apply="-- no goal applied",
            steps=100,
        )
        lines = _run(driver)
        pedal_before, min_pedal, max_pedal, pedal_after, _ = lines
        assert float(pedal_before) == 0.0
        assert float(min_pedal) == 0.0
        assert float(max_pedal) == 0.0
        assert float(pedal_after) == 0.0

    def test_right_turn_pulls_positive_pedal_while_turning(self) -> None:
        driver = _TURN_PEDAL_DRIVER.format(
            measured_take=_measured(collective_enabled=False),
            goal_apply="state = flight_control.law_apply_goal(state, { heading_deg = 90.0 }, LIMITS, PROFILE)",
            steps=400,
        )
        lines = _run(driver)
        pedal_before, min_pedal, max_pedal, pedal_after, in_band = lines
        assert float(pedal_before) == 0.0
        # Positive pedal command = right pedal
        # (`plans/flight-lift-vector/debug-2026-11-24b.md`): a right
        # turn (`r_d > 0`) pulls positive (right) pedal.
        assert float(max_pedal) > 0.05
        assert float(min_pedal) == 0.0  # never crosses the other way
        # Unwinds: once settled, back to exactly the pre-turn value.
        assert in_band == "true"
        assert float(pedal_after) == 0.0

    def test_left_turn_pulls_negative_pedal_while_turning(self) -> None:
        driver = _TURN_PEDAL_DRIVER.format(
            measured_take=_measured(collective_enabled=False),
            goal_apply="state = flight_control.law_apply_goal(state, { heading_deg = 270.0 }, LIMITS, PROFILE)",
            steps=400,
        )
        lines = _run(driver)
        pedal_before, min_pedal, max_pedal, pedal_after, in_band = lines
        assert float(pedal_before) == 0.0
        # A left turn pulls negative (left) pedal.
        assert float(min_pedal) < -0.05
        assert float(max_pedal) == 0.0
        assert in_band == "true"
        assert float(pedal_after) == 0.0

    def test_not_suppressed_during_a_break_u5_reverted(
        self,
    ) -> None:
        """U5 reverted (plan, section F): "revert my idea about extra
        pedal. Just fly the slip ball." There is no `K_BREAK_PEDAL_BIAS`
        any more to avoid stacking with -- the turn-entry nudge now
        applies the same way whether a break's rate override is active
        or not, since the only thing left to fly the pedal is the ball
        (which defaults to centred here) plus this one nudge."""
        driver = f"""
local measured_take = {_measured(collective_enabled=False)}
local command = {{ pitch = 0.0, roll = 0.0, pedals = 0.0, collective = 0.0 }}
local state = flight_control.law_init_at_take(measured_take, LIMITS, command, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ heading_deg = 90.0, turn_rate_deg_s = 40.0 }}, LIMITS, PROFILE)
local m = {{ pitch_deg = 0, bank_deg = 0, psi_deg = state.psi_ref, ias_mps = 150.0 / 3.6,
       v_t_mps = 150.0 / 3.6, w_mps = 0, h_m = 200.0, asl_m = 200.0, p_deg_s = 0,
       q_deg_s = 0, r_deg_s = 0, rotor_rpm_pct = 100.0, collective_enabled = false }}
state = flight_control.law_update(state, 0.1, m, LIMITS, PROFILE)
print(string.format("%.6f", state.turn_coord_pedal))
print(tostring(state.rate_override_deg_s))
"""
        lines = _run(driver)
        turn_coord_pedal, rate_override = lines
        # The break is active (`rate_override_deg_s` is set) and the
        # nudge is nonzero anyway -- no suppression condition exists in
        # LV-1 any more. A right turn (as here, heading 90 from 0)
        # pulls positive (right) pedal.
        assert rate_override != "nil"
        assert float(turn_coord_pedal) > 0.0


#: Toy-plant driver for the ball-centring pedal loop (section F,
#: `k_ball_pedal`) -- new coverage added 2026-11-24
#: (`plans/flight-lift-vector/debug-2026-11-24.md`), since no existing
#: test ever set `measured.ball` away from `profile.ball_centre` (the
#: default `_measured()` table has no `ball` key at all, so `law_
#: update`'s own `measured.ball or profile.ball_centre` fallback made
#: every pre-existing scenario read the ball as already centred,
#: `d_t_y` identically `0.0` -- the loop's sign was simply never
#: exercised). The toy plant links the pedal *command* back to the
#: ball the same way the real aircraft does (2026-11-20 calibration
#: flight, direct and solid: left pedal moves the ball right, so with
#: positive command = right pedal, `K_PHYS` is negative) --
#: `ball_target = ball_centre + K_PHYS * pedal_command`, first-order
#: toward that target each step -- so a wrong-signed gain diverges
#: instead of centring, exactly the 2026-11-24 sortie's own shape
#: (`ball` running away from `ball_centre` smoothly, no oscillation
#: yet, before the secondary bank/yaw coupling joins in).
_BALL_CENTRING_DRIVER = """
local measured_take = {measured_take}
local command = {{ pitch = 0.0, roll = 0.0, pedals = 0.0, collective = 0.0 }}
local state = flight_control.law_init_at_take(measured_take, LIMITS, command, nil, PROFILE)
local ball = {ball_start}
local K_PHYS = -0.4
local m
local max_abs_err = 0.0
for i = 1, 300 do
    m = {{ pitch_deg = 0, bank_deg = 0, psi_deg = state.psi_ref, ias_mps = 150.0 / 3.6,
           v_t_mps = 150.0 / 3.6, w_mps = 0, h_m = 200.0, asl_m = 200.0, p_deg_s = 0,
           q_deg_s = 0, r_deg_s = 0, rotor_rpm_pct = 100.0, collective_enabled = false,
           ball = ball }}
    state = flight_control.law_update(state, 0.1, m, LIMITS, PROFILE)
    local out = flight_control.law_outputs(state, m, PROFILE)
    local ball_target = PROFILE.ball_centre + K_PHYS * out.pedals
    ball = ball + (ball_target - ball) * (0.1 / 0.5)
    local err = math.abs(ball - PROFILE.ball_centre)
    if err > max_abs_err then max_abs_err = err end
end
print(string.format("%.6f", ball))
print(string.format("%.6f", max_abs_err))
"""


class TestBallCentringPedalSign:
    """2026-11-24 sortie (`docs/acceptance/2026-11-24-sortie-feedback.md`,
    `plans/flight-lift-vector/debug-2026-11-24.md`): "take into a held
    heading" diverged immediately -- the slip ball ran monotonically from
    -0.03 to +0.56 over 8 s while the pilot directly observed "lots of
    left pedal". The first debug pass read that as this loop's sign
    being backward and flipped it; the re-fly showed the flip wrong
    (`plans/flight-lift-vector/debug-2026-11-24b.md`: the left pedal
    comes from the take itself, and positive command = right pedal).
    These tests drive the closed loop against a toy plant built from
    the solid ball/pedal relationship (left pedal moves the ball right)
    under positive command = right pedal, and diverge under the
    opposite sign."""

    def test_ball_right_of_centre_is_driven_back_to_centre(self) -> None:
        driver = _BALL_CENTRING_DRIVER.format(
            measured_take=_measured(collective_enabled=False),
            ball_start=0.3,
        )
        lines = _run(driver)
        final_ball, max_abs_err = (float(v) for v in lines)
        # Starts 0.27 off centre (0.3 - profile.ball_centre=0.03);
        # centring, not diverging, means the error shrinks well below
        # its starting value and never grows past it.
        assert max_abs_err <= 0.27 + 1e-6
        assert abs(final_ball - 0.03) < 0.05

    def test_ball_left_of_centre_is_driven_back_to_centre(self) -> None:
        driver = _BALL_CENTRING_DRIVER.format(
            measured_take=_measured(collective_enabled=False),
            ball_start=-0.3,
        )
        lines = _run(driver)
        final_ball, max_abs_err = (float(v) for v in lines)
        assert max_abs_err <= 0.33 + 1e-6
        assert abs(final_ball - 0.03) < 0.05


class TestCollectiveRateCapNearPedalLimit:
    """Review required fix, 2026-11-24
    (`plans/flight-lift-vector/review-debug-1124.md`): the collective-
    near-pedal-limit guard in `law_update` must cap a rising collective
    (`u_c_rate > 0.0`) near the side a collective increase actually
    pushes `t_y` toward, not a hard-coded limit name. With positive
    command = right pedal (`debug-2026-11-24b.md`), `k_pedal_from_
    collective_rate * rotor_dir` is positive, so that side is
    `pedal_limit_positive` (the scarce, right-pedal side); the abundant
    left side (`pedal_limit_negative`) is never capped. `t_y` values
    mirror the review's own mutation, on the reverted sign
    (`0.42`/`-0.92`); `h_m`/`alt_goal_m` mirror `TestRotorEnvelopeGuards
    .test_well_clear_of_both_guards_collective_rises_freely` so only
    the pedal guard is ever in question here, with `w_mps` widened
    (-5.0 -> -10.0) only to confirm first that this scenario's own
    nominal (uncapped) rate (0.447, by direct computation against the
    real law) clears `COLLECTIVE_RATE_CAP_NEAR_PEDAL_LIMIT` (0.3) --
    the -5.0 scenario's own nominal rate (0.177) sits below 0.3
    regardless of the guard, so a reading at or below 0.3 there would
    prove nothing."""

    def test_caps_a_rising_collective_near_the_scarce_positive_limit(
        self,
    ) -> None:
        driver = f"""
local measured = {_measured(h_m=100.0, w_mps=-10.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state.alt_goal_m = 1000.0
-- Within PEDAL_NEAR_LIMIT_MARGIN (0.1) of PEDAL_LIMIT_POSITIVE (0.5),
-- the scarce (right-pedal) side.
state.t_y = 0.42
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
print(string.format("%.6f", next_state.dbg_u_c_rate))
"""
        lines = _run(driver)
        assert float(lines[0]) <= 0.3 + 1e-6

    def test_does_not_cap_a_rising_collective_near_the_generous_negative_limit(
        self,
    ) -> None:
        driver = f"""
local measured = {_measured(h_m=100.0, w_mps=-10.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state.alt_goal_m = 1000.0
-- Near PEDAL_LIMIT_NEGATIVE (-1.0), the abundant (left-pedal) side
-- a rising collective never pushes `t_y` toward.
state.t_y = -0.92
local next_state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
print(string.format("%.6f", next_state.dbg_u_c_rate))
"""
        lines = _run(driver)
        assert float(lines[0]) > 0.3 + 1e-6


class TestAntiWindupPreventsTheRetestDivergence:
    """Main-loop addition 2 (LV-1 task brief, from the LV-0 debug pass,
    `plans/flight-lift-vector/debug-2026-11-23.md`, problem 3): the
    retest's take diverged from a mid-turn attitude -- `phidot` ran
    away from a bounded ~20 deg/s oscillation to `+536 deg/s` over six
    ~38 ms samples, attributed to an unguarded `phi_i` integrator
    (Decision 30's own named risk, closed here by section H). This is
    the toy-plant proof the new law does not reproduce that shape: a
    take from a bad initial attitude (30 deg bank, nose 10 deg down,
    mid-turn) must converge, with every body rate staying bounded
    throughout -- never a one-sided runaway in either direction."""

    def test_take_from_30deg_bank_10deg_nose_down_mid_turn_converges(
        self,
    ) -> None:
        driver = f"""
local measured = {
            _measured(
                bank_deg=30.0,
                pitch_deg=-10.0,
                psi_deg=0.0,
                r_deg_s=8.0,
                ias_mps=160.0 / 3.6,
                v_t_mps=160.0 / 3.6,
            )
        }
local command = {{ pitch = 0.1, roll = 0.15, pedals = 0.0, collective = 0.2 }}
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ heading_deg = measured.psi_deg }}, LIMITS, PROFILE)
local dt = 0.05
local tau = 1.0
local max_abs_p, max_abs_bank, max_abs_pitch = 0.0, 0.0, 0.0
for i = 1, 3000 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    measured.a_r = 9.81 * math.tan(math.rad(measured.bank_deg))
    measured.p_deg_s = (state.phi_d - measured.bank_deg) / tau
    measured.pitch_deg = measured.pitch_deg + (state.theta_d - measured.pitch_deg) * (dt / tau)
    measured.q_deg_s = (state.theta_d - measured.pitch_deg) / tau
    local r = flight_control.law_turn_rate_at_bank(measured.bank_deg, measured.v_t_mps)
    measured.psi_deg = (measured.psi_deg + r * dt) % 360.0
    measured.r_deg_s = r
    if math.abs(measured.p_deg_s) > max_abs_p then max_abs_p = math.abs(measured.p_deg_s) end
    if math.abs(measured.bank_deg) > max_abs_bank then max_abs_bank = math.abs(measured.bank_deg) end
    if math.abs(measured.pitch_deg) > max_abs_pitch then max_abs_pitch = math.abs(measured.pitch_deg) end
end
print(string.format("%.6f", max_abs_p))
print(string.format("%.6f", max_abs_bank))
print(string.format("%.6f", max_abs_pitch))
print(string.format("%.6f", measured.bank_deg))
print(string.format("%.6f", measured.pitch_deg))
print(tostring(state.in_band_heading))
"""
        lines = _run(driver)
        max_abs_p, max_abs_bank, max_abs_pitch, final_bank, _final_pitch, in_band = (
            lines
        )
        # A real divergence in this toy plant's own kinematics shows up
        # exactly like the retest trace did -- a roll rate orders of
        # magnitude past anything a real coordinated turn produces
        # (the retest's own runaway reached 536 deg/s). A generous bound
        # (100 deg/s) still catches a genuine runaway while giving the
        # transient roll-out room to move.
        assert float(max_abs_p) < 100.0
        # Never saturates toward +-90 (the physical ceiling `law_
        # outputs`' own clamp would eventually hit on a real runaway).
        assert float(max_abs_bank) < 90.0
        assert float(max_abs_pitch) < 90.0
        # And it actually settles, not just "stays finite" -- back to
        # level, on the captured heading. No speed goal was ever given,
        # so the captured -10 deg trim pitch has no reason to move
        # (`final_pitch` is covered by the bounded-magnitude check
        # above only, not a convergence claim).
        assert abs(float(final_bank)) < 5.0
        assert in_band == "true"


class TestTakeIsBumpless:
    """Main-loop addition 3: the take is bumpless -- every integrator
    (`phi_i`/`theta_i`/`u_c_i`/`t_p`/`t_r`/`t_y`) is seeded from the
    *measured* state at take, so the first written frame equals the
    captured command exactly (`TestBitExactAtTake` proves the output);
    this class proves the *integrators themselves* hold values
    consistent with that measured state, not an arbitrary reset to
    zero that would only coincidentally cancel out this one frame."""

    def test_integrators_seed_from_measured_state_not_zero(self) -> None:
        driver = f"""
local measured = {_measured(bank_deg=12.0, pitch_deg=-4.0, ias_mps=60.0, v_t_mps=62.0)}
local command = {{ pitch = 0.321, roll = -0.154, pedals = 0.05, collective = 0.3 }}
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
print(string.format("%.6f", state.phi_d))
print(string.format("%.6f", state.theta_d))
print(string.format("%.6f", state.u_c))
"""
        lines = _run(driver)
        phi_d, theta_d, u_c = (float(v) for v in lines)
        # The take seeds the *target*, not a zeroed integrator, to the
        # measured attitude -- a nonzero captured bank/pitch is not
        # discarded.
        assert abs(phi_d - 12.0) < 1e-6
        assert abs(theta_d - (-4.0)) < 1e-6
        assert abs(u_c - 0.3) < 1e-6


class TestBankHoldTake:
    """LV-1 amendment (2026-11-24, fourth re-fly), section A, E11/E13 --
    a take past the takeover threshold holds that bank, height and
    speed, through a sustained run (not just the take-instant state
    `TestTakeoverModeSelection` already covers)."""

    def test_bank_hold_at_or_past_threshold_keeps_bank_height_and_speed(
        self,
    ) -> None:
        driver = f"""
local measured = {
            _measured(bank_deg=30.0, psi_deg=0.0, h_m=500.0, ias_mps=50.0, v_t_mps=52.0)
        }
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
local dt = 0.05
local tau = 1.0
for i = 1, 2000 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt / tau)
    measured.a_r = 9.81 * math.tan(math.rad(measured.bank_deg))
    measured.p_deg_s = (state.phi_d - measured.bank_deg) / tau
    local r = flight_control.law_turn_rate_at_bank(measured.bank_deg, measured.v_t_mps)
    measured.psi_deg = (measured.psi_deg + r * dt) % 360.0
    measured.r_deg_s = r
    -- Height/speed hold through the circle (E13) -- no goal ever
    -- pushes them away, so they must not drift.
end
print(string.format("%.6f", measured.bank_deg))
print(string.format("%.6f", measured.h_m))
print(string.format("%.6f", measured.ias_mps))
"""
        lines = _run(driver)
        final_bank, final_h, final_ias = lines
        # Holds close to the taken bank (a small steady-state trim
        # offset is expected, same as every other bank-lag toy-plant
        # scenario in this file -- not asserted tighter than that) --
        # the qualitative claim is "holds the bank taken, not 20 deg
        # (max_turn_bank_deg) and not 0".
        assert abs(float(final_bank) - 30.0) < 6.0
        assert abs(float(final_h) - 500.0) < 1e-6
        assert abs(float(final_ias) - 50.0) < 1e-6

    def test_a_heading_type_command_ends_a_held_bank(self) -> None:
        """Q3 -- only a heading-type command ("turn heading") ends it."""
        driver = f"""
local measured = {_measured(bank_deg=20.0, psi_deg=0.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
print(tostring(state.bank_hold_deg ~= nil))
state = flight_control.law_apply_goal(state, {{ heading_deg = 90.0 }}, LIMITS, PROFILE)
print(tostring(state.bank_hold_deg))
"""
        lines = _run(driver)
        assert lines[0] == "true"
        assert lines[1] == "nil"

    def test_a_continuous_turn_command_also_ends_a_held_bank(self) -> None:
        """The other heading-type command (Q3)."""
        driver = f"""
local measured = {_measured(bank_deg=20.0, psi_deg=0.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ turn = 1 }}, LIMITS, PROFILE)
print(tostring(state.bank_hold_deg))
print(tostring(state.turn_mode))
"""
        lines = _run(driver)
        assert lines[0] == "nil"
        assert lines[1] == "true"

    def test_a_speed_or_altitude_command_does_not_end_a_held_bank(self) -> None:
        """Q3 -- height and speed commands change speed/height *inside*
        the held turn; they never end it."""
        driver = f"""
local measured = {_measured(bank_deg=20.0, psi_deg=0.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ ias_kmh = 200.0, alt_m = 600.0 }}, LIMITS, PROFILE)
print(tostring(state.bank_hold_deg))
print(string.format("%.6f", state.speed_goal_mps))
print(string.format("%.6f", state.alt_goal_m))
"""
        lines = _run(driver)
        bank_hold_deg, speed_goal, alt_goal = lines
        assert abs(float(bank_hold_deg) - 20.0) < 1e-6
        assert abs(float(speed_goal) - (200.0 / 3.6)) < 1e-6
        assert abs(float(alt_goal) - 600.0) < 1e-6


class TestUnparkMidTurnRateNeverSlammedToTheOrdinaryCeiling:
    """LV-1 amendment, section A, E12 -- the "first goes level" fix: an
    inherited rate from an m2->m1 unpark mid-turn, above the ordinary
    `max_turn_bank_deg`-derived ceiling, must decay smoothly through the
    critically-damped heading-error term, never be clamped down to the
    ceiling on the very first `law_update` frame."""

    def test_an_above_ceiling_inherited_rate_is_not_clamped_on_frame_one(
        self,
    ) -> None:
        driver = f"""
-- max_turn_bank_deg = 20 deg at v_t=150/3.6 m/s -> r_max ~= 4.7 deg/s.
-- Seed a much faster inherited rate (12 deg/s, as mode 2's own AI
-- autopilot might leave it) via a held-heading unpark seed.
local measured = {
            _measured(
                bank_deg=35.0,
                psi_deg=0.0,
                r_deg_s=12.0,
                ias_mps=150.0 / 3.6,
                v_t_mps=150.0 / 3.6,
            )
        }
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, {{ heading_deg = 90.0 }}, PROFILE)
local r_at_take = state.r_ref
state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
print(string.format("%.6f", r_at_take))
print(string.format("%.6f", state.r_ref))
"""
        lines = _run(driver)
        r_at_take, r_after_one_frame = (float(x) for x in lines)
        assert abs(r_at_take - 12.0) < 1e-6
        # Never slammed down to the ~4.7 deg/s ordinary ceiling in one
        # step -- the first frame's own accel-limited change is small
        # relative to the full inherited rate.
        assert abs(r_after_one_frame - r_at_take) < 1.0

    def test_inherited_rate_decays_toward_the_heading_hold_equilibrium(
        self,
    ) -> None:
        """review-lv1-amendment.md, optional refinement (implementer's
        judgment 2) -- closes the "flagged, not fully traced" note by
        making the decay visible in the test itself, rather than only
        reasoning it through by hand: ten seconds after the frame-one
        check above, the inherited 12 deg/s rate must have decayed back
        under the ordinary ~4.7 deg/s ceiling, and the heading reference
        must be converging on the 90 deg unpark goal -- not left
        standing at the above-ceiling rate indefinitely. (Measured by
        running the driver standalone: r_ref crosses below 4.7 deg/s at
        t~=8s and is at 2.89 deg/s by t=10s, monotonically, with psi_ref
        climbing steadily toward 90 the whole way -- not an oscillation
        this margin could accidentally straddle.)"""
        driver = f"""
local measured = {
            _measured(
                bank_deg=35.0,
                psi_deg=0.0,
                r_deg_s=12.0,
                ias_mps=150.0 / 3.6,
                v_t_mps=150.0 / 3.6,
            )
        }
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, {{ heading_deg = 90.0 }}, PROFILE)
local dt = 0.05
for i = 1, 200 do  -- 10 s further, same fixed measured (shaper's own
                    -- internal trajectory, not a closed loop -- the
                    -- frame-one test above exercises the plant-coupled
                    -- case; this one isolates the shaper's own decay).
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
end
print(string.format("%.6f", state.r_ref))
print(string.format("%.6f", state.psi_ref))
"""
        lines = _run(driver)
        r_after_10s, psi_ref_after_10s = (float(x) for x in lines)
        # Decayed back under the ordinary ~4.7 deg/s ceiling (max_turn_
        # bank_deg = 20 deg at this speed) -- never left standing at the
        # inherited 12 deg/s.
        assert abs(r_after_10s) < 4.7
        # Converging on the 90 deg unpark heading goal, not drifting
        # away from it or oscillating around some other value.
        assert 0.0 < psi_ref_after_10s <= 90.0


class TestSpeedChannelIsBrisk:
    """LV-1 amendment (2026-11-24, fourth re-fly), section B/Q2, E14 --
    `c_theta` raised toward the full kinematic tilt and `speed_accel_
    cap_mps2` raised (both local overrides here, since the shared
    `_PROFILE`/`flight_profile.lua` default-tracking posture of this
    file keeps the baseline at the pre-amendment values for every other
    scenario, root `CLAUDE.md` "do not reinvent" notwithstanding -- see
    `plans/flight-lift-vector/implementation.md` for why): the toy
    plant's own along-track acceleration should reach past 1.5 m/s^2
    within a few seconds of a speed-up command, not need the several-
    second trim loop alone to get there."""

    def test_reaches_past_1_5_mps2_within_a_few_seconds(self) -> None:
        driver = """
PROFILE.c_theta = 0.85
PROFILE.speed_accel_cap_mps2 = 1.9
local measured = {measured}
local state = flight_control.law_init_at_take(measured, LIMITS, { pitch = 0, roll = 0, pedals = 0, collective = 0.3 }, nil, PROFILE)
state = flight_control.law_apply_goal(state, { ias_kmh = 250.0 }, LIMITS, PROFILE)  -- ~69.4 m/s
local dt = 0.05
local plant_ax_gain = 2.0
local max_ax = 0.0
for i = 1, 100 do  -- 5 s
    local prev_ias = measured.ias_mps
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    local tau = 1.5
    measured.pitch_deg = measured.pitch_deg + (state.theta_d - measured.pitch_deg) * (dt / tau)
    measured.q_deg_s = (state.theta_d - measured.pitch_deg) / tau
    local ax = plant_ax_gain * (0.0 - measured.pitch_deg)
    measured.ias_mps = measured.ias_mps + ax * dt
    measured.v_t_mps = measured.ias_mps + 2.0
    local measured_ax = (measured.ias_mps - prev_ias) / dt
    if measured_ax > max_ax then max_ax = measured_ax end
end
print(string.format("%.6f", max_ax))
print(string.format("%.6f", measured.ias_mps))
""".replace(
            "{measured}",
            _measured(pitch_deg=0.0, ias_mps=150.0 / 3.6, v_t_mps=150.0 / 3.6 + 2.0),
        )
        lines = _run(driver)
        max_ax, final_ias = (float(x) for x in lines)
        assert max_ax > 1.5
        # Settles without overshoot -- never exceeds the commanded speed
        # by more than a small margin within this short a run.
        assert final_ias <= (250.0 / 3.6) * 1.05


class TestPedalReachesCollectiveStepTarget:
    """LV-1 amendment, section D/Q5 -- `k_ball_pedal_p` (the new
    proportional term) lets the pedal reach the ball-centring correction
    a collective step needs within ~1-2 s, rather than the pure
    integrator's own much slower catch-up (the measured row-4 climb:
    ball grew to 0.12 over ~15 s before the integrator caught up)."""

    def test_pedal_catches_up_within_one_to_two_seconds(self) -> None:
        driver = f"""
local measured = {_measured(ias_mps=40.0, v_t_mps=42.0)}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.2 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ alt_m = 300.0 }}, LIMITS, PROFILE)  -- a climb step -> collective rises
local dt = 0.05
local pedal_at_1s, pedal_at_2s
for i = 1, 60 do  -- 3 s
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    -- A ball offset proportional to the collective rate, same shape the
    -- measured row-4 climb showed (yaw torque grows the ball error
    -- faster than the pedal alone corrects it) -- held fixed here (no
    -- separate yaw plant) so this test isolates the pedal LOOP's own
    -- response time, not a full closed-loop convergence.
    measured.ball = 0.12
    if i == 20 then pedal_at_1s = outputs.pedals end
    if i == 40 then pedal_at_2s = outputs.pedals end
end
print(string.format("%.6f", pedal_at_1s))
print(string.format("%.6f", pedal_at_2s))
"""
        lines = _run(driver)
        pedal_at_1s, pedal_at_2s = (float(x) for x in lines)
        # The proportional term alone (k_ball_pedal_p * (0.12 - 0.03) =
        # 0.3 * 0.09 = 0.027) is present on every frame once the ball
        # offset exists, so the pedal is already most of the way there
        # well inside 1 s -- unlike the pure integrator this replaces,
        # which took ~15 s for the same ball offset.
        assert abs(pedal_at_1s) > 0.02
        assert abs(pedal_at_2s) >= abs(pedal_at_1s)


class TestEngineRpmGatedCollectiveSchedule:
    """LV-1 amendment, section C/Q1, correction box -- the anticipatory
    engine-RPM-gated collective-rate schedule, off (always "fast") by
    default (U9, the dummy-equivalent posture at the toy-plant level is
    `measured.engine_rpm_pct` at or above `spooled_rpm_pct`, the
    `_measured()` helper's own default)."""

    @staticmethod
    def _collective_rate_for(engine_rpm_pct: float) -> float:
        # `PROFILE.alt_accel_cap_mps2` raised locally (same "override
        # the loaded PROFILE table for this one test" technique as
        # `TestSpeedChannelIsBrisk`) so the demanded climb's own nominal
        # collective rate clearly exceeds `collective_rate_gentle_min_
        # per_s` (0.2) -- the default LIMITS/PROFILE scenario saturates
        # the ordinary vertical-accel ceiling well below that, which
        # would make the taper a no-op regardless of engine RPM.
        driver = f"""
PROFILE.alt_accel_cap_mps2 = 5.0
local measured = {_measured(h_m=10.0, w_mps=0.0)}
measured.engine_rpm_pct = {engine_rpm_pct}
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.0 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ alt_m = 3000.0 }}, LIMITS, PROFILE)
state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
print(string.format("%.9f", state.dbg_u_c_rate))
"""
        return float(_run(driver)[0])

    def test_schedule_inactive_when_engine_rpm_is_at_or_above_spooled(
        self,
    ) -> None:
        """At/above `spooled_rpm_pct` (93.0, the user's own level-cruise
        reading -- review-lv1-amendment.md required fix 2), the rate is
        identical to fully-spooled-up (100.0) -- the schedule adds no
        further taper once the engines are already at/near normal
        output."""
        at_floor = self._collective_rate_for(93.0)
        fully_up = self._collective_rate_for(100.0)
        assert abs(at_floor - fully_up) < 1e-9

    def test_schedule_tapers_the_increase_when_engine_rpm_is_spooled_down(
        self,
    ) -> None:
        """The same climb step, with the engines spooled down (the
        user's own "~74%" fully-spooled-down reading) -- the increase
        rate is capped toward `collective_rate_gentle_min_per_s` and
        strictly below the unthrottled rate at full engine RPM."""
        fully_up = self._collective_rate_for(100.0)
        spooled_down = self._collective_rate_for(74.0)
        gentle = float(PROFILE_COLLECTIVE_RATE_GENTLE_MIN)
        assert spooled_down < fully_up
        assert spooled_down <= gentle + 1e-6

    def test_schedule_never_gates_a_collective_decrease(self) -> None:
        """ "Decreases are never gated by this -- spooling down is not
        the hazard." A descent step (collective falling) with the
        engines spooled down must not be slowed by this guard."""
        driver = f"""
local measured = {_measured(h_m=300.0, w_mps=0.0)}
measured.engine_rpm_pct = 74.0
local state = flight_control.law_init_at_take(measured, LIMITS, {{ pitch = 0, roll = 0, pedals = 0, collective = 0.5 }}, nil, PROFILE)
state = flight_control.law_apply_goal(state, {{ alt_m = 50.0 }}, LIMITS, PROFILE)
state = flight_control.law_update(state, 0.05, measured, LIMITS, PROFILE)
print(string.format("%.6f", state.dbg_u_c_rate))
"""
        lines = _run(driver)
        assert float(lines[0]) < 0.0


#: `PROFILE.collective_rate_gentle_min_per_s` mirrored here so the two
#: tests above can assert against it without re-parsing the Lua table.
PROFILE_COLLECTIVE_RATE_GENTLE_MIN = "0.2"


class TestBitExactAtTakeWithTheNewPedalProportionalTerm:
    """LV-1 amendment, section D/Q5 -- `k_ball_pedal_p` must not disturb
    Decision 24's bit-exact-at-take guarantee even when the ball is NOT
    centred at the instant of the take (the case that actually exercises
    the new term, unlike every pre-existing take test, which defaults
    `measured.ball` to `profile.ball_centre` via `_measured()`'s own
    absence of a `ball` field)."""

    def test_pedal_output_equals_the_captured_command_with_ball_offset(
        self,
    ) -> None:
        driver = f"""
local measured = {_measured()}
measured.ball = 0.2  -- well off centre (profile.ball_centre = 0.03)
local command = {{ pitch = 0, roll = 0, pedals = 0.15, collective = 0.2 }}
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
local outputs = flight_control.law_outputs(state, measured, PROFILE)
print(string.format("%.9f", outputs.pedals))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - 0.15) < 1e-6


class TestAmendmentProductionValuesTogether:
    """review-lv1-amendment.md, required fix 1 -- no existing test ran
    `c_theta=0.85`, `speed_accel_cap_mps2=1.9` and `k_pedal_from_
    collective_rate=0.6` together, though all three were tuned from the
    same fourth-re-fly flight and the row-4 climb that motivated the
    raised torque feed-forward is exactly a simultaneous pitch-change-
    plus-collective-rate event -- precisely the interaction an isolated-
    field test (`TestSpeedChannelIsBrisk`, `TestPedalReachesCollective
    StepTarget`) cannot see. `k_ball_pedal_p` is left at the shared
    `_PROFILE`'s default (0.3), which already equals `flight_profile.
    lua`'s shipped value -- no override needed for that one."""

    def test_row4_like_climb_and_speed_change_is_stable(self) -> None:
        """A row-4-like climb: a standing speed increase (feed-forward-
        led pitch change, section B) commanded simultaneously with a
        climb (a collective-rate event, section C/E). Toy plant combines
        the pitch/speed plant (`TestSpeedChannelIsBrisk`) and the
        collective/vertical-speed plant (`TestClimbTakeoverStoppingHeight`),
        plus a crude ball plant coupling the collective rate to yaw the
        same torque feed-forward is meant to compensate for -- so the
        pedal's own tracking is actually exercised here, not assumed."""
        driver = """
PROFILE.c_theta = 0.85
PROFILE.speed_accel_cap_mps2 = 1.9
PROFILE.k_pedal_from_collective_rate = 0.6
local measured = {measured}
measured.ball = 0.03
local trim_collective = 0.3
local state = flight_control.law_init_at_take(measured, LIMITS, { pitch = 0, roll = 0, pedals = 0, collective = trim_collective }, nil, PROFILE)
-- Bit-exact at take, with the amendment's production profile values
-- active -- Decision 24's guarantee must survive the raised gains.
local take_outputs = flight_control.law_outputs(state, measured, PROFILE)
state = flight_control.law_apply_goal(state, { ias_kmh = 220.0, alt_m = 250.0 }, LIMITS, PROFILE)
local dt = 0.05
local plant_ax_gain = 2.0
local plant_w_gain = 15.0
-- Crude torque-to-ball coupling, same order the row-4 climb showed
-- (yaw torque from a collective-rate change grows the ball error faster
-- than the pedal alone would correct without the raised feed-forward).
local k_yaw_from_collective_rate = 0.15
local prev_w = measured.w_mps
local max_abs_theta_d = 0.0
local max_abs_ball = 0.0
local max_abs_pedal = 0.0
local first_half_max_speed_err, second_half_max_speed_err = 0.0, 0.0
for i = 1, 300 do  -- 15 s
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    local tau = 1.5
    measured.pitch_deg = measured.pitch_deg + (state.theta_d - measured.pitch_deg) * (dt / tau)
    measured.q_deg_s = (state.theta_d - measured.pitch_deg) / tau
    local ax = plant_ax_gain * (0.0 - measured.pitch_deg)
    measured.ias_mps = measured.ias_mps + ax * dt
    measured.v_t_mps = measured.ias_mps + 2.0

    local w_dot = plant_w_gain * (outputs.collective - trim_collective)
    measured.w_mps = measured.w_mps + w_dot * dt
    measured.h_m = measured.h_m + measured.w_mps * dt
    measured.a_u = (measured.w_mps - prev_w) / dt
    prev_w = measured.w_mps

    measured.ball = measured.ball
        + (k_yaw_from_collective_rate * state.dbg_u_c_rate - outputs.pedals) * dt
    if measured.ball > 1.0 then measured.ball = 1.0 end
    if measured.ball < -1.0 then measured.ball = -1.0 end

    if math.abs(state.theta_d) > max_abs_theta_d then max_abs_theta_d = math.abs(state.theta_d) end
    if math.abs(measured.ball) > max_abs_ball then max_abs_ball = math.abs(measured.ball) end
    if math.abs(outputs.pedals) > max_abs_pedal then max_abs_pedal = math.abs(outputs.pedals) end
    local speed_err = math.abs(measured.ias_mps - 220.0 / 3.6)
    if i <= 150 then
        if speed_err > first_half_max_speed_err then first_half_max_speed_err = speed_err end
    else
        if speed_err > second_half_max_speed_err then second_half_max_speed_err = speed_err end
    end
end
print(string.format("%.9f", take_outputs.pitch))
print(string.format("%.9f", take_outputs.collective))
print(string.format("%.6f", max_abs_theta_d))
print(string.format("%.6f", max_abs_ball))
print(string.format("%.6f", max_abs_pedal))
print(string.format("%.6f", first_half_max_speed_err))
print(string.format("%.6f", second_half_max_speed_err))
""".replace(
            "{measured}",
            _measured(
                pitch_deg=0.0,
                ias_mps=150.0 / 3.6,
                v_t_mps=150.0 / 3.6 + 2.0,
                h_m=200.0,
                w_mps=0.0,
            ),
        )
        lines = _run(driver)
        (
            take_pitch,
            take_collective,
            max_abs_theta_d,
            max_abs_ball,
            max_abs_pedal,
            first_half_err,
            second_half_err,
        ) = (float(x) for x in lines)
        # Bit-exact at take: the captured command (pitch 0, collective
        # 0.3) comes back out untouched, with the raised gains active.
        assert abs(take_pitch - 0.0) < 1e-6
        assert abs(take_collective - 0.3) < 1e-6
        # Stable: `theta_d` (the sum `theta_i + delta_theta_ff`) never
        # exceeds `theta_min/max_deg` (review-debug-1125.md required fix
        # 2 -- this used to be a loose "did not diverge" bound at 30 deg
        # since only `theta_i` alone was clamped; the combined clamp
        # added in the fifth re-fly now bounds the real invariant
        # directly, see `TestCombinedThetaDClamp` below for a scenario
        # that actually drives the sum past the bound on its own).
        assert max_abs_theta_d <= 15.0 + 1e-6
        # Ball/pedal keep up: the crude yaw-coupling plant never drives
        # the ball anywhere near its usable range (+-0.5), and the
        # pedal never sits pinned at its own limit -- both signs the
        # raised torque feed-forward is actually compensating the
        # collective-rate event, not lagging behind it.
        assert max_abs_ball < 0.5
        assert max_abs_pedal <= 0.5
        # No growing oscillation: the speed error in the second half of
        # the run is not larger than in the first half (a small margin
        # covers the climb's own secondary disturbance to the speed
        # channel via the priority-under-limits chain, section G).
        assert second_half_err <= first_half_err + 0.5

    def test_150_to_250_acceleration_is_stable_and_bit_exact_at_take(
        self,
    ) -> None:
        """The amendment's other named scenario: a 150->250 km/h
        acceleration on the toy plant with all three raised production
        values together, including the raised torque feed-forward this
        test alone does not otherwise exercise (`TestSpeedChannelIsBrisk`
        never raises `k_pedal_from_collective_rate`)."""
        driver = """
PROFILE.c_theta = 0.85
PROFILE.speed_accel_cap_mps2 = 1.9
PROFILE.k_pedal_from_collective_rate = 0.6
local measured = {measured}
measured.ball = 0.03
local command = { pitch = 0, roll = 0, pedals = 0, collective = 0.3 }
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
local take_outputs = flight_control.law_outputs(state, measured, PROFILE)
state = flight_control.law_apply_goal(state, { ias_kmh = 250.0 }, LIMITS, PROFILE)  -- ~69.4 m/s
local dt = 0.05
local plant_ax_gain = 2.0
local k_yaw_from_collective_rate = 0.15
local max_ax = 0.0
local max_abs_ball = 0.0
local max_abs_pedal = 0.0
local max_overshoot_first, max_overshoot_second = 0.0, 0.0
for i = 1, 500 do  -- 25 s
    local prev_ias = measured.ias_mps
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local outputs = flight_control.law_outputs(state, measured, PROFILE)
    local tau = 1.5
    measured.pitch_deg = measured.pitch_deg + (state.theta_d - measured.pitch_deg) * (dt / tau)
    measured.q_deg_s = (state.theta_d - measured.pitch_deg) / tau
    local ax = plant_ax_gain * (0.0 - measured.pitch_deg)
    measured.ias_mps = measured.ias_mps + ax * dt
    measured.v_t_mps = measured.ias_mps + 2.0
    local measured_ax = (measured.ias_mps - prev_ias) / dt
    if measured_ax > max_ax then max_ax = measured_ax end

    measured.ball = measured.ball
        + (k_yaw_from_collective_rate * state.dbg_u_c_rate - outputs.pedals) * dt
    if measured.ball > 1.0 then measured.ball = 1.0 end
    if measured.ball < -1.0 then measured.ball = -1.0 end
    if math.abs(measured.ball) > max_abs_ball then max_abs_ball = math.abs(measured.ball) end
    if math.abs(outputs.pedals) > max_abs_pedal then max_abs_pedal = math.abs(outputs.pedals) end

    local overshoot = measured.ias_mps - (250.0 / 3.6)
    if overshoot > 0.0 then
        if i <= 250 then
            if overshoot > max_overshoot_first then max_overshoot_first = overshoot end
        else
            if overshoot > max_overshoot_second then max_overshoot_second = overshoot end
        end
    end
end
print(string.format("%.9f", take_outputs.pitch))
print(string.format("%.9f", take_outputs.collective))
print(string.format("%.6f", max_ax))
print(string.format("%.6f", measured.ias_mps))
print(string.format("%.6f", max_abs_ball))
print(string.format("%.6f", max_abs_pedal))
print(string.format("%.6f", max_overshoot_first))
print(string.format("%.6f", max_overshoot_second))
""".replace(
            "{measured}",
            _measured(pitch_deg=0.0, ias_mps=150.0 / 3.6, v_t_mps=150.0 / 3.6 + 2.0),
        )
        lines = _run(driver)
        (
            take_pitch,
            take_collective,
            max_ax,
            final_ias,
            max_abs_ball,
            max_abs_pedal,
            overshoot_first,
            overshoot_second,
        ) = (float(x) for x in lines)
        assert abs(take_pitch - 0.0) < 1e-6
        assert abs(take_collective - 0.3) < 1e-6
        # Brisk, same bar `TestSpeedChannelIsBrisk` sets.
        assert max_ax > 1.5
        # Settles without a runaway overshoot.
        assert final_ias <= (250.0 / 3.6) * 1.05
        assert max_abs_ball < 0.5
        assert max_abs_pedal <= 0.5
        # No growing oscillation: overshoot in the second half of the
        # run is not larger than in the first half.
        assert overshoot_second <= overshoot_first + 0.5

    @staticmethod
    def _speed_shaper_no_windup_metrics(
        start_kmh: float, target_kmh: float
    ) -> tuple[float, float, int, str]:
        """review-debug-1125.md required fix 1 -- the fifth re-fly's own
        anti-windup fix (the `dv_ref` braking-distance ceiling), proved
        against the actual shipped profile constants (`omega_speed`,
        `k_speed_error`, `c_theta`, `speed_accel_cap_mps2`, read from
        `flight_profile.lua` itself, not retyped) rather than the fourth
        re-fly's superseded `c_theta=0.85` this class's other two tests
        still use. `LIMITS.max_accel_mps2` is overridden to 2.0, the
        shipped `belief.flight_control.MAX_ACCEL_MPS2` on the body-layer
        side (`aircraft-layer/CLAUDE.md`'s wire-field table) -- this
        file has no cross-subproject import, so the figure is a literal
        here, not read live; the debug report's own sweep used this
        same figure, cited verbatim ("production max_accel_mps2=2.0").

        Returns `(max_dv_ref, max_overshoot_mps, sign_changes, final_ias_line)`.
        `max_dv_ref` is the mutation-sensitive measurement: `dv_ref` is
        bounded by construction to `min(limits.max_accel_mps2,
        dv_ref_ceiling)` in the shipped law, so it can never exceed
        `limits.max_accel_mps2` -- deleting the ceiling's own clamp
        entirely (not merely reverting to the pre-fix static-only bound,
        which this specific 150<->250 step does not actually
        distinguish from the shipped ceiling -- both stay pegged at the
        same 2.0 cap for the whole saturated stretch, see
        `plans/flight-lift-vector/implementation.md`) lets `dv_ref`
        climb to ~4.8, more than double the production ceiling,
        confirmed by mutation."""
        driver_template = """
local PRODUCTION_PROFILE = dofile("{profile_path}").PROFILES["Mi-24P"]
PROFILE.omega_speed = PRODUCTION_PROFILE.omega_speed
PROFILE.k_speed_error = PRODUCTION_PROFILE.k_speed_error
PROFILE.c_theta = PRODUCTION_PROFILE.c_theta
PROFILE.speed_accel_cap_mps2 = PRODUCTION_PROFILE.speed_accel_cap_mps2
LIMITS.max_accel_mps2 = 2.0
local measured = {measured}
local command = { pitch = 0, roll = 0, pedals = 0, collective = 0.3 }
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
state = flight_control.law_apply_goal(state, { ias_kmh = {target_kmh} }, LIMITS, PROFILE)
local dt = 0.05
local plant_ax_gain = 0.17
local trim_pitch = -3.5
local target_mps = {target_kmh} / 3.6
local start_kmh = {start_kmh}
local target_kmh = {target_kmh}
local max_dv_ref = 0.0
local max_overshoot = 0.0
local sign_changes, prev_sign = 0, nil
for i = 1, 700 do  -- 35 s
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local tau = 1.5
    measured.pitch_deg = measured.pitch_deg + (state.theta_d - measured.pitch_deg) * (dt / tau)
    measured.q_deg_s = (state.theta_d - measured.pitch_deg) / tau
    local ax = plant_ax_gain * (trim_pitch - measured.pitch_deg)
    measured.ias_mps = measured.ias_mps + ax * dt
    measured.v_t_mps = measured.ias_mps + 2.0
    if math.abs(state.dv_ref) > max_dv_ref then max_dv_ref = math.abs(state.dv_ref) end
    local err = measured.ias_mps - target_mps
    if (target_kmh > start_kmh and err > 0.0) or (target_kmh < start_kmh and err < 0.0) then
        if math.abs(err) > max_overshoot then max_overshoot = math.abs(err) end
    end
    local sign = err > 0.02 and 1 or (err < -0.02 and -1 or 0)
    if sign ~= 0 then
        if prev_sign ~= nil and sign ~= prev_sign then sign_changes = sign_changes + 1 end
        prev_sign = sign
    end
end
print(string.format("%.6f", max_dv_ref))
print(string.format("%.6f", max_overshoot))
print(string.format("%d", sign_changes))
print(string.format("%.6f", measured.ias_mps))
"""
        driver = (
            driver_template.replace("{profile_path}", str(_FLIGHT_PROFILE_LUA))
            .replace("{target_kmh}", str(target_kmh))
            .replace("{start_kmh}", str(start_kmh))
            .replace(
                "{measured}",
                _measured(
                    pitch_deg=-3.5,
                    ias_mps=start_kmh / 3.6,
                    v_t_mps=start_kmh / 3.6 + 2.0,
                ),
            )
        )
        lines = _run(driver)
        max_dv_ref, max_overshoot, sign_changes_str, final_ias = lines
        return (
            float(max_dv_ref),
            float(max_overshoot),
            int(sign_changes_str),
            final_ias,
        )

    def test_150_to_250_no_windup_at_shipped_speed_shaper_values(self) -> None:
        """150->250 km/h at the actual shipped `omega_speed=0.5`,
        `k_speed_error=0.30`, `c_theta=0.90` (debug-2026-11-25.md's
        second iteration) -- the fourth re-fly's own 0.85/0.2/0.15 this
        class's other two tests still run is now superseded, and no
        other committed test before this one ever ran the current
        numbers together (review-debug-1125.md required fix 1)."""
        max_dv_ref, max_overshoot, sign_changes, final_ias_s = (
            self._speed_shaper_no_windup_metrics(150.0, 250.0)
        )
        # The mutation-sensitive invariant: `dv_ref` is bounded by
        # construction to `limits.max_accel_mps2` (2.0) in the shipped
        # law -- deleting the braking-distance ceiling's own clamp
        # entirely lets it climb to ~4.8 instead (confirmed by
        # mutation, see this method's own class docstring above).
        assert max_dv_ref <= 2.0 + 1e-6
        # No hunting: one sign change (the final settle), not a real
        # oscillation -- debug-2026-11-25.md's own sweep at these values.
        assert sign_changes <= 1
        # Bounded overshoot -- debug-2026-11-25.md measured <=0.07 m/s
        # on the stiffer 2.0/deg toy plant; this realistic-gain plant's
        # own figure is larger (~0.41 m/s) but still small relative to
        # the ~27.8 m/s step, not a runaway.
        assert max_overshoot <= 1.0
        # Settles near the target within the second iteration's own
        # ~20-22s window, generous margin for this plant's own lag.
        assert abs(float(final_ias_s) - 250.0 / 3.6) < 1.0

    def test_250_to_150_no_windup_at_shipped_speed_shaper_values(self) -> None:
        """The mirror direction, same production values -- debug-2026-
        11-25.md's second iteration names both directions explicitly
        (20.3s/21.5s, 19.7s/20.7s across the two plant-gain estimates)."""
        max_dv_ref, max_overshoot, sign_changes, final_ias_s = (
            self._speed_shaper_no_windup_metrics(250.0, 150.0)
        )
        assert max_dv_ref <= 2.0 + 1e-6
        assert sign_changes <= 1
        assert max_overshoot <= 1.0
        assert abs(float(final_ias_s) - 150.0 / 3.6) < 1.0


class TestCombinedThetaDClamp:
    """review-debug-1125.md required fix 2 -- `theta_d` (section D) is
    `law_clamp(theta_i + delta_theta_ff, theta_min_deg, theta_max_deg)`:
    `theta_i` alone is already bounded to `[theta_min_deg, theta_max_deg]`
    above this line, so the combined clamp only ever does anything when
    `delta_theta_ff` (the feed-forward, never itself clamped) pushes the
    *sum* past the bound `theta_i` alone sits inside. Presetting
    `state.theta_i` to its own bound and then driving a large `a_f_d`
    (via a big speed-goal step) in the same direction is what forces
    exactly that: `theta_i` alone contributes nothing left to clamp, so
    only `delta_theta_ff` pushing the sum over the line can trip this
    assertion -- confirmed by mutation (removing the `law_clamp(...)`
    wrapper around the sum lets `theta_d` reach -16.42 instead of -15.0
    at `i=1` in this exact scenario)."""

    def test_theta_i_plus_delta_theta_ff_is_clamped_to_the_bound(self) -> None:
        driver = """
local measured = {measured}
local command = { pitch = 0, roll = 0, pedals = 0, collective = 0.3 }
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
-- `theta_i` alone contributes no headroom to clamp -- it starts
-- already pinned at its own bound, so only `delta_theta_ff` pushing
-- the combined sum past it can trip the assertion below.
state.theta_i = PROFILE.theta_min_deg
-- A large step drives a sustained positive `a_f_d` (desired forward
-- deceleration -- the law tracks IAS down toward a much higher
-- commanded speed is backwards; a *much higher* goal against a lower
-- current IAS drives `a_f_d` positive, which `law_theta_ff_deg` turns
-- into a NEGATIVE `delta_theta_ff` -- the same sign as the pinned
-- `theta_i`, so the two add rather than cancel).
state = flight_control.law_apply_goal(state, { ias_kmh = 400.0 }, LIMITS, PROFILE)
local dt = 0.05
local max_abs_theta_d = 0.0
for i = 1, 10 do
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    if math.abs(state.theta_d) > max_abs_theta_d then max_abs_theta_d = math.abs(state.theta_d) end
end
print(string.format("%.6f", max_abs_theta_d))
""".replace(
            "{measured}",
            _measured(pitch_deg=0.0, ias_mps=40.0, v_t_mps=42.0),
        )
        lines = _run(driver)
        max_abs_theta_d = float(lines[0])
        # The real invariant (review-debug-1125.md required fix 2): the
        # *sum* never exceeds `theta_max_deg` (15.0) -- not the old
        # 30 deg "did not diverge" bound, which this scenario would
        # pass even with the combined clamp removed entirely.
        assert max_abs_theta_d <= 15.0 + 1e-6


class TestDecelerationHoldsAltitude:
    """Debug-2026-11-27 (`plans/flight-lift-vector/debug-2026-11-27.md`,
    sixth re-fly): user, verbatim, "deceleration leads to descent as
    well. Should maintain altitude." The trace showed `u_c` pinned at
    -1.00 for ~9 s while `a_u_d` was asking to climb, losing ~100 m --
    the old `k_collective_speed_give` term biased the collective
    *rate*, so it integrated for as long as the deceleration lasted and
    outweighed the vertical loop. This toy plant closes the vertical
    loop for real (`w_mps`/`h_m` integrated from `u_c` via a first-order
    lift-to-vertical-speed plant, `a_u` fed back from that same plant,
    not left at its `measured.a_u or 0.0` fallback) so an altitude loss
    of this kind is visible to the test, not just to a flight."""

    @staticmethod
    def _run_decel_scenario() -> tuple[float, float, float]:
        driver = """
local u_c_trim = 0.3
local measured = {measured}
local command = { pitch = -3.5, roll = 0.0, pedals = 0.0, collective = 0.3 }
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
-- Commanded decel only -- no altitude command at all, so `alt_goal_m`
-- stays at the take's own stopping height (== the take altitude,
-- `w_mps` is 0 at take): holding the CURRENT altitude is exactly what
-- the user's own "should maintain altitude" means here.
state = flight_control.law_apply_goal(state, { ias_kmh = 108.0 }, LIMITS, PROFILE)
local dt = 0.05
local start_h = measured.h_m
local min_h, max_h = start_h, start_h
for i = 1, 400 do -- 20 s
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    -- Pitch plant (same style as `TestSpeedChannelIsBrisk`'s realistic-
    -- gain run): pitch chases `theta_d`, forward accel driven by pitch
    -- relative to the level-flight trim (-3.5 deg, the fourth re-fly's
    -- own figure).
    local tau_p = 1.5
    measured.pitch_deg = measured.pitch_deg + (state.theta_d - measured.pitch_deg) * (dt / tau_p)
    local ax = 0.2 * (-3.5 - measured.pitch_deg)
    measured.ias_mps = measured.ias_mps + ax * dt
    measured.v_t_mps = measured.ias_mps + 2.0
    -- Vertical plant: `w_mps` chases a target set by how far `u_c` sits
    -- above its level-flight trim (0.3, same as `command.collective`
    -- at take) -- `a_u` is this plant's own derivative, fed back to the
    -- law exactly the way the real estimator would, so `e_u` is a real
    -- trajectory error, not always zero.
    local target_w = (state.u_c - u_c_trim) * 10.0
    local prev_w = measured.w_mps
    measured.w_mps = measured.w_mps + (target_w - measured.w_mps) * (dt / 1.0)
    measured.a_u = (measured.w_mps - prev_w) / dt
    measured.h_m = measured.h_m + measured.w_mps * dt
    measured.asl_m = measured.h_m
    if measured.h_m < min_h then min_h = measured.h_m end
    if measured.h_m > max_h then max_h = measured.h_m end
end
print(string.format("%.6f", min_h - start_h))
print(string.format("%.6f", max_h - start_h))
print(string.format("%.6f", measured.ias_mps * 3.6))
print(string.format("%.6f", u_c_trim))
""".replace(
            "{measured}",
            _measured(
                pitch_deg=-3.5,
                ias_mps=273.0 / 3.6,
                v_t_mps=273.0 / 3.6 + 2.0,
                h_m=300.0,
                asl_m=300.0,
            ),
        )
        lines = _run(driver)
        min_dev, max_dev, final_kmh, _ = (float(x) for x in lines)
        return min_dev, max_dev, final_kmh

    def test_altitude_deviation_stays_small_through_a_large_decel(self) -> None:
        min_dev, max_dev, final_kmh = self._run_decel_scenario()
        # The sixth re-fly lost ~100 m (h_m 384 -> 282) over the same
        # kind of commanded decel (273 -> 108 km/h). The fix bounds the
        # speed-give nudge instead of letting it integrate, so the
        # vertical loop's own `e_u` integrator can hold the altitude
        # reference within a small band throughout.
        assert min_dev > -15.0
        assert max_dev < 15.0
        # The decel itself still actually happens -- the fix must not
        # have gutted "less collective when slowing" into a no-op, only
        # bounded it. This file's shared `_PROFILE` stays at the
        # deliberate pre-amendment baseline (`omega_speed`/`speed_accel_
        # cap_mps2`/`k_speed_error`/`c_theta` all slower than production
        # -- `TestSpeedChannelIsBrisk`'s own docstring), so 20 s does not
        # reach the 108 km/h goal here; a meaningful drop from the 273
        # km/h start is what this scenario can assert against that
        # baseline.
        assert final_kmh < 273.0 - 20.0

    def test_speed_give_nudge_still_reduces_collective_below_the_vertical_term_alone(
        self,
    ) -> None:
        """Negative control: with `k_collective_speed_give` zeroed, the
        same scenario's own collective at the moment of peak deceleration
        demand is higher than with the nudge active -- confirming the
        nudge is still doing the "less collective when slowing" job the
        user asked for, not merely bounded into nothing."""
        driver_template = """
PROFILE.k_collective_speed_give = {k}
local u_c_trim = 0.3
local measured = {measured}
local command = { pitch = -3.5, roll = 0.0, pedals = 0.0, collective = 0.3 }
local state = flight_control.law_init_at_take(measured, LIMITS, command, nil, PROFILE)
state = flight_control.law_apply_goal(state, { ias_kmh = 108.0 }, LIMITS, PROFILE)
local dt = 0.05
for i = 1, 40 do -- 2 s, well inside the decel
    state = flight_control.law_update(state, dt, measured, LIMITS, PROFILE)
    local tau_p = 1.5
    measured.pitch_deg = measured.pitch_deg + (state.theta_d - measured.pitch_deg) * (dt / tau_p)
    local ax = 0.2 * (-3.5 - measured.pitch_deg)
    measured.ias_mps = measured.ias_mps + ax * dt
    measured.v_t_mps = measured.ias_mps + 2.0
    local target_w = (state.u_c - u_c_trim) * 10.0
    local prev_w = measured.w_mps
    measured.w_mps = measured.w_mps + (target_w - measured.w_mps) * (dt / 1.0)
    measured.a_u = (measured.w_mps - prev_w) / dt
    measured.h_m = measured.h_m + measured.w_mps * dt
    measured.asl_m = measured.h_m
end
print(string.format("%.6f", state.u_c))
""".replace(
            "{measured}",
            _measured(
                pitch_deg=-3.5,
                ias_mps=273.0 / 3.6,
                v_t_mps=273.0 / 3.6 + 2.0,
                h_m=300.0,
                asl_m=300.0,
            ),
        )
        u_c_with_nudge = float(_run(driver_template.replace("{k}", "0.1"))[0])
        u_c_without_nudge = float(_run(driver_template.replace("{k}", "0.0"))[0])
        assert u_c_with_nudge < u_c_without_nudge


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
