"""Tests for `collector.f10_command_receiver.F10CommandReceiver` --
`plans/f10-crew-commands/plan.md`. Mirrors `test_text_sender.py`'s pattern
of exercising a real loopback UDP socket rather than mocking it, plus the
receive-side additions this channel needs: allowed-token filtering and
queue-bound behavior."""

from __future__ import annotations

import json
import socket
import threading
import time

from collector.cache import F10CommandQueue
from collector.f10_command_receiver import ALLOWED_COMMANDS, F10CommandReceiver


def _send(port: int, payload: object, sock: socket.socket | None = None) -> None:
    """Sends one UDP datagram. With no `sock` given, opens and closes a
    throwaway socket per call (fine for single-datagram tests). Callers
    that send multiple datagrams and care about delivery order should pass
    a shared `sock` -- UDP delivery order across independently-created
    sockets is not guaranteed by the OS, even on loopback."""
    owned_sock = sock is None
    if sock is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(json.dumps(payload).encode("utf-8"), ("127.0.0.1", port))
    finally:
        if owned_sock:
            sock.close()


def _run_receiver_briefly(receiver: F10CommandReceiver) -> None:
    """Runs `serve_forever` on a background thread just long enough for a
    just-sent datagram to be processed, then shuts the receiver down.
    `serve_forever` is a blocking loop (mirroring `CollectorServer`'s own
    shape), so every test drives it this way rather than calling
    `_handle_datagram` directly -- this exercises the real socket path."""
    thread = threading.Thread(target=receiver.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    receiver.close()
    thread.join(timeout=5)


def test_well_formed_allowed_command_is_enqueued() -> None:
    queue = F10CommandQueue()
    receiver = F10CommandReceiver(queue, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"command": "watch_nearest"})
    _run_receiver_briefly(receiver)

    drained = queue.drain_all()
    assert len(drained) == 1
    assert drained[0].command == "watch_nearest"


def test_all_allowed_commands_are_enqueued() -> None:
    """Sends all three commands over one shared socket, reused across the
    sends -- mirroring the real Hook script's `sendToken` (petrobrain-f10-
    commands-hook.lua), which opens `sendSocket` once and reuses it for
    every token forwarded from one `pollAndForward` call, rather than the
    one-socket-per-datagram pattern `_send`'s default uses. A single socket
    sending in a tight loop over loopback preserves send order in practice
    (and is representative of the real sender), whereas UDP delivery order
    across independently-created sockets is not guaranteed by the OS."""
    queue = F10CommandQueue()
    receiver = F10CommandReceiver(queue, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for command in ALLOWED_COMMANDS:
            _send(port, {"command": command}, sock=sock)
    finally:
        sock.close()
    _run_receiver_briefly(receiver)

    drained = [event.command for event in queue.drain_all()]
    assert sorted(drained) == sorted(ALLOWED_COMMANDS)


def test_unrecognized_command_is_dropped() -> None:
    queue = F10CommandQueue()
    receiver = F10CommandReceiver(queue, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"command": "shut_down_dcs"})
    _run_receiver_briefly(receiver)

    assert queue.drain_all() == []


def test_malformed_json_is_dropped() -> None:
    queue = F10CommandQueue()
    receiver = F10CommandReceiver(queue, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(b"not json", ("127.0.0.1", port))
    finally:
        sock.close()
    _run_receiver_briefly(receiver)

    assert queue.drain_all() == []


def test_non_object_json_is_dropped() -> None:
    queue = F10CommandQueue()
    receiver = F10CommandReceiver(queue, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, ["watch_nearest"])
    _run_receiver_briefly(receiver)

    assert queue.drain_all() == []


def test_missing_command_field_is_dropped() -> None:
    queue = F10CommandQueue()
    receiver = F10CommandReceiver(queue, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"not_command": "watch_nearest"})
    _run_receiver_briefly(receiver)

    assert queue.drain_all() == []


def test_queue_bound_is_respected() -> None:
    queue = F10CommandQueue(maxlen=2)
    receiver = F10CommandReceiver(queue, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    for _ in range(5):
        _send(port, {"command": "scan_forward"})
    _run_receiver_briefly(receiver)

    assert len(queue.drain_all()) == 2
