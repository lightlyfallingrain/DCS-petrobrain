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


def _send(port: int, payload: object) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(json.dumps(payload).encode("utf-8"), ("127.0.0.1", port))
    finally:
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
    queue = F10CommandQueue()
    receiver = F10CommandReceiver(queue, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    for command in ALLOWED_COMMANDS:
        _send(port, {"command": command})
    _run_receiver_briefly(receiver)

    drained = [event.command for event in queue.drain_all()]
    assert drained == list(ALLOWED_COMMANDS)


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
