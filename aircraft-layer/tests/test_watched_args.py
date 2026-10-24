"""The generic cockpit-arg readback (`plans/effector-sequences/plan.md`
Stage 4, "readback by need" option B): `WatchedArgsState`/
`parse_arg_values`, `WatchedArgsCache`, collector line routing,
`GET /watched_args/latest`, and `POST /command/watch_args`.

The one-shot `POST /query/read_args` path (`ArgReadBroker`) has its own
test file, `test_arg_read_broker.py` -- it needs a threaded fake sender
and timing, a different shape of test from this file's."""

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
    PetrovichIndicationCache,
    PetrovichWheelCache,
    TelemetryCache,
    WatchedArgsCache,
    WorldObjectsCache,
)
from collector.command_sender import CommandSender, CommandSendError
from collector.server import CollectorServer
from schema import WatchedArgsParseError, WatchedArgsState, parse_arg_values


class TestParseArgValues:
    def test_valid_map(self) -> None:
        assert parse_arg_values({"886": 1.0, "898": 0.0}) == {886: 1.0, 898: 0.0}

    def test_not_an_object_is_an_error(self) -> None:
        with pytest.raises(WatchedArgsParseError):
            parse_arg_values([1, 2])

    def test_too_many_keys_is_an_error(self) -> None:
        raw = {str(n): 0.0 for n in range(65)}
        with pytest.raises(WatchedArgsParseError):
            parse_arg_values(raw)

    def test_exactly_64_keys_is_fine(self) -> None:
        raw = {str(n): 0.0 for n in range(64)}
        assert len(parse_arg_values(raw)) == 64

    @pytest.mark.parametrize("key", ["abc", "-1", "4096", "1.5", ""])
    def test_bad_key_is_an_error(self, key: str) -> None:
        with pytest.raises(WatchedArgsParseError):
            parse_arg_values({key: 0.0})

    def test_key_of_exactly_4095_is_fine(self) -> None:
        assert parse_arg_values({"4095": 0.0}) == {4095: 0.0}

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_value_is_an_error(self, value: float) -> None:
        """Mutation (security plan review): drop `math.isfinite` and a
        NaN survives -- `abs(NaN - t) < g` is `False` in Python, so it
        would read as "differs" and a caller's own `_matches` would
        write on it."""
        with pytest.raises(WatchedArgsParseError):
            parse_arg_values({"886": value})

    def test_boolean_value_is_an_error(self) -> None:
        with pytest.raises(WatchedArgsParseError):
            parse_arg_values({"886": True})


class TestWatchedArgsState:
    def test_parses_a_line(self) -> None:
        sample = WatchedArgsState.from_json_line(
            '{"t":11.423,"watch_id":"abc123","watched":{"886":1.0,"898":0.0}}',
            received_wall_clock_s=99.0,
        )
        assert sample.dcs_model_time_s == pytest.approx(11.423)
        assert sample.received_wall_clock_s == 99.0
        assert sample.watch_id == "abc123"
        assert sample.values == {886: 1.0, 898: 0.0}

    def test_missing_watch_id_is_an_error(self) -> None:
        with pytest.raises(WatchedArgsParseError):
            WatchedArgsState.from_dict(
                {"t": 1.0, "watched": {}}, received_wall_clock_s=2.0
            )

    def test_17_char_watch_id_is_an_error(self) -> None:
        with pytest.raises(WatchedArgsParseError):
            WatchedArgsState.from_dict(
                {"t": 1.0, "watch_id": "a" * 17, "watched": {}},
                received_wall_clock_s=2.0,
            )

    def test_bad_watched_map_is_an_error(self) -> None:
        """Delegates to `parse_arg_values` -- one representative case,
        not the full matrix (covered by `TestParseArgValues` above)."""
        with pytest.raises(WatchedArgsParseError):
            WatchedArgsState.from_dict(
                {"t": 1.0, "watch_id": "abc", "watched": {"886": float("nan")}},
                received_wall_clock_s=2.0,
            )

    def test_to_api_dict_shape_matches_stage_2s_args_map(self) -> None:
        """`belief.effector_engine.observed_value`/`advance` read
        `readback.get(str(arg))` -- this shape must not change."""
        sample = WatchedArgsState(
            11.423, 99.0, watch_id="abc123", values={886: 1.0, 898: 0.0}
        )
        assert sample.to_api_dict() == {
            "t": pytest.approx(11.423),
            "received_wall_clock_s": pytest.approx(99.0),
            "watch_id": "abc123",
            "args": {"886": pytest.approx(1.0), "898": pytest.approx(0.0)},
        }


