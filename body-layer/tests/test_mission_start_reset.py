"""Per-class completeness tests for `reset_for_new_mission()` --
`plans/bl15-mission-start/plan.md` (BL-15 Stage 1).

**This is the test that would have caught `BL-B68`'s own gap** (clearing
`store` but not `attack_run_state`): rather than hand-listing which fields
a reset must clear and asserting each one individually (a list that can
silently fall out of sync with a class's own field declarations the moment
someone adds a new one), every test here enumerates the class's *actual*
fields at test time (`dataclasses.fields()` for the two dataclasses,
`vars()` for the three plain classes) and asserts that every field not
named in that class's documented preserve-set equals the value a fresh
constructor call would give it. A field added later and not threaded
through a preserve-set update fails this test immediately, rather than
surviving a mission restart unnoticed.

The orchestration tests at the bottom (`_reset_mission_state`/`_check_for_
new_mission`) are unit tests against `logger`'s private functions directly
-- the wiring-level proof that the real poll loops actually reach them is
`test_logger.py::test_crew_text_poll_loop_resets_belief_on_mission_restart`.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest

from aircraft_client import AircraftLayerClient
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.tasks import TaskStore
from logger import (
    ConsolePerceptionRunner,
    _check_for_new_mission,
    _enter_refusal_mode,
    _maybe_switch_theatre,
    _reset_mission_state,
)
from mission_memory.entries import FiredOnPayload
from mission_memory.store import MissionMemory
from store.models import Region
from store.writer import insert_region, open_for_build

#: A single, distinguishable sentinel used to poison every field under
#: test -- the field's own type is irrelevant here (nothing is read back
#: except by `==` against a fresh default), only "did `reset_for_new_
#: mission()` actually overwrite this field" is being asked.
_SENTINEL = object()


def _poison(instance: object, field_names: set[str], preserve: set[str]) -> None:
    for name in field_names:
        if name in preserve:
            continue
        setattr(instance, name, _SENTINEL)


def _assert_value_matches_fresh_default(
    name: str, actual: object, fresh: object
) -> None:
    """`==` for ordinary values; falls back to comparing `vars()` one level
    deep for a plain object with no `__eq__` of its own (`belief.groups.
    GroupStore`, the one such field in this module's scope) -- two freshly
    constructed instances of such a class are never `==` under Python's
    default identity equality, even though their own state is identical."""
    if (
        hasattr(actual, "__dict__")
        and hasattr(fresh, "__dict__")
        and type(actual).__eq__ is object.__eq__
    ):
        assert vars(actual) == vars(fresh), (
            f"field {name!r} did not reset to its constructor default: "
            f"{vars(actual)!r} != {vars(fresh)!r}"
        )
        return
    assert actual == fresh, (
        f"field {name!r} did not reset to its constructor default: "
        f"{actual!r} != {fresh!r}"
    )


# --- ContactStore / TaskStore -- plain classes, enumerated via vars() -------


def test_contact_store_reset_clears_every_field() -> None:
    store = ContactStore()
    field_names = set(vars(store))
    _poison(store, field_names, preserve=set())

    store.reset_for_new_mission()

    fresh = ContactStore()
    for name in field_names:
        _assert_value_matches_fresh_default(
            name, getattr(store, name), getattr(fresh, name)
        )


def test_task_store_reset_clears_every_field() -> None:
    store = TaskStore()
    field_names = set(vars(store))
    _poison(store, field_names, preserve=set())

    store.reset_for_new_mission()

    fresh = TaskStore()
    for name in field_names:
        _assert_value_matches_fresh_default(
            name, getattr(store, name), getattr(fresh, name)
        )


# --- ConsolePerceptionRunner -- a dataclass, enumerated via dataclasses.fields --

#: `ConsolePerceptionRunner.reset_for_new_mission`'s own documented
#: preserve-set (its docstring and `plans/bl15-mission-start/plan.md`'s
#: "reset mechanism" section are the two other places this list is
#: written down -- kept in sync by hand, same as every preserve-set in
#: this codebase).
_RUNNER_PRESERVE = {
    "aircraft_client",
    "sources",
    "store",
    "tasks",
    "output",
    "overlay_client",
    "group_trace_sink",
    "world_model_conn",
    "theatre",
}


def test_console_perception_runner_reset_preserves_declared_fields_and_resets_rest() -> (
    None
):
    fake_client = cast(AircraftLayerClient, object())
    runner = ConsolePerceptionRunner(aircraft_client=fake_client)
    field_names = {f.name for f in dataclasses.fields(runner)}
    assert _RUNNER_PRESERVE <= field_names, (
        "the preserve-set names a field ConsolePerceptionRunner no longer has"
    )

    preserved_values = {name: getattr(runner, name) for name in _RUNNER_PRESERVE}
    _poison(runner, field_names, preserve=_RUNNER_PRESERVE)

    runner.reset_for_new_mission()

    # The preserved fields must be the exact objects they were before --
    # object identity, not merely equality (`store`/`tasks` in particular:
    # `_reset_mission_state`'s own docstring on why this must be the same
    # `ContactStore`/`TaskStore` instance, not an equal-but-different one).
    for name in _RUNNER_PRESERVE:
        assert getattr(runner, name) is preserved_values[name], (
            f"preserved field {name!r} was replaced, not passed through"
        )

    fresh = ConsolePerceptionRunner(**preserved_values)
    for name in field_names - _RUNNER_PRESERVE:
        _assert_value_matches_fresh_default(
            name, getattr(runner, name), getattr(fresh, name)
        )


# --- CrewConsole -- a dataclass, enumerated via dataclasses.fields ----------

#: `CrewConsole.reset_for_new_mission`'s own documented preserve-set.
_CREW_CONSOLE_PRESERVE = {
    "store",
    "tasks",
    "brain_client",
    "output",
    "aircraft_client",
    "mark_here_fn",
    "mark_target_fn",
    "transcript_log",
    "overlay_client",
    "speech_client",
    "speech_log_sink",
    "silenced",
}


def test_crew_console_reset_preserves_declared_fields_and_resets_rest() -> None:
    store = ContactStore()
    crew_console = CrewConsole(store=store, silenced=True)
    field_names = {f.name for f in dataclasses.fields(crew_console)}
    assert _CREW_CONSOLE_PRESERVE <= field_names, (
        "the preserve-set names a field CrewConsole no longer has"
    )

    preserved_values = {
        name: getattr(crew_console, name) for name in _CREW_CONSOLE_PRESERVE
    }
    _poison(crew_console, field_names, preserve=_CREW_CONSOLE_PRESERVE)

    crew_console.reset_for_new_mission()

    for name in _CREW_CONSOLE_PRESERVE:
        assert getattr(crew_console, name) is preserved_values[name] or (
            # `silenced` is a plain bool -- `is` would reject an equal-but-
            # reconstructed `True`/`False` on some interpreters' small-int/
            # bool caching quirks, so this one preserved field is compared
            # by value, every other preserved field by identity.
            name == "silenced" and getattr(crew_console, name) == preserved_values[name]
        ), f"preserved field {name!r} was replaced, not passed through"

    fresh = CrewConsole(**preserved_values)
    for name in field_names - _CREW_CONSOLE_PRESERVE:
        _assert_value_matches_fresh_default(
            name, getattr(crew_console, name), getattr(fresh, name)
        )


def test_crew_console_reset_preserves_silenced_true() -> None:
    """A pilot's deliberate mute survives a mission restart -- the plan's
    stated conservative default, pending the user's own call (see the
    plan's "Decisions Requiring User Input")."""
    crew_console = CrewConsole(store=ContactStore(), silenced=True)

    crew_console.reset_for_new_mission()

    assert crew_console.silenced is True


# --- _reset_mission_state / _check_for_new_mission (logger.py) -------------


class _FakeMissionStartClient:
    def __init__(self) -> None:
        self.event: dict[str, Any] | None = None

    def get_mission_start_latest(self) -> dict[str, Any] | None:
        return self.event


def test_check_for_new_mission_does_nothing_on_first_poll_even_with_sequence_present() -> (
    None
):
    """The very first poll of a process must never reset, even if the
    collector already holds a mission-start event from before body-layer
    connected -- the plan's explicit design (see "Decisions Requiring User
    Input")."""
    client = _FakeMissionStartClient()
    client.event = {"sequence": 5, "theatre": None, "received_wall_clock_s": 0.0}
    runner = ConsolePerceptionRunner(
        aircraft_client=cast(AircraftLayerClient, object())
    )
    assert runner.last_mission_start_sequence is None

    reset_happened = _check_for_new_mission(
        runner, None, MissionMemory(), cast(AircraftLayerClient, client)
    )

    assert reset_happened is False
    assert runner.last_mission_start_sequence == 5


def test_check_for_new_mission_resets_on_sequence_change() -> None:
    client = _FakeMissionStartClient()
    runner = ConsolePerceptionRunner(
        aircraft_client=cast(AircraftLayerClient, object())
    )
    runner.last_mission_start_sequence = 1  # already past the first poll
    runner.tasks.create(
        "scan_area",
        None,
        created_sim=0.0,
        deadline_sim=100.0,
        reason="test",
    )
    assert runner.tasks.tasks

    client.event = {"sequence": 2, "theatre": None, "received_wall_clock_s": 0.0}
    reset_happened = _check_for_new_mission(
        runner, None, MissionMemory(), cast(AircraftLayerClient, client)
    )

    assert reset_happened is True
    assert runner.last_mission_start_sequence == 2
    assert runner.tasks.tasks == []


def test_check_for_new_mission_is_a_no_op_when_sequence_unchanged() -> None:
    client = _FakeMissionStartClient()
    runner = ConsolePerceptionRunner(
        aircraft_client=cast(AircraftLayerClient, object())
    )
    runner.last_mission_start_sequence = 3
    runner.tasks.create(
        "scan_area",
        None,
        created_sim=0.0,
        deadline_sim=100.0,
        reason="test",
    )

    client.event = {"sequence": 3, "theatre": None, "received_wall_clock_s": 0.0}
    reset_happened = _check_for_new_mission(
        runner, None, MissionMemory(), cast(AircraftLayerClient, client)
    )

    assert reset_happened is False
    assert runner.tasks.tasks  # not cleared -- no restart was detected


def test_check_for_new_mission_is_a_no_op_when_cache_is_empty() -> None:
    client = _FakeMissionStartClient()
    runner = ConsolePerceptionRunner(
        aircraft_client=cast(AircraftLayerClient, object())
    )
    runner.last_mission_start_sequence = 1

    reset_happened = _check_for_new_mission(
        runner, None, MissionMemory(), cast(AircraftLayerClient, client)
    )

    assert reset_happened is False
    assert runner.last_mission_start_sequence == 1


def test_reset_mission_state_resets_store_tasks_sources_and_mission_memory() -> None:
    runner = ConsolePerceptionRunner(
        aircraft_client=cast(AircraftLayerClient, object())
    )
    runner.tasks.create(
        "scan_area",
        None,
        created_sim=0.0,
        deadline_sim=100.0,
        reason="test",
    )
    mission_memory = MissionMemory()
    mission_memory.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=FiredOnPayload(
            shooter_seq=None, shooter_ref="CONTACT_1", targets_ownship=True
        ),
    )

    _reset_mission_state(runner, None, mission_memory)

    assert runner.tasks.tasks == []
    assert mission_memory.entries == []


