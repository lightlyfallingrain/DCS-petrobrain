"""Tests for `belief.ptt_hold.PttHoldGate` (`[[BL-B133]]`,
`body-layer/ROADMAP/BL-B133.md`).

Exercised against a real loopback `http.server` instance, mirroring
`test_aircraft_client.py`'s own pattern -- cheap to spin up and catches
real wire-format mismatches a mock would paper over. The debounce/
staleness timing itself is exercised with injected fake clocks
(`monotonic`/`wall_clock`), never a real `time.sleep`, so these tests are
deterministic and fast."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aircraft_client import AircraftLayerClient
from belief.ptt_hold import PTT_RELEASE_DEBOUNCE_S, PTT_STALE_AFTER_S, PttHoldGate
from connection_reporter import ConnectionReporter


def _ptt_body(
    *, intercom: bool, radio: bool, received_wall_clock_s: float | None = None
) -> dict[str, object]:
    # `None` defaults to "right now" (real wall clock) -- a held sample
    # must never read as stale just because the test didn't ask about
    # staleness; the dedicated staleness tests below pass an explicit,
    # deliberately old timestamp instead.
    if received_wall_clock_s is None:
        received_wall_clock_s = time.time()
    return {
        "t": 123.5,
        "received_wall_clock_s": received_wall_clock_s,
        "raw": 0.5 if intercom else (1.0 if radio else 0.0),
        "intercom": intercom,
        "radio": radio,
        "last_seat": "pilot",
    }


def _make_handler(responses: list[object]) -> type[BaseHTTPRequestHandler]:
    """Serves `responses.pop(0)` (or the last element, once exhausted) for
    every `GET /ptt/state`; `responses=[None]` answers JSON `null`
    forever, same shape every other fixture here needs."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/ptt/state":
                self._respond(404, {"error": "not found"})
                return
            body = responses.pop(0) if len(responses) > 1 else responses[0]
            self._respond(200, body)

        def _respond(self, status: int, body: object) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return _Handler


def _server(responses: list[object]) -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(responses))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.fixture
def released_server() -> Iterator[str]:
    yield from _server([_ptt_body(intercom=False, radio=False)])


@pytest.fixture
def intercom_held_server() -> Iterator[str]:
    yield from _server([_ptt_body(intercom=True, radio=False)])


@pytest.fixture
def radio_held_server() -> Iterator[str]:
    yield from _server([_ptt_body(intercom=False, radio=True)])


@pytest.fixture
def never_moved_server() -> Iterator[str]:
    yield from _server([None])


