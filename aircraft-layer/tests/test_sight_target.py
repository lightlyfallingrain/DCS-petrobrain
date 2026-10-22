"""The 9K113 pointing channel's wire op (`plans/9k113-sight-pointing/
plan.md`, BL-B80 v2): `CommandSender.send_sight_target` and the
`POST /command/sight_target` endpoint.

Mirrors `test_cockpit_switch.py`'s `TestSendCockpitSwitch`/
`TestCockpitSwitchCommandEndpoint` structure -- same shape-validation-
only, raise-on-failure posture -- with the bound checks this op has and
`cockpit_switch` does not: a numeric bound on every field, including
`t_sim` (the security plan review's required change, re-plan v2: `t_sim`
feeds `Export.lua`'s own `clamp(t - t_sim, 0, cap)` directly, so it is
bounded exactly like `az`/`el`/`rate`)."""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import (
    _SIGHT_TARGET_AZ_BOUND,
    _SIGHT_TARGET_EL_BOUND,
    _SIGHT_TARGET_RATE_BOUND,
    _SIGHT_TARGET_TSIM_BOUND,
    TelemetryAPIServer,
)
from collector.cache import TelemetryCache
from collector.command_sender import CommandSender, CommandSendError

_VALID_BODY = {
    "goal_az_deg": 12.0,
    "goal_el_deg": -3.0,
    "goal_rate_az_deg_s": 1.5,
    "goal_rate_el_deg_s": -0.5,
    "t_sim": 123.0,
}


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
                sender.send_sight_target(12.0, -3.0, 1.5, -0.5, 123.0)

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded == {
                "op": "sight_target",
                "goal_az_deg": 12.0,
                "goal_el_deg": -3.0,
                "goal_rate_az_deg_s": 1.5,
                "goal_rate_el_deg_s": -0.5,
                "t_sim": 123.0,
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
            sender.send_sight_target(12.0, -3.0, 1.5, -0.5, 123.0)


class _RecordingCommandSender(CommandSender):
    """A `CommandSender` double that records calls instead of sending UDP."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[float, float, float, float, float]] = []
        self.raise_on_send = False

    def send_sight_target(  # type: ignore[override]
        self,
        goal_az_deg: float,
        goal_el_deg: float,
        goal_rate_az_deg_s: float,
        goal_rate_el_deg_s: float,
        t_sim: float,
    ) -> None:
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.sent.append(
            (goal_az_deg, goal_el_deg, goal_rate_az_deg_s, goal_rate_el_deg_s, t_sim)
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


class TestSightTargetCommandEndpoint:
    """`POST /command/sight_target` -- shape validation plus the per-field
    bound checks (no allow-list question here, unlike `cockpit_switch` --
    there is only one `(device, cmd)` pair this op ever reaches)."""

    def test_valid_request_forwards_to_sender(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, body = _post(server, "/command/sight_target", _VALID_BODY)
        assert status == 200
        assert body == {"ok": True}
        assert sender.sent == [(12.0, -3.0, 1.5, -0.5, 123.0)]

    def test_integer_values_are_accepted_and_forwarded_as_floats(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/sight_target",
            {
                "goal_az_deg": 0,
                "goal_el_deg": 1,
                "goal_rate_az_deg_s": 0,
                "goal_rate_el_deg_s": 0,
                "t_sim": 5,
            },
        )
        assert status == 200
        assert sender.sent == [(0.0, 1.0, 0.0, 0.0, 5.0)]

    def test_values_at_the_bound_are_accepted(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/sight_target",
            {
                "goal_az_deg": _SIGHT_TARGET_AZ_BOUND,
                "goal_el_deg": -_SIGHT_TARGET_EL_BOUND,
                "goal_rate_az_deg_s": _SIGHT_TARGET_RATE_BOUND,
                "goal_rate_el_deg_s": -_SIGHT_TARGET_RATE_BOUND,
                "t_sim": _SIGHT_TARGET_TSIM_BOUND,
            },
        )
        assert status == 200
        assert sender.sent == [
            (
                _SIGHT_TARGET_AZ_BOUND,
                -_SIGHT_TARGET_EL_BOUND,
                _SIGHT_TARGET_RATE_BOUND,
                -_SIGHT_TARGET_RATE_BOUND,
                _SIGHT_TARGET_TSIM_BOUND,
            )
        ]

    def test_goal_az_deg_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "goal_az_deg": _SIGHT_TARGET_AZ_BOUND + 0.1}
        status, _body = _post(server, "/command/sight_target", body)
        assert status == 400
        assert sender.sent == []

    def test_goal_el_deg_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "goal_el_deg": -(_SIGHT_TARGET_EL_BOUND + 0.1)}
        status, _body = _post(server, "/command/sight_target", body)
        assert status == 400
        assert sender.sent == []

    def test_goal_rate_az_deg_s_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "goal_rate_az_deg_s": _SIGHT_TARGET_RATE_BOUND + 0.1}
        status, _body = _post(server, "/command/sight_target", body)
        assert status == 400
        assert sender.sent == []

    def test_goal_rate_el_deg_s_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "goal_rate_el_deg_s": -(_SIGHT_TARGET_RATE_BOUND + 0.1)}
        status, _body = _post(server, "/command/sight_target", body)
        assert status == 400
        assert sender.sent == []

    def test_t_sim_beyond_the_bound_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        """The security plan review's required change -- `t_sim` is
        bounded exactly like every other field."""
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "t_sim": _SIGHT_TARGET_TSIM_BOUND + 1.0}
        status, _body = _post(server, "/command/sight_target", body)
        assert status == 400
        assert sender.sent == []

    def test_negative_t_sim_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        """DCS model time is never negative -- unlike `az`/`el`/`rate`,
        `t_sim`'s own lower bound is 0, not symmetric."""
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "t_sim": -1.0}
        status, _body = _post(server, "/command/sight_target", body)
        assert status == 400
        assert sender.sent == []

    def test_non_finite_t_sim_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "t_sim": float("nan")}
        status, _body = _post(server, "/command/sight_target", body)
        assert status == 400
        assert sender.sent == []

    def test_missing_goal_az_deg_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {k: v for k, v in _VALID_BODY.items() if k != "goal_az_deg"}
        status, body_out = _post(server, "/command/sight_target", body)
        assert status == 400
        assert isinstance(body_out, dict)
        assert "error" in body_out
        assert sender.sent == []

    def test_missing_t_sim_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {k: v for k, v in _VALID_BODY.items() if k != "t_sim"}
        status, _body = _post(server, "/command/sight_target", body)
        assert status == 400
        assert sender.sent == []

    def test_boolean_goal_az_deg_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "goal_az_deg": True}
        status, _body = _post(server, "/command/sight_target", body)
        assert status == 400
        assert sender.sent == []

    def test_non_finite_goal_el_deg_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        body = {**_VALID_BODY, "goal_el_deg": float("nan")}
        status, _body = _post(server, "/command/sight_target", body)
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
            status, body = _post(server, "/command/sight_target", _VALID_BODY)
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
        status, body = _post(server, "/command/sight_target", _VALID_BODY)
        assert status == 500
        assert isinstance(body, dict)
        assert "error" in body
