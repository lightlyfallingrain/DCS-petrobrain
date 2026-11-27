"""BL-16 mode 2's goal channel wire op (`plans/flight-control/plan.md`,
"Stage P2 ready to build", "The goal channel -- wire shape"):
`CommandSender.send_ai_pilot_goal` and the `POST /command/ai_pilot_goal`
endpoint.

Mirrors `test_sight_target.py`'s `TestSendSightTarget`/
`TestSightTargetCommandEndpoint` structure -- same shape-validation-only,
raise-on-failure posture, plain `json.dumps` (not `_format_fixed_point`,
per `send_ai_pilot_goal`'s own docstring on why this channel has no
near-zero-exponent risk)."""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import (
    _AI_PILOT_GOAL_ALTITUDE_MAX_M,
    _AI_PILOT_GOAL_HEADING_MAX_DEG,
    _AI_PILOT_GOAL_SEQ_MAX,
    TelemetryAPIServer,
)
from collector.cache import TelemetryCache
from collector.command_sender import CommandSender, CommandSendError

_VALID_BODY = {
    "goal_seq": 1,
    "param": "heading",
    "heading_target_deg": 90.0,
    "altitude_target_m": None,
    "altitude_target_ref": None,
    "speed_target_kmh": None,
    "hvrt_direction": None,
    "hvrt_step": None,
}

_IDLE_BODY = {
    "goal_seq": 0,
    "param": None,
    "heading_target_deg": None,
    "altitude_target_m": None,
    "altitude_target_ref": None,
    "speed_target_kmh": None,
    "hvrt_direction": None,
    "hvrt_step": None,
}


