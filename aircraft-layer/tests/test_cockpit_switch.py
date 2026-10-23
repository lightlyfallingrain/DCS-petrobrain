"""The 9K113 cockpit-switch channel (`plans/9k113-effectors/plan.md`,
BL-B66 Stage 1): schema, cache, line routing, `send_cockpit_switch`, and
the `GET /cockpit_switch/latest` / `POST /command/cockpit_switch`
endpoints.

Mirrors `test_schema_spu8.py`'s structure for the read side (same
raw-plus-decided shape, six args instead of three) and
`test_petrovich_search_api.py`'s structure for the write side (same
shape-validation-only, raise-on-failure posture) -- except this write
path has **no allow-list of which `(device, cmd)` pairs are accepted**
(user direction 2026-10-21, see `aircraft-layer/CLAUDE.md`'s "What this
is" section), so the invalid-request tests here cover shape only
(non-integer device/cmd, non-finite value), never an unknown switch.
"""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import (
    CockpitSwitchCache,
    PetrovichIndicationCache,
    PetrovichWheelCache,
    TelemetryCache,
    WorldObjectsCache,
)
from collector.command_sender import CommandSender, CommandSendError
from collector.server import CollectorServer
from schema import CockpitSwitchParseError, CockpitSwitchState


class TestCockpitSwitchState:
    def test_parses_a_line(self) -> None:
        sample = CockpitSwitchState.from_json_line(
            '{"t":11.423,"missl_pw":1.0,"cplr_distr":0.0,"sight_pw":1.0,'
            '"scho_pw":0.0,"observe":1.0,"weap_safe":0.0}',
            received_wall_clock_s=99.0,
        )
        assert sample.dcs_model_time_s == pytest.approx(11.423)
        assert sample.received_wall_clock_s == 99.0
        assert sample.missl_pw == pytest.approx(1.0)
        assert sample.cplr_distr == pytest.approx(0.0)
        assert sample.sight_pw == pytest.approx(1.0)
        assert sample.scho_pw == pytest.approx(0.0)
        assert sample.observe == pytest.approx(1.0)
        assert sample.weap_safe == pytest.approx(0.0)
        assert sample.sight_az is None
        assert sample.sight_elev is None

    def test_parses_a_line_with_sight_position_readback(self) -> None:
        """BL-B66 Stage 4b: args 874/876, wire keys `sight_az`/
        `sight_elev` -- present and numeric is parsed."""
        sample = CockpitSwitchState.from_json_line(
            '{"t":11.423,"missl_pw":1.0,"cplr_distr":0.0,"sight_pw":1.0,'
            '"scho_pw":0.0,"observe":1.0,"weap_safe":0.0,'
            '"sight_az":0.16500,"sight_elev":-0.28125}',
            received_wall_clock_s=99.0,
        )
        assert sample.sight_az == pytest.approx(0.16500)
        assert sample.sight_elev == pytest.approx(-0.28125)

    def test_a_present_but_non_numeric_sight_position_is_a_parse_error(
        self,
    ) -> None:
        """Absent is `None` (the test above's sibling); present-but-wrong-
        typed is still an error, same as any required field -- a value
        that arrived malformed is not the same fact as one that never
        arrived."""
        with pytest.raises(CockpitSwitchParseError):
            CockpitSwitchState.from_dict(
                {
                    "t": 1.0,
                    "missl_pw": 1.0,
                    "cplr_distr": 0.0,
                    "sight_pw": 0.0,
                    "scho_pw": 0.0,
                    "observe": 0.0,
                    "weap_safe": 0.0,
                    "sight_az": "not a number",
                },
                received_wall_clock_s=2.0,
            )

    def test_the_switches_threshold_at_half_not_equality(self) -> None:
        """All six animate through intermediate values for ~0.1s on a
        flip (confirmed live, 2026-10-17 probe) -- a reader must
        threshold, not test equality."""
        mid_transit = CockpitSwitchState(
            1.0,
            2.0,
            missl_pw=0.64,
            cplr_distr=0.0,
            sight_pw=0.0,
            scho_pw=0.0,
            observe=0.0,
            weap_safe=0.0,
        )
        assert mid_transit.missl_pw_on is True

        still_low = CockpitSwitchState(
            1.0,
            2.0,
            missl_pw=0.32,
            cplr_distr=0.0,
            sight_pw=0.0,
            scho_pw=0.0,
            observe=0.0,
            weap_safe=0.0,
        )
        assert still_low.missl_pw_on is False

    def test_weap_safe_on_means_armed(self) -> None:
        """arg 673: 1 is ARMED, 0 is SAFE (`body-layer/research/
        2026-10-14-9k113-warmup-atgm-procedure.md` Finding 6)."""
        armed = CockpitSwitchState(
            1.0,
            2.0,
            missl_pw=0.0,
            cplr_distr=0.0,
            sight_pw=0.0,
            scho_pw=0.0,
            observe=0.0,
            weap_safe=1.0,
        )
        safe = CockpitSwitchState(
            1.0,
            2.0,
            missl_pw=0.0,
            cplr_distr=0.0,
            sight_pw=0.0,
            scho_pw=0.0,
            observe=0.0,
            weap_safe=0.0,
        )
        assert armed.weapons_armed is True
        assert safe.weapons_armed is False

    def test_a_missing_value_is_a_parse_error(self) -> None:
        with pytest.raises(CockpitSwitchParseError):
            CockpitSwitchState.from_dict(
                {"t": 1.0, "missl_pw": 1.0}, received_wall_clock_s=2.0
            )

    def test_a_non_numeric_value_is_a_parse_error(self) -> None:
        with pytest.raises(CockpitSwitchParseError):
            CockpitSwitchState.from_dict(
                {
                    "t": 1.0,
                    "missl_pw": "on",
                    "cplr_distr": 0.0,
                    "sight_pw": 0.0,
                    "scho_pw": 0.0,
                    "observe": 0.0,
                    "weap_safe": 0.0,
                },
                received_wall_clock_s=2.0,
            )

    def test_a_boolean_is_not_a_number(self) -> None:
        with pytest.raises(CockpitSwitchParseError):
            CockpitSwitchState.from_dict(
                {
                    "t": 1.0,
                    "missl_pw": True,
                    "cplr_distr": 0.0,
                    "sight_pw": 0.0,
                    "scho_pw": 0.0,
                    "observe": 0.0,
                    "weap_safe": 0.0,
                },
                received_wall_clock_s=2.0,
            )

    def test_to_api_dict_carries_raw_and_decided_fields(self) -> None:
        sample = CockpitSwitchState(
            11.423,
            99.0,
            missl_pw=1.0,
            cplr_distr=0.0,
            sight_pw=1.0,
            scho_pw=0.0,
            observe=1.0,
            weap_safe=0.0,
        )
        assert sample.to_api_dict() == {
            "t": pytest.approx(11.423),
            "received_wall_clock_s": pytest.approx(99.0),
            "missl_pw": pytest.approx(1.0),
            "cplr_distr": pytest.approx(0.0),
            "sight_pw": pytest.approx(1.0),
            "scho_pw": pytest.approx(0.0),
            "observe": pytest.approx(1.0),
            "weap_safe": pytest.approx(0.0),
            "missl_pw_on": True,
            "cplr_distr_on": False,
            "sight_pw_on": True,
            "scho_pw_on": False,
            "observe_on": True,
            "weapons_armed": False,
            "sight_az": None,
            "sight_elev": None,
            "align_lamp": None,
            "ready_lamp": None,
            "launch_perm_lamp": None,
            "args": {
                "773": pytest.approx(1.0),
                "761": pytest.approx(0.0),
                "885": pytest.approx(1.0),
                "955": pytest.approx(0.0),
                "886": pytest.approx(1.0),
                "673": pytest.approx(0.0),
            },
        }


