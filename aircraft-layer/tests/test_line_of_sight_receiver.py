"""Tests for `collector.line_of_sight_receiver.LineOfSightReceiver` --
`plans/dcs-driven-los/plan.md` (X-B29). Mirrors
`test_unit_velocity_receiver.py`'s pattern of exercising a real loopback
UDP socket."""

from __future__ import annotations

import json
import socket
import threading
import time

from collector.cache import LineOfSightCache
from collector.line_of_sight_receiver import LineOfSightReceiver


def _send(port: int, payload: object) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(json.dumps(payload).encode("utf-8"), ("127.0.0.1", port))
    finally:
        sock.close()


def _run_receiver_briefly(receiver: LineOfSightReceiver) -> None:
    thread = threading.Thread(target=receiver.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    receiver.close()
    thread.join(timeout=5)


def test_well_formed_envelope_is_pushed_to_cache() -> None:
    cache = LineOfSightCache()
    receiver = LineOfSightReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(
        port,
        {
            "payload": "172|12|12|3|45|1234.5|Truck-1:1:0",
            "bridge_call_ms": 1.6,
        },
    )
    _run_receiver_briefly(receiver)

    snapshot = cache.latest()
    assert snapshot is not None
    assert snapshot.dcs_model_time_s == 1234.5
    assert snapshot.units_in_bubble == 172
    assert snapshot.units_in_wedge == 12
    assert snapshot.hour_used == 3
    assert snapshot.fov_half_deg_used == 45
    assert snapshot.bridge_call_ms == 1.6
    assert snapshot.verdicts["Truck-1"].building_clear is True
    assert snapshot.verdicts["Truck-1"].terrain_clear is False


def test_malformed_json_is_dropped() -> None:
    cache = LineOfSightCache()
    receiver = LineOfSightReceiver(cache, host="127.0.0.1", port=0)
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
    cache = LineOfSightCache()
    receiver = LineOfSightReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, ["not", "an", "object"])
    _run_receiver_briefly(receiver)

    assert cache.latest() is None


def test_missing_payload_field_is_dropped() -> None:
    cache = LineOfSightCache()
    receiver = LineOfSightReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"bridge_call_ms": 1.0})
    _run_receiver_briefly(receiver)

    assert cache.latest() is None


def test_malformed_payload_string_is_dropped() -> None:
    cache = LineOfSightCache()
    receiver = LineOfSightReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"payload": "garbage", "bridge_call_ms": 1.0})
    _run_receiver_briefly(receiver)

    assert cache.latest() is None


def test_non_numeric_bridge_call_ms_is_dropped() -> None:
    cache = LineOfSightCache()
    receiver = LineOfSightReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"payload": "0|0|0|0|45|1.0|", "bridge_call_ms": "fast"})
    _run_receiver_briefly(receiver)

    assert cache.latest() is None
