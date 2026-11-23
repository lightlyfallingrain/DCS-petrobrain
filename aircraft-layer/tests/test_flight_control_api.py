"""BL-16 mode 1 (unparked, raw axes), Stage M1 (`plans/flight-control/
plan.md`, "Revised 2026-11-18"): schema, cache, line routing, and the
`GET /flight_control/latest` endpoint. **BL-16 Stage 3** (`plans/
flight-desired-state/plan.md`) replaces `CommandSender.send_flight_
control`/`POST /command/flight_control` with `send_flight`/`POST
/command/flight` -- the one numbered channel.

Mirrors `test_ai_pilot_wheel_api.py` (the sibling per-frame-feed tier)
for the read side and `test_ai_pilot_goal.py` (the sibling write-channel
tier) for the write side -- same "not an error" `None`-before-first-
sample posture, same routing-ahead-of-telemetry shape, same shape-
validation-only/raise-on-failure posture for the command endpoint."""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import (
    _RESET_EPOCH_MAX,
    TelemetryAPIServer,
)
from collector.cache import (
    FlightControlCache,
    PetrovichIndicationCache,
    PetrovichWheelCache,
    TelemetryCache,
    WorldObjectsCache,
)
from collector.command_sender import CommandSender, CommandSendError
from collector.server import CollectorServer
from schema import FlightControlParseError, FlightControlState

_LINE = (
    '{"t":12.5,"fc_mode":"active",'
    '"fc_take_origin":"voice","fc_takeover_mode":"heading",'
    '"fc_measured_heading":271.2,"fc_measured_altitude":480.0,'
    '"fc_measured_speed":160.0,"fc_in_band_heading":null,'
    '"fc_in_band_altitude":null,"fc_in_band_speed":null,'
    '"fc_agl_source":"radar","fc_release_reason":null,'
    '"fc_refuse_cause":null,"fc_limit_hit":false,'
    '"fc_axes_pitch":true,"fc_axes_roll":true,"fc_axes_pedal":false,'
    '"fc_axes_collective":false}'
)