class TestCockpitSwitchCache:
    def test_empty_until_a_line_arrives(self) -> None:
        assert CockpitSwitchCache().latest() is None

    def test_keeps_only_the_latest(self) -> None:
        cache = CockpitSwitchCache()
        cache.push(
            CockpitSwitchState(
                1.0,
                2.0,
                missl_pw=1.0,
                cplr_distr=0.0,
                sight_pw=0.0,
                scho_pw=0.0,
                observe=0.0,
                weap_safe=0.0,
            )
        )
        cache.push(
            CockpitSwitchState(
                2.0,
                3.0,
                missl_pw=0.0,
                cplr_distr=0.0,
                sight_pw=0.0,
                scho_pw=0.0,
                observe=0.0,
                weap_safe=0.0,
            )
        )
        latest = cache.latest()
        assert latest is not None
        assert latest.missl_pw == 0.0


class TestCollectorRouting:
    def _collector(self, cockpit_switch_cache: CockpitSwitchCache) -> CollectorServer:
        return CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            cockpit_switch_cache=cockpit_switch_cache,
        )

    _LINE = (
        '{"t":1.0,"missl_pw":1.0,"cplr_distr":0.0,"sight_pw":0.0,'
        '"scho_pw":0.0,"observe":0.0,"weap_safe":0.0}'
    )

    def test_a_missl_pw_line_reaches_the_cache(self) -> None:
        cache = CockpitSwitchCache()
        self._collector(cache)._handle_line(self._LINE)
        latest = cache.latest()
        assert latest is not None
        assert latest.missl_pw_on is True

    def test_a_missl_pw_line_is_never_parsed_as_telemetry(self) -> None:
        """It routes ahead of the telemetry fallthrough; reaching that
        would log every cockpit-switch change as a malformed sample."""
        telemetry = TelemetryCache()
        cache = CockpitSwitchCache()
        collector = CollectorServer(
            telemetry,
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            cockpit_switch_cache=cache,
        )
        collector._handle_line(self._LINE)
        assert telemetry.latest() is None
        assert cache.latest() is not None

    def test_a_collector_with_no_cockpit_switch_cache_drops_the_line(self) -> None:
        """Correct behaviour rather than an error: nothing downstream is
        listening, and every pre-existing construction site passes no
        cache."""
        collector = CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
        )
        collector._handle_line(self._LINE)  # must not raise

    def test_a_malformed_missl_pw_line_is_dropped_not_raised(self) -> None:
        cache = CockpitSwitchCache()
        self._collector(cache)._handle_line(
            '{"t":1.0,"missl_pw":"nope","cplr_distr":0.0,"sight_pw":0.0,'
            '"scho_pw":0.0,"observe":0.0,"weap_safe":0.0}'
        )
        assert cache.latest() is None


