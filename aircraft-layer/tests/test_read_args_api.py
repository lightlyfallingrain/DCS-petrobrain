"""`POST /query/read_args` -- the synchronous one-shot read endpoint
(`plans/effector-sequences/plan.md` Stage 4, S4.2). Against a real
`TelemetryAPIServer` with a recording `ArgReadBroker` double, mirroring
`test_watched_args.py`'s `TestWatchArgsCommandEndpoint` structure for the
other new endpoint."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.arg_read_broker import ArgReadBrokerBusy, ArgReadResult, ArgReadTimeout
from collector.cache import TelemetryCache
from collector.command_sender import CommandSendError


class _RecordingArgReadBroker:
    """A double for `ArgReadBroker` -- records the args it was asked to
    read and returns/raises whatever the test configured, never touching
    a real socket or thread."""

    def __init__(self) -> None:
        self.requested: list[list[int]] = []
        self.result: ArgReadResult | None = ArgReadResult(
            dcs_model_time_s=5.0, values={}
        )
        self.raise_: BaseException | None = None

    def read(self, args: list[int]) -> ArgReadResult:
        self.requested.append(list(args))
        if self.raise_ is not None:
            raise self.raise_
        assert self.result is not None
        return self.result


@pytest.fixture
def running_server_with_broker() -> Iterator[
    tuple[TelemetryAPIServer, _RecordingArgReadBroker]
]:
    cache = TelemetryCache()
    broker = _RecordingArgReadBroker()
    server = TelemetryAPIServer(
        cache,
        host="127.0.0.1",
        port=0,
        arg_read_broker=broker,  # type: ignore[arg-type]
    )
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, broker
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


class TestReadArgsEndpoint:
    def test_valid_request_returns_values(
        self,
        running_server_with_broker: tuple[TelemetryAPIServer, _RecordingArgReadBroker],
    ) -> None:
        server, broker = running_server_with_broker
        broker.result = ArgReadResult(
            dcs_model_time_s=12.5, values={773: 1.0, 761: 0.0}
        )
        status, body = _post(server, "/query/read_args", {"args": [773, 761]})
        assert status == 200
        assert body == {
            "t": pytest.approx(12.5),
            "values": {"773": pytest.approx(1.0), "761": pytest.approx(0.0)},
        }
        assert broker.requested == [[761, 773]]  # deduped+sorted by _validate_arg_list

    def test_missing_args_returns_400(
        self,
        running_server_with_broker: tuple[TelemetryAPIServer, _RecordingArgReadBroker],
    ) -> None:
        server, broker = running_server_with_broker
        status, _body = _post(server, "/query/read_args", {})
        assert status == 400
        assert broker.requested == []

    def test_out_of_range_arg_returns_400(
        self,
        running_server_with_broker: tuple[TelemetryAPIServer, _RecordingArgReadBroker],
    ) -> None:
        server, broker = running_server_with_broker
        status, _body = _post(server, "/query/read_args", {"args": [4096]})
        assert status == 400
        assert broker.requested == []

    def test_too_many_args_returns_400(
        self,
        running_server_with_broker: tuple[TelemetryAPIServer, _RecordingArgReadBroker],
    ) -> None:
        server, broker = running_server_with_broker
        status, _body = _post(server, "/query/read_args", {"args": list(range(65))})
        assert status == 400
        assert broker.requested == []

    def test_non_json_body_returns_400(
        self,
        running_server_with_broker: tuple[TelemetryAPIServer, _RecordingArgReadBroker],
    ) -> None:
        server, broker = running_server_with_broker
        status, _body = _post(server, "/query/read_args", b"not json")
        assert status == 400
        assert broker.requested == []

    def test_without_configured_broker_returns_503(self) -> None:
        cache = TelemetryCache()
        server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, body = _post(server, "/query/read_args", {"args": [886]})
            assert status == 503
            assert isinstance(body, dict)
            assert "error" in body
        finally:
            server.close()
            thread.join(timeout=5)

    def test_broker_timeout_returns_504(
        self,
        running_server_with_broker: tuple[TelemetryAPIServer, _RecordingArgReadBroker],
    ) -> None:
        server, broker = running_server_with_broker
        broker.raise_ = ArgReadTimeout("no reply")
        status, body = _post(server, "/query/read_args", {"args": [886]})
        assert status == 504
        assert isinstance(body, dict)
        assert "error" in body

    def test_broker_busy_returns_503(
        self,
        running_server_with_broker: tuple[TelemetryAPIServer, _RecordingArgReadBroker],
    ) -> None:
        server, broker = running_server_with_broker
        broker.raise_ = ArgReadBrokerBusy("too many")
        status, body = _post(server, "/query/read_args", {"args": [886]})
        assert status == 503
        assert isinstance(body, dict)
        assert "error" in body

    def test_send_failure_returns_500(
        self,
        running_server_with_broker: tuple[TelemetryAPIServer, _RecordingArgReadBroker],
    ) -> None:
        server, broker = running_server_with_broker
        broker.raise_ = CommandSendError("simulated send failure")
        status, body = _post(server, "/query/read_args", {"args": [886]})
        assert status == 500
        assert isinstance(body, dict)
        assert "error" in body