class TestWatchedArgsCache:
    def test_empty_until_a_line_arrives(self) -> None:
        assert WatchedArgsCache().latest() is None

    def test_keeps_only_the_latest(self) -> None:
        cache = WatchedArgsCache()
        cache.push(WatchedArgsState(1.0, 2.0, watch_id="a", values={886: 1.0}))
        cache.push(WatchedArgsState(2.0, 3.0, watch_id="a", values={886: 0.0}))
        latest = cache.latest()
        assert latest is not None
        assert latest.values == {886: 0.0}

    def test_clear_resets_to_empty(self) -> None:
        cache = WatchedArgsCache()
        cache.push(WatchedArgsState(1.0, 2.0, watch_id="a", values={886: 1.0}))
        cache.clear()
        assert cache.latest() is None


class TestCollectorRouting:
    def _collector(self, watched_args_cache: WatchedArgsCache) -> CollectorServer:
        return CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            watched_args_cache=watched_args_cache,
        )

    _LINE = '{"t":1.0,"watch_id":"abc123","watched":{"886":1.0}}'

    def test_a_watch_id_line_reaches_the_cache(self) -> None:
        cache = WatchedArgsCache()
        self._collector(cache)._handle_line(self._LINE)
        latest = cache.latest()
        assert latest is not None
        assert latest.values == {886: 1.0}

    def test_a_watch_id_line_is_never_parsed_as_telemetry(self) -> None:
        telemetry = TelemetryCache()
        cache = WatchedArgsCache()
        collector = CollectorServer(
            telemetry,
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            watched_args_cache=cache,
        )
        collector._handle_line(self._LINE)
        assert telemetry.latest() is None
        assert cache.latest() is not None

    def test_a_collector_with_no_watched_args_cache_drops_the_line(self) -> None:
        collector = CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
        )
        collector._handle_line(self._LINE)  # must not raise

    def test_a_malformed_watch_id_line_is_dropped_not_raised(self) -> None:
        cache = WatchedArgsCache()
        self._collector(cache)._handle_line(
            '{"t":1.0,"watch_id":"abc123","watched":{"886":"nope"}}'
        )
        assert cache.latest() is None

    def test_an_old_missl_pw_line_is_dropped_not_misparsed(self) -> None:
        """The old cockpit-switch readback feed no longer exists on this
        side -- an old deployed `Export.lua`'s line is dropped, not
        misreported as malformed telemetry."""
        telemetry = TelemetryCache()
        collector = CollectorServer(
            telemetry,
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
        )
        collector._handle_line(
            '{"t":1.0,"missl_pw":1.0,"cplr_distr":0.0,"sight_pw":0.0,'
            '"scho_pw":0.0,"observe":0.0,"weap_safe":0.0}'
        )
        assert telemetry.latest() is None

    def test_export_version_line_clears_the_cache(self) -> None:
        """A new `Export.lua` session means the watched set was reset --
        clearing turns the stale pre-restart line into `None`, which is
        what tells body-layer to re-send its `watch_args` install."""
        cache = WatchedArgsCache()
        collector = self._collector(cache)
        collector._handle_line(self._LINE)
        assert cache.latest() is not None
        collector._handle_line('{"export_version":"2026-10-24"}')
        assert cache.latest() is None