class TestFlightControlState:
    """BL-16 Stage 3 (`plans/flight-desired-state/plan.md`) dropped
    `fc_goal_*`/`fc_take_seq`/`fc_goal_seq`/`fc_last_cmd_seq` from this
    schema entirely -- the commanded heading/altitude/speed is `flight_
    desired`'s own `fd_*` fields now (`test_flight_desired_api.py`)."""

    def test_parses_a_line(self) -> None:
        sample = FlightControlState.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.dcs_model_time_s == pytest.approx(12.5)
        assert sample.received_wall_clock_s == 99.0
        assert sample.fc_mode == "active"
        assert sample.take_origin == "voice"
        assert sample.takeover_mode == "heading"
        assert sample.measured_heading_deg == pytest.approx(271.2)
        assert sample.measured_altitude_m == pytest.approx(480.0)
        assert sample.measured_speed_kmh == pytest.approx(160.0)
        assert sample.agl_source == "radar"
        assert sample.release_reason is None
        assert sample.refuse_cause is None
        assert sample.limit_hit is False
        assert sample.axes_enabled == {
            "pitch": True,
            "roll": True,
            "pedal": False,
            "collective": False,
        }

    def test_missing_t_is_a_parse_error(self) -> None:
        with pytest.raises(FlightControlParseError):
            FlightControlState.from_json_line(
                '{"fc_mode":"off"}', received_wall_clock_s=0.0
            )

    def test_missing_fc_mode_is_a_parse_error(self) -> None:
        with pytest.raises(FlightControlParseError):
            FlightControlState.from_json_line('{"t":1.0}', received_wall_clock_s=0.0)

    def test_non_string_fc_mode_is_a_parse_error(self) -> None:
        with pytest.raises(FlightControlParseError):
            FlightControlState.from_json_line(
                '{"t":1.0,"fc_mode":3}', received_wall_clock_s=0.0
            )

    def test_missing_axes_enabled_field_is_a_parse_error(self) -> None:
        """Every `fc_axes_*` field is required on the wire, unlike every
        other field here -- `Export.lua` always knows its own enable
        flags, so there is no "an older script omits this" case to
        tolerate."""
        with pytest.raises(FlightControlParseError):
            FlightControlState.from_json_line(
                '{"t":1.0,"fc_mode":"off","fc_axes_pitch":true,'
                '"fc_axes_roll":true,"fc_axes_pedal":false}',
                received_wall_clock_s=0.0,
            )

    def test_non_number_optional_field_is_a_parse_error(self) -> None:
        with pytest.raises(FlightControlParseError):
            FlightControlState.from_json_line(
                '{"t":1.0,"fc_mode":"off","fc_measured_heading":"bogus",'
                '"fc_axes_pitch":true,"fc_axes_roll":true,'
                '"fc_axes_pedal":false,"fc_axes_collective":false}',
                received_wall_clock_s=0.0,
            )

    def test_absent_optional_fields_parse_as_none(self) -> None:
        line = (
            '{"t":1.0,"fc_mode":"off","fc_axes_pitch":true,'
            '"fc_axes_roll":true,"fc_axes_pedal":false,'
            '"fc_axes_collective":false}'
        )
        sample = FlightControlState.from_json_line(line, received_wall_clock_s=0.0)
        assert sample.take_origin is None
        assert sample.release_reason is None
        assert sample.limit_hit is False

    def test_slip_ball_fields_are_optional_and_absent_parses_as_none(self) -> None:
        sample = FlightControlState.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.slip_ball_pilot_raw is None
        assert sample.slip_ball_operator_raw is None
        assert sample.slip_ball_lo_api is None

    def test_slip_ball_fields_parse_when_present(self) -> None:
        line = _LINE[:-1] + (
            ',"fc_slip_ball_pilot_raw":0.125,'
            '"fc_slip_ball_operator_raw":-0.25,'
            '"fc_slip_ball_lo_api":null}'
        )
        sample = FlightControlState.from_json_line(line, received_wall_clock_s=99.0)
        assert sample.slip_ball_pilot_raw == pytest.approx(0.125)
        assert sample.slip_ball_operator_raw == pytest.approx(-0.25)
        assert sample.slip_ball_lo_api is None

    def test_est_fields_are_optional_and_absent_parses_as_none(self) -> None:
        """BL-16 lift-vector law, Stage LV-0 (`plans/flight-lift-vector/
        plan.md`) -- the estimator's own shadow fields, same optional
        posture as `fc_slip_ball_*` above."""
        sample = FlightControlState.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.est_a_f is None
        assert sample.est_a_r is None
        assert sample.est_a_u is None
        assert sample.est_v_g is None
        assert sample.est_v_g_f is None
        assert sample.est_phi_dot is None
        assert sample.est_theta_dot is None
        assert sample.est_psi_dot is None
        assert sample.est_ball is None
        assert sample.est_lambda is None

    def test_est_fields_parse_when_present(self) -> None:
        line = _LINE[:-1] + (
            ',"fc_est_a_f":0.1,"fc_est_a_r":-0.2,"fc_est_a_u":0.05,'
            '"fc_est_v_g":41.6,"fc_est_v_g_f":40.1,'
            '"fc_est_phi_dot":1.5,"fc_est_theta_dot":-0.5,"fc_est_psi_dot":3.2,'
            '"fc_est_ball":0.031,"fc_est_lambda":1.0}'
        )
        sample = FlightControlState.from_json_line(line, received_wall_clock_s=99.0)
        assert sample.est_a_f == pytest.approx(0.1)
        assert sample.est_a_r == pytest.approx(-0.2)
        assert sample.est_a_u == pytest.approx(0.05)
        assert sample.est_v_g == pytest.approx(41.6)
        assert sample.est_v_g_f == pytest.approx(40.1)
        assert sample.est_phi_dot == pytest.approx(1.5)
        assert sample.est_theta_dot == pytest.approx(-0.5)
        assert sample.est_psi_dot == pytest.approx(3.2)
        assert sample.est_ball == pytest.approx(0.031)
        assert sample.est_lambda == pytest.approx(1.0)

    def test_to_api_dict_carries_every_field(self) -> None:
        sample = FlightControlState.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.to_api_dict() == {
            "t": pytest.approx(12.5),
            "received_wall_clock_s": pytest.approx(99.0),
            "fc_mode": "active",
            "fc_take_origin": "voice",
            "fc_takeover_mode": "heading",
            "fc_measured_heading": pytest.approx(271.2),
            "fc_measured_altitude": pytest.approx(480.0),
            "fc_measured_speed": pytest.approx(160.0),
            "fc_in_band_heading": None,
            "fc_in_band_altitude": None,
            "fc_in_band_speed": None,
            "fc_agl_source": "radar",
            "fc_release_reason": None,
            "fc_refuse_cause": None,
            "fc_reset_epoch": None,
            "fc_limit_hit": False,
            "fc_axes_pitch": True,
            "fc_axes_roll": True,
            "fc_axes_pedal": False,
            "fc_axes_collective": False,
            "fc_slip_ball_pilot_raw": None,
            "fc_slip_ball_operator_raw": None,
            "fc_slip_ball_lo_api": None,
            "fc_est_a_f": None,
            "fc_est_a_r": None,
            "fc_est_a_u": None,
            "fc_est_v_g": None,
            "fc_est_v_g_f": None,
            "fc_est_phi_dot": None,
            "fc_est_theta_dot": None,
            "fc_est_psi_dot": None,
            "fc_est_ball": None,
            "fc_est_lambda": None,
        }