class TestCockpitSwitchLatestEndpoint:
    @pytest.fixture
    def server(self) -> Iterator[tuple[str, CockpitSwitchCache]]:
        cache = CockpitSwitchCache()
        api = TelemetryAPIServer(
            TelemetryCache(), host="127.0.0.1", port=0, cockpit_switch_cache=cache
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
            f"{base_url}/cockpit_switch/latest", timeout=5
        ) as response:
            return json.loads(response.read())

    def test_null_before_the_first_line_arrives(
        self, server: tuple[str, CockpitSwitchCache]
    ) -> None:
        base_url, _ = server
        assert self._get(base_url) is None

    def test_serves_the_raw_values_and_decided_fields(
        self, server: tuple[str, CockpitSwitchCache]
    ) -> None:
        base_url, cache = server
        cache.push(
            CockpitSwitchState(
                11.423,
                99.0,
                missl_pw=1.0,
                cplr_distr=0.0,
                sight_pw=1.0,
                scho_pw=0.0,
                observe=1.0,
                weap_safe=0.0,
            )
        )
        payload = self._get(base_url)
        assert payload == {
            "t": pytest.approx(11.423),
            "received_wall_clock_s": pytest.approx(99.0),
            "missl_pw": pytest.approx(1.0),
            "cplr_distr": pytest.approx(0.0),
            "sight_pw": pytest.approx(1.0),
            "scho_pw": pytest.approx(0.0),
            "observe": pytest.approx(1.0),
            "weap_safe": pytest.approx(0.0),
            "missl_pw_on": True,
            "cplr_distr_on": False,
            "sight_pw_on": True,
            "scho_pw_on": False,
            "observe_on": True,
            "weapons_armed": False,
            "sight_az": None,
            "sight_elev": None,
            "align_lamp": None,
            "ready_lamp": None,
            "launch_perm_lamp": None,
            "args": {
                "773": pytest.approx(1.0),
                "761": pytest.approx(0.0),
                "885": pytest.approx(1.0),
                "955": pytest.approx(0.0),
                "886": pytest.approx(1.0),
                "673": pytest.approx(0.0),
            },
        }


