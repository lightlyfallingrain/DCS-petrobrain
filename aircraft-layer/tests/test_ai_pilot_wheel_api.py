"""The AI-pilot wheel's own per-frame status feed (`plans/flight-control/
plan.md`, "Revised 2026-11-15"/"Revised 2026-11-16", BL-16 mode 2, Stage
P1): schema, cache, line routing, and the `GET /ai_pilot_wheel/latest`
endpoint.

Mirrors `test_sight_servo_api.py`'s `TestCollectorRouting`/
`TestSightServoLatestEndpoint` structure -- same "not an error"
`None`-before-first-sample posture, same routing-ahead-of-telemetry shape,
with the wire key `"apw_parked_active"` and a read-only endpoint (no
write side; this is a status feed body-layer only ever reads)."""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import (
    AiPilotWheelCache,
    PetrovichIndicationCache,
    PetrovichWheelCache,
    TelemetryCache,
    WorldObjectsCache,
)
from collector.server import CollectorServer
from schema import AiPilotWheelParseError, AiPilotWheelState

_LINE = (
    '{"t":1.5,"apw_parked_active":true,"apw_mode_text":"ALT",'
    '"apw_course_text":"090","apw_alt_text":"500 R","apw_alt_add_text":"MAX",'
    '"apw_speed_text":"120","apw_last_press":"altitude_nudge_up",'
    '"apw_arg852":0.95,"apw_arg952":0.05,'
    '"apw_takeover_stage":"correcting_altitude","apw_correction_path":"hold",'
    '"apw_seat":"operator","apw_cam_fwd_m":4.7}'
)


class TestAiPilotWheelState:
    def test_parses_a_line(self) -> None:
        sample = AiPilotWheelState.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.dcs_model_time_s == pytest.approx(1.5)
        assert sample.received_wall_clock_s == 99.0
        assert sample.parked_active is True
        assert sample.mode_text == "ALT"
        assert sample.course_text == "090"
        assert sample.alt_text == "500 R"
        assert sample.alt_add_text == "MAX"
        assert sample.speed_text == "120"
        assert sample.last_press == "altitude_nudge_up"
        assert sample.arg_852 == pytest.approx(0.95)
        assert sample.arg_952 == pytest.approx(0.05)
        assert sample.takeover_stage == "correcting_altitude"
        assert sample.correction_path == "hold"

    def test_null_optional_fields_parse_as_none(self) -> None:
        # Unparked, or the overlay box not currently populated this
        # frame -- the schema's own docstring posture, not a behavioural
        # fix.
        line = (
            '{"t":1.5,"apw_parked_active":false,"apw_mode_text":null,'
            '"apw_course_text":null,"apw_alt_text":null,'
            '"apw_alt_add_text":null,"apw_speed_text":null,'
            '"apw_last_press":null}'
        )
        sample = AiPilotWheelState.from_json_line(line, received_wall_clock_s=99.0)
        assert sample.parked_active is False
        assert sample.mode_text is None
        assert sample.course_text is None
        assert sample.alt_text is None
        assert sample.alt_add_text is None
        assert sample.speed_text is None
        assert sample.last_press is None
        # Not present at all on this line (an older `Export.lua`'s own
        # shape, before the "Revised 2026-11-16" diagnostic fields
        # existed) -- missing is None, same as explicit null.
        assert sample.arg_852 is None
        assert sample.arg_952 is None
        assert sample.takeover_stage is None
        assert sample.correction_path is None

    def test_non_number_apw_arg852_is_a_parse_error(self) -> None:
        with pytest.raises(AiPilotWheelParseError):
            AiPilotWheelState.from_json_line(
                '{"t":1.5,"apw_parked_active":true,"apw_arg852":"not-a-number"}',
                received_wall_clock_s=99.0,
            )

    def test_missing_t_is_a_parse_error(self) -> None:
        with pytest.raises(AiPilotWheelParseError):
            AiPilotWheelState.from_json_line(
                '{"apw_parked_active":true}', received_wall_clock_s=99.0
            )

    def test_missing_apw_parked_active_is_a_parse_error(self) -> None:
        with pytest.raises(AiPilotWheelParseError):
            AiPilotWheelState.from_json_line('{"t":1.5}', received_wall_clock_s=99.0)

    def test_non_boolean_apw_parked_active_is_a_parse_error(self) -> None:
        with pytest.raises(AiPilotWheelParseError):
            AiPilotWheelState.from_json_line(
                '{"t":1.5,"apw_parked_active":"nope"}', received_wall_clock_s=99.0
            )

    def test_non_string_optional_field_is_a_parse_error(self) -> None:
        with pytest.raises(AiPilotWheelParseError):
            AiPilotWheelState.from_json_line(
                '{"t":1.5,"apw_parked_active":true,"apw_mode_text":123}',
                received_wall_clock_s=99.0,
            )

    def test_to_api_dict_carries_every_field(self) -> None:
        sample = AiPilotWheelState(
            dcs_model_time_s=1.5,
            received_wall_clock_s=99.0,
            parked_active=True,
            mode_text="ALT",
            course_text="090",
            alt_text="500 R",
            alt_add_text="MAX",
            speed_text="120",
            last_press="altitude_nudge_up",
            arg_852=0.95,
            arg_952=0.05,
            takeover_stage="correcting_altitude",
            correction_path="hold",
            seat="operator",
            cam_fwd_m=4.7,
            goal_progress="pressing",
            goal_seq=3,
        )
        assert sample.to_api_dict() == {
            "t": pytest.approx(1.5),
            "received_wall_clock_s": pytest.approx(99.0),
            "apw_parked_active": True,
            "apw_mode_text": "ALT",
            "apw_course_text": "090",
            "apw_alt_text": "500 R",
            "apw_alt_add_text": "MAX",
            "apw_speed_text": "120",
            "apw_last_press": "altitude_nudge_up",
            "apw_arg852": pytest.approx(0.95),
            "apw_arg952": pytest.approx(0.05),
            "apw_takeover_stage": "correcting_altitude",
            "apw_correction_path": "hold",
            "apw_seat": "operator",
            "apw_cam_fwd_m": pytest.approx(4.7),
            "apw_goal_progress": "pressing",
            "apw_goal_seq": 3,
            "apw_cbtm_status": None,
            "apw_cbtm_seq": None,
            # `AiPilotWheelState(...)` above predates the BL-16 sortie
            # 2026-11-20 reset-epoch field -- `None` default, same
            # "missing is None" posture every other optional field here
            # already has.
            "apw_reset_epoch": None,
        }