class TestFlightControlCache:
    def test_empty_until_a_line_arrives(self) -> None:
        assert FlightControlCache().latest() is None

    def test_keeps_only_the_latest(self) -> None:
        cache = FlightControlCache()
        first = FlightControlState.from_json_line(_LINE, received_wall_clock_s=1.0)
        second = FlightControlState.from_json_line(_LINE, received_wall_clock_s=2.0)
        cache.push(first)
        cache.push(second)
        assert cache.latest() is second


class TestCollectorRouting:
    def _collector(self, flight_control_cache: FlightControlCache) -> CollectorServer:
        return CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            flight_control_cache=flight_control_cache,
        )

    def test_an_fc_line_reaches_the_cache(self) -> None:
        cache = FlightControlCache()
        self._collector(cache)._handle_line(_LINE)
        latest = cache.latest()
        assert latest is not None
        assert latest.fc_mode == "active"

    def test_an_fc_line_is_never_parsed_as_telemetry(self) -> None:
        telemetry = TelemetryCache()
        cache = FlightControlCache()
        collector = CollectorServer(
            telemetry,
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            flight_control_cache=cache,
        )
        collector._handle_line(_LINE)
        assert telemetry.latest() is None
        assert cache.latest() is not None

    def test_a_collector_with_no_flight_control_cache_drops_the_line(self) -> None:
        collector = CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
        )
        collector._handle_line(_LINE)  # must not raise

    def test_a_malformed_fc_line_is_dropped_not_raised(self) -> None:
        cache = FlightControlCache()
        self._collector(cache)._handle_line('{"t":1.0,"fc_mode":3}')
        assert cache.latest() is None