# --- BL-15 Stage 3: theatre switching (`_maybe_switch_theatre`) and loud- --
# refusal mode (`_enter_refusal_mode`) -- `plans/bl15-mission-start/plan.md`
# Stage 3, revised by `stage1-decisions.md` decision 1. -----------------------


def _build_region_store(path: Path, theatre: str) -> None:
    """A minimal on-disk world-model store whose embedded `Region.theatre`
    is `theatre` -- mirrors `test_logger.py`'s own
    `test_main_rejects_world_model_db_theatre_mismatch` fixture pattern."""
    conn = open_for_build(path)
    insert_region(
        conn,
        Region(
            name=f"{theatre.lower()}-full",
            theatre=theatre,
            centre_x=0.0,
            centre_z=0.0,
            half_extent_x_m=1000.0,
            half_extent_z_m=1000.0,
            built_at="2026-10-19T00:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()


def _runner_on(path: Path, theatre: str) -> ConsolePerceptionRunner:
    from perception.geometry import open_world_model

    return ConsolePerceptionRunner(
        aircraft_client=cast(AircraftLayerClient, object()),
        world_model_conn=open_world_model(path),
        theatre=theatre,
    )


def test_maybe_switch_theatre_is_a_noop_when_event_theatre_is_none() -> None:
    """A `None` theatre (Hook could not read `env.mission.theatre`) is not
    evidence of a mismatch -- keep the current store, per decision: "I used
    the initial silence mode as proxy ... did not touch this point"."""
    runner = ConsolePerceptionRunner(
        aircraft_client=cast(AircraftLayerClient, object()), theatre="Syria"
    )
    runner.sources = ["sentinel"]  # type: ignore[list-item]

    _maybe_switch_theatre(
        runner, None, None, None, trace_sink=None, forest_occlusion=False
    )

    assert runner.theatre == "Syria"
    assert runner.sources == ["sentinel"]


def test_maybe_switch_theatre_is_a_noop_when_theatre_unchanged(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "syria-full.sqlite"
    _build_region_store(db_path, "Syria")
    runner = _runner_on(db_path, "Syria")
    original_conn = runner.world_model_conn
    runner.sources = ["sentinel"]  # type: ignore[list-item]

    _maybe_switch_theatre(
        runner, None, "Syria", tmp_path, trace_sink=None, forest_occlusion=False
    )

    assert runner.world_model_conn is original_conn
    assert runner.sources == ["sentinel"]


def test_maybe_switch_theatre_enters_refusal_mode_when_world_model_dir_is_none(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "syria-full.sqlite"
    _build_region_store(db_path, "Syria")
    runner = _runner_on(db_path, "Syria")
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)

    _maybe_switch_theatre(
        runner,
        crew_console,
        "Afghanistan",
        None,
        trace_sink=None,
        forest_occlusion=False,
    )

    assert runner.world_model_conn is None
    assert runner.sources == []
    assert crew_console.refused is True
    # `theatre` itself is left as the old value -- there is no new one to
    # switch to, only a store to drop.
    assert runner.theatre == "Syria"


def test_maybe_switch_theatre_enters_refusal_mode_for_unknown_theatre(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "syria-full.sqlite"
    _build_region_store(db_path, "Syria")
    runner = _runner_on(db_path, "Syria")
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)

    _maybe_switch_theatre(
        runner,
        crew_console,
        "Narnia",
        tmp_path,
        trace_sink=None,
        forest_occlusion=False,
    )

    assert runner.world_model_conn is None
    assert runner.sources == []
    assert crew_console.refused is True


def test_maybe_switch_theatre_enters_refusal_mode_when_store_not_built(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "syria-full.sqlite"
    _build_region_store(db_path, "Syria")
    runner = _runner_on(db_path, "Syria")
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)
    # `tmp_path` has no `afghanistan-full.sqlite` at all.

    _maybe_switch_theatre(
        runner,
        crew_console,
        "Afghanistan",
        tmp_path,
        trace_sink=None,
        forest_occlusion=False,
    )

    assert runner.world_model_conn is None
    assert runner.sources == []
    assert crew_console.refused is True


def test_maybe_switch_theatre_enters_refusal_mode_on_region_mismatch(
    tmp_path: Path,
) -> None:
    """A store at the name the mission's theatre resolves to, but whose
    own embedded `Region.theatre` disagrees -- the same guard `main()`'s
    own startup path already runs, exercised here at runtime instead."""
    db_path = tmp_path / "syria-full.sqlite"
    _build_region_store(db_path, "Syria")
    runner = _runner_on(db_path, "Syria")
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)
    # Named for Afghanistan, but built for Syria -- a mismatch the
    # filename alone cannot catch.
    mismatched_path = tmp_path / "afghanistan-full.sqlite"
    _build_region_store(mismatched_path, "Syria")

    _maybe_switch_theatre(
        runner,
        crew_console,
        "Afghanistan",
        tmp_path,
        trace_sink=None,
        forest_occlusion=False,
    )

    assert runner.world_model_conn is None
    assert runner.sources == []
    assert crew_console.refused is True


def test_maybe_switch_theatre_succeeds_rebuilds_sources_and_clears_refusal(
    tmp_path: Path,
) -> None:
    syria_path = tmp_path / "syria-full.sqlite"
    afghanistan_path = tmp_path / "afghanistan-full.sqlite"
    _build_region_store(syria_path, "Syria")
    _build_region_store(afghanistan_path, "Afghanistan")
    runner = _runner_on(syria_path, "Syria")
    old_conn = runner.world_model_conn
    runner.enrichment = object()  # type: ignore[assignment]  # sentinel -- must be cleared
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)
    crew_console.refused = True  # simulate recovering from an earlier failure

    _maybe_switch_theatre(
        runner,
        crew_console,
        "Afghanistan",
        tmp_path,
        trace_sink=None,
        forest_occlusion=False,
    )

    assert runner.theatre == "Afghanistan"
    assert runner.world_model_conn is not None
    assert runner.world_model_conn is not old_conn
    assert (
        len(runner.sources) == 2
    )  # Hybrid + NakedEye, same as _build_sources always builds
    assert runner.enrichment is None
    assert crew_console.refused is False
    # The old connection was closed, not merely abandoned.
    with pytest.raises(sqlite3.ProgrammingError):
        old_conn.execute("SELECT 1")


def test_enter_refusal_mode_closes_the_open_connection() -> None:
    """`_enter_refusal_mode` itself (not just `_maybe_switch_theatre`'s use
    of it) -- a store for the wrong theatre is dropped, not retained."""
    runner = ConsolePerceptionRunner(
        aircraft_client=cast(AircraftLayerClient, object())
    )
    runner.world_model_conn = cast(Any, _FakeClosableConnection())
    runner.sources = ["sentinel"]  # type: ignore[list-item]
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)

    _enter_refusal_mode(runner, crew_console)

    assert runner.world_model_conn is None
    assert runner.sources == []
    assert crew_console.refused is True


