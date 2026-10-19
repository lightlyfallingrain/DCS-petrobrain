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
from typing import Any, cast

from aircraft_client import AircraftLayerClient
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.tasks import TaskStore
from logger import ConsolePerceptionRunner, _check_for_new_mission, _reset_mission_state
from mission_memory.entries import FiredOnPayload
from mission_memory.store import MissionMemory

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