class TestSendCockpitSwitch:
    """`CommandSender.send_cockpit_switch` -- mirrors `test_command_sender.
    py`'s structure for `send_command`."""

    def test_delivers_well_formed_datagram(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_cockpit_switch(7, 3001, 1.0)

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded == {
                "op": "cockpit_switch",
                "device": 7,
                "cmd": 3001,
                "value": 1.0,
            }
        finally:
            receiver.close()

    def test_raises_command_send_error_on_a_failed_send(self) -> None:
        class _FailingSocket:
            def sendto(self, payload: bytes, address: tuple[str, int]) -> int:
                raise OSError("simulated send failure")

            def close(self) -> None:
                pass

        sender = CommandSender(host="127.0.0.1", port=1)
        sender.open()
        sender._socket = _FailingSocket()  # type: ignore[assignment]

        with pytest.raises(CommandSendError):
            sender.send_cockpit_switch(7, 3001, 1.0)


class _RecordingCommandSender(CommandSender):
    """A `CommandSender` double that records calls instead of sending UDP."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[int, int, float]] = []
        self.raise_on_send = False

    def send_cockpit_switch(  # type: ignore[override]
        self, device: int, cmd: int, value: float
    ) -> None:
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.sent.append((device, cmd, value))


@pytest.fixture
def running_server_with_sender() -> Iterator[
    tuple[TelemetryAPIServer, _RecordingCommandSender]
]:
    cache = TelemetryCache()
    sender = _RecordingCommandSender()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0, command_sender=sender)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, sender
    finally:
        server.close()
        thread.join(timeout=5)


def _post(server: TelemetryAPIServer, path: str, body: object) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    data = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


class TestCockpitSwitchCommandEndpoint:
    """`POST /command/cockpit_switch` -- shape validation only, **no
    allow-list** (user direction 2026-10-21)."""

    def test_valid_request_forwards_to_sender(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 7, "cmd": 3001, "value": 1},
        )
        assert status == 200
        assert body == {"ok": True}
        assert sender.sent == [(7, 3001, 1.0)]

    def test_an_arbitrary_device_cmd_pair_is_accepted(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        """No allow-list -- any shape-valid (device, cmd, value) is
        forwarded, including one this entry's six switches never use."""
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 99, "cmd": 12345, "value": 0.5},
        )
        assert status == 200
        assert sender.sent == [(99, 12345, 0.5)]

    def test_missing_device_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, body = _post(
            server, "/command/cockpit_switch", {"cmd": 3001, "value": 1}
        )
        assert status == 400
        assert isinstance(body, dict)
        assert "error" in body
        assert sender.sent == []

    def test_non_integer_device_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 7.5, "cmd": 3001, "value": 1},
        )
        assert status == 400
        assert sender.sent == []

    def test_boolean_device_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/cockpit_switch",
            {"device": True, "cmd": 3001, "value": 1},
        )
        assert status == 400
        assert sender.sent == []

    def test_non_integer_cmd_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 7, "cmd": "x", "value": 1},
        )
        assert status == 400
        assert sender.sent == []

    def test_non_finite_value_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 7, "cmd": 3001, "value": float("inf")},
        )
        assert status == 400
        assert sender.sent == []

    def test_missing_value_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/cockpit_switch", {"device": 7, "cmd": 3001}
        )
        assert status == 400
        assert sender.sent == []

    def test_non_json_body_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/cockpit_switch", b"not json")
        assert status == 400
        assert sender.sent == []

    def test_without_configured_sender_returns_503(self) -> None:
        cache = TelemetryCache()
        server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, body = _post(
                server,
                "/command/cockpit_switch",
                {"device": 7, "cmd": 3001, "value": 1},
            )
            assert status == 503
            assert isinstance(body, dict)
            assert "error" in body
        finally:
            server.close()
            thread.join(timeout=5)

    def test_send_failure_returns_500(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        sender.raise_on_send = True
        status, body = _post(
            server,
            "/command/cockpit_switch",
            {"device": 7, "cmd": 3001, "value": 1},
        )
        assert status == 500
        assert isinstance(body, dict)
        assert "error" in body