class _Clock:
    """A fake `monotonic`/`wall_clock` pair, advanced by the test."""

    def __init__(self, start: float = 0.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


# -- basic held/released reads -------------------------------------------


def test_intercom_held_reports_held(intercom_held_server: str) -> None:
    gate = PttHoldGate(AircraftLayerClient(base_url=intercom_held_server))
    assert gate.is_held() is True


def test_radio_held_reports_held(radio_held_server: str) -> None:
    """Radio, not just intercom, holds speech too (U1's own 'either')."""
    gate = PttHoldGate(AircraftLayerClient(base_url=radio_held_server))
    assert gate.is_held() is True


def test_released_with_no_prior_hold_reports_not_held_immediately(
    released_server: str,
) -> None:
    """A gate that has never observed `held` owes no release debounce --
    see module docstring's last paragraph. Repeated calls stay `False`,
    with no artificial one-window delay."""
    gate = PttHoldGate(AircraftLayerClient(base_url=released_server))
    assert gate.is_held() is False
    assert gate.is_held() is False


def test_never_moved_reports_not_held(never_moved_server: str) -> None:
    """`null` (the trigger has not moved this collector lifetime) is the
    ordinary startup state, not an unknown -- reads as released
    immediately, no debounce wait."""
    gate = PttHoldGate(AircraftLayerClient(base_url=never_moved_server))
    assert gate.is_held() is False


# -- release debounce (the mechanical-transit guard) ----------------------


def test_release_debounce_keeps_held_true_until_window_elapses() -> None:
    samples: list[dict[str, object]] = [_ptt_body(intercom=True, radio=False)]
    gate = _gate_over_sequence(samples)
    clock = gate._monotonic
    assert gate.is_held() is True

    # Trigger reads released now, but not long enough yet.
    samples[0] = _ptt_body(intercom=False, radio=False)
    assert gate.is_held() is True
    clock.advance(PTT_RELEASE_DEBOUNCE_S / 2)
    assert gate.is_held() is True

    clock.advance(PTT_RELEASE_DEBOUNCE_S)
    assert gate.is_held() is False


def test_release_debounce_resets_on_a_flicker_back_to_held() -> None:
    samples: list[dict[str, object]] = [_ptt_body(intercom=True, radio=False)]
    gate = _gate_over_sequence(samples)
    clock = gate._monotonic
    assert gate.is_held() is True

    samples[0] = _ptt_body(intercom=False, radio=False)
    clock.advance(PTT_RELEASE_DEBOUNCE_S * 0.9)
    assert gate.is_held() is True  # still inside the first window

    # A transit blip back to held resets the window.
    samples[0] = _ptt_body(intercom=True, radio=False)
    assert gate.is_held() is True
    samples[0] = _ptt_body(intercom=False, radio=False)
    clock.advance(PTT_RELEASE_DEBOUNCE_S * 0.9)
    assert gate.is_held() is True  # inside the *new* window, not the old one
    clock.advance(PTT_RELEASE_DEBOUNCE_S)
    assert gate.is_held() is False


class _FakeAircraftClient:
    """Stands in for `AircraftLayerClient` -- returns `responses[0]`,
    read live on every call so a test can mutate it in place between
    calls (used for the debounce tests above, where the point is
    changing what the *next* read reports)."""

    def __init__(self, responses: list[dict[str, object] | None]) -> None:
        self._responses = responses

    def get_ptt_state_latest(self) -> dict[str, object] | None:
        return self._responses[0]


def _gate_over_sequence(samples: list[dict[str, object]]) -> PttHoldGate:
    clock = _Clock()
    gate = PttHoldGate(_FakeAircraftClient(samples), monotonic=clock)
    return gate


# -- staleness (held reading stuck past the bound) -------------------------


def test_stale_held_reading_reports_released_and_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    wall_clock = _Clock(start=10_000.0)
    sample = _ptt_body(intercom=True, radio=False, received_wall_clock_s=10_000.0)
    client = _FakeAircraftClient([sample])
    gate = PttHoldGate(client, wall_clock=wall_clock)

    # Fresh: held.
    assert gate.is_held() is True

    # Age it past the bound -- the collector is still answering, but this
    # cached sample has not changed in far longer than any real hold.
    wall_clock.advance(PTT_STALE_AFTER_S + 1.0)
    with caplog.at_level("WARNING"):
        assert gate.is_held() is False
        assert gate.is_held() is False  # second stale read: no second warning

    stale_warnings = [r for r in caplog.records if "stale" in r.message]
    assert len(stale_warnings) == 1


def test_idle_untouched_trigger_is_never_reported_stale(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ordinary idle case: the trigger has not been touched in a
    long time, so its timestamp ages indefinitely -- that alone must
    never warn, since the gate already reports released with no need to
    look at the age (module docstring's "Stale" paragraph)."""
    wall_clock = _Clock(start=10_000.0)
    sample = _ptt_body(intercom=False, radio=False, received_wall_clock_s=0.0)
    client = _FakeAircraftClient([sample])
    gate = PttHoldGate(client, wall_clock=wall_clock)

    wall_clock.advance(PTT_STALE_AFTER_S * 10)
    with caplog.at_level("WARNING"):
        assert gate.is_held() is False

    assert not [r for r in caplog.records if "stale" in r.message]


# -- unavailable feed --------------------------------------------------


def test_unreachable_feed_reports_released_via_connection_reporter() -> None:
    reporter = ConnectionReporter(logging.getLogger("test"), label="ptt feed")
    gate = PttHoldGate(
        AircraftLayerClient(base_url="http://127.0.0.1:1", timeout_s=0.5),
        reporter=reporter,
    )
    assert gate.is_held() is False


def test_unreachable_feed_logs_once_with_no_reporter_configured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gate = PttHoldGate(
        AircraftLayerClient(base_url="http://127.0.0.1:1", timeout_s=0.5),
    )
    with caplog.at_level("WARNING"):
        assert gate.is_held() is False
        assert gate.is_held() is False

    unavailable_warnings = [r for r in caplog.records if "unavailable" in r.message]
    # No `ConnectionReporter` here, so this path logs every call -- unlike
    # the reporter path, which is transition-only. Both still resolve to
    # "released", which is the behaviour this test actually guards.
    assert len(unavailable_warnings) == 2
