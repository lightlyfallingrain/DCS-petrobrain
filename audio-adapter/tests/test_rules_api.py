"""Tests for `server.TTSAdapterServer`'s `PUT /rules` and the
`X-Rules-Version` header on `GET /transcripts/poll` (`plans/
speech-rules/plan.md` D1/D2, Stage 1b; `category` added D16/Stage 3b).
Structural copy of `test_transcribe_api.py`'s pattern (real loopback
server, recording/fake collaborator doubles)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from server import TTSAdapterServer


class _FakeTTSEngine:
    def synthesize(self, text: str) -> bytes:
        return b"FAKE-WAV-BYTES"


class _NullSink:
    def deliver(
        self, audio: bytes, urgent: bool, correlation_id: str | None = None
    ) -> None:
        pass

    def interrupt(self) -> None:
        pass


@pytest.fixture
def running_server() -> Iterator[TTSAdapterServer]:
    server = TTSAdapterServer(_FakeTTSEngine(), _NullSink(), host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.close()
        thread.join(timeout=5)


def _put_rules(server: TTSAdapterServer, body: object) -> tuple[int, dict[str, object]]:
    url = f"http://127.0.0.1:{server.port}/rules"
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="PUT"
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _poll_headers(server: TTSAdapterServer) -> dict[str, str]:
    url = f"http://127.0.0.1:{server.port}/transcripts/poll"
    with urllib.request.urlopen(url) as response:
        return dict(response.headers)


def test_a_valid_rule_is_accepted(running_server: TTSAdapterServer) -> None:
    status, body = _put_rules(
        running_server,
        {
            "version": "v1",
            "rules": [
                {
                    "id": "example_rule",
                    "pattern": "xyzzy <direction:left|right> <degrees:angle>",
                    "category": "flight_control",
                }
            ],
        },
    )
    assert status == 200
    assert body["version"] == "v1"
    assert body["accepted"] == ["example_rule"]
    assert body["rejected"] == []


def test_bad_grammar_is_rejected_with_a_reason(
    running_server: TTSAdapterServer,
) -> None:
    status, body = _put_rules(
        running_server,
        {
            "version": "v1",
            "rules": [
                {"id": "bad", "pattern": "scan <deg:bearing>", "category": "always"}
            ],
        },
    )
    assert status == 200
    assert body["accepted"] == []
    assert body["rejected"][0]["id"] == "bad"
    assert "bad grammar" in body["rejected"][0]["reason"]


def test_a_rule_colliding_with_an_existing_command_is_rejected(
    running_server: TTSAdapterServer,
) -> None:
    status, body = _put_rules(
        running_server,
        {
            "version": "v1",
            "rules": [{"id": "new_rule", "pattern": "scan left", "category": "always"}],
        },
    )
    assert status == 200
    assert body["accepted"] == []
    assert body["rejected"][0]["id"] == "new_rule"


def test_a_mis_hearing_that_only_reaches_a_legacy_command_keeps_the_rule(
    running_server: TTSAdapterServer,
) -> None:
    """Both CBTM rules were rejected until 2026-11-19: their perturbed
    probes ("light", "repeat turn left") resolve to legacy `point`/`report`,
    which win those mis-hearings with or without the rule. The real legacy
    matcher and the real `flight.lua` patterns."""
    status, body = _put_rules(
        running_server,
        {
            "version": "v1",
            "rules": [
                {"id": "cbtm_align", "pattern": "align", "category": "flight_control"},
                {
                    "id": "cbtm_break",
                    "pattern": "break turn <direction:left|right>",
                    "category": "flight_control",
                },
            ],
        },
    )
    assert status == 200
    assert sorted(body["accepted"]) == ["cbtm_align", "cbtm_break"]
    assert body["rejected"] == []


def test_missing_version_is_a_400(running_server: TTSAdapterServer) -> None:
    status, _body = _put_rules(running_server, {"rules": []})
    assert status == 400


def test_missing_rules_is_a_400(running_server: TTSAdapterServer) -> None:
    status, _body = _put_rules(running_server, {"version": "v1"})
    assert status == 400


def test_a_rule_missing_an_id_is_a_400(running_server: TTSAdapterServer) -> None:
    status, _body = _put_rules(
        running_server,
        {"version": "v1", "rules": [{"pattern": "x", "category": "always"}]},
    )
    assert status == 400


def test_a_rule_missing_a_category_is_a_400(running_server: TTSAdapterServer) -> None:
    """D16/Stage 3b -- `category` is required, same 400 shape as a
    missing `id`/`pattern`."""
    status, _body = _put_rules(
        running_server,
        {"version": "v1", "rules": [{"id": "x", "pattern": "x"}]},
    )
    assert status == 400


def test_a_rule_with_a_non_string_category_is_a_400(
    running_server: TTSAdapterServer,
) -> None:
    status, _body = _put_rules(
        running_server,
        {
            "version": "v1",
            "rules": [{"id": "x", "pattern": "x", "category": 1}],
        },
    )
    assert status == 400


def test_poll_has_no_version_header_before_any_push(
    running_server: TTSAdapterServer,
) -> None:
    headers = _poll_headers(running_server)
    assert "X-Rules-Version" not in headers


def test_poll_carries_the_version_header_after_a_push(
    running_server: TTSAdapterServer,
) -> None:
    _put_rules(running_server, {"version": "v7", "rules": []})
    headers = _poll_headers(running_server)
    assert headers["X-Rules-Version"] == "v7"


def test_pushing_the_same_set_twice_is_harmless(
    running_server: TTSAdapterServer,
) -> None:
    body = {
        "version": "v1",
        "rules": [
            {
                "id": "example_rule",
                "pattern": "xyzzy <direction:left|right> <degrees:angle>",
                "category": "flight_control",
            }
        ],
    }
    status1, response1 = _put_rules(running_server, body)
    status2, response2 = _put_rules(running_server, body)
    assert status1 == status2 == 200
    assert response1 == response2