class TestWatchedArgsLatestEndpoint:
    @pytest.fixture
    def server(self) -> Iterator[tuple[str, WatchedArgsCache]]:
        cache = WatchedArgsCache()
        api = TelemetryAPIServer(
            TelemetryCache(), host="127.0.0.1", port=0, watched_args_cache=cache
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
            f"{base_url}/watched_args/latest", timeout=5
        ) as response:
            return json.loads(response.read())

    def test_null_before_the_first_line_arrives(
        self, server: tuple[str, WatchedArgsCache]
    ) -> None:
        base_url, _ = server
        assert self._get(base_url) is None

    def test_serves_the_args_map(self, server: tuple[str, WatchedArgsCache]) -> None:
        base_url, cache = server
        cache.push(WatchedArgsState(11.423, 99.0, watch_id="abc123", values={886: 1.0}))
        payload = self._get(base_url)
        assert payload == {
            "t": pytest.approx(11.423),
            "received_wall_clock_s": pytest.approx(99.0),
            "watch_id": "abc123",
            "args": {"886": pytest.approx(1.0)},
        }


class TestSendWatchArgs:
    def test_delivers_well_formed_datagram(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        try:
            with CommandSender(host="127.0.0.1", port=port) as sender:
                sender.send_watch_args("abc123", [898, 886, 960])

            data, _addr = receiver.recvfrom(4096)
            decoded = json.loads(data.decode("utf-8"))
            assert decoded == {
                "op": "watch_args",
                "watch_id": "abc123",
                "args": [898, 886, 960],
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
            sender.send_watch_args("abc123", [886])


class _RecordingCommandSender(CommandSender):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[str, list[int]]] = []
        self.raise_on_send = False

    def send_watch_args(  # type: ignore[override]
        self, watch_id: str, args: list[int]
    ) -> None:
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.sent.append((watch_id, args))


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


class TestWatchArgsCommandEndpoint:
    def test_valid_request_forwards_to_sender(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, body = _post(
            server, "/command/watch_args", {"watch_id": "abc123", "args": [886, 898]}
        )
        assert status == 200
        assert body == {"ok": True}
        assert sender.sent == [("abc123", [886, 898])]

    def test_missing_watch_id_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/watch_args", {"args": [886]})
        assert status == 400
        assert sender.sent == []

    def test_bad_watch_id_chars_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/watch_args", {"watch_id": "has space", "args": [886]}
        )
        assert status == 400
        assert sender.sent == []

    def test_17_char_watch_id_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/watch_args", {"watch_id": "a" * 17, "args": [886]}
        )
        assert status == 400
        assert sender.sent == []

    def test_non_list_args_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/watch_args", {"watch_id": "abc", "args": "886"}
        )
        assert status == 400
        assert sender.sent == []

    def test_out_of_range_arg_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/watch_args", {"watch_id": "abc", "args": [4096]}
        )
        assert status == 400
        assert sender.sent == []

    def test_boolean_arg_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/watch_args", {"watch_id": "abc", "args": [True]}
        )
        assert status == 400
        assert sender.sent == []

    def test_too_many_args_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/watch_args", {"watch_id": "abc", "args": list(range(65))}
        )
        assert status == 400
        assert sender.sent == []

    def test_empty_args_list_is_valid(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        """An empty list clears the watched set -- valid, not an error."""
        server, sender = running_server_with_sender
        status, _body = _post(
            server, "/command/watch_args", {"watch_id": "abc", "args": []}
        )
        assert status == 200
        assert sender.sent == [("abc", [])]

    def test_non_json_body_returns_400(
        self,
        running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
    ) -> None:
        server, sender = running_server_with_sender
        status, _body = _post(server, "/command/watch_args", b"not json")
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
                server, "/command/watch_args", {"watch_id": "abc", "args": [886]}
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
            server, "/command/watch_args", {"watch_id": "abc", "args": [886]}
        )
        assert status == 500
        assert isinstance(body, dict)
        assert "error" in body