class TestFlightControlLatestEndpoint:
    @pytest.fixture
    def server(self) -> Iterator[tuple[str, FlightControlCache]]:
        cache = FlightControlCache()
        api = TelemetryAPIServer(
            TelemetryCache(), host="127.0.0.1", port=0, flight_control_cache=cache
        )
        api.open()
        thread = threading.Thread(target=api.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{api.port}", cache
        finally:
            api.close()
            thread.join(timeout=5)

    def _get(self, base_url: str) -> object:
        with urllib.request.urlopen(
            f"{base_url}/flight_control/latest", timeout=5
        ) as response:
            return json.loads(response.read())

    def test_null_before_the_first_line_arrives(
        self, server: tuple[str, FlightControlCache]
    ) -> None:
        base_url, _ = server
        assert self._get(base_url) is None

    def test_serves_the_latest_sample(
        self, server: tuple[str, FlightControlCache]
    ) -> None:
        base_url, cache = server
        cache.push(FlightControlState.from_json_line(_LINE, received_wall_clock_s=99.0))
        payload = self._get(base_url)
        assert (
            payload
            == FlightControlState.from_json_line(
                _LINE, received_wall_clock_s=99.0
            ).to_api_dict()
        )


class TestSendFlight:
    """`CommandSender.send_flight` -- BL-16 Stage 3's one numbered
    channel (`plans/flight-desired-state/plan.md`, section 5), replacing
    `send_flight_control` entirely."""

    def test_delivers_well_formed_datagram(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_flight(7, 1, 123.5, "take", {})

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded == {
                "op": "flight",
                "epoch": 7,
                "seq": 1,
                "until": 123.5,
                "kind": "take",
            }
        finally:
            receiver.close()

    def test_a_set_message_carries_its_fields(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_flight(7, 2, 124.0, "set", {"heading_deg": 90.0})

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded["kind"] == "set"
            assert decoded["heading_deg"] == pytest.approx(90.0)
        finally:
            receiver.close()

    def test_raises_command_send_error_on_a_failed_send(self) -> None:
        """Mirrors `test_ai_pilot_goal.py`'s own identical test -- a
        fake socket whose `sendto` always raises `OSError`, rather than
        relying on a real network failure mode."""

        class _FailingSocket:
            def sendto(self, payload: bytes, address: tuple[str, int]) -> int:
                raise OSError("simulated send failure")

            def close(self) -> None:
                pass

        sender = CommandSender(host="127.0.0.1", port=1)
        sender.open()
        sender._socket = _FailingSocket()  # type: ignore[assignment]

        with pytest.raises(CommandSendError):
            sender.send_flight(7, 1, 1.0, "release", {})


class TestSendFlightLease:
    """`CommandSender.send_flight_lease` -- BL-16 Stage 2 (`plans/
    flight-desired-state/plan.md`, refinement 3), mirrors `TestSend
    FlightControl` above."""

    def test_delivers_well_formed_datagram(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_flight_lease(42, {"arm_lease_s": 3.0})

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded == {
                "op": "flight_lease",
                "epoch": 42,
                "limits": {"arm_lease_s": 3.0},
            }
        finally:
            receiver.close()

    def test_raises_command_send_error_on_a_failed_send(self) -> None:
        class _FailingSocket:
            def sendto(self, payload: bytes, address: tuple[str, int]) -> int:
                raise OSError("simulated send failure")

            def close(self) -> None:
                pass

        sender = CommandSender(host="127.0.0.1", port=1)
        sender.open()
        sender._socket = _FailingSocket()  # type: ignore[assignment]

        with pytest.raises(CommandSendError):
            sender.send_flight_lease(1, None)


class _RecordingCommandSender:
    def __init__(self, *, raise_on_send: bool = False) -> None:
        self.sent: list[tuple[int, int, float, str, dict[str, object]]] = []
        self.reset_sent: list[int] = []
        self.lease_sent: list[tuple[int, object]] = []
        self.raise_on_send = raise_on_send

    def send_flight(
        self,
        epoch: int,
        seq: int,
        until: float,
        kind: str,
        fields: dict[str, object],
    ) -> None:
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.sent.append((epoch, seq, until, kind, fields))

    def send_reset(self, epoch: int) -> None:
        """BL-16 sortie 2026-11-20 (`docs/acceptance/
        2026-11-20-sortie-feedback.md`) -- `POST /command/reset`'s own
        forwarding target."""
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.reset_sent.append(epoch)

    def send_flight_lease(self, epoch: int, limits: dict[str, float] | None) -> None:
        """BL-16 Stage 2 (`plans/flight-desired-state/plan.md`,
        refinement 3) -- `POST /command/flight_lease`'s own forwarding
        target, replacing the old `send_flight_control(..., "arm", ...)`
        call."""
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.lease_sent.append((epoch, limits))


@pytest.fixture
def running_server_with_sender() -> Iterator[
    tuple[TelemetryAPIServer, _RecordingCommandSender]
]:
    cache = TelemetryCache()
    sender = _RecordingCommandSender()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0, command_sender=sender)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, sender
    finally:
        server.close()
        thread.join(timeout=5)


def _post(server: TelemetryAPIServer, path: str, body: object) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    data = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


class TestFlightCommandEndpoint:
    """BL-16 Stage 3 (`plans/flight-desired-state/plan.md`, section 5) --
    `POST /command/flight`, replacing `/command/flight_control`
    entirely. Fields are flat on the body, never nested under `"goal"`."""

    def test_a_take_message_forwards_to_sender(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {"epoch": 7, "seq": 1, "until": 10.5, "kind": "take"}
        status, resp_body = _post(server, "/command/flight", body)
        assert status == 200
        assert resp_body == {"ok": True}
        assert sender.sent == [(7, 1, pytest.approx(10.5), "take", {})]

    def test_a_set_message_forwards_only_its_present_fields(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {
            "epoch": 7,
            "seq": 2,
            "until": 10.5,
            "kind": "set",
            "heading_deg": 180.0,
            "turn": None,
        }
        status, _body = _post(server, "/command/flight", body)
        assert status == 200
        assert sender.sent == [
            (7, 2, pytest.approx(10.5), "set", {"heading_deg": 180.0})
        ]

    def test_a_turn_field_is_accepted(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {"epoch": 7, "seq": 3, "until": 10.5, "kind": "set", "turn": -1}
        status, _body = _post(server, "/command/flight", body)
        assert status == 200
        assert sender.sent == [(7, 3, pytest.approx(10.5), "set", {"turn": -1})]

    def test_an_invalid_turn_value_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {"epoch": 7, "seq": 4, "until": 10.5, "kind": "set", "turn": 2}
        status, _body = _post(server, "/command/flight", body)
        assert status == 400
        assert sender.sent == []

    def test_a_turn_style_field_is_accepted(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {
            "epoch": 7,
            "seq": 5,
            "until": 10.5,
            "kind": "set",
            "heading_deg": 90.0,
            "turn_rate_deg_s": -20.0,
            "turn_style": "break",
        }
        status, _body = _post(server, "/command/flight", body)
        assert status == 200
        assert sender.sent == [
            (
                7,
                5,
                pytest.approx(10.5),
                "set",
                {
                    "heading_deg": 90.0,
                    "turn_rate_deg_s": -20.0,
                    "turn_style": "break",
                },
            )
        ]

    def test_an_invalid_turn_style_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {
            "epoch": 7,
            "seq": 5,
            "until": 10.5,
            "kind": "set",
            "turn_style": "bogus",
        }
        status, _body = _post(server, "/command/flight", body)
        assert status == 400
        assert sender.sent == []

    def test_an_invalid_alt_ref_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {
            "epoch": 7,
            "seq": 6,
            "until": 10.5,
            "kind": "set",
            "alt_m": 200.0,
            "alt_ref": "bogus",
        }
        status, _body = _post(server, "/command/flight", body)
        assert status == 400
        assert sender.sent == []

    def test_an_invalid_kind_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {"epoch": 7, "seq": 1, "until": 10.5, "kind": "bogus"}
        status, _body = _post(server, "/command/flight", body)
        assert status == 400
        assert sender.sent == []

    def test_a_mode_2_only_kind_is_a_valid_shape(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        """BL-16 Stage 3: `align`/`align_for_launch`/`recover`/
        `translate`/`hover_hold`/`hover_step` are accepted *shapes* at
        this layer (`Export.lua` is what refuses `wrong_mode` until
        Stage 4 wires them up) -- this layer never reshapes the closed
        vocabulary for a kind it does not implement yet."""
        server, sender = running_server_with_sender
        body = {"epoch": 7, "seq": 1, "until": 10.5, "kind": "align"}
        status, _body = _post(server, "/command/flight", body)
        assert status == 200
        assert sender.sent == [(7, 1, pytest.approx(10.5), "align", {})]

    def test_missing_epoch_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {"seq": 1, "until": 10.5, "kind": "take"}
        status, _body = _post(server, "/command/flight", body)
        assert status == 400
        assert sender.sent == []

    def test_missing_seq_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {"epoch": 7, "until": 10.5, "kind": "take"}
        status, _body = _post(server, "/command/flight", body)
        assert status == 400
        assert sender.sent == []

    def test_missing_until_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {"epoch": 7, "seq": 1, "kind": "take"}
        status, _body = _post(server, "/command/flight", body)
        assert status == 400
        assert sender.sent == []

    def test_a_heading_field_beyond_its_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {
            "epoch": 7,
            "seq": 1,
            "until": 10.5,
            "kind": "set",
            "heading_deg": 999.0,
        }
        status, _body = _post(server, "/command/flight", body)
        assert status == 400
        assert sender.sent == []

    def test_a_non_json_body_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, _sender = running_server_with_sender
        status, _body = _post(server, "/command/flight", b"not json")
        assert status == 400

    def test_unconfigured_sender_returns_503(self) -> None:
        cache = TelemetryCache()
        server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = {"epoch": 7, "seq": 1, "until": 10.5, "kind": "take"}
            status, _body = _post(server, "/command/flight", body)
            assert status == 503
        finally:
            server.close()
            thread.join(timeout=5)

    def test_send_failure_returns_500(self) -> None:
        cache = TelemetryCache()
        sender = _RecordingCommandSender(raise_on_send=True)
        server = TelemetryAPIServer(
            cache, host="127.0.0.1", port=0, command_sender=sender
        )
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = {"epoch": 7, "seq": 1, "until": 10.5, "kind": "take"}
            status, _body = _post(server, "/command/flight", body)
            assert status == 500
        finally:
            server.close()
            thread.join(timeout=5)

    def test_the_old_flight_control_path_is_gone(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        """BL-16 Stage 3 -- `/command/flight_control` is retired
        entirely; the old path now resolves as any other unknown one."""
        server, _sender = running_server_with_sender
        body = {"seq": 1, "cmd": "take", "limits": None, "goal": None}
        status, _body = _post(server, "/command/flight_control", body)
        assert status == 404


class TestFlightLeaseCommandEndpoint:
    """BL-16 Stage 2 (`plans/flight-desired-state/plan.md`, refinement
    3) -- `POST /command/flight_lease`, replacing the old `{"cmd":
    "arm"}` message on `/command/flight_control`."""

    def test_a_lease_message_forwards_to_sender(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {"epoch": 7, "limits": {"min_ias_kmh": 80.0}}
        status, resp_body = _post(server, "/command/flight_lease", body)
        assert status == 200
        assert resp_body == {"ok": True}
        assert sender.lease_sent == [(7, {"min_ias_kmh": 80.0})]

    def test_missing_epoch_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/flight_lease", {"limits": None})
        assert status == 400
        assert sender.lease_sent == []

    def test_a_limits_field_beyond_its_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {"epoch": 1, "limits": {"min_ias_kmh": 10_000.0}}
        status, _body = _post(server, "/command/flight_lease", body)
        assert status == 400
        assert sender.lease_sent == []

    def test_no_limits_is_accepted(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/flight_lease", {"epoch": 1})
        assert status == 200
        assert sender.lease_sent == [(1, None)]

    def test_unconfigured_sender_returns_503(self) -> None:
        cache = TelemetryCache()
        server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _body = _post(server, "/command/flight_lease", {"epoch": 1})
            assert status == 503
        finally:
            server.close()
            thread.join(timeout=5)

    def test_send_failure_returns_500(self) -> None:
        cache = TelemetryCache()
        sender = _RecordingCommandSender(raise_on_send=True)
        server = TelemetryAPIServer(
            cache, host="127.0.0.1", port=0, command_sender=sender
        )
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _body = _post(server, "/command/flight_lease", {"epoch": 1})
            assert status == 500
        finally:
            server.close()
            thread.join(timeout=5)


class TestResetCommandEndpoint:
    """BL-16 sortie 2026-11-20 (`docs/acceptance/
    2026-11-20-sortie-feedback.md`) -- `POST /command/reset`, same
    shape-validation-only/raise-on-failure posture as `/command/
    flight_control` above."""

    def test_a_reset_message_forwards_to_sender(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, resp_body = _post(server, "/command/reset", {"epoch": 1234})
        assert status == 200
        assert resp_body == {"ok": True}
        assert sender.reset_sent == [1234]

    def test_missing_epoch_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/reset", {})
        assert status == 400
        assert sender.reset_sent == []

    def test_negative_epoch_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/reset", {"epoch": -1})
        assert status == 400
        assert sender.reset_sent == []

    def test_epoch_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/reset", {"epoch": _RESET_EPOCH_MAX + 1})
        assert status == 400
        assert sender.reset_sent == []

    def test_a_non_json_body_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, _sender = running_server_with_sender
        status, _body = _post(server, "/command/reset", b"not json")
        assert status == 400

    def test_unconfigured_sender_returns_503(self) -> None:
        cache = TelemetryCache()
        server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _body = _post(server, "/command/reset", {"epoch": 1})
            assert status == 503
        finally:
            server.close()
            thread.join(timeout=5)

    def test_send_failure_returns_500(self) -> None:
        cache = TelemetryCache()
        sender = _RecordingCommandSender(raise_on_send=True)
        server = TelemetryAPIServer(
            cache, host="127.0.0.1", port=0, command_sender=sender
        )
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _body = _post(server, "/command/reset", {"epoch": 1})
            assert status == 500
        finally:
            server.close()
            thread.join(timeout=5)