class TestSendAiPilotGoal:
    """`CommandSender.send_ai_pilot_goal` -- mirrors `test_sight_target.
    py`'s `TestSendSightTarget` structure."""

    def test_delivers_well_formed_datagram(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_ai_pilot_goal(
                    3, "altitude", None, 300.0, "barometric", None, None
                )

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded == {
                "op": "ai_pilot_goal",
                "goal_seq": 3,
                "param": "altitude",
                "heading_target_deg": None,
                "altitude_target_m": 300.0,
                "altitude_target_ref": "barometric",
                "speed_target_kmh": None,
                "hvrt_direction": None,
                "hvrt_step": None,
                "cbtm_action": None,
                "cbtm_seq": None,
                "wake": False,
            }
        finally:
            receiver.close()

    def test_wake_true_is_forwarded(self) -> None:
        """`[[BL-B139]]` -- the recovery-only wake flag."""
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_ai_pilot_goal(
                    3, "altitude", None, 300.0, "barometric", None, None, wake=True
                )

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded["wake"] is True
        finally:
            receiver.close()

    def test_hvrt_step_is_a_one_shot_field(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_ai_pilot_goal(5, None, None, None, None, None, None, "up")

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded["hvrt_step"] == "up"
        finally:
            receiver.close()

    def test_the_idle_message_carries_every_field_null(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_ai_pilot_goal(0, None, None, None, None, None, None)

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded["param"] is None
            assert decoded["heading_target_deg"] is None
            assert decoded["altitude_target_m"] is None
            assert decoded["speed_target_kmh"] is None
            assert decoded["hvrt_direction"] is None
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
            sender.send_ai_pilot_goal(1, "heading", 90.0, None, None, None, None)


class _RecordingCommandSender(CommandSender):
    """A `CommandSender` double that records calls instead of sending UDP."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[object, ...]] = []
        self.raise_on_send = False

    def send_ai_pilot_goal(  # type: ignore[override]
        self,
        goal_seq: int,
        param: object,
        heading_target_deg: object,
        altitude_target_m: object,
        altitude_target_ref: object,
        speed_target_kmh: object,
        hvrt_direction: object,
        hvrt_step: object = None,
        cbtm_action: object = None,
        cbtm_seq: object = None,
        wake: object = False,
    ) -> None:
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.sent.append(
            (
                goal_seq,
                param,
                heading_target_deg,
                altitude_target_m,
                altitude_target_ref,
                speed_target_kmh,
                hvrt_direction,
                hvrt_step,
                cbtm_action,
                cbtm_seq,
                wake,
            )
        )


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


class TestAiPilotGoalCommandEndpoint:
    def test_valid_request_forwards_to_sender(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, body = _post(server, "/command/ai_pilot_goal", _VALID_BODY)
        assert status == 200
        assert body == {"ok": True}
        assert sender.sent == [
            (1, "heading", 90.0, None, None, None, None, None, None, None, False)
        ]

    def test_the_idle_message_is_accepted(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/ai_pilot_goal", _IDLE_BODY)
        assert status == 200
        assert sender.sent == [
            (0, None, None, None, None, None, None, None, None, None, False)
        ]

    def test_integer_target_values_are_accepted_and_forwarded_as_floats(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "heading_target_deg": 90}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 200
        assert sender.sent == [
            (1, "heading", 90.0, None, None, None, None, None, None, None, False)
        ]

    def test_a_wake_true_message_is_forwarded(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        """`[[BL-B139]]` -- `body.py` sets `wake` only while a recovery
        is underway; this endpoint just forwards whatever boolean it is
        given, same shape-validation-only posture as every other field
        here."""
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "wake": True}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 200
        assert sender.sent == [
            (1, "heading", 90.0, None, None, None, None, None, None, None, True)
        ]

    def test_a_non_boolean_wake_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "wake": "yes"}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_an_hvrt_direction_message_is_accepted(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_IDLE_BODY, "goal_seq": 2, "hvrt_direction": "left"}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 200
        assert sender.sent == [
            (2, None, None, None, None, None, "left", None, None, None, False)
        ]

    def test_an_invalid_param_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "param": "bogus"}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_an_invalid_altitude_target_ref_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {
            **_IDLE_BODY,
            "param": "altitude",
            "altitude_target_m": 300.0,
            "altitude_target_ref": "bogus",
        }
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_an_invalid_hvrt_direction_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_IDLE_BODY, "hvrt_direction": "up"}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_an_hvrt_step_message_is_accepted(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_IDLE_BODY, "goal_seq": 3, "hvrt_step": "up"}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 200
        assert sender.sent == [
            (3, None, None, None, None, None, None, "up", None, None, False)
        ]

    def test_an_invalid_hvrt_step_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_IDLE_BODY, "hvrt_step": "sideways"}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_heading_target_deg_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {
            **_VALID_BODY,
            "heading_target_deg": _AI_PILOT_GOAL_HEADING_MAX_DEG + 1.0,
        }
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_altitude_target_m_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {
            **_IDLE_BODY,
            "param": "altitude",
            "altitude_target_m": _AI_PILOT_GOAL_ALTITUDE_MAX_M + 1.0,
        }
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_goal_seq_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "goal_seq": _AI_PILOT_GOAL_SEQ_MAX + 1}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_negative_goal_seq_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "goal_seq": -1}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_missing_goal_seq_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {k: v for k, v in _VALID_BODY.items() if k != "goal_seq"}
        status, body_out = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert isinstance(body_out, dict)
        assert "error" in body_out
        assert sender.sent == []

    def test_boolean_goal_seq_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "goal_seq": True}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_non_finite_heading_target_deg_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "heading_target_deg": float("nan")}
        status, _body = _post(server, "/command/ai_pilot_goal", body)
        assert status == 400
        assert sender.sent == []

    def test_non_json_body_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/ai_pilot_goal", b"not json")
        assert status == 400
        assert sender.sent == []

    def test_without_configured_sender_returns_503(self) -> None:
        cache = TelemetryCache()
        server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, body = _post(server, "/command/ai_pilot_goal", _VALID_BODY)
            assert status == 503
            assert isinstance(body, dict)
            assert "error" in body
        finally:
            server.close()
            thread.join(timeout=5)

    def test_send_failure_returns_500(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        sender.raise_on_send = True
        status, body = _post(server, "/command/ai_pilot_goal", _VALID_BODY)
        assert status == 500
        assert isinstance(body, dict)
        assert "error" in body
