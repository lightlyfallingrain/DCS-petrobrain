"""Testing aid (2026-11-28): "launch" presses Fire Shturm (6/3036) then
releases it, on a background thread, and always releases even when the
press write fails."""

from __future__ import annotations

import threading
from typing import cast

import pytest

import belief.crew_console as crew_console_module
from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole


class _FakeClient:
    def __init__(self, fail_press: bool = False) -> None:
        self.writes: list[tuple[int, int, float]] = []
        self.released = threading.Event()
        self._fail_press = fail_press

    def write_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
        self.writes.append((device, cmd, value))
        if value == 0.0:
            self.released.set()
        elif self._fail_press:
            raise AircraftLayerError("boom")


def _console(client: _FakeClient) -> CrewConsole:
    return CrewConsole(
        store=ContactStore(), aircraft_client=cast(AircraftLayerClient, client)
    )


def test_launch_presses_then_releases_fire_shturm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(crew_console_module, "_LAUNCH_PRESS_S", 0.0)
    client = _FakeClient()

    assert _console(client).handle_command("launch", now_sim=0.0) == ["Launching."]

    assert client.released.wait(2.0)
    assert client.writes == [(6, 3036, 1.0), (6, 3036, 0.0)]


def test_launch_releases_even_when_the_press_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(crew_console_module, "_LAUNCH_PRESS_S", 0.0)
    client = _FakeClient(fail_press=True)

    _console(client).handle_command("launch", now_sim=0.0)

    assert client.released.wait(2.0)
    assert client.writes == [(6, 3036, 1.0), (6, 3036, 0.0)]


def test_launch_without_aircraft_link_is_unable() -> None:
    console = CrewConsole(store=ContactStore())

    assert console.handle_command("launch", now_sim=0.0) == [
        "Unable, no aircraft link."
    ]
