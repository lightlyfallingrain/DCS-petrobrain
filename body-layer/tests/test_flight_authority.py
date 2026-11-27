"""Tests for `belief.flight_authority` -- BL-16 (`plans/
flight-desired-state/plan.md`, Stages 1-3). `advance_flight_authority`
is exercised against a real loopback `http.server` instance via a real
`AircraftLayerClient`, same posture as `test_flight_control.py`'s own
convention (the project's "no mocked `urllib`" rule). `decide_flight_
speech`/`parse_acks`/`resolve_pending_take` are pure, so they are
exercised directly against `FlightAuthorityState`/`PendingTake` values,
no server needed."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from aircraft_client import AircraftLayerClient
from belief.flight_authority import (
    FLIGHT_REQUEST_ACCEPT_WINDOW_S,
    FlightAuthorityState,
    PendingFlightReadback,
    PendingTake,
    advance_flight_authority,
    controls_to_petrovich_edge,
    controls_to_player_edge,
    decide_carried_value_speech,
    decide_flight_speech,
    parse_acks,
    resolve_pending_flight_readbacks,
    resolve_pending_take,
)
from belief.flight_control import (
    FLOOR_AGL_M,
    HANDOVER_ACK_TIMEOUT_S,
    MAX_IAS_KMH,
)


class _Handler(BaseHTTPRequestHandler):
    sample: dict[str, Any] | None = None

    def do_GET(self) -> None:
        body = json.dumps(self.sample).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def server_with_sample() -> Iterator[str]:
    _Handler.sample = {
        "t": 12.5,
        "fd_mode": "m1",
        "fd_mode_cause": "take",
        "fd_mode_n": 3,
        "fd_has_m2": True,
        "fd_hdg_mode": "heading",
        "fd_heading": 90.0,
        "fd_hdg_ref": "true",
        "fd_turn_dir": None,
        "fd_turn_rate": None,
        "fd_turn_style": "normal",
        "fd_alt": 300.0,
        "fd_alt_ref": "agl",
        "fd_ias": 150.0,
        "fd_manoeuvre": "none",
        "fd_manoeuvre_seq": 0,
        "fd_stamp_hdg": 1,
        "fd_stamp_alt": 1,
        "fd_stamp_spd": 1,
        "fd_hdg_true_deg": 90.5,
        "fd_hdg_mag_deg": 97.8,
        "fd_measured_agl": 300.0,
        "fd_measured_msl": 350.0,
        "fd_measured_ias": 150.0,
        "fd_overlay_course": 71.0,
        "fd_reset_epoch": 42,
    }
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


@pytest.fixture
def server_with_null() -> Iterator[str]:
    _Handler.sample = None
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


class TestAdvanceFlightAuthority:
    def test_a_sample_is_parsed_into_the_mirror(self, server_with_sample: str) -> None:
        client = AircraftLayerClient(base_url=server_with_sample)
        state = advance_flight_authority(FlightAuthorityState(), client)
        assert state.fd_mode == "m1"
        assert state.mode_cause == "take"
        assert state.mode_n == 3
        assert state.has_m2 is True
        assert state.hdg_mode == "heading"
        assert state.heading_deg == pytest.approx(90.0)
        assert state.hdg_ref == "true"
        assert state.alt_m == pytest.approx(300.0)
        assert state.alt_ref == "agl"
        assert state.ias_kmh == pytest.approx(150.0)
        assert state.hdg_true_deg == pytest.approx(90.5)
        assert state.hdg_mag_deg == pytest.approx(97.8)
        assert state.overlay_course_deg == pytest.approx(71.0)
        assert state.reset_epoch == 42

    def test_a_null_sample_leaves_state_unchanged(self, server_with_null: str) -> None:
        client = AircraftLayerClient(base_url=server_with_null)
        original = FlightAuthorityState(fd_mode="m2", mode_n=7)
        state = advance_flight_authority(original, client)
        assert state == original

    def test_a_negative_heading_degree_wraps_into_0_360(
        self, server_with_sample: str
    ) -> None:
        """`Export.lua`'s `flight_desired.lua` now converts
        `LoGetMagneticYaw`'s own radians via `math.deg` and wraps before
        the wire -- this mirror wraps again defensively at its own
        boundary (`_as_optional_degrees_0_360`'s own docstring), so a
        value that arrives negative (a hair of float rounding, or an
        older/un-fixed `Export.lua`) still reads as this project's
        canonical `[0, 360)` compass range rather than a bare negative
        degree."""
        _Handler.sample = dict(_Handler.sample or {})
        _Handler.sample["fd_hdg_true_deg"] = -5.0
        _Handler.sample["fd_hdg_mag_deg"] = -0.06788
        client = AircraftLayerClient(base_url=server_with_sample)
        state = advance_flight_authority(FlightAuthorityState(), client)
        assert state.hdg_true_deg == pytest.approx(355.0)
        assert state.hdg_mag_deg == pytest.approx(359.93212)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    @pytest.mark.parametrize(
        "field", ["fd_alt", "fd_ias", "fd_heading", "fd_turn_rate"]
    )
    def test_a_non_finite_wire_value_degrades_to_none(
        self, server_with_sample: str, field: str, bad: float
    ) -> None:
        """Security review, `plans/flight-lift-vector/security.md`
        Required Fix 1: a LAN peer answering `GET /flight_desired/
        latest` with a non-standard `NaN`/`Infinity` literal (which
        Python's `json.loads` accepts by default) must not reach belief
        state as a value -- it degrades to `None`, the same "nothing
        received yet" state a missing field already gets, rather than
        carrying a non-finite float into a later `clamp_*`/`int()`
        call."""
        _Handler.sample = dict(_Handler.sample or {})
        _Handler.sample[field] = bad
        client = AircraftLayerClient(base_url=server_with_sample)
        state = advance_flight_authority(FlightAuthorityState(), client)
        attr = {
            "fd_alt": "alt_m",
            "fd_ias": "ias_kmh",
            "fd_heading": "heading_deg",
            "fd_turn_rate": "turn_rate_deg_s",
        }[field]
        assert getattr(state, attr) is None

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    @pytest.mark.parametrize("field", ["fd_hdg_true_deg", "fd_hdg_mag_deg"])
    def test_a_non_finite_degree_field_degrades_to_none(
        self, server_with_sample: str, field: str, bad: float
    ) -> None:
        """Same guard, for the `_as_optional_degrees_0_360` wrapper --
        `NaN % 360.0`/`inf % 360.0` are themselves non-finite (`NaN`),
        so without the guard this field would carry a `NaN` degree
        forward into belief state; it must degrade to `None` same as
        the plain float fields above."""
        _Handler.sample = dict(_Handler.sample or {})
        _Handler.sample[field] = bad
        client = AircraftLayerClient(base_url=server_with_sample)
        state = advance_flight_authority(FlightAuthorityState(), client)
        attr = {
            "fd_hdg_true_deg": "hdg_true_deg",
            "fd_hdg_mag_deg": "hdg_mag_deg",
        }[field]
        assert getattr(state, attr) is None


class TestDecideFlightSpeech:
    def test_no_mode_n_on_either_side_is_a_no_op(self) -> None:
        assert (
            decide_flight_speech(FlightAuthorityState(), FlightAuthorityState()) is None
        )

    def test_an_unchanged_mode_n_is_a_no_op(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=1)
        new = FlightAuthorityState(fd_mode="m1", mode_n=1)
        assert decide_flight_speech(prev, new) is None

    def test_a_take_edge_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="off", mode_n=1)
        new = FlightAuthorityState(fd_mode="m1", mode_n=2, mode_cause="take")
        assert decide_flight_speech(prev, new) is None

    def test_a_park_edge_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=2)
        new = FlightAuthorityState(fd_mode="m2", mode_n=3, mode_cause="park")
        assert decide_flight_speech(prev, new) is None

    def test_a_successful_unpark_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="m2", mode_n=3)
        new = FlightAuthorityState(fd_mode="m1", mode_n=4, mode_cause="unpark")
        assert decide_flight_speech(prev, new) is None

    def test_a_player_release_into_off_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=2)
        new = FlightAuthorityState(fd_mode="off", mode_n=3, mode_cause="release")
        assert decide_flight_speech(prev, new) is None

    def test_a_mission_stop_into_off_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="m2", mode_n=3)
        new = FlightAuthorityState(fd_mode="off", mode_n=4, mode_cause="stop")
        assert decide_flight_speech(prev, new) is None

    def test_a_body_layer_reset_into_off_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=2)
        new = FlightAuthorityState(fd_mode="off", mode_n=3, mode_cause="reset")
        assert decide_flight_speech(prev, new) is None

    @pytest.mark.parametrize(
        "cause", ["unpark_refused", "unpark_unarmed", "envelope", "nan", "dead"]
    )
    def test_a_forced_handover_into_off_is_urgent(self, cause: str) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=2)
        new = FlightAuthorityState(fd_mode="off", mode_n=3, mode_cause=cause)
        decision = decide_flight_speech(prev, new)
        assert decision is not None
        assert decision.says == "You have controls!"
        assert decision.urgent is True


class TestControlsToPlayerEdge:
    """`controls_to_player_edge` -- the SAU-handover trigger's own "when"
    (`plans/flight-lift-vector/explore-notes.md`, "SAU in mode 1"): fires
    on an `fd_mode` edge from `"m1"`/`"m2"`/`"taking"` into `"off"`, for
    *every* cause -- unlike `decide_flight_speech`, which stays silent on
    the causes in `_SILENT_OFF_CAUSES`."""

    @pytest.mark.parametrize("prior_mode", ["m1", "m2", "taking"])
    @pytest.mark.parametrize(
        "cause",
        ["release", "stop", "reset", "unpark_refused", "envelope", "nan", "dead"],
    )
    def test_fires_on_every_kind_of_edge_into_off(
        self, prior_mode: str, cause: str
    ) -> None:
        prev = FlightAuthorityState(fd_mode=prior_mode)
        new = FlightAuthorityState(fd_mode="off", mode_cause=cause)
        assert controls_to_player_edge(prev, new) is True

    def test_does_not_fire_on_a_take_edge(self) -> None:
        prev = FlightAuthorityState(fd_mode="off")
        new = FlightAuthorityState(fd_mode="taking", mode_cause="take")
        assert controls_to_player_edge(prev, new) is False

    def test_does_not_fire_on_a_park_edge(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1")
        new = FlightAuthorityState(fd_mode="m2", mode_cause="park")
        assert controls_to_player_edge(prev, new) is False

    def test_does_not_fire_on_a_successful_unpark_edge(self) -> None:
        prev = FlightAuthorityState(fd_mode="m2")
        new = FlightAuthorityState(fd_mode="m1", mode_cause="unpark")
        assert controls_to_player_edge(prev, new) is False

    def test_does_not_fire_when_already_off(self) -> None:
        prev = FlightAuthorityState(fd_mode="off")
        new = FlightAuthorityState(fd_mode="off")
        assert controls_to_player_edge(prev, new) is False

    def test_does_not_fire_on_the_default_no_sample_state(self) -> None:
        assert (
            controls_to_player_edge(FlightAuthorityState(), FlightAuthorityState())
            is False
        )


class TestControlsToPetrovichEdge:
    """`controls_to_petrovich_edge` -- the twin of `TestControlsToPlayerEdge`
    above, the other direction: fires on an `fd_mode` edge into `"m1"`
    from anything else (`plans/flight-lift-vector/explore-notes.md`, "M4
    SAU explore (2026-11-28)")."""

    @pytest.mark.parametrize("prior_mode", ["off", "taking", "m2"])
    def test_fires_entering_m1_from_any_other_mode(self, prior_mode: str) -> None:
        prev = FlightAuthorityState(fd_mode=prior_mode)
        new = FlightAuthorityState(fd_mode="m1")
        assert controls_to_petrovich_edge(prev, new) is True

    def test_does_not_fire_when_already_in_m1(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1")
        new = FlightAuthorityState(fd_mode="m1")
        assert controls_to_petrovich_edge(prev, new) is False

    def test_does_not_fire_on_an_edge_into_m2(self) -> None:
        prev = FlightAuthorityState(fd_mode="off")
        new = FlightAuthorityState(fd_mode="m2", mode_cause="park")
        assert controls_to_petrovich_edge(prev, new) is False

    def test_does_not_fire_on_an_edge_into_off(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1")
        new = FlightAuthorityState(fd_mode="off", mode_cause="release")
        assert controls_to_petrovich_edge(prev, new) is False

    def test_does_not_fire_on_the_default_no_sample_state(self) -> None:
        assert (
            controls_to_petrovich_edge(FlightAuthorityState(), FlightAuthorityState())
            is False
        )

    def test_fires_once_on_a_retake_cycle(self) -> None:
        """m1 -> off -> taking -> m1 fires exactly once, on the poll
        that lands back in m1 -- not on the intermediate edges."""
        m1 = FlightAuthorityState(fd_mode="m1")
        off = FlightAuthorityState(fd_mode="off", mode_cause="release")
        taking = FlightAuthorityState(fd_mode="taking", mode_cause="take")
        m1_again = FlightAuthorityState(fd_mode="m1")
        assert controls_to_petrovich_edge(m1, off) is False
        assert controls_to_petrovich_edge(off, taking) is False
        assert controls_to_petrovich_edge(taking, m1_again) is True


class TestDecideCarriedValueSpeech:
    """Review-fix round (`plans/flight-desired-state/review-s3.md`
    Required Fix 1): U2's "a carried value the new mode cannot fly
    exactly is announced once, not urgent" line, the m2->m1 half."""

    def test_no_mode_n_on_either_side_is_a_no_op(self) -> None:
        assert (
            decide_carried_value_speech(FlightAuthorityState(), FlightAuthorityState())
            == []
        )

    def test_an_unchanged_mode_n_is_a_no_op(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=1)
        new = FlightAuthorityState(fd_mode="m1", mode_n=1)
        assert decide_carried_value_speech(prev, new) == []

    def test_a_park_edge_says_nothing(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=2)
        new = FlightAuthorityState(fd_mode="m2", mode_n=3, mode_cause="park")
        assert decide_carried_value_speech(prev, new) == []

    def test_an_unpark_whose_values_fit_says_nothing(self) -> None:
        prev = FlightAuthorityState(fd_mode="m2", mode_n=3)
        new = FlightAuthorityState(
            fd_mode="m1",
            mode_n=4,
            mode_cause="unpark",
            ias_kmh=150.0,
            alt_m=300.0,
            alt_ref="agl",
        )
        assert decide_carried_value_speech(prev, new) == []

    def test_a_carried_speed_of_0_is_flown_exactly_no_floor_no_announcement(
        self,
    ) -> None:
        """BL-16 lift-vector law, Stage LV-1 (U8, "no floor"): the
        plan's own worked example used to say mode 1 could not fly
        0 km/h and announced its own minimum instead -- that floor
        (`MIN_IAS_KMH`) is gone entirely now, so "speed 0" in mode 2,
        then unpark, is flown exactly as commanded and says nothing new
        (`clamp_speed(0.0) == 0.0`, matching the carried value exactly)."""
        prev = FlightAuthorityState(fd_mode="m2", mode_n=3)
        new = FlightAuthorityState(
            fd_mode="m1", mode_n=4, mode_cause="unpark", ias_kmh=0.0
        )
        assert decide_carried_value_speech(prev, new) == []

    def test_a_carried_speed_above_the_ceiling_is_clamped_down(self) -> None:
        prev = FlightAuthorityState(fd_mode="m2", mode_n=3)
        new = FlightAuthorityState(
            fd_mode="m1",
            mode_n=4,
            mode_cause="unpark",
            ias_kmh=MAX_IAS_KMH + 100.0,
        )
        decisions = decide_carried_value_speech(prev, new)
        assert len(decisions) == 1
        digits = " ".join(str(int(MAX_IAS_KMH)))
        assert decisions[0].says == f"Speed {digits}."

    def test_a_carried_agl_altitude_below_the_floor_is_announced(self) -> None:
        prev = FlightAuthorityState(fd_mode="m2", mode_n=3)
        new = FlightAuthorityState(
            fd_mode="m1",
            mode_n=4,
            mode_cause="unpark",
            alt_m=FLOOR_AGL_M - 10.0,
            alt_ref="agl",
        )
        decisions = decide_carried_value_speech(prev, new)
        assert len(decisions) == 1
        assert decisions[0].says == f"{int(FLOOR_AGL_M)} meters."
        assert decisions[0].urgent is False

    def test_a_carried_baro_altitude_is_never_floored(self) -> None:
        """`clamp_altitude`'s own "agl floor only" rule -- a barometric
        carry, however low, is never clamped or announced here."""
        prev = FlightAuthorityState(fd_mode="m2", mode_n=3)
        new = FlightAuthorityState(
            fd_mode="m1",
            mode_n=4,
            mode_cause="unpark",
            alt_m=FLOOR_AGL_M - 10.0,
            alt_ref="baro",
        )
        assert decide_carried_value_speech(prev, new) == []

    def test_only_altitude_is_carried_badly_now_speed_has_no_floor(self) -> None:
        """BL-16 lift-vector law, Stage LV-1 (U8, "no floor"): `ias_kmh
        = 0.0` used to be a second badly-carried part (clamped up to
        `MIN_IAS_KMH`) alongside the altitude floor -- that floor is
        gone, so only the altitude part announces now."""
        prev = FlightAuthorityState(fd_mode="m2", mode_n=3)
        new = FlightAuthorityState(
            fd_mode="m1",
            mode_n=4,
            mode_cause="unpark",
            ias_kmh=0.0,
            alt_m=0.0,
            alt_ref="agl",
        )
        decisions = decide_carried_value_speech(prev, new)
        assert len(decisions) == 1
        assert all(decision.urgent is False for decision in decisions)

    def test_a_voice_take_edge_is_never_this_announcement(self) -> None:
        """`mode_cause == "take"` (a voice take) never carries anything
        from mode 2 -- only `"unpark"` does."""
        prev = FlightAuthorityState(fd_mode="off", mode_n=1)
        new = FlightAuthorityState(
            fd_mode="m1", mode_n=2, mode_cause="take", ias_kmh=0.0
        )
        assert decide_carried_value_speech(prev, new) == []


class TestParseAcks:
    """BL-16 Stage 3 (`plans/flight-desired-state/plan.md`, section 5) --
    `parse_acks` reads `Export.lua`'s own semicolon-joined `fd_acks` ring
    string."""

    def test_none_is_empty(self) -> None:
        assert parse_acks(None) == []

    def test_empty_string_is_empty(self) -> None:
        assert parse_acks("") == []

    def test_a_single_accept(self) -> None:
        assert parse_acks("1:a:m1") == [(1, "a", "m1")]

    def test_several_entries_in_order(self) -> None:
        assert parse_acks("1:a:m1;2:r:wrong_mode;3:a:m2") == [
            (1, "a", "m1"),
            (2, "r", "wrong_mode"),
            (3, "a", "m2"),
        ]

    def test_a_malformed_entry_is_skipped_not_raised(self) -> None:
        assert parse_acks("1:a:m1;garbage;2:a:m2") == [
            (1, "a", "m1"),
            (2, "a", "m2"),
        ]


class TestResolvePendingTake:
    """BL-16 Stage 3, section 3a -- the voice-take confirm/timeout
    handshake, driven by `fd_acks` instead of `decide_flight_control`'s
    own (deleted) `fc_take_seq`/`fc_mode` polling."""

    def test_no_pending_take_is_a_no_op(self) -> None:
        pending, decision = resolve_pending_take(None, "1:a:m1", 10.0)
        assert pending is None
        assert decision is None

    def test_still_waiting_with_no_matching_ack_and_no_timeout(self) -> None:
        pending = PendingTake(seq=1, says="I have controls.", sent_at_sim=0.0)
        new_pending, decision = resolve_pending_take(pending, None, 0.5)
        assert new_pending is pending
        assert decision is None

    def test_accepted_speaks_the_recorded_says_urgently_and_clears(self) -> None:
        pending = PendingTake(seq=1, says="I have controls.", sent_at_sim=0.0)
        new_pending, decision = resolve_pending_take(pending, "1:a:m1", 0.5)
        assert new_pending is None
        assert decision is not None
        assert decision.says == "I have controls."
        assert decision.urgent is True

    def test_an_ack_for_a_different_seq_is_ignored(self) -> None:
        pending = PendingTake(seq=2, says="I have controls.", sent_at_sim=0.0)
        new_pending, decision = resolve_pending_take(pending, "1:a:m1", 0.5)
        assert new_pending is pending
        assert decision is None

    def test_refused_speaks_unable_not_ready_non_urgently_and_clears(self) -> None:
        pending = PendingTake(seq=1, says="I have controls.", sent_at_sim=0.0)
        new_pending, decision = resolve_pending_take(pending, "1:r:precondition", 0.5)
        assert new_pending is None
        assert decision is not None
        assert decision.says == "Unable, not ready."
        assert decision.urgent is False

    def test_timeout_with_no_ack_speaks_unable_not_ready_and_clears(self) -> None:
        pending = PendingTake(seq=1, says="I have controls.", sent_at_sim=0.0)
        new_pending, decision = resolve_pending_take(
            pending, None, HANDOVER_ACK_TIMEOUT_S
        )
        assert new_pending is None
        assert decision is not None
        assert decision.says == "Unable, not ready."
        assert decision.urgent is False

    def test_an_ack_and_a_timeout_in_the_same_tick_resolve_as_the_ack(self) -> None:
        """Section 3a: "an ack and a deadline in the same tick resolve
        as the ack" -- `resolve_pending_take` checks `acks` before the
        timeout, so an accept landing exactly at (or after) the timeout
        instant still wins over it."""
        pending = PendingTake(seq=1, says="I have controls.", sent_at_sim=0.0)
        new_pending, decision = resolve_pending_take(
            pending, "1:a:m1", HANDOVER_ACK_TIMEOUT_S
        )
        assert new_pending is None
        assert decision is not None
        assert decision.says == "I have controls."
        assert decision.urgent is True


class TestResolvePendingFlightReadbacks:
    """BL-16 Stage 3b (`plans/flight-desired-state/plan.md`, section 3a)
    -- `resolve_pending_flight_readbacks`, generalising `resolve_pending_
    take`'s own ack-driven wait to every ordinary flight-channel
    command's readback (U1: "Readback on acting on command -> wait for
    lua")."""

    def test_no_pending_entries_is_a_no_op(self) -> None:
        remaining, decisions = resolve_pending_flight_readbacks([], "1:a:m1", 10.0)
        assert remaining == []
        assert decisions == []

    def test_accepted_speaks_every_line_non_urgently_and_clears(self) -> None:
        pending = [
            PendingFlightReadback(seq=1, lines=("Heading 090.",), sent_at_sim=0.0)
        ]
        remaining, decisions = resolve_pending_flight_readbacks(pending, "1:a:m1", 0.5)
        assert remaining == []
        assert [d.says for d in decisions] == ["Heading 090."]
        assert all(d.urgent is False for d in decisions)

    def test_accepted_speaks_every_line_in_order_for_one_seq(self) -> None:
        """`level_flight`'s own handler calls `say` more than once --
        every line a single accepted `seq` carries speaks, in order."""
        pending = [
            PendingFlightReadback(
                seq=1,
                lines=("Heading 090.", "300 meters.", "Speed 150."),
                sent_at_sim=0.0,
            )
        ]
        remaining, decisions = resolve_pending_flight_readbacks(pending, "1:a:m2", 0.5)
        assert remaining == []
        assert [d.says for d in decisions] == [
            "Heading 090.",
            "300 meters.",
            "Speed 150.",
        ]

    def test_refused_speaks_the_mapped_unable_token(self) -> None:
        pending = [
            PendingFlightReadback(seq=1, lines=("Heading 090.",), sent_at_sim=0.0)
        ]
        remaining, decisions = resolve_pending_flight_readbacks(
            pending, "1:r:wrong_mode", 0.5
        )
        assert remaining == []
        assert [d.says for d in decisions] == ["Unable, AI overlay."]

    def test_an_unmapped_refusal_reason_falls_back_to_not_ready(self) -> None:
        pending = [
            PendingFlightReadback(seq=1, lines=("Heading 090.",), sent_at_sim=0.0)
        ]
        remaining, decisions = resolve_pending_flight_readbacks(
            pending, "1:r:stale", 0.5
        )
        assert remaining == []
        assert [d.says for d in decisions] == ["Unable, not ready."]

    def test_timeout_with_no_ack_speaks_unable_not_ready_and_clears(self) -> None:
        pending = [
            PendingFlightReadback(seq=1, lines=("Heading 090.",), sent_at_sim=0.0)
        ]
        remaining, decisions = resolve_pending_flight_readbacks(
            pending, None, HANDOVER_ACK_TIMEOUT_S
        )
        assert remaining == []
        assert [d.says for d in decisions] == ["Unable, not ready."]

    def test_still_waiting_leaves_the_entry_untouched(self) -> None:
        pending = [
            PendingFlightReadback(seq=1, lines=("Heading 090.",), sent_at_sim=0.0)
        ]
        remaining, decisions = resolve_pending_flight_readbacks(pending, None, 0.5)
        assert remaining == pending
        assert decisions == []

    def test_an_unresolved_front_holds_a_resolved_later_entry(self) -> None:
        """3a: "ack outcomes in seq order, never arrival order" -- `seq`
        2's own accept arrives first, but `seq` 1 is still unresolved and
        not yet timed out, so neither speaks this call."""
        pending = [
            PendingFlightReadback(seq=1, lines=("Heading 090.",), sent_at_sim=0.0),
            PendingFlightReadback(seq=2, lines=("Speed 200.",), sent_at_sim=0.0),
        ]
        remaining, decisions = resolve_pending_flight_readbacks(pending, "2:a:m1", 0.5)
        assert remaining == pending
        assert decisions == []

    def test_two_accepted_entries_speak_in_seq_order(self) -> None:
        """3a's own card example: "climb 50, climb 50" in one breath --
        two readbacks, in the order spoken, not the order the acks
        happen to arrive."""
        pending = [
            PendingFlightReadback(seq=1, lines=("350 meters.",), sent_at_sim=0.0),
            PendingFlightReadback(seq=2, lines=("400 meters.",), sent_at_sim=0.0),
        ]
        remaining, decisions = resolve_pending_flight_readbacks(
            pending, "2:a:m1;1:a:m1", 0.5
        )
        assert remaining == []
        assert [d.says for d in decisions] == ["350 meters.", "400 meters."]

    def test_suppress_accepted_still_consumes_the_ack_but_speaks_nothing(self) -> None:
        """3a: "a change into off in the same read suppresses the
        readbacks of requests accepted in that read" -- the entry is
        still resolved (removed from the queue), it just yields no
        decision."""
        pending = [
            PendingFlightReadback(seq=1, lines=("Heading 090.",), sent_at_sim=0.0)
        ]
        remaining, decisions = resolve_pending_flight_readbacks(
            pending, "1:a:m1", 0.5, suppress_accepted=True
        )
        assert remaining == []
        assert decisions == []

    def test_suppress_accepted_never_suppresses_a_refusal_or_timeout(self) -> None:
        pending = [
            PendingFlightReadback(seq=1, lines=("Heading 090.",), sent_at_sim=0.0),
            PendingFlightReadback(seq=2, lines=("Speed 200.",), sent_at_sim=0.0),
        ]
        remaining, decisions = resolve_pending_flight_readbacks(
            pending,
            "1:r:precondition",
            HANDOVER_ACK_TIMEOUT_S,
            suppress_accepted=True,
        )
        # `seq` 1 refused, `seq` 2 times out -- neither is the accepted
        # case `suppress_accepted` guards, so both still speak.
        assert remaining == []
        assert [d.says for d in decisions] == [
            "Unable, not ready.",
            "Unable, not ready.",
        ]


def test_handover_ack_timeout_exceeds_accept_window_with_margin() -> None:
    """Section 3a: `HANDOVER_ACK_TIMEOUT_S` must exceed `FLIGHT_REQUEST_
    ACCEPT_WINDOW_S` by at least one body-layer poll (1.0 s) plus
    `Export.lua`'s own push cadence (0.2 s) -- tuning one constant must
    not silently break the other."""
    assert HANDOVER_ACK_TIMEOUT_S >= FLIGHT_REQUEST_ACCEPT_WINDOW_S + 1.0 + 0.2
