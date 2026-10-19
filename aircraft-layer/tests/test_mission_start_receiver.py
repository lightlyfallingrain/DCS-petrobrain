"""Tests for `collector.mission_start_receiver.MissionStartReceiver` --
`plans/bl15-mission-start/plan.md` (BL-15 Stage 1). Mirrors
`test_unit_velocity_receiver.py`'s pattern of exercising a real loopback
UDP socket."""

from __future__ import annotations

import json
import socket
import threading
import time

from collector.cache import MissionStartCache
from collector.mission_start_receiver import MissionStartReceiver


def _send(port: int, payload: object) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(json.dumps(payload).encode("utf-8"), ("127.0.0.1", port))
    finally:
        sock.close()


def _run_receiver_briefly(receiver: MissionStartReceiver) -> None:
    thread = threading.Thread(target=receiver.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    receiver.close()
    thread.join(timeout=5)


def test_well_formed_event_is_pushed_to_cache() -> None:
    cache = MissionStartCache()
    receiver = MissionStartReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"sequence": 1, "theatre": "Syria"})
    _run_receiver_briefly(receiver)

    event = cache.latest()
    assert event is not None
    assert event.sequence == 1
    assert event.theatre == "Syria"


def test_null_theatre_is_accepted() -> None:
    cache = MissionStartCache()
    receiver = MissionStartReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"sequence": 1, "theatre": None})
    _run_receiver_briefly(receiver)

    event = cache.latest()
    assert event is not None
    assert event.theatre is None


def test_malformed_json_is_dropped() -> None:
    cache = MissionStartCache()
    receiver = MissionStartReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(b"not json", ("127.0.0.1", port))
    finally:
        sock.close()
    _run_receiver_briefly(receiver)

    assert cache.latest() is None


def test_non_object_json_is_dropped() -> None:
    cache = MissionStartCache()
    receiver = MissionStartReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, ["not", "an", "object"])
    _run_receiver_briefly(receiver)

    assert cache.latest() is None


def test_missing_sequence_field_is_dropped() -> None:
    cache = MissionStartCache()
    receiver = MissionStartReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"theatre": "Syria"})
    _run_receiver_briefly(receiver)

    assert cache.latest() is None


def test_non_int_sequence_is_dropped() -> None:
    cache = MissionStartCache()
    receiver = MissionStartReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"sequence": "one", "theatre": None})
    _run_receiver_briefly(receiver)

    assert cache.latest() is None


def test_non_string_theatre_is_dropped() -> None:
    cache = MissionStartCache()
    receiver = MissionStartReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"sequence": 1, "theatre": 42})
    _run_receiver_briefly(receiver)

    assert cache.latest() is None