class TestAiPilotWheelGoalChannelFields:
    """Stage P2's own additions (`plans/flight-control/plan.md`, "Stage
    P2 ready to build", "The goal channel -- wire shape")."""

    def test_parses_goal_progress_and_goal_seq(self) -> None:
        line = (
            '{"t":1.5,"apw_parked_active":true,"apw_goal_progress":"pressing",'
            '"apw_goal_seq":7}'
        )
        sample = AiPilotWheelState.from_json_line(line, received_wall_clock_s=99.0)
        assert sample.goal_progress == "pressing"
        assert sample.goal_seq == 7

    def test_absent_goal_fields_parse_as_none(self) -> None:
        sample = AiPilotWheelState.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.goal_progress is None
        assert sample.goal_seq is None

    def test_non_whole_number_goal_seq_is_a_parse_error(self) -> None:
        with pytest.raises(AiPilotWheelParseError):
            AiPilotWheelState.from_json_line(
                '{"t":1.5,"apw_parked_active":true,"apw_goal_seq":1.5}',
                received_wall_clock_s=99.0,
            )

    def test_non_string_goal_progress_is_a_parse_error(self) -> None:
        with pytest.raises(AiPilotWheelParseError):
            AiPilotWheelState.from_json_line(
                '{"t":1.5,"apw_parked_active":true,"apw_goal_progress":1}',
                received_wall_clock_s=99.0,
            )


class TestAiPilotWheelCache:
    def test_empty_until_a_line_arrives(self) -> None:
        assert AiPilotWheelCache().latest() is None

    def test_keeps_only_the_latest(self) -> None:
        cache = AiPilotWheelCache()
        first = AiPilotWheelState.from_json_line(_LINE, received_wall_clock_s=1.0)
        second = AiPilotWheelState.from_json_line(_LINE, received_wall_clock_s=2.0)
        cache.push(first)
        cache.push(second)
        assert cache.latest() is second


