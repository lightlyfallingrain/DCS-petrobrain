"""Tests for `belief.console` -- `plans/pb2-contact-memory/plan.md` Stage
4's line parser + pretty-printer over `belief.tools`.

Includes the plan's required Stage 4 acceptance test (a scripted console
session over a replayed stream produces the expected transcript) and a
structural check that the module contains no belief logic of its own --
every command dispatches straight into a `belief.tools` function."""

from __future__ import annotations

import ast
import inspect
import pathlib

from belief import console as console_module
from belief import tools as tools_module
from belief.console import Console
from belief.contacts import ContactStore
from belief.decay import LOST_THRESHOLD_S, OBSERVED_WINDOW_S
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *,
    obs_id: str,
    t_sim: float,
    classification_raw: str = "Ural truck",
    bearing_deg: float = 0.0,
    range_m: float = 1000.0,
    source: str = SOURCE_PETROVICH_DETECTION_ASSOCIATED,
) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=source,
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
        range_m=range_m,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
    )


def test_contacts_command_lists_nothing_on_an_empty_store() -> None:
    console = Console(store=ContactStore())
    assert console.handle_line("contacts", now_sim=0.0) == ["no contacts"]


def test_contacts_command_rejects_an_unknown_filter() -> None:
    console = Console(store=ContactStore())
    lines = console.handle_line("contacts bogus", now_sim=0.0)
    assert len(lines) == 1
    assert "unknown filter" in lines[0]


def test_show_command_reports_unknown_id() -> None:
    console = Console(store=ContactStore())
    assert console.handle_line("show CONTACT_999", now_sim=0.0) == [
        "no such contact: CONTACT_999"
    ]


def test_show_command_usage_message_with_no_argument() -> None:
    console = Console(store=ContactStore())
    assert console.handle_line("show", now_sim=0.0) == ["usage: show <id>"]


def test_history_command_usage_message_with_no_argument() -> None:
    console = Console(store=ContactStore())
    assert console.handle_line("history", now_sim=0.0) == ["usage: history <id>"]


def test_find_command_usage_message_with_no_argument() -> None:
    console = Console(store=ContactStore())
    assert console.handle_line("find", now_sim=0.0) == ["usage: find <text>"]


def test_unknown_command_is_reported() -> None:
    console = Console(store=ContactStore())
    assert console.handle_line("bogus", now_sim=0.0) == ["unknown command: bogus"]


def test_blank_line_produces_no_output() -> None:
    console = Console(store=ContactStore())
    assert console.handle_line("   ", now_sim=0.0) == []


def test_scripted_console_session_over_a_replayed_stream() -> None:
    """The plan's required Stage 4 acceptance test: feed a fixed sequence of
    `Observation`s through a `ContactStore`, then run a scripted sequence of
    console commands and check the transcript."""
    store = ContactStore()
    console = Console(store=store)

    # t=0: a truck is first observed.
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="Ural truck")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id

    contacts_output = console.handle_line("contacts", now_sim=0.0)
    assert contacts_output == [
        f"{contact_id}: Ural truck, observed, currently visible."
    ]

    show_output = console.handle_line(f"show {contact_id}", now_sim=0.0)
    assert show_output[0] == contact_id
    assert "  classification: {'value': 'Ural truck'}" in show_output
    assert "  certainty: observed" in show_output
    assert show_output[-1] == "summary: Ural truck, observed, currently visible."

    watch_output = console.handle_line(f"watch {contact_id}", now_sim=0.0)
    assert watch_output == [f"watching {contact_id}"]

    watched_output = console.handle_line("contacts watched", now_sim=0.0)
    assert watched_output == [
        f"{contact_id}: Ural truck, observed, currently visible. Being watched."
    ]

    # t = LOST_THRESHOLD_S + 1: the truck has not been seen again -- it goes
    # lost and CONTACT_LOST is materialised.
    lost_at = LOST_THRESHOLD_S + 1.0
    store.tick(now_sim=lost_at)

    lost_contacts_output = console.handle_line("contacts visible", now_sim=lost_at)
    assert lost_contacts_output == ["no contacts"]

    history_output = console.handle_line(f"history {contact_id}", now_sim=lost_at)
    assert any("sighting source=" in line for line in history_output)
    assert any("kind=CONTACT_DETECTED" in line for line in history_output)
    assert any("kind=CONTACT_LOST" in line for line in history_output)

    find_output = console.handle_line("find ural", now_sim=lost_at)
    assert find_output == [
        f"{contact_id}: Ural truck, lost, last seen {lost_at:.0f}s ago. Being watched."
    ]

    unwatch_output = console.handle_line(f"unwatch {contact_id}", now_sim=lost_at)
    assert unwatch_output == [f"no longer watching {contact_id}"]

    stats_output = console.handle_line("stats", now_sim=lost_at)
    assert stats_output == ["contacts=1 observations=1 events=2"]


def test_console_prints_to_its_configured_output() -> None:
    import io

    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0)],
        now_sim=0.0,
    )
    output = io.StringIO()
    console = Console(store=store, output=output)
    console.handle_line("stats", now_sim=0.0)
    assert output.getvalue() == "contacts=1 observations=1 events=0\n"


def test_visible_filter_excludes_a_contact_past_the_observed_window() -> None:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)
    console = Console(store=store)
    now_sim = OBSERVED_WINDOW_S + 1.0
    assert console.handle_line("contacts visible", now_sim=now_sim) == ["no contacts"]


def test_console_module_contains_no_belief_logic() -> None:
    """Structural check mirroring `test_contacts.
    test_belief_source_never_references_derived_world_position`'s grep
    style: every command handler in `console.py` must be a thin wrapper that
    calls straight into a `belief.tools` function, never reimplementing
    filtering/certainty/decay logic inline.

    Concretely: every name `belief.tools` exports as a public function must
    be referenced somewhere in `console.py`'s source (so each of the six
    commands really does dispatch into `tools.py`), and `console.py` must
    never import from `belief.decay`, `belief.contacts.Certainty`-adjacent
    internals, or anything else that would let it recompute belief state
    itself rather than asking `tools.py`."""
    console_source = inspect.getsource(console_module)

    tool_function_names = [
        name
        for name, obj in vars(tools_module).items()
        if inspect.isfunction(obj)
        and obj.__module__ == tools_module.__name__
        and not name.startswith("_")
    ]
    assert tool_function_names, "expected at least one tool function to check against"
    for name in tool_function_names:
        assert name in console_source, f"console.py never calls belief.tools.{name}"

    # console.py must not import belief.decay/belief.association_over_time
    # directly -- those are tools.py's job to consult, not console.py's.
    tree = ast.parse(console_source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "belief.decay" not in imported_modules
    assert "belief.association_over_time" not in imported_modules


def test_console_module_is_named_console_py() -> None:
    """Sanity check the structural test above is actually inspecting the
    right file."""
    path = pathlib.Path(inspect.getfile(console_module))
    assert path.name == "console.py"
