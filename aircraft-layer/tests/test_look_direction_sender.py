"""Tests for `collector.command_sender.LookDirectionSender` -- `plans/
dcs-driven-los/plan.md` (X-B29). Mirrors `test_command_sender.py`'s
structure -- same raise-on-failure posture as `CommandSender`."""

from __future__ import annotations

import json
import socket

import pytest

from collector.command_sender import CommandSendError, LookDirectionSender


def test_send_look_direction_delivers_well_formed_datagram() -> None:
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(2.0)
    port = receiver.getsockname()[1]

    try:
        with LookDirectionSender(host="127.0.0.1", port=port) as sender:
            sender.send_look_direction(3, 90)

        data, _addr = receiver.recvfrom(4096)
        decoded = json.loads(data.decode("utf-8"))
        assert decoded == {"op": "look_direction", "hour": 3, "fov_half_deg": 90}
    finally:
        receiver.close()


def test_send_look_direction_opens_socket_lazily_if_not_opened() -> None:
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(2.0)
    port = receiver.getsockname()[1]

    sender = LookDirectionSender(host="127.0.0.1", port=port)
    try:
        sender.send_look_direction(0, 45)
        data, _addr = receiver.recvfrom(4096)
        assert json.loads(data.decode("utf-8"))["hour"] == 0
    finally:
        sender.close()
        receiver.close()


class _FailingSocket:
    """Mirrors `test_command_sender.py`'s own `_FailingSocket` -- a real
    closed-port UDP send does not reliably raise synchronously, so the
    raise-on-failure path needs direct failure injection to test at all."""

    def sendto(self, payload: bytes, address: tuple[str, int]) -> int:
        raise OSError("simulated send failure")

    def close(self) -> None:
        pass


def test_send_look_direction_raises_command_send_error_on_a_failed_send() -> None:
    sender = LookDirectionSender(host="127.0.0.1", port=1)
    sender.open()
    sender._socket = _FailingSocket()  # type: ignore[assignment]

    with pytest.raises(CommandSendError):
        sender.send_look_direction(0, 45)