class TestCollectorRouting:
    def _collector(self, ai_pilot_wheel_cache: AiPilotWheelCache) -> CollectorServer:
        return CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            ai_pilot_wheel_cache=ai_pilot_wheel_cache,
        )

    def test_an_apw_line_reaches_the_cache(self) -> None:
        cache = AiPilotWheelCache()
        self._collector(cache)._handle_line(_LINE)
        latest = cache.latest()
        assert latest is not None
        assert latest.parked_active is True

    def test_an_apw_line_is_never_parsed_as_telemetry(self) -> None:
        """It routes ahead of the telemetry fallthrough; reaching that
        would log every AI-pilot-wheel status update as a malformed
        sample."""
        telemetry = TelemetryCache()
        cache = AiPilotWheelCache()
        collector = CollectorServer(
            telemetry,
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            ai_pilot_wheel_cache=cache,
        )
        collector._handle_line(_LINE)
        assert telemetry.latest() is None
        assert cache.latest() is not None

    def test_a_collector_with_no_ai_pilot_wheel_cache_drops_the_line(self) -> None:
        """Correct behaviour rather than an error: nothing downstream is
        listening, and every pre-existing construction site passes no
        cache."""
        collector = CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
        )
        collector._handle_line(_LINE)  # must not raise

    def test_a_malformed_apw_line_is_dropped_not_raised(self) -> None:
        cache = AiPilotWheelCache()
        self._collector(cache)._handle_line('{"t":1.0,"apw_parked_active":"nope"}')
        assert cache.latest() is None


class TestAiPilotWheelLatestEndpoint:
    @pytest.fixture
    def server(self) -> Iterator[tuple[str, AiPilotWheelCache]]:
        cache = AiPilotWheelCache()
        api = TelemetryAPIServer(
            TelemetryCache(), host="127.0.0.1", port=0, ai_pilot_wheel_cache=cache
        )
        api.open()
        thread = threading.Thread(target=api.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{api.port}", cache
        finally:
            api.close()
            thread.join(timeout=5)

    def _get(self, base_url: str) -> object:
        with urllib.request.urlopen(
            f"{base_url}/ai_pilot_wheel/latest", timeout=5
        ) as response:
            return json.loads(response.read())

    def test_null_before_the_first_line_arrives(
        self, server: tuple[str, AiPilotWheelCache]
    ) -> None:
        base_url, _ = server
        assert self._get(base_url) is None

    def test_serves_the_latest_sample(
        self, server: tuple[str, AiPilotWheelCache]
    ) -> None:
        base_url, cache = server
        cache.push(AiPilotWheelState.from_json_line(_LINE, received_wall_clock_s=99.0))
        payload = self._get(base_url)
        assert payload == {
            "t": pytest.approx(1.5),
            "received_wall_clock_s": pytest.approx(99.0),
            "apw_parked_active": True,
            "apw_mode_text": "ALT",
            "apw_course_text": "090",
            "apw_alt_text": "500 R",
            "apw_alt_add_text": "MAX",
            "apw_speed_text": "120",
            "apw_last_press": "altitude_nudge_up",
            "apw_arg852": pytest.approx(0.95),
            "apw_arg952": pytest.approx(0.05),
            "apw_takeover_stage": "correcting_altitude",
            "apw_correction_path": "hold",
            "apw_seat": "operator",
            "apw_cam_fwd_m": pytest.approx(4.7),
            # `_LINE` predates the Stage P2 goal-channel fields -- absent
            # on the wire, not an error, same "missing is None" posture
            # every other optional field here already has.
            "apw_goal_progress": None,
            "apw_goal_seq": None,
            "apw_cbtm_status": None,
            "apw_cbtm_seq": None,
            "apw_reset_epoch": None,
        }


def test_a_line_without_the_seat_fields_still_parses() -> None:
    """fix/ai-wheel-pilot-seat-gate: an older `Export.lua` sends no
    `apw_seat`/`apw_cam_fwd_m` -- both read `None`, the line still parses."""
    old_line = _LINE.replace(',"apw_seat":"operator","apw_cam_fwd_m":4.7', "")
    state = AiPilotWheelState.from_json_line(old_line, received_wall_clock_s=0.0)
    assert state.seat is None
    assert state.cam_fwd_m is None


def test_a_non_string_seat_is_rejected() -> None:
    bad = _LINE.replace('"apw_seat":"operator"', '"apw_seat":3')
    with pytest.raises(AiPilotWheelParseError):
        AiPilotWheelState.from_json_line(bad, received_wall_clock_s=0.0)