class _FakeClosableConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_enter_refusal_mode_is_a_true_no_op_for_console_mode() -> None:
    """`crew_console is None` (the `--console` debug path) -- no production
    command surface to refuse on; this call must not raise."""
    runner = ConsolePerceptionRunner(
        aircraft_client=cast(AircraftLayerClient, object())
    )

    _enter_refusal_mode(runner, None)  # must not raise

    assert runner.world_model_conn is None
    assert runner.sources == []


def test_check_for_new_mission_switches_theatre_end_to_end(tmp_path: Path) -> None:
    """Wiring-level proof that `_check_for_new_mission` itself (not just
    `_maybe_switch_theatre` called directly) performs the switch when a
    mission (re)start's event carries a new theatre and `world_model_dir`
    is supplied."""
    syria_path = tmp_path / "syria-full.sqlite"
    afghanistan_path = tmp_path / "afghanistan-full.sqlite"
    _build_region_store(syria_path, "Syria")
    _build_region_store(afghanistan_path, "Afghanistan")
    runner = _runner_on(syria_path, "Syria")
    runner.last_mission_start_sequence = 1
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)
    client = _FakeMissionStartClient()
    client.event = {
        "sequence": 2,
        "theatre": "Afghanistan",
        "received_wall_clock_s": 0.0,
    }

    reset_happened = _check_for_new_mission(
        runner,
        crew_console,
        MissionMemory(),
        cast(AircraftLayerClient, client),
        world_model_dir=tmp_path,
    )

    assert reset_happened is True
    assert runner.theatre == "Afghanistan"
    assert crew_console.refused is False


def test_check_for_new_mission_refuses_when_new_theatre_has_no_store(
    tmp_path: Path,
) -> None:
    syria_path = tmp_path / "syria-full.sqlite"
    _build_region_store(syria_path, "Syria")
    runner = _runner_on(syria_path, "Syria")
    runner.last_mission_start_sequence = 1
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)
    client = _FakeMissionStartClient()
    client.event = {
        "sequence": 2,
        "theatre": "Afghanistan",
        "received_wall_clock_s": 0.0,
    }

    reset_happened = _check_for_new_mission(
        runner,
        crew_console,
        MissionMemory(),
        cast(AircraftLayerClient, client),
        world_model_dir=tmp_path,  # no afghanistan-full.sqlite present
    )

    assert reset_happened is True  # the belief reset still happened
    assert crew_console.refused is True
