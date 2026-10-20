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


def test_mark_target_writes_immediately_even_while_the_channel_is_busy() -> None:
    """Review `plans/voice-latency-instrumentation/review.md`, Required Fix
    1: the write must never wait on the channel -- only its spoken
    acknowledgement may. `mark_target_fn` is called at command time, at the
    busy channel's own `now_sim`, even though the readback is deferred."""
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
    console.scheduler.busy_until_sim = 100.0

    lines = console.handle_command("mark_target", now_sim=3.0)

    # The write already happened, at the command's own `now_sim` -- not
    # deferred, not waiting on the channel.
    assert calls == [("CONTACT_7", 3.0)]
    # Only the readback is deferred.
    assert lines == []
    assert len(console._pending_positional_replies) == 1

    spoken = console.drain_pending_positional_replies(now_sim=100.0)
    assert spoken == [f"mark 1 set on {task.contact_id}"]
    # Draining re-speaks the already-computed text; it must not call the
    # write again.
    assert calls == [("CONTACT_7", 3.0)]


def test_mark_target_write_survives_refusal_dropping_the_pending_readback() -> None:
    """The exact defect the review found by running it: a pending readback
    dropped by `self.refused` must drop only the spoken echo, never the
    mark write that already happened at command time."""
    tasks = TaskStore()
    tasks.create(
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
    console.scheduler.busy_until_sim = 100.0

    lines = console.handle_command("mark_target", now_sim=3.0)
    assert lines == []
    assert calls == [("CONTACT_7", 3.0)]
    assert len(console._pending_positional_replies) == 1

    console.refused = True
    spoken = console.drain_pending_positional_replies(now_sim=100.0)

    # The pending readback is dropped (refusal mode's established posture,
    # same as every other pending entry) -- but the write itself, which
    # already ran at command time, is untouched: it was never deferred, so
    # there is nothing for refusal to lose.
    assert spoken == []
    assert console._pending_positional_replies == []
    assert calls == [("CONTACT_7", 3.0)]


def test_mark_target_write_survives_a_mission_reset_dropping_the_pending_readback() -> (
    None
):
    """Same defect, reached via a mission (re)start instead of a refusal --
    `reset_for_new_mission` clears `_pending_positional_replies` (it is not
    in that method's "survives" list), but the mark write already happened
    before the reset and is not something the reset can undo."""
    tasks = TaskStore()
    tasks.create(
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
    console.scheduler.busy_until_sim = 100.0

    lines = console.handle_command("mark_target", now_sim=3.0)
    assert lines == []
    assert calls == [("CONTACT_7", 3.0)]
    assert len(console._pending_positional_replies) == 1

    console.reset_for_new_mission()

    assert console._pending_positional_replies == []
    # The write ran before the reset and is unaffected by it.
    assert calls == [("CONTACT_7", 3.0)]
