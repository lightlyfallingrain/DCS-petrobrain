"""Tests for `belief.altimeter_qnh_sync` -- BL-B118 (`plans/
bl16-qnh-mission-start/plan.md`, Stage 2). Every terminal phase against a
fake `AircraftLayerClient` double, no network/live DCS -- same posture as
`test_effector_engine.py`'s own `_FakeAircraftClient`."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

import belief.altimeter_qnh_sync as altimeter_qnh_sync_module
from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.altimeter_qnh_sync import (
    ALTIMETER_QNH_MAX_DURATION_S,
    ALTIMETER_QNH_MAX_ITERATIONS,
    ALTIMETER_QNH_MAX_STEP,
    ALTIMETER_QNH_NO_RESPONSE_STRIKES,
    ALTIMETER_QNH_SETTLE_S,
    ALTIMETER_QNH_TOLERANCE_MMHG,
    AltimeterQnhSyncState,
    advance_altimeter_qnh_sync,
    start_altimeter_qnh_sync,
)


class _FakeAircraftClient:
    """`read_args`/`write_cockpit_switch` double simulating device 42's
    own arg834. `respond` is called with each commanded delta and the
    arg value *before* that write, and returns the arg value *after* it
    -- the one hook every fake below customises to simulate a different
    device response shape. Clamped to `[0.0, 1.0]`, the real LEV
    element's own `arg_lim` (`aircraft-layer/research/2026-11-16-
    mi24p-operator-altimeter-recon.md` section B)."""

    def __init__(
        self, initial_arg: float, respond: Callable[[float, float], float]
    ) -> None:
        self.arg_value = initial_arg
        self._respond = respond
        self.writes: list[float] = []
        self.read_calls = 0
        self.fail_reads_remaining = 0
        self.fail_writes_remaining = 0

    def read_args(self, args: list[int]) -> dict[str, float]:
        self.read_calls += 1
        if self.fail_reads_remaining > 0:
            self.fail_reads_remaining -= 1
            raise AircraftLayerError("simulated read failure")
        assert args == [834]
        return {"834": self.arg_value}

    def write_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
        if self.fail_writes_remaining > 0:
            self.fail_writes_remaining -= 1
            raise AircraftLayerError("simulated write failure")
        assert device == 42
        assert cmd == 3001
        self.writes.append(value)
        self.arg_value = max(0.0, min(1.0, self._respond(self.arg_value, value)))


def _client(fake: _FakeAircraftClient) -> AircraftLayerClient:
    return cast(AircraftLayerClient, fake)


def _linear_gain(gain: float) -> Callable[[float, float], float]:
    return lambda arg, delta: arg + delta * gain


def _ignores_writes(arg: float, delta: float) -> float:
    return arg


def _advance_until_terminal(
    state: AltimeterQnhSyncState,
    fake: _FakeAircraftClient,
    *,
    step_wall_s: float = ALTIMETER_QNH_SETTLE_S,
    max_calls: int = 500,
) -> AltimeterQnhSyncState:
    """Drives `advance_altimeter_qnh_sync` poll by poll, advancing
    `now_wall` by `step_wall_s` each call (>= `ALTIMETER_QNH_SETTLE_S` so
    every call actually attempts a step, never just re-checks the settle
    gate) until a terminal phase is reached."""
    now_wall = state.started_wall
    client = _client(fake)
    for _ in range(max_calls):
        now_wall += step_wall_s
        state = advance_altimeter_qnh_sync(state, client, now_wall)
        if state.phase != "running":
            return state
    raise AssertionError(
        f"did not reach a terminal phase within {max_calls} calls "
        f"(last phase={state.phase!r}, iterations={state.iterations})"
    )


def test_start_clamps_qnh_outside_window() -> None:
    state = start_altimeter_qnh_sync(1000.0, now_wall=0.0)

    assert state.target_mmhg == 790.0
    assert state.phase == "running"


def test_start_does_not_clamp_qnh_inside_window() -> None:
    state = start_altimeter_qnh_sync(750.0, now_wall=0.0)

    assert state.target_mmhg == 750.0


def test_converges_from_worst_case_120_mmhg_span() -> None:
    """arg834 starts at 0.0 (670 mmHg), target is 790 mmHg (arg 1.0) --
    the full window span. A realistic, exact-gain device converges well
    within the iteration/duration bounds, and no single write ever
    exceeds `ALTIMETER_QNH_MAX_STEP`."""
    fake = _FakeAircraftClient(initial_arg=0.0, respond=_linear_gain(1.0))
    state = start_altimeter_qnh_sync(790.0, now_wall=0.0)

    state = _advance_until_terminal(state, fake)

    assert state.phase == "succeeded"
    assert state.iterations < ALTIMETER_QNH_MAX_ITERATIONS
    assert fake.writes, "expected at least one write"
    assert all(abs(delta) <= ALTIMETER_QNH_MAX_STEP for delta in fake.writes)
    final_mmhg = 670.0 + 120.0 * fake.arg_value
    assert abs(final_mmhg - 790.0) <= ALTIMETER_QNH_TOLERANCE_MMHG


def test_converges_with_inverted_gain_sign() -> None:
    """A gain estimate that starts out wrong-signed (the probe step
    always guesses positive) only costs an extra iteration -- the secant
    update corrects itself once the first real response is observed.
    Started away from the device's own `[0.0, 1.0]` saturation boundary
    (unlike `test_converges_from_worst_case_120_mmhg_span`) so the first,
    wrong-signed probe step is a real, observable movement rather than a
    clamped no-op that would itself look like a non-responding knob."""
    fake = _FakeAircraftClient(initial_arg=0.5, respond=_linear_gain(-1.0))
    state = start_altimeter_qnh_sync(670.0, now_wall=0.0)

    state = _advance_until_terminal(state, fake)

    assert state.phase == "succeeded"
    assert all(abs(delta) <= ALTIMETER_QNH_MAX_STEP for delta in fake.writes)


def test_non_responding_knob_fails_no_response() -> None:
    """The knob never moves (e.g. written from the pilot seat, the
    plan's own named risk) -- `ALTIMETER_QNH_NO_RESPONSE_STRIKES`
    consecutive non-responses trips `failed_no_response`, not a silent
    hang."""
    fake = _FakeAircraftClient(initial_arg=0.0, respond=_ignores_writes)
    state = start_altimeter_qnh_sync(790.0, now_wall=0.0)

    state = _advance_until_terminal(state, fake)

    assert state.phase == "failed_no_response"
    assert state.no_response_strikes >= ALTIMETER_QNH_NO_RESPONSE_STRIKES
    assert all(abs(delta) <= ALTIMETER_QNH_MAX_STEP for delta in fake.writes)


def test_one_noisy_non_response_does_not_trip_failure() -> None:
    """A single non-responding poll must not trip `failed_no_response`
    on its own -- only `ALTIMETER_QNH_NO_RESPONSE_STRIKES` *consecutive*
    ones. Device responds normally except for exactly one write, whose
    effect is suppressed."""
    calls = {"n": 0}

    def _one_dead_write(arg: float, delta: float) -> float:
        calls["n"] += 1
        if calls["n"] == 2:
            return arg
        return arg + delta * 1.0

    fake = _FakeAircraftClient(initial_arg=0.0, respond=_one_dead_write)
    state = start_altimeter_qnh_sync(790.0, now_wall=0.0)

    state = _advance_until_terminal(state, fake)

    assert state.phase == "succeeded"


def test_oscillating_response_fails_timeout() -> None:
    """A response that bears no stable relationship to the commanded
    delta (the plan's "pathological response curve" risk -- a dead
    zone, or a gain that flips sign mid-range) never lets the secant
    estimate converge, but moves enough each step that no-response never
    trips either -- bounded by `ALTIMETER_QNH_MAX_ITERATIONS`/
    `ALTIMETER_QNH_MAX_DURATION_S` instead, catching this as
    `failed_timeout`, not a silent hang."""
    state_box = {"flip": False}

    def _oscillate(arg: float, delta: float) -> float:
        state_box["flip"] = not state_box["flip"]
        direction = 1.0 if state_box["flip"] else -1.0
        return arg + direction * 0.05

    fake = _FakeAircraftClient(initial_arg=0.5, respond=_oscillate)
    state = start_altimeter_qnh_sync(790.0, now_wall=0.0)

    state = _advance_until_terminal(state, fake)

    assert state.phase == "failed_timeout"
    assert all(abs(delta) <= ALTIMETER_QNH_MAX_STEP for delta in fake.writes)


def test_duration_bound_also_reaches_failed_timeout() -> None:
    """Even with headroom left on `ALTIMETER_QNH_MAX_ITERATIONS`, the
    wall-clock bound alone must terminate the loop -- a settle gap large
    enough that `ALTIMETER_QNH_MAX_DURATION_S` elapses in far fewer than
    `ALTIMETER_QNH_MAX_ITERATIONS` steps."""
    fake = _FakeAircraftClient(initial_arg=0.5, respond=_ignores_writes)
    state = start_altimeter_qnh_sync(790.0, now_wall=0.0)
    big_step = ALTIMETER_QNH_MAX_DURATION_S  # one step alone exceeds the bound

    state = _advance_until_terminal(state, fake, step_wall_s=big_step, max_calls=5)

    assert state.phase in ("failed_timeout", "failed_no_response")
    assert state.iterations < ALTIMETER_QNH_MAX_ITERATIONS


def test_transient_read_failure_is_skipped_and_retried() -> None:
    """A transport failure on `read_args` degrades to "skip this poll,
    retry next" -- it must not count as an iteration, and the run must
    still reach `succeeded` once the transport recovers."""
    fake = _FakeAircraftClient(initial_arg=0.0, respond=_linear_gain(1.0))
    fake.fail_reads_remaining = 3
    state = start_altimeter_qnh_sync(790.0, now_wall=0.0)

    now_wall = 0.0
    for _ in range(3):
        now_wall += ALTIMETER_QNH_SETTLE_S
        state = advance_altimeter_qnh_sync(state, _client(fake), now_wall)
        assert state.phase == "running"
        assert state.iterations == 0

    state = _advance_until_terminal(state, fake)

    assert state.phase == "succeeded"
    assert not fake.writes or all(
        abs(delta) <= ALTIMETER_QNH_MAX_STEP for delta in fake.writes
    )


def test_transient_write_failure_is_skipped_and_retried() -> None:
    """Same posture as the read failure above, for `write_cockpit_switch`
    -- the poll that fails to write leaves `prev_arg_value`/
    `prev_delta_sent`/`iterations` untouched, so the next poll retries
    from the same state."""
    fake = _FakeAircraftClient(initial_arg=0.0, respond=_linear_gain(1.0))
    fake.fail_writes_remaining = 2
    state = start_altimeter_qnh_sync(790.0, now_wall=0.0)

    now_wall = 0.0
    for _ in range(2):
        now_wall += ALTIMETER_QNH_SETTLE_S
        state = advance_altimeter_qnh_sync(state, _client(fake), now_wall)
        assert state.phase == "running"
        assert state.iterations == 0

    state = _advance_until_terminal(state, fake)

    assert state.phase == "succeeded"


def test_settle_gate_blocks_a_step_before_the_wait_elapses() -> None:
    """Calling `advance_altimeter_qnh_sync` again before
    `ALTIMETER_QNH_SETTLE_S` has elapsed since the last write must be a
    true no-op -- no second read, no second write."""
    fake = _FakeAircraftClient(initial_arg=0.0, respond=_linear_gain(1.0))
    state = start_altimeter_qnh_sync(790.0, now_wall=0.0)

    state = advance_altimeter_qnh_sync(state, _client(fake), ALTIMETER_QNH_SETTLE_S)
    assert state.phase == "running"
    reads_after_first_step = fake.read_calls
    writes_after_first_step = len(fake.writes)

    # Not even half the settle window has passed -- must not step again.
    state = advance_altimeter_qnh_sync(
        state, _client(fake), ALTIMETER_QNH_SETTLE_S + ALTIMETER_QNH_SETTLE_S / 4
    )

    assert fake.read_calls == reads_after_first_step
    assert len(fake.writes) == writes_after_first_step


def test_succeeded_state_is_inert() -> None:
    """Once a run reaches a terminal phase, further
    `advance_altimeter_qnh_sync` calls must return it unchanged --
    never a second read or write."""
    fake = _FakeAircraftClient(initial_arg=0.0, respond=_linear_gain(1.0))
    state = start_altimeter_qnh_sync(670.3, now_wall=0.0)
    state = advance_altimeter_qnh_sync(state, _client(fake), ALTIMETER_QNH_SETTLE_S)
    assert state.phase == "succeeded"
    reads_at_success = fake.read_calls

    state = advance_altimeter_qnh_sync(state, _client(fake), 10_000.0)

    assert state.phase == "succeeded"
    assert fake.read_calls == reads_at_success


def test_calibration_step_is_clamped_to_max_step_even_when_configured_larger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ALTIMETER_QNH_CALIBRATION_STEP`'s declared range (0.01-0.2) and
    `ALTIMETER_QNH_MAX_STEP`'s (0.05-1.0) do not themselves enforce
    `CALIBRATION_STEP <= MAX_STEP` -- a legal `config/tuning.toml`
    override can invert the pair. The first step of every run (taken
    while `prev_delta_sent` is still `None`, so no gain estimate exists)
    must still obey `MAX_STEP` regardless -- the gap the review found in
    the `else` branch of the delta computation."""
    monkeypatch.setattr(
        altimeter_qnh_sync_module, "ALTIMETER_QNH_CALIBRATION_STEP", 0.2
    )
    monkeypatch.setattr(altimeter_qnh_sync_module, "ALTIMETER_QNH_MAX_STEP", 0.05)

    fake = _FakeAircraftClient(initial_arg=0.0, respond=_ignores_writes)
    state = start_altimeter_qnh_sync(790.0, now_wall=0.0)
    assert state.prev_delta_sent is None  # confirms the no-gain branch will run

    state = advance_altimeter_qnh_sync(state, _client(fake), ALTIMETER_QNH_SETTLE_S)

    assert state.phase == "running"
    assert fake.writes, "expected the first (no-gain) step to write"
    assert all(abs(delta) <= 0.05 for delta in fake.writes)
