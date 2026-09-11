"""Tests for `collector.command_sender.CommandSender` -- BL-6 (`plans/
bl6-commands-inspect-adapt/plan.md`). Mirrors `test_text_sender.py`'s
structure, except the "send to a closed port" case: unlike
`TextOverlaySender.send_line`, `CommandSender.send_command` is documented
to raise on a clearly-failed send rather than swallow it (see the module
docstring's asymmetry note)."""

from __future__ import annotations

import json
import socket

import pytest

from collector.command_sender import CommandSender, CommandSendError


def test_send_command_delivers_well_formed_datagram() -> None:
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(2.0)
    port = receiver.getsockname()[1]

    try:
        with CommandSender(host="127.0.0.1", port=port) as sender:
            sender.send_command("forward")

        data, _addr = receiver.recvfrom(4096)
        decoded = json.loads(data.decode("utf-8"))
        assert decoded == {"op": "petrovich_search", "mode": "forward"}
    finally:
        receiver.close()


def test_send_command_boresight_mode() -> None:
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(2.0)
    port = receiver.getsockname()[1]

    try:
        with CommandSender(host="127.0.0.1", port=port) as sender:
            sender.send_command("boresight")

        data, _addr = receiver.recvfrom(4096)
        decoded = json.loads(data.decode("utf-8"))
        assert decoded == {"op": "petrovich_search", "mode": "boresight"}
    finally:
        receiver.close()


def test_send_command_opens_socket_lazily_if_not_opened() -> None:
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(2.0)
    port = receiver.getsockname()[1]

    sender = CommandSender(host="127.0.0.1", port=port)
    try:
        sender.send_command("forward")
        data, _addr = receiver.recvfrom(4096)
        assert json.loads(data.decode("utf-8"))["mode"] == "forward"
    finally:
        sender.close()
        receiver.close()


class _FailingSocket:
    """A `socket.socket` stand-in whose `sendto` always raises `OSError` --
    used to exercise `send_command`'s raise-on-failure path deterministically
    (unlike `TextOverlaySender`, a real closed-port UDP send does not
    reliably raise synchronously, see `test_text_sender.py`'s own comment on
    that -- so this asymmetric behavior needs a direct failure injection,
    not a real socket, to test at all)."""

    def sendto(self, payload: bytes, address: tuple[str, int]) -> int:
        raise OSError("simulated send failure")

    def close(self) -> None:
        pass


def test_send_command_raises_command_send_error_on_a_failed_send() -> None:
    sender = CommandSender(host="127.0.0.1", port=1)
    sender.open()
    sender._socket = _FailingSocket()  # type: ignore[assignment]

    with pytest.raises(CommandSendError):
        sender.send_command("forward")
