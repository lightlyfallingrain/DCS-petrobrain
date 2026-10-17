"""`CrewConsole`'s `mark_here`/`mark_target` dispatch -- BL-8 Stage 3,
plan Decision 6. `mark_here_fn`/`mark_target_fn` are plain injected
closures (this console never imports `mission_memory` -- see their own
field docstring), so these tests use fakes rather than a real
`mission_memory.store.MissionMemory`; `tests/test_mission_memory_marks.py`
covers the closures' own real logic."""

from __future__ import annotations

from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.tasks import TaskStore


def test_mark_here_dispatches_to_the_injected_closure() -> None:
    calls: list[float] = []

    def fake_mark_here(now_sim: float) -> str:
        calls.append(now_sim)
        return "mark 1 set"

    console = CrewConsole(store=ContactStore(), mark_here_fn=fake_mark_here)
    lines = console.handle_command("mark_here", now_sim=5.0)
    assert lines == ["mark 1 set"]
    assert calls == [5.0]


def test_mark_here_without_a_closure_reports_not_configured() -> None:
    console = CrewConsole(store=ContactStore())
    lines = console.handle_command("mark_here", now_sim=0.0)
    assert lines == ["no mission memory configured"]


def test_mark_target_dispatches_with_the_selected_target() -> None:
    tasks = TaskStore()
    task = tasks.create(
        kind="attack_target",
        area=None,
        created_sim=0.0,
        deadline_sim=1e9,
        reason="test",
        contact_id="CONTACT_7",
    )
    calls: list[tuple[str, float]] = []

    def fake_mark_target(contact_id: str, now_sim: float) -> str:
        calls.append((contact_id, now_sim))
        return f"mark 1 set on {contact_id}"

    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        mark_target_fn=fake_mark_target,
    )
    lines = console.handle_command("mark_target", now_sim=3.0)
    assert lines == [f"mark 1 set on {task.contact_id}"]
    assert calls == [("CONTACT_7", 3.0)]


def test_mark_target_with_nothing_selected_fails_the_usual_way() -> None:
    """The exact wording `_handle_step` already uses for the same missing
    input -- not a bespoke message for this command."""
    console = CrewConsole(
        store=ContactStore(),
        tasks=TaskStore(),
        mark_target_fn=lambda contact_id, now_sim: "unreachable",
    )
    lines = console.handle_command("mark_target", now_sim=0.0)
    assert lines == ["no target selected"]


def test_mark_target_without_a_closure_reports_not_configured() -> None:
    tasks = TaskStore()
    tasks.create(
        kind="attack_target",
        area=None,
        created_sim=0.0,
        deadline_sim=1e9,
        reason="test",
        contact_id="CONTACT_7",
    )
    console = CrewConsole(store=ContactStore(), tasks=tasks)
    lines = console.handle_command("mark_target", now_sim=0.0)
    assert lines == ["no mission memory configured"]
