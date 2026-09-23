"""`DcsPTT` -- the aircraft's own intercom trigger as a talk control.

Against a real loopback `http.server`, matching this subproject's posture
for anything that is fundamentally a wire contract. The two behaviours
worth the most attention are the two that came from measurement rather
than design: a full press *transits* the intercom stop for 19-32 ms on its
way to the radio stop, so the stop must be debounced; and debouncing alone
cannot catch a slow full press, so reaching the radio stop latches a
discard. Both are in
`aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md`'s third
addendum.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ptt_source import INTERCOM_DEBOUNCE_S, DcsPTT, PTTError


class _State:
    """The payload the fake collector currently serves."""

    def __init__(self) -> None:
        self.payload: object = None
        self.status = 200


def _make_handler(state: _State) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/ptt/state":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(state.payload).encode("utf-8")
            self.send_response(state.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return _Handler


@pytest.fixture
def collector() -> Iterator[tuple[str, _State]]:
    state = _State()
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", state
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


class _Clock:
    """A hand-advanced monotonic clock, so debounce timing is exact rather
    than slept through."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _released() -> dict[str, object]:
    return {"t": 1.0, "raw": 0.0, "intercom": False, "radio": False}


def _intercom() -> dict[str, object]:
    return {"t": 1.0, "raw": 0.5, "intercom": True, "radio": False}


def _radio() -> dict[str, object]:
    return {"t": 1.0, "raw": 1.0, "intercom": False, "radio": True}


def test_untouched_trigger_reads_as_not_pressed(
    collector: tuple[str, _State],
) -> None:
    """`null` is the ordinary startup state -- Export.lua sends a line only
    on change, so a trigger nobody has touched produces nothing. It must
    not look like a failure."""
    url, state = collector
    state.payload = None
    assert DcsPTT(url).is_down() is False


def test_released_trigger_is_not_down(collector: tuple[str, _State]) -> None:
    url, state = collector
    state.payload = _released()
    assert DcsPTT(url).is_down() is False


def test_intercom_stop_is_down_only_after_the_debounce(
    collector: tuple[str, _State],
) -> None:
    url, state = collector
    clock = _Clock()
    ptt = DcsPTT(url, monotonic=clock)
    state.payload = _intercom()

    assert ptt.is_down() is False  # first sight of it: not yet settled
    clock.now += INTERCOM_DEBOUNCE_S / 2
    assert ptt.is_down() is False
    clock.now += INTERCOM_DEBOUNCE_S
    assert ptt.is_down() is True


def test_a_transit_through_the_intercom_stop_never_reads_as_down(
    collector: tuple[str, _State],
) -> None:
    """The measured failure this debounce exists for: a full press passes
    through 0.5 for 19-32 ms. Without the debounce every radio call to ATC
    would open a capture."""
    url, state = collector
    clock = _Clock()
    ptt = DcsPTT(url, monotonic=clock)

    state.payload = _intercom()
    assert ptt.is_down() is False
    clock.now += 0.032  # the worst transit actually observed
    state.payload = _radio()
    assert ptt.is_down() is False
    clock.now += 1.0
    state.payload = _released()
    assert ptt.is_down() is False


def test_the_debounce_restarts_after_a_release(
    collector: tuple[str, _State],
) -> None:
    """Otherwise a brief touch would leave the timer running and the *next*
    transit would be admitted instantly."""
    url, state = collector
    clock = _Clock()
    ptt = DcsPTT(url, monotonic=clock)

    state.payload = _intercom()
    ptt.is_down()
    state.payload = _released()
    assert ptt.is_down() is False

    clock.now += 10.0
    state.payload = _intercom()
    assert ptt.is_down() is False  # timer restarted, not carried over


def test_radio_latches_a_discard_and_the_latch_is_consumed_once(
    collector: tuple[str, _State],
) -> None:
    """Debouncing stops a capture *starting* on a fast radio press; it
    cannot help a slow one that dwells past the window. So reaching the
    radio stop latches, and the capture loop consumes the latch at
    release."""
    url, state = collector
    ptt = DcsPTT(url)

    state.payload = _radio()
    ptt.is_down()

    assert ptt.discard_requested() is True
    assert ptt.discard_requested() is False  # consumed by reading


def test_no_discard_is_requested_for_an_ordinary_intercom_press(
    collector: tuple[str, _State],
) -> None:
    url, state = collector
    clock = _Clock()
    ptt = DcsPTT(url, monotonic=clock)
    state.payload = _intercom()
    ptt.is_down()
    clock.now += 1.0
    assert ptt.is_down() is True
    state.payload = _released()
    ptt.is_down()

    assert ptt.discard_requested() is False


def test_an_unreachable_collector_raises_rather_than_reading_released() -> None:
    """A dead collector and a released trigger must not look the same --
    silently reporting "not pressed" forever is a talk control that never
    fires and never explains itself."""
    ptt = DcsPTT("http://127.0.0.1:1", timeout_s=0.5)
    with pytest.raises(PTTError):
        ptt.is_down()
