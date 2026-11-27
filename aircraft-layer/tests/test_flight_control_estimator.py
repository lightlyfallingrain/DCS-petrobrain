"""BL-16 lift-vector law, Stage LV-0 (`plans/flight-lift-vector/plan.md`,
section A) -- the estimator's own ring-buffer least-squares math and
Euler-rate transform, against a real Lua interpreter.

**Technique**: identical to `test_flight_control_law.py` (load the whole
file as an IIFE, call the module's exported functions directly, no DCS
mock) -- none of `est_ring_*`/`est_euler_rates`/`est_reset`/`est_sample`
reads a `LoGet*` global; `est_sample` only ever reads from the `raw`
table its caller builds, never from DCS directly. Skips cleanly without
a Lua interpreter on `PATH`.
"""

from __future__ import annotations

import math
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


#: `est_sample`'s own `est` state table -- built fresh (not through
#: `flight_control.lua`'s module-level `fc_est`, which is private) so
#: each scenario starts from a known-empty estimator, mirroring the
#: shape `flight_control.lua`'s own `fc_est` local literal declares.
_EST_STATE = """
local function new_est()
    return {
        sample_t = nil, last_law_t = nil,
        rings = {
            pos_n = flight_control.est_ring_new(), pos_u = flight_control.est_ring_new(),
            pos_e = flight_control.est_ring_new(),
            vec_n = flight_control.est_ring_new(), vec_u = flight_control.est_ring_new(),
            vec_e = flight_control.est_ring_new(),
            acc1_n = flight_control.est_ring_new(), acc1_u = flight_control.est_ring_new(),
            acc1_e = flight_control.est_ring_new(),
            acc2_n = flight_control.est_ring_new(), acc2_u = flight_control.est_ring_new(),
            acc2_e = flight_control.est_ring_new(),
            ball = flight_control.est_ring_new(),
            -- LV-1 amendment (2026-11-24, fourth re-fly), section A --
            -- the new averaged-bank ring.
            bank = flight_control.est_ring_new(),
        },
        v = { n = 0.0, u = 0.0, e = 0.0 },
        v_unselected = { n = 0.0, u = 0.0, e = 0.0 },
        a = { n = 0.0, u = 0.0, e = 0.0, f = 0.0, r = 0.0 },
        euler = { phi_dot = 0.0, theta_dot = 0.0, psi_dot = 0.0 },
        ball = 0.0,
        phi_bar = 0.0,
        v_g = 0.0, v_g_f = 0.0, v_g_r = 0.0,
        lambda = 0.0,
    }
end
"""

#: Mirrors `flight_profile.lua`'s own estimator fields (LV-0 defaults).
_PROFILE = """
local PROFILE = {
    velocity_source = "position",
    w_v_s = 0.1,
    w_a_s = 0.2,
    w_a2_s = 0.1,
    w_b = 0.2,
    ball_centre = 0.03,
    law_hz = 30.0,
    -- BL-16 lift-vector law, Stage LV-3 -- `est_sample` now derives
    -- `est.lambda` via `law_lambda`, which reads these two breakpoints.
    -- Values picked only so the existing tests' own velocities (none
    -- of them exercise the hover/forward blend) do not matter here.
    lambda_hover_kmh = 25.0,
    lambda_forward_kmh = 80.0,
}
"""


