"""The 9K113 cockpit-switch *write* path (`plans/9k113-effectors/plan.md`,
BL-B66 Stage 1): `CommandSender.send_cockpit_switch` and
`POST /command/cockpit_switch`.

**Split out of the old `test_cockpit_switch.py`** (`plans/
effector-sequences/plan.md` Stage 4, decided "remove"): that file's
*readback* half (`CockpitSwitchState`/`CockpitSwitchCache`/
`GET /cockpit_switch/latest`) is gone -- replaced by
`test_watched_args.py` -- but this write op is untouched by Stage 4 (only
its readback sibling was removed; see the module docstring in
`aircraft-layer/src/api/server.py`), so its tests move here rather than
being deleted with the rest."""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import TelemetryCache
from collector.command_sender import CommandSender, CommandSendError


class TestSendCockpitSwitch:
    """`CommandSender.send_cockpit_switch` -- mirrors `test_command_sender.
    py`'s structure for `send_command`."""

    def test_delivers_well_formed_datagram(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_cockpit_switch(7, 3001, 1.0)

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded == {
                "op": "cockpit_switch",
                "device": 7,
                "cmd": 3001,
                "value": 1.0,
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
            sender.send_cockpit_switch(7, 3001, 1.0)


class _RecordingCommandSender(CommandSender):
    """A `CommandSender` double that records calls instead of sending UDP."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[int, int, float]] = []
        self.raise_on_send = False

    def send_cockpit_switch(  # type: ignore[override]
        self, device: int, cmd: int, value: float
    ) -> None:
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.sent.append((device, cmd, value))


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


class TestCockpitSwitchCommandEndpoint:
    """`POST /command/cockpit_switch` -- shape validation only, **no
    allow-list** (user direction 2026-10-21)."""

    def test_valid_request_forwards_to_sender(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 7, "cmd": 3001, "value": 1},
        )
        assert status == 200
        assert body == {"ok": True}
        assert sender.sent == [(7, 3001, 1.0)]

    def test_an_arbitrary_device_cmd_pair_is_accepted(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        """No allow-list -- any shape-valid (device, cmd, value) is
        forwarded, including one this entry's six switches never use."""
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 99, "cmd": 12345, "value": 0.5},
        )
        assert status == 200
        assert sender.sent == [(99, 12345, 0.5)]

    def test_missing_device_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, body = _post(
            server, "/command/cockpit_switch", {"cmd": 3001, "value": 1}
        )
        assert status == 400
        assert isinstance(body, dict)
        assert "error" in body
        assert sender.sent == []

    def test_non_integer_device_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 7.5, "cmd": 3001, "value": 1},
        )
        assert status == 400
        assert sender.sent == []

    def test_boolean_device_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/cockpit_switch",
            {"device": True, "cmd": 3001, "value": 1},
        )
        assert status == 400
        assert sender.sent == []

    def test_non_integer_cmd_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 7, "cmd": "x", "value": 1},
        )
        assert status == 400
        assert sender.sent == []

    def test_non_finite_value_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 7, "cmd": 3001, "value": float("inf")},
        )
        assert status == 400
        assert sender.sent == []

    def test_missing_value_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/cockpit_switch", {"device": 7, "cmd": 3001}
        )
        assert status == 400
        assert sender.sent == []

    def test_non_json_body_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/cockpit_switch", b"not json")
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
                "/command/cockpit_switch",
                {"device": 7, "cmd": 3001, "value": 1},
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
            "/command/cockpit_switch",
            {"device": 7, "cmd": 3001, "value": 1},
        )
        assert status == 500
        assert isinstance(body, dict)
        assert "error" in body
