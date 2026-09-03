"""Tests for `osm.overpass.fetch_bbox`'s caching behavior.

HARD CONSTRAINT (see `plans/m3-osm-overlay/plan.md`): pytest must never make
a network call. `test_fetch_bbox_returns_cached_path_without_network_call`
proves `fetch_bbox` never touches the network on a cache hit by
monkeypatching `urllib.request.urlopen` to raise if called at all.
"""

import urllib.request
from pathlib import Path
from typing import Any, Self

import pytest

from osm.overpass import BBox, fetch_bbox


def _bbox() -> BBox:
    return BBox(south=39.170, west=36.050, north=39.195, east=36.090)


def test_fetch_bbox_returns_cached_path_without_network_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "gemerek_bbox.json"
    cache_path.write_text('{"elements": []}', encoding="utf-8")

    def _fail_if_called(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "fetch_bbox must not touch the network when the cache file already exists"
        )

    monkeypatch.setattr(urllib.request, "urlopen", _fail_if_called)

    result = fetch_bbox(_bbox(), cache_path)

    assert result == cache_path
    assert result.read_text(encoding="utf-8") == '{"elements": []}'


def test_fetch_bbox_writes_cache_and_creates_parent_dirs_on_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "nested" / "gemerek_bbox.json"

    class _FakeResponse:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"elements": []}'

    calls: list[tuple[Any, float]] = []

    def _fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        calls.append((request, timeout))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    result = fetch_bbox(_bbox(), cache_path)

    assert result == cache_path
    assert result.read_text(encoding="utf-8") == '{"elements": []}'
    assert len(calls) == 1