def _run(driver: str) -> list[str]:
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    module_source = _FLIGHT_CONTROL_LUA.read_text(encoding="utf-8")
    script = (
        "local flight_control = (function()\n"
        + module_source
        + "\nend)()\n"
        + _EST_STATE
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


class TestRingLeastSquaresSlope:
    def test_slope_of_a_perfectly_linear_series_is_exact(self) -> None:
        """A ring's own least-squares slope over a perfectly linear
        series must recover the true slope exactly, regardless of how
        much of the series the window has already evicted -- this is
        the regression case for the off-by-one eviction-index bug this
        stage's own smoke test caught (the oldest *live* sample sits
        `count - 1` slots behind `head`, not `count`)."""
        driver = """
local r = flight_control.est_ring_new()
for i = 0, 40 do
    local t = i * 0.05
    flight_control.est_ring_push(r, t, 3.0 * t + 7.0, 0.2)
end
print(string.format("%.9f", flight_control.est_ring_slope(r)))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - 3.0) < 1e-6

    def test_slope_with_fewer_than_two_samples_is_zero(self) -> None:
        driver = """
local r = flight_control.est_ring_new()
print(string.format("%.6f", flight_control.est_ring_slope(r)))
flight_control.est_ring_push(r, 0.0, 5.0, 0.2)
print(string.format("%.6f", flight_control.est_ring_slope(r)))
"""
        lines = _run(driver)
        assert float(lines[0]) == 0.0
        assert float(lines[1]) == 0.0

    def test_mean_tracks_a_constant_series(self) -> None:
        driver = """
local r = flight_control.est_ring_new()
for i = 0, 20 do
    flight_control.est_ring_push(r, i * 0.05, 4.2, 0.2)
end
print(string.format("%.6f", flight_control.est_ring_mean(r)))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - 4.2) < 1e-9

    def test_window_actually_evicts_old_samples(self) -> None:
        """A slope that changes sharply must be dominated by the
        in-window samples, not by every sample the ring has ever seen
        -- otherwise a fixed-size ring with a long-running mission
        would never forget a stale regime."""
        driver = """
local r = flight_control.est_ring_new()
-- 2 s of slope 0, then 0.5 s of slope 10 -- a 0.2 s window should see
-- only the second regime once it has fully slid past the transition.
for i = 0, 40 do
    flight_control.est_ring_push(r, i * 0.05, 0.0, 0.2)
end
for i = 1, 10 do
    local t = 2.0 + i * 0.05
    flight_control.est_ring_push(r, t, (t - 2.0) * 10.0, 0.2)
end
print(string.format("%.3f", flight_control.est_ring_slope(r)))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - 10.0) < 0.5


class TestRingRebasing:
    """BL-16 lift-vector law, Stage LV-1 fix (review-lv1.md, required
    fix 2 -- `review-lv0.md`'s own "re-check before LV-1 closes the
    loop on it"). `est_ring_push`'s `rt = t - ring.t0` used to rebase
    only once, at the ring's first sample since the last reset -- over
    a long session the two terms the least-squares denominator
    subtracts (`n*sum_t2` and `sum_t*sum_t`) both grow with session
    length even though their true difference does not, so the slope's
    floating-point cancellation error grows with it. `EST_RING_REBASE_
    INTERVAL_S` periodically re-bases `rt` back to a small value
    instead."""

    def test_slope_of_a_linear_series_stays_accurate_over_three_simulated_hours(
        self,
    ) -> None:
        """3 simulated hours at 30 Hz (`law_hz`, the estimator's own
        update rate) -- `review-lv0.md`'s own ask. A known linear series
        whose own *value* also grows with elapsed time (`3*t + 7`, the
        worst case for this cancellation error and the realistic one --
        a real position coordinate grows with time the same way during
        a sustained-direction flight leg) must still read back close to
        its true slope, not merely at the very end but all the way
        through (three checkpoints: 1 h, 2 h, 3 h) -- the error this fix
        bounds grows with elapsed time, so a check only at the end would
        miss a mid-session regression.

        Measured directly, both ways, before picking this bound: with
        `EST_RING_REBASE_INTERVAL_S` disabled (one-time rebase only, the
        pre-fix behaviour), the slope drifts to ~3.169 by 3 h (~5.6%
        relative error, growing with elapsed time, confirming the
        defect review-lv0.md flagged); with the periodic rebase, it
        stays within ~0.0024 (~0.08% relative) the whole way through --
        bounded, not merely small at today's sortie lengths, and
        unmistakably different from the un-rebased number. The bound
        below is a generous 1% relative, comfortably inside the
        rebased behaviour and comfortably outside the un-rebased one."""
        driver = """
local r = flight_control.est_ring_new()
local HZ = 30.0
local dt = 1.0 / HZ
local CHECKPOINT_S = 3600.0
local next_checkpoint = CHECKPOINT_S
local steps = 3 * 3600 * HZ
for i = 0, steps do
    local t = i * dt
    flight_control.est_ring_push(r, t, 3.0 * t + 7.0, 0.2)
    if t >= next_checkpoint then
        print(string.format("%.9f", flight_control.est_ring_slope(r)))
        next_checkpoint = next_checkpoint + CHECKPOINT_S
    end
end
print(string.format("%.9f", flight_control.est_ring_slope(r)))
"""
        lines = _run(driver)
        assert len(lines) == 4, lines
        for line in lines:
            relative_error = abs(float(line) - 3.0) / 3.0
            assert relative_error < 0.01, line


class TestEulerRateTransform:
    def test_steady_60_degree_bank_turn_body_q_does_not_equal_euler_theta_dot(
        self,
    ) -> None:
        """The plan's own worked example: in a steady, level, coordinated
        turn the body-axis pitch rate `q` reads `psi_dot*sin(phi)`
        (nonzero at 60 deg bank), while the Euler pitch rate
        (`theta_dot`) is the rate an attitude indicator would show --
        zero, since pitch attitude is not actually changing."""
        driver = """
local psi_dot_true = 15.0
local phi = 60.0
local theta = 0.0
local q = psi_dot_true * math.sin(math.rad(phi))
local r = psi_dot_true * math.cos(math.rad(phi))
local phi_dot, theta_dot, psi_dot = flight_control.est_euler_rates(0.0, q, r, phi, theta)
print(string.format("%.6f", phi_dot))
print(string.format("%.6f", theta_dot))
print(string.format("%.6f", psi_dot))
print(string.format("%.6f", q))
"""
        lines = _run(driver)
        phi_dot, theta_dot, psi_dot, body_q = (float(x) for x in lines)
        assert abs(phi_dot) < 1e-6
        assert abs(theta_dot) < 1e-6
        assert abs(psi_dot - 15.0) < 1e-6
        # The body rate q is NOT near zero -- the thing LV-0's own card
        # (row c) measures in flight: q != 0 while theta_dot == 0.
        assert abs(body_q) > 10.0

    def test_level_flight_body_and_euler_rates_agree(self) -> None:
        """At zero bank and pitch, body rates and Euler rates coincide
        exactly -- the degenerate case M0-A could not distinguish."""
        driver = """
local phi_dot, theta_dot, psi_dot = flight_control.est_euler_rates(2.0, -3.0, 7.0, 0.0, 0.0)
print(string.format("%.6f", phi_dot))
print(string.format("%.6f", theta_dot))
print(string.format("%.6f", psi_dot))
"""
        lines = _run(driver)
        phi_dot, theta_dot, psi_dot = (float(x) for x in lines)
        assert abs(phi_dot - 2.0) < 1e-6
        assert abs(theta_dot - (-3.0)) < 1e-6
        assert abs(psi_dot - 7.0) < 1e-6

    def test_near_vertical_pitch_does_not_blow_up(self) -> None:
        """`cos(theta)` in `psi_dot`'s own denominator is guarded --
        near +-90 deg pitch this must fail soft to 0.0, never NaN/inf."""
        driver = """
local phi_dot, theta_dot, psi_dot = flight_control.est_euler_rates(1.0, 1.0, 1.0, 0.0, 89.95)
print(tostring(psi_dot))
print(tostring(psi_dot == psi_dot))
"""
        lines = _run(driver)
        assert lines[0] == "0.000000" or math.isfinite(float(lines[0]))
        assert lines[1] == "true"  # psi_dot == psi_dot is false only for NaN


class TestResetAndPriming:
    def test_a_model_time_gap_past_dt_cap_re_primes_with_no_spike(self) -> None:
        """Plan, "Reset/priming": a stall (`dt > DT_CAP`) must never
        produce an acceleration spike -- the ring re-primes from the
        gap sample instead of differencing a huge position jump over a
        huge `dt`."""
        driver = """
local est = new_est()
for i = 0, 30 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = 10.0 * t, pos_u = 0.0, pos_e = 0.0,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
end
print(string.format("%.4f", est.v.n))
print(string.format("%.4f", est.a.n))

-- A huge model-time jump (well past DT_CAP = 2.0) with a huge position
-- jump too -- a naive differencer would read this as an enormous
-- velocity/acceleration spike.
local raw_after_gap = {
    pos_n = 50000.0, pos_u = 0.0, pos_e = 0.0,
    psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
    p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
}
flight_control.est_sample(est, 500.0, raw_after_gap, PROFILE)
print(string.format("%.4f", est.v.n))
print(string.format("%.4f", est.a.n))
"""
        lines = _run(driver)
        v_before, a_before, v_after, a_after = (float(x) for x in lines)
        assert abs(v_before - 10.0) < 0.1
        assert abs(a_before) < 1.0
        # Re-primed: a single sample gives no slope at all (0.0), not a
        # spike derived from the 50000 m jump over nothing.
        assert v_after == 0.0
        assert a_after == 0.0

    def test_the_first_sample_ever_primes_without_a_spike(self) -> None:
        driver = """
local est = new_est()
local raw = {
    pos_n = 12345.0, pos_u = 0.0, pos_e = 0.0,
    psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
    p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
}
flight_control.est_sample(est, 12.0, raw, PROFILE)
print(string.format("%.4f", est.v.n))
print(string.format("%.4f", est.a.n))
"""
        lines = _run(driver)
        v, a = (float(x) for x in lines)
        assert v == 0.0
        assert a == 0.0

    def test_est_reset_clears_every_ring_and_derived_field(self) -> None:
        driver = """
local est = new_est()
for i = 0, 10 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = 10.0 * t, pos_u = 5.0 * t, pos_e = -2.0 * t,
        psi_deg = 10.0, phi_deg = 5.0, theta_deg = -3.0,
        p_deg_s = 1.0, q_deg_s = 2.0, r_deg_s = 3.0, ball_raw = 0.2,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
end
flight_control.est_reset(est)
print(tostring(est.sample_t))
print(tostring(est.last_law_t))
print(string.format("%.4f", est.v.n))
print(string.format("%.4f", est.a.n))
print(string.format("%.4f", est.ball))
print(string.format("%.4f", est.v_g))
"""
        lines = _run(driver)
        assert lines[0] == "nil"
        assert lines[1] == "nil"
        assert all(float(x) == 0.0 for x in lines[2:])

    def test_duplicate_timestamp_sample_does_not_spike_acceleration(self) -> None:
        """Debug-2026-11-23 (`plans/flight-lift-vector/debug-2026-11-23.md`,
        problem 2b) -- the real LV-0 sortie trace showed `v` reading
        exactly 0.0 for one sample mid-flight (position source) while
        the raw `LoGetVectorVelocity` channel stayed perfectly smooth,
        producing a 300-550 m/s^2 acceleration spike over the next
        ~0.3 s. Reproduced here with two samples sharing one timestamp
        -- `est_ring_slope`'s own `denom == 0.0` guard, the same
        degenerate shape a duplicated/undercounted model-time tick
        would give. A steady 30 m/s climb-free run, then one duplicate
        tick, then normal ticks resume: velocity must hold at its last
        known value through the duplicate (never snap to 0), and the
        acceleration that follows must not spike."""
        driver = """
local est = new_est()
local v_n = 30.0
local pos_n = 0.0
for i = 0, 20 do
    local t = i * (1.0 / 30.0)
    pos_n = pos_n + v_n * (1.0 / 30.0)
    local raw = {
        pos_n = pos_n, pos_u = 0.0, pos_e = 0.0,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
end
print(string.format("%.4f", est.v.n))
print(string.format("%.4f", est.a.n))

-- A duplicate-timestamp tick: same `t` as the last real sample, no
-- position change either (as a duplicate frame would report).
local t_dup = 20 * (1.0 / 30.0)
local raw_dup = {
    pos_n = pos_n, pos_u = 0.0, pos_e = 0.0,
    psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
    p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
}
flight_control.est_sample(est, t_dup, raw_dup, PROFILE)
print(string.format("%.4f", est.v.n))
print(string.format("%.4f", est.a.n))

-- Normal ticks resume.
local max_abs_a = 0.0
for i = 21, 31 do
    local t = i * (1.0 / 30.0)
    pos_n = pos_n + v_n * (1.0 / 30.0)
    local raw = {
        pos_n = pos_n, pos_u = 0.0, pos_e = 0.0,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
    if math.abs(est.a.n) > max_abs_a then
        max_abs_a = math.abs(est.a.n)
    end
end
print(string.format("%.4f", max_abs_a))
"""
        lines = _run(driver)
        v_before, a_before, v_at_dup, a_at_dup, max_abs_a_after = (
            float(x) for x in lines
        )
        assert abs(v_before - 30.0) < 0.5
        assert abs(a_before) < 1.0
        # The duplicate tick must hold velocity at its last known value
        # -- never snap to 0.0 the way a bare `est_ring_slope` would.
        assert abs(v_at_dup - v_before) < 0.5
        assert abs(a_at_dup) < 1.0
        # No acceleration spike in the frames that follow either.
        assert max_abs_a_after < 1.0

    def test_invalid_self_data_holds_velocity_instead_of_snapping_to_origin(
        self,
    ) -> None:
        """Debug-2026-11-23, problem 2 ("not fixed" note, confirmed by
        the 2026-11-23 retest sortie): the retest trace showed the
        aircraft departing controlled flight, being destroyed, and
        `LoGetSelfData` failing a few frames later -- at that point
        `a_f` reached -13,000,000 m/s^2, because the position ring
        still held ~115s of real history and the failed-read fallback
        (`pos_n/u/e = 0.0`) was fed into it as a genuine sample, a
        >100m "position jump" to the origin in one `dt`. `raw.pos_
        valid = false` (now set by `read_estimator_raw` whenever
        `LoGetSelfData`'s `Position` is not a clean numeric table) must
        hold velocity at its last value instead."""
        driver = """
local est = new_est()
local v_n = 50.0
local pos_n = 0.0
for i = 0, 30 do
    local t = i * (1.0 / 30.0)
    pos_n = pos_n + v_n * (1.0 / 30.0)
    local raw = {
        pos_n = pos_n, pos_u = 0.0, pos_e = 0.0, pos_valid = true,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
end
print(string.format("%.4f", est.v.n))

-- `LoGetSelfData` starts failing -- the aircraft is gone. The fallback
-- position (0.0) must never be treated as a real sample.
local max_abs_a = 0.0
for i = 31, 40 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = 0.0, pos_u = 0.0, pos_e = 0.0, pos_valid = false,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
    if math.abs(est.a.n) > max_abs_a then
        max_abs_a = math.abs(est.a.n)
    end
end
print(string.format("%.4f", est.v.n))
print(string.format("%.4f", max_abs_a))
"""
        lines = _run(driver)
        v_before, v_after, max_abs_a_after = (float(x) for x in lines)
        assert abs(v_before - 50.0) < 1.0
        # Velocity holds at its last known value through the invalid
        # reads -- never snaps toward 0 because the position "jumped".
        assert abs(v_after - v_before) < 1.0
        assert max_abs_a_after < 10.0

    def test_mission_start_bridges_from_vector_velocity_while_priming(
        self,
    ) -> None:
        """Debug-2026-11-23, problem 2a -- the real LV-0 sortie trace
        showed a_f 350-700 m/s^2 for ~0.35 s at every mission start: the
        very first sample primes the position ring at v=0 (no
        information yet), and the second sample's real velocity used
        to be fed straight into the acceleration ring as a one-step
        jump from that artificial 0. The LV-0 card always flies with
        the trace flag on, which also means `LoGetVectorVelocity` is
        being read every frame (`raw.vec_n` not nil) -- that direct
        reading now bridges the position ring's priming gap instead of
        a fabricated 0, so the acceleration estimate never sees a step
        discontinuity to begin with."""
        driver = """
local est = new_est()
local v_n = 42.0
for i = 0, 10 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = v_n * t, pos_u = 0.0, pos_e = 0.0,
        vec_n = v_n, vec_u = 0.0, vec_e = 0.0,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
    print(string.format("%.4f", est.a.n))
end
"""
        lines = _run(driver)
        a_values = [float(x) for x in lines]
        assert max(abs(a) for a in a_values) < 1.0

    def test_mission_start_without_vector_velocity_still_bounded(
        self,
    ) -> None:
        """Documented residual (debug report, problem 2a "not fully
        fixed"): with no `LoGetVectorVelocity` reading available at all
        (trace off, `velocity_source == "position"`), there is no way
        to know velocity before the position ring has two real samples
        -- the warm-up transient this test measures is the genuine,
        bounded cost of that, not a regression. Pinned here so a
        future change that makes it worse is caught."""
        driver = """
local est = new_est()
local v_n = 42.0
for i = 0, 10 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = v_n * t, pos_u = 0.0, pos_e = 0.0,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
    print(string.format("%.4f", est.a.n))
end
"""
        lines = _run(driver)
        a_values = [float(x) for x in lines]
        assert max(abs(a) for a in a_values) < 1500.0


class TestGroundSpeedAndHeadingFrameRotation:
    def test_northbound_ground_speed_matches_heading(self) -> None:
        """A straight, level, northbound leg -- `V_g` should match the
        constant velocity, and `v_g,f` (along the nose) should read the
        full speed while `v_g,r` (across the nose) reads ~0, the LV-0
        card's own row (b) (position axes: x north, z east)."""
        driver = """
local est = new_est()
for i = 0, 40 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = 20.0 * t, pos_u = 0.0, pos_e = 0.0,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
end
print(string.format("%.3f", est.v_g))
print(string.format("%.3f", est.v_g_f))
print(string.format("%.3f", est.v_g_r))
"""
        lines = _run(driver)
        v_g, v_g_f, v_g_r = (float(x) for x in lines)
        assert abs(v_g - 20.0) < 0.1
        assert abs(v_g_f - 20.0) < 0.1
        assert abs(v_g_r) < 0.1

    def test_eastbound_ground_speed_matches_heading(self) -> None:
        driver = """
local est = new_est()
for i = 0, 40 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = 0.0, pos_u = 0.0, pos_e = 20.0 * t,
        psi_deg = 90.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
end
print(string.format("%.3f", est.v_g))
print(string.format("%.3f", est.v_g_f))
print(string.format("%.3f", est.v_g_r))
"""
        lines = _run(driver)
        v_g, v_g_f, v_g_r = (float(x) for x in lines)
        assert abs(v_g - 20.0) < 0.1
        assert abs(v_g_f - 20.0) < 0.1
        assert abs(v_g_r) < 0.1

    def test_level_turn_vertical_acceleration_reads_zero(self) -> None:
        """Section A: `a_u` is the slope of world-up velocity directly
        -- no gravity, no body frame -- so a level turn (`pos_u`
        constant) must read `a_u` near zero, "exactly as the altimeter
        says", unlike a body-frame G-meter reading which would read
        about 2 g at 60 deg bank (goal-check finding 1's own failure
        mode this estimator is built to avoid)."""
        driver = """
local est = new_est()
for i = 0, 60 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = 20.0 * math.cos(t), pos_u = 100.0, pos_e = 20.0 * math.sin(t),
        psi_deg = math.deg(t), phi_deg = 45.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
end
print(string.format("%.4f", est.a.u))
"""
        lines = _run(driver)
        assert abs(float(lines[0])) < 0.5


class TestVelocitySourceSelection:
    def test_vector_source_averages_rather_than_differentiates(self) -> None:
        """`velocity_source = "vector"` reads `raw.vec_*` as an already-
        a-velocity running average, never a position-style slope -- a
        constant `vec_n` must read back as that same constant, not 0
        (which a slope of a constant series would also give, so this
        scenario also feeds a *changing* `pos_n` that the vector source
        must NOT track, proving it really read the vector channel)."""
        driver = """
local est = new_est()
local vector_profile = {
    velocity_source = "vector", w_v_s = 0.1, w_a_s = 0.2, w_a2_s = 0.1,
    w_b = 0.2, ball_centre = 0.03, law_hz = 30.0,
    lambda_hover_kmh = 25.0, lambda_forward_kmh = 80.0,
}
for i = 0, 20 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = 999.0 * t,  -- would give slope ~999 if wrongly used
        pos_u = 0.0, pos_e = 0.0,
        vec_n = 42.0, vec_u = 0.0, vec_e = 0.0,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.03,
    }
    flight_control.est_sample(est, t, raw, vector_profile)
end
print(string.format("%.3f", est.v.n))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - 42.0) < 0.1


class TestBallRunningAverage:
    def test_ball_tracks_a_constant_reading(self) -> None:
        driver = """
local est = new_est()
for i = 0, 20 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = 0.0, pos_u = 0.0, pos_e = 0.0,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = 0.27,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
end
print(string.format("%.4f", est.ball))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - 0.27) < 0.01

    def test_a_missing_ball_reading_falls_back_to_profile_centre(self) -> None:
        driver = """
local est = new_est()
for i = 0, 20 do
    local t = i * (1.0 / 30.0)
    local raw = {
        pos_n = 0.0, pos_u = 0.0, pos_e = 0.0,
        psi_deg = 0.0, phi_deg = 0.0, theta_deg = 0.0,
        p_deg_s = 0.0, q_deg_s = 0.0, r_deg_s = 0.0, ball_raw = nil,
    }
    flight_control.est_sample(est, t, raw, PROFILE)
end
print(string.format("%.4f", est.ball))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - 0.03) < 0.01


def test_file_parses_without_a_lua_interpreter_too() -> None:
    """Same sanity the other Lua-backed test files run -- the module
    file must at least be well-formed Python-side-readable text even
    when no Lua toolchain is installed in CI."""
    assert _FLIGHT_CONTROL_LUA.exists()
    text = _FLIGHT_CONTROL_LUA.read_text(encoding="utf-8")
    assert "est_ring_push" in text
    assert "est_euler_rates" in text
