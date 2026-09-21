"""Tests for `collector.unit_velocity_receiver.UnitVelocityReceiver` --
`plans/movement-detection/plan.md` Stage 1. Mirrors
`test_f10_command_receiver.py`'s pattern of exercising a real loopback UDP
socket."""

from __future__ import annotations

import json
import socket
import threading
import time

from collector.cache import UnitVelocityCache
from collector.unit_velocity_receiver import UnitVelocityReceiver


def _send(port: int, payload: object) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(json.dumps(payload).encode("utf-8"), ("127.0.0.1", port))
    finally:
        sock.close()


def _run_receiver_briefly(receiver: UnitVelocityReceiver) -> None:
    thread = threading.Thread(target=receiver.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    receiver.close()
    thread.join(timeout=5)


def test_well_formed_envelope_is_pushed_to_cache() -> None:
    cache = UnitVelocityCache()
    receiver = UnitVelocityReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(
        port,
        {"payload": "1|1234.5|Truck-1:1.0:0.0:2.0", "bridge_call_ms": 4.2},
    )
    _run_receiver_briefly(receiver)

    snapshot = cache.latest()
    assert snapshot is not None
    assert snapshot.dcs_model_time_s == 1234.5
    assert snapshot.unit_count == 1
    assert snapshot.bridge_call_ms == 4.2
    assert snapshot.samples["Truck-1"].vx == 1.0


def test_malformed_json_is_dropped() -> None:
    cache = UnitVelocityCache()
    receiver = UnitVelocityReceiver(cache, host="127.0.0.1", port=0)
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
    cache = UnitVelocityCache()
    receiver = UnitVelocityReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, ["not", "an", "object"])
    _run_receiver_briefly(receiver)

    assert cache.latest() is None


def test_missing_payload_field_is_dropped() -> None:
    cache = UnitVelocityCache()
    receiver = UnitVelocityReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"bridge_call_ms": 1.0})
    _run_receiver_briefly(receiver)

    assert cache.latest() is None


def test_malformed_payload_string_is_dropped() -> None:
    cache = UnitVelocityCache()
    receiver = UnitVelocityReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"payload": "garbage", "bridge_call_ms": 1.0})
    _run_receiver_briefly(receiver)

    assert cache.latest() is None


def test_non_numeric_bridge_call_ms_is_dropped() -> None:
    cache = UnitVelocityCache()
    receiver = UnitVelocityReceiver(cache, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"payload": "0|1.0|", "bridge_call_ms": "fast"})
    _run_receiver_briefly(receiver)

    assert cache.latest() is None
