"""The 9K113 pointing channel's wire op (`plans/9k113-sight-pointing/
plan.md`, BL-B80): `CommandSender.send_sight_target` and the
`POST /command/sight_target` endpoint.

Mirrors `test_cockpit_switch.py`'s `TestSendCockpitSwitch`/
`TestCockpitSwitchCommandEndpoint` structure -- same shape-validation-
only, raise-on-failure posture -- with one addition this op has and
`cockpit_switch` does not: a numeric bound on both fields (the Security
plan review's non-blocking recommendation, since Export.lua's own rate
limiter only ever *approaches* an out-of-range target rather than
jumping to it, but an absurd magnitude should not reach its "commanded
is non-trivial" comparison either)."""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import _SIGHT_TARGET_CMD_BOUND, TelemetryAPIServer
from collector.cache import TelemetryCache
from collector.command_sender import CommandSender, CommandSendError


class TestSendSightTarget:
    """`CommandSender.send_sight_target` -- mirrors `test_command_sender.
    py`'s structure for `send_command`."""

    def test_delivers_well_formed_datagram(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_sight_target(0.5, -0.25)

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded == {
                "op": "sight_target",
                "az_cmd": 0.5,
                "elev_cmd": -0.25,
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
            sender.send_sight_target(0.5, -0.25)


class _RecordingCommandSender(CommandSender):
    """A `CommandSender` double that records calls instead of sending UDP."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[float, float]] = []
        self.raise_on_send = False

    def send_sight_target(  # type: ignore[override]
        self, az_cmd: float, elev_cmd: float
    ) -> None:
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.sent.append((az_cmd, elev_cmd))


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


class TestSightTargetCommandEndpoint:
    """`POST /command/sight_target` -- shape validation plus the bound
    check (no allow-list question here, unlike `cockpit_switch` -- there
    is only one `(device, cmd)` pair this op ever reaches)."""

    def test_valid_request_forwards_to_sender(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, body = _post(
            server,
            "/command/sight_target",
            {"az_cmd": 0.5, "elev_cmd": -0.25},
        )
        assert status == 200
        assert body == {"ok": True}
        assert sender.sent == [(0.5, -0.25)]

    def test_integer_values_are_accepted_and_forwarded_as_floats(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/sight_target", {"az_cmd": 0, "elev_cmd": 1}
        )
        assert status == 200
        assert sender.sent == [(0.0, 1.0)]

    def test_values_at_the_bound_are_accepted(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/sight_target",
            {
                "az_cmd": _SIGHT_TARGET_CMD_BOUND,
                "elev_cmd": -_SIGHT_TARGET_CMD_BOUND,
            },
        )
        assert status == 200
        assert sender.sent == [(_SIGHT_TARGET_CMD_BOUND, -_SIGHT_TARGET_CMD_BOUND)]

    def test_az_cmd_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/sight_target",
            {"az_cmd": _SIGHT_TARGET_CMD_BOUND + 0.1, "elev_cmd": 0.0},
        )
        assert status == 400
        assert sender.sent == []

    def test_elev_cmd_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/sight_target",
            {"az_cmd": 0.0, "elev_cmd": -(_SIGHT_TARGET_CMD_BOUND + 0.1)},
        )
        assert status == 400
        assert sender.sent == []

    def test_missing_az_cmd_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, body = _post(server, "/command/sight_target", {"elev_cmd": 0.0})
        assert status == 400
        assert isinstance(body, dict)
        assert "error" in body
        assert sender.sent == []

    def test_missing_elev_cmd_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/sight_target", {"az_cmd": 0.0})
        assert status == 400
        assert sender.sent == []

    def test_boolean_az_cmd_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/sight_target", {"az_cmd": True, "elev_cmd": 0.0}
        )
        assert status == 400
        assert sender.sent == []

    def test_non_finite_elev_cmd_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/sight_target",
            {"az_cmd": 0.0, "elev_cmd": float("nan")},
        )
        assert status == 400
        assert sender.sent == []

    def test_non_json_body_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/sight_target", b"not json")
        assert status == 400
        assert sender.sent == []

    def test_without_configured_sender_returns_503(self) -> None:
        cache = TelemetryCache()
        server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, body = _post(
                server,
                "/command/sight_target",
                {"az_cmd": 0.0, "elev_cmd": 0.0},
            )
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
        status, body = _post(
            server,
            "/command/sight_target",
            {"az_cmd": 0.0, "elev_cmd": 0.0},
        )
        assert status == 500
        assert isinstance(body, dict)
        assert "error" in body
