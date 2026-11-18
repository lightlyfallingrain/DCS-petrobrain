"""The whole `[[BL-17]]` D20 chain, end to end, through the real sandbox
(`plans/speech-rules/plan.md` Stage 3d's own test item 4's last
sentence): a Lua call to `effector.write` -> the validated `rules.
actions` wrapper -> `ActionContext.request_effector_write`'s closure ->
`belief.effector_engine.request_write` -> an `EffectorRunState.ad_hoc_
runs` entry -> `advance` -> `EffectorRunState.spoken` -> `CrewConsole.
drain_effector_speech`. No sequence file, no shipped rule, no real
aircraft -- a small synthetic test-only rule file, never shipped
(`config/rules/` is untouched by this test)."""

from __future__ import annotations

import io
import re
import threading
from pathlib import Path
from typing import cast

import body as body_module
from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.contacts import ContactStore
from belief.crew_console import (
    ACTION_FILE_ERROR_LINE,
    CrewConsole,
    PendingEffectorWrite,
)
from belief.effector_engine import EffectorRunState, advance, request_write
from belief.effector_registry import EffectorDef
from rules.actions import ACTION_NAMESPACES, ActionContext
from rules.engine import RuleSet, run_rule
from rules.sandbox import RuleSandbox

_SRC = Path(__file__).resolve().parent.parent / "src"

_OBSERV = EffectorDef(
    name="observ",
    source_element="OBSERVE-PTR",
    device=7,
    cmd=3002,
    arg=886,
    values={"on": 1.0, "off": 0.0},
    shape="default_2_position_tumb",
)
_REGISTRY = {"observ": _OBSERV}


class _FakeAircraftClient:
    def __init__(self, read_values: dict[int, float]) -> None:
        self.writes: list[tuple[int, int, float]] = []
        self.read_values = read_values

    def write_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
        self.writes.append((device, cmd, value))

    def read_args(self, args: list[int]) -> dict[str, float]:
        return {str(a): self.read_values[a] for a in args if a in self.read_values}


def _client(fake: _FakeAircraftClient) -> AircraftLayerClient:
    return cast(AircraftLayerClient, fake)


def test_effector_write_rule_runs_end_to_end_through_the_real_sandbox(
    tmp_path: Path,
) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_observ_on", "x", "always", function(s)\n'
        '  effector.write("observ", "on", "Observ on.")\n'
        "end)\n",
        encoding="utf-8",
    )

    # `body.py`'s own closure shape, but against a plain local variable
    # rather than a `ConsolePerceptionRunner`'s field -- the whole point
    # of injecting the closure (D4/D5) is that `rules.actions`/`rules.
    # engine` never need to know what holds the real state.
    engine_state = EffectorRunState()

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        nonlocal engine_state
        effector_def = _REGISTRY.get(name)
        if effector_def is None or value not in effector_def.values:
            return {"ok": False, "reason": "UNKNOWN_EFFECTOR"}
        engine_state = request_write(engine_state, "req-1", name, value, says, 0.0)
        return {"ok": True, "reason": None}

    console = CrewConsole(store=ContactStore())
    console.output = io.StringIO()
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)
    assert rule_set.failures == ()

    # 1. The Lua call -> the validated action -> the ad hoc run is
    # enqueued. Silent on dispatch (D20's own "queued" convention).
    outcome = run_rule(rule_set, "probe_observ_on", None, sandbox)
    assert outcome.lines == []
    assert outcome.error is False
    assert set(engine_state.ad_hoc_runs) == {"req-1"}

    # 2. `advance` processes the ad hoc run -- a real write, since the
    # fake client reports "observ" currently off.
    client = _FakeAircraftClient(read_values={886: 0.0})
    engine_state = advance(engine_state, 0.0, _client(client), {}, _REGISTRY)
    assert client.writes == [(7, 3002, 1.0)]
    assert engine_state.spoken == ("Observ on.",)
    assert engine_state.ad_hoc_runs == {}

    # 3. `CrewConsole.drain_effector_speech` -- the same drain `body.py`
    # calls once per poll, unconditionally.
    console.drain_effector_speech(0.0, engine_state.spoken)
    assert console.output.getvalue() == "Observ on.\n"


def test_effector_write_rule_unknown_effector_never_reaches_the_engine(
    tmp_path: Path,
) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_bad", "x", "always", function(s)\n'
        '  effector.write("no_such_effector", "on", "Hi.")\n'
        "end)\n",
        encoding="utf-8",
    )
    engine_state = EffectorRunState()

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        effector_def = _REGISTRY.get(name)
        if effector_def is None or value not in effector_def.values:
            return {"ok": False, "reason": "UNKNOWN_EFFECTOR"}
        raise AssertionError("must not reach the engine for an unknown effector")

    console = CrewConsole(store=ContactStore())
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)
    assert rule_set.failures == ()

    outcome = run_rule(rule_set, "probe_bad", None, sandbox)
    assert outcome.lines == ["Unable."]
    assert outcome.error is False
    assert engine_state.ad_hoc_runs == {}


def test_effector_write_rule_illegal_value_never_reaches_the_engine(
    tmp_path: Path,
) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_bad_value", "x", "always", function(s)\n'
        '  effector.write("observ", "sideways", "Hi.")\n'
        "end)\n",
        encoding="utf-8",
    )
    engine_state = EffectorRunState()

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        effector_def = _REGISTRY.get(name)
        if effector_def is None or value not in effector_def.values:
            return {"ok": False, "reason": "UNKNOWN_EFFECTOR"}
        raise AssertionError("must not reach the engine for an illegal value")

    console = CrewConsole(store=ContactStore())
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)

    outcome = run_rule(rule_set, "probe_bad_value", None, sandbox)
    assert outcome.lines == ["Unable."]
    assert engine_state.ad_hoc_runs == {}


def test_effector_write_says_is_optional(tmp_path: Path) -> None:
    """Lua may omit the trailing `says` argument entirely (D20: it is
    optional, free-text) -- the action still validates and enqueues."""
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_no_says", "x", "always", function(s)\n'
        '  effector.write("observ", "on")\n'
        "end)\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, str, str | None]] = []

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        calls.append((name, value, says))
        return {"ok": True, "reason": None}

    console = CrewConsole(store=ContactStore())
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)

    outcome = run_rule(rule_set, "probe_no_says", None, sandbox)
    assert outcome.lines == []
    assert calls == [("observ", "on", None)]


def test_effector_write_says_explicit_nil_is_also_optional(tmp_path: Path) -> None:
    """Distinct from the omitted-argument case above -- an explicit Lua
    `nil` as the third argument (`feedback_lua_native_function_optional_
    trailing_arg.md`'s own pattern: write both, never assume one implies
    the other) must resolve the same way as omitting it entirely."""
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_explicit_nil_says", "x", "always", function(s)\n'
        '  effector.write("observ", "on", nil)\n'
        "end)\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, str, str | None]] = []

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        calls.append((name, value, says))
        return {"ok": True, "reason": None}

    console = CrewConsole(store=ContactStore())
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)
    assert rule_set.failures == ()

    outcome = run_rule(rule_set, "probe_explicit_nil_says", None, sandbox)
    assert outcome.lines == []
    assert calls == [("observ", "on", None)]


def test_effector_write_queued_from_background_thread_is_applied_on_next_poll_drain(
    tmp_path: Path,
) -> None:
    """Stage 3d review fix 1 (`plans/speech-rules/review-stage3d.md`
    Required Fix 1) -- `body.py`'s real closure only validates and
    appends a `PendingEffectorWrite` to `CrewConsole.pending_effector_
    writes`; it never touches an `EffectorRunState` itself. Dispatching
    the rule from a background thread (standing in for the REPL thread
    `handle_command` is also reachable from, concurrently with the poll
    thread's own voice dispatch) proves the enqueue step cannot race the
    poll thread's `EffectorRunState` reads/writes, because it never
    reaches one -- only the simulated poll-loop drain below, run on
    *this* thread, ever calls `request_write`."""
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_observ_on", "x", "always", function(s)\n'
        '  effector.write("observ", "on", "Observ on.")\n'
        "end)\n",
        encoding="utf-8",
    )
    console = CrewConsole(store=ContactStore())

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        # Mirrors `body.py`'s real closure post-fix: validate, then
        # queue -- never touch any `EffectorRunState`.
        effector_def = _REGISTRY.get(name)
        if effector_def is None or value not in effector_def.values:
            return {"ok": False, "reason": "UNKNOWN_EFFECTOR"}
        console.queue_effector_write("req-1", name, value, says)
        return {"ok": True, "reason": None}

    sandbox = RuleSandbox()
    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)
    assert rule_set.failures == ()

    thread = threading.Thread(
        target=lambda: run_rule(rule_set, "probe_observ_on", None, sandbox)
    )
    thread.start()
    thread.join()

    # Queued by the "REPL" thread; nothing applied yet, and no
    # `EffectorRunState` was ever touched by the dispatch itself.
    assert len(console.pending_effector_writes) == 1
    queued = console.pending_effector_writes[0]
    assert (queued.effector, queued.value, queued.says) == (
        "observ",
        "on",
        "Observ on.",
    )

    # The "poll thread"'s own drain (`body.py`'s poll loop, same shape)
    # -- only now does the request actually reach the engine.
    pending, console.pending_effector_writes = console.pending_effector_writes, []
    engine_state = EffectorRunState()
    for request in pending:
        engine_state = request_write(
            engine_state,
            request.request_id,
            request.effector,
            request.value,
            request.says,
            0.0,
        )
    assert set(engine_state.ad_hoc_runs) == {"req-1"}
    assert console.pending_effector_writes == []


def test_a_write_that_never_gets_a_readback_is_silently_retried(
    tmp_path: Path,
) -> None:
    """D20/U24's own inherited posture, exercised end to end: a write
    that keeps failing (here, `write_cockpit_switch` always raising)
    never speaks and is retried indefinitely -- never "Action file
    error.", since the dispatch itself already returned cleanly."""
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_observ_on", "x", "always", function(s)\n'
        '  effector.write("observ", "on", "Observ on.")\n'
        "end)\n",
        encoding="utf-8",
    )
    engine_state = EffectorRunState()

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        nonlocal engine_state
        engine_state = request_write(engine_state, "req-1", name, value, says, 0.0)
        return {"ok": True, "reason": None}

    class _AlwaysFailsClient:
        def write_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
            raise AircraftLayerError("simulated")

        def read_args(self, args: list[int]) -> dict[str, float]:
            return {"886": 0.0}

    console = CrewConsole(store=ContactStore())
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)

    outcome = run_rule(rule_set, "probe_observ_on", None, sandbox)
    assert outcome.lines == []

    client = cast(AircraftLayerClient, _AlwaysFailsClient())
    engine_state = advance(engine_state, 0.0, client, {}, _REGISTRY)
    assert engine_state.spoken == ()
    assert engine_state.ad_hoc_runs["req-1"].status == "failed_write"


def test_a_write_then_a_later_error_in_the_same_dispatch_is_rolled_back(
    tmp_path: Path,
) -> None:
    """Stage 3d re-review Required Fix 4 (`plans/speech-rules/
    review-stage3d.md`), test (1), the basic case: a rule that calls
    `effector.write` and then raises later in the *same* dispatch must
    never have that write reach `pending_effector_writes` at all -- the
    switch must never move, and no confirmation must ever be spoken, for
    an action whose own dispatch just reported "Action file error."
    Round 2 (buffer-then-commit) makes this a non-event rather than a
    rollback: the write sits in `_dispatch_rule`'s own thread-local
    buffer the whole time and the buffer is simply discarded on error,
    so the shared list this test checks was never touched in the first
    place. Dispatched through the real `handle_command`/`_dispatch_rule`
    path, not `run_rule` directly, since the gate/category/buffer
    plumbing this is testing only exists on that path."""
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_write_then_error", "x", "always", function(s)\n'
        '  effector.write("observ", "on", "Observ on.")\n'
        '  digits("not_a_number")\n'
        "end)\n",
        encoding="utf-8",
    )
    console = CrewConsole(store=ContactStore())
    sandbox = RuleSandbox()

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        console.queue_effector_write("req-1", name, value, says)
        return {"ok": True, "reason": None}

    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)
    assert rule_set.failures == ()

    def rule_runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = rule_runner
    console.set_enabled_rule_ids(frozenset({"probe_write_then_error"}))

    lines = console.handle_command("probe_write_then_error", 0.0)

    assert lines == [ACTION_FILE_ERROR_LINE]
    assert console.pending_effector_writes == []


def test_concurrent_dispatches_do_not_lose_each_others_queued_writes(
    tmp_path: Path,
) -> None:
    """Stage 3d re-review Required Fix 4, round 2, test (2): two
    dispatches running concurrently on independent threads must not
    interfere with each other's writes, in either direction -- rule A's
    own write must stay invisible to the shared list while A is still
    open (nothing for a concurrent drain to see), and rule B's own
    write, committed while A is still paused, must survive untouched
    once A later errors and discards its own buffer. Round 1's version
    of this test asserted both entries were visible on the shared list
    *while A was still open* (the point being that a length-based
    truncate would wrongly discard B's entry too); round 2's buffer-
    then-commit shape makes that assertion false for a different, better
    reason -- A's own write was never on the shared list to begin with,
    so there is nothing for any truncate, length-based or otherwise, to
    get wrong.

    Uses two independent `RuleSandbox`es (two separate `LuaRuntime`s),
    one per dispatch, rather than sharing one sandbox between the two
    threads -- lupa's own per-runtime lock serializes every call into a
    *single* shared runtime (`research/2026-11-17-lupa-sandbox.md` R4),
    which would force the two dispatches to run one after the other and
    never actually overlap. What is under test here is `CrewConsole`'s
    own per-dispatch buffering over the *shared* `pending_effector_
    writes` list -- a field on `CrewConsole`, not on either sandbox --
    so two independent Lua runtimes feeding the same `CrewConsole` is a
    faithful way to get real overlap without fighting a lock this test
    has nothing to do with."""
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "r.lua").write_text(
        'when.speech("probe_a_write_then_error", "x", "always", function(s)\n'
        '  effector.write("observ", "on", "Observ on.")\n'
        '  digits("not_a_number")\n'
        "end)\n",
        encoding="utf-8",
    )
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "r.lua").write_text(
        'when.speech("probe_b_write", "x", "always", function(s)\n'
        '  effector.write("weapons", "safe", "Weapons safe.")\n'
        "end)\n",
        encoding="utf-8",
    )

    console = CrewConsole(store=ContactStore())
    a_queued = threading.Event()
    allow_a_to_proceed = threading.Event()

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        console.queue_effector_write(f"req-{name}", name, value, says)
        if name == "observ":
            # Rule A's own write -- pause here, still inside A's own
            # open `_dispatch_rule` call on *this* thread (so A's write
            # sits only in A's own thread-local buffer, not yet on the
            # shared list), so the test can run rule B's whole dispatch
            # to completion before letting A's error happen.
            a_queued.set()
            assert allow_a_to_proceed.wait(timeout=5.0)
        return {"ok": True, "reason": None}

    sandbox_a = RuleSandbox()
    ctx_a = ActionContext(
        console=console, request_effector_write=request_effector_write
    )
    rule_set_a = RuleSet.load(tmp_path / "a", sandbox_a, ACTION_NAMESPACES, ctx_a)
    assert rule_set_a.failures == ()

    sandbox_b = RuleSandbox()
    ctx_b = ActionContext(
        console=console, request_effector_write=request_effector_write
    )
    rule_set_b = RuleSet.load(tmp_path / "b", sandbox_b, ACTION_NAMESPACES, ctx_b)
    assert rule_set_b.failures == ()

    def rule_runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        if token == "probe_a_write_then_error":
            outcome = run_rule(rule_set_a, token, slots, sandbox_a)
        else:
            outcome = run_rule(rule_set_b, token, slots, sandbox_b)
        return outcome.lines, outcome.error

    console.rule_runner = rule_runner
    console.set_enabled_rule_ids(
        frozenset({"probe_a_write_then_error", "probe_b_write"})
    )

    a_result: list[list[str]] = []
    thread_a = threading.Thread(
        target=lambda: a_result.append(
            console.handle_command("probe_a_write_then_error", 0.0)
        )
    )
    thread_a.start()
    assert a_queued.wait(timeout=5.0)

    thread_b = threading.Thread(
        target=lambda: console.handle_command("probe_b_write", 0.0)
    )
    thread_b.start()
    thread_b.join(timeout=5.0)

    # Only B's entry is visible while A is still paused, mid-dispatch --
    # A's own write has not been committed yet, so it is sitting in A's
    # own thread-local buffer, not on the shared list at all.
    assert [(w.effector, w.value) for w in console.pending_effector_writes] == [
        ("weapons", "safe")
    ]

    allow_a_to_proceed.set()
    thread_a.join(timeout=5.0)

    assert a_result == [[ACTION_FILE_ERROR_LINE]]
    assert [(w.effector, w.value) for w in console.pending_effector_writes] == [
        ("weapons", "safe")
    ]


def test_poll_thread_drain_during_an_open_dispatch_window_gets_nothing_from_it(
    tmp_path: Path,
) -> None:
    """The new finding from the Stage 3d re-review's "Re-review (Fix 4)"
    section: round 1's identity-stamped rollback could be defeated by
    the poll thread's own unconditional per-poll drain (`body.py`'s
    `pending_writes, crew_console.pending_effector_writes = crew_console.
    pending_effector_writes, []`) landing *inside* an open dispatch's
    window -- after its own `effector.write` call, before its own
    error -- because that drain read the shared list before the
    rollback ever ran to remove the entry. Reproduces that exact
    interleaving against the real `_dispatch_rule`/`handle_command`
    path, with the drain run from the test itself (standing in for the
    poll thread) while the REPL-style dispatch is still paused mid-
    handler, then lets the dispatch error -- and asserts the drain saw
    *nothing* (not just that `pending_effector_writes` ends up empty,
    which would also be true if the entry had been drained away and
    then fed into a real `EffectorRunState`, the actual bug this guards
    against)."""
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_write_then_error", "x", "always", function(s)\n'
        '  effector.write("observ", "on", "Observ on.")\n'
        '  digits("not_a_number")\n'
        "end)\n",
        encoding="utf-8",
    )
    console = CrewConsole(store=ContactStore())
    sandbox = RuleSandbox()
    write_queued = threading.Event()
    allow_dispatch_to_error = threading.Event()

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        console.queue_effector_write("req-1", name, value, says)
        # Still inside the open dispatch, past the write, not yet at
        # the error -- pause so the test can run the poll thread's own
        # drain against the shared list during this exact window.
        write_queued.set()
        assert allow_dispatch_to_error.wait(timeout=5.0)
        return {"ok": True, "reason": None}

    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)
    assert rule_set.failures == ()

    def rule_runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = rule_runner
    console.set_enabled_rule_ids(frozenset({"probe_write_then_error"}))

    result: list[list[str]] = []
    dispatch_thread = threading.Thread(
        target=lambda: result.append(
            console.handle_command("probe_write_then_error", 0.0)
        )
    )
    dispatch_thread.start()
    assert write_queued.wait(timeout=5.0)

    # The poll thread's exact drain line (`body.py` ~line 5089), run
    # from this thread while the dispatch above is still open.
    drained, console.pending_effector_writes = console.pending_effector_writes, []
    engine_state = EffectorRunState()
    for request in drained:
        engine_state = request_write(
            engine_state,
            request.request_id,
            request.effector,
            request.value,
            request.says,
            0.0,
        )

    # Nothing was there to drain -- the write is still sitting in the
    # open dispatch's own thread-local buffer, not on the shared list.
    assert drained == []
    assert engine_state.ad_hoc_runs == {}

    allow_dispatch_to_error.set()
    dispatch_thread.join(timeout=5.0)

    assert result == [[ACTION_FILE_ERROR_LINE]]
    # The dispatch's own buffer was discarded on error -- still nothing
    # on the shared list, and nothing was ever fed into the engine for
    # this dispatch at all (`engine_state.ad_hoc_runs` above, asserted
    # before the error even happened, already proves the stronger
    # claim: not just "ends up empty" but "never had anything to lose").
    assert console.pending_effector_writes == []


def test_a_successful_dispatchs_write_commits_to_the_shared_list(
    tmp_path: Path,
) -> None:
    """The success side of buffer-then-commit: a dispatch that calls
    `effector.write` and returns cleanly (no later error) must have its
    write land on `pending_effector_writes` once `_dispatch_rule`
    returns, exactly as if it had been appended directly -- the buffer
    is a staging area for the error case, not a behaviour change for
    the ordinary one. Dispatched through the real `handle_command`/
    `_dispatch_rule` path, since that is the only place a buffer is
    opened at all."""
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_write_then_success", "x", "always", function(s)\n'
        '  effector.write("observ", "on", "Observ on.")\n'
        "end)\n",
        encoding="utf-8",
    )
    console = CrewConsole(store=ContactStore())
    sandbox = RuleSandbox()

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        console.queue_effector_write("req-1", name, value, says)
        return {"ok": True, "reason": None}

    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)
    assert rule_set.failures == ()

    def rule_runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = rule_runner
    console.set_enabled_rule_ids(frozenset({"probe_write_then_success"}))

    lines = console.handle_command("probe_write_then_success", 0.0)

    assert lines == []
    assert [(w.effector, w.value, w.says) for w in console.pending_effector_writes] == [
        ("observ", "on", "Observ on.")
    ]


def test_a_write_before_a_failed_action_still_commits(tmp_path: Path) -> None:
    """User, 2026-11-18: a failed action ends the handler with "unable",
    and nothing it already did is undone. `run_rule` reports that as a
    non-error outcome, so `_dispatch_rule` commits the buffered write
    rather than discarding it as it does on a Lua error (the test above
    this one's error twin). Pins that two-file interaction through the
    real `handle_command`/`_dispatch_rule` path."""
    (tmp_path / "r.lua").write_text(
        'when.speech("probe_write_then_unable", "x", "always", function(s)\n'
        '  say("Observ on.")\n'
        '  effector.write("observ", "on")\n'
        '  effector.write("no_such_effector", "on")\n'
        '  say("never")\n'
        "end)\n",
        encoding="utf-8",
    )
    console = CrewConsole(store=ContactStore())
    sandbox = RuleSandbox()

    def request_effector_write(
        name: str, value: str, says: str | None
    ) -> dict[str, object]:
        if name != "observ":
            return {"ok": False, "reason": "UNKNOWN_EFFECTOR"}
        console.queue_effector_write("req-1", name, value, says)
        return {"ok": True, "reason": None}

    ctx = ActionContext(console=console, request_effector_write=request_effector_write)
    rule_set = RuleSet.load(tmp_path, sandbox, ACTION_NAMESPACES, ctx)
    assert rule_set.failures == ()

    def rule_runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = rule_runner
    console.set_enabled_rule_ids(frozenset({"probe_write_then_unable"}))

    lines = console.handle_command("probe_write_then_unable", 0.0)

    assert lines == ["Observ on.", "Unable."]
    assert [(w.effector, w.value) for w in console.pending_effector_writes] == [
        ("observ", "on")
    ]


# --- `queue_effector_write`: the one appender, and the one construction site ---
#
# `body.py`'s real `_request_effector_write` closure is nested inside `main()`,
# which is untested by design (`body-layer/CLAUDE.md`'s module map: "`main()`'s
# CLI wiring is untested by design -- the runners are tested against fakes"),
# and cannot be exercised here without a live aircraft-layer/world-model setup.
# The actual defect a prior follow-up closed -- a caller appending a bare
# `PendingEffectorWrite` by hand, bypassing the one construction site -- is
# pinned two other ways instead: a direct test of `queue_effector_write`'s own
# buffer-or-direct-append behaviour, and a grep-enforced fence (the same shape
# `mission_memory/store.py`'s own "single construction site" test already uses
# in this codebase) proving `body.py` cannot reintroduce a hand-built
# `PendingEffectorWrite` without failing a test.


def test_queue_effector_write_buffers_inside_a_dispatch_and_appends_directly_outside_one() -> (
    None
):
    """Outside any dispatch (`_dispatch_write_buffer_local` unset, its
    ordinary state), `queue_effector_write` appends straight to the
    shared `pending_effector_writes` -- there is no dispatch buffer to
    stage the entry in, and none to roll back, so immediate visibility
    is correct (this is the path `test_effector_write_queued_from_
    background_thread_is_applied_on_next_poll_drain` above actually
    exercises, via `run_rule` directly rather than `_dispatch_rule`).
    Inside one (simulated here by setting the thread-local buffer
    directly, the same field `_dispatch_rule` itself opens), the queued
    write lands in that buffer instead -- not yet visible on the shared
    list at all."""
    console = CrewConsole(store=ContactStore())

    console.queue_effector_write("req-1", "observ", "on", "Observ on.")
    assert len(console.pending_effector_writes) == 1
    assert console.pending_effector_writes[-1].effector == "observ"

    buffer: list[PendingEffectorWrite] = []
    console._dispatch_write_buffer_local.buffer = buffer
    console.queue_effector_write("req-2", "weapons", "safe", "Weapons safe.")
    # Still just the one entry from before -- the new write went to the
    # buffer, not the shared list.
    assert len(console.pending_effector_writes) == 1
    assert len(buffer) == 1
    assert buffer[0].effector == "weapons"


def test_pending_effector_write_is_constructed_in_exactly_one_place_in_crew_console_py() -> (
    None
):
    """`queue_effector_write` is the plan's named single construction
    site for a live `PendingEffectorWrite` -- grepped, not counted by
    eye, mirroring `test_mission_memory_store.py`'s own `test_entry_is_
    constructed_in_exactly_one_place_in_store_py`."""
    text = (_SRC / "belief" / "crew_console.py").read_text(encoding="utf-8")
    hits = re.findall(r"\bPendingEffectorWrite\(", text)
    assert len(hits) == 1, (
        f"expected exactly one `PendingEffectorWrite(` construction in "
        f"crew_console.py (inside queue_effector_write), found {len(hits)}"
    )


def test_body_py_never_constructs_pending_effector_write_directly() -> None:
    """`body.py`'s real `_request_effector_write` closure must call
    `crew_console.queue_effector_write(...)`, never build a
    `PendingEffectorWrite` by hand -- the exact gap this follow-up
    closes (the closure originally appended one with no `dispatch_
    token`, so the rollback had nothing to find in production).
    Checked against the live module's own source file, not a copy, so a
    future edit cannot silently reintroduce this without failing here."""
    text = Path(body_module.__file__).read_text(encoding="utf-8")
    assert "PendingEffectorWrite(" not in text, (
        "body.py constructs PendingEffectorWrite() directly -- it should "
        "call crew_console.queue_effector_write(...) instead"
    )
    assert "PendingEffectorWrite" not in text, (
        "body.py still references PendingEffectorWrite -- drop the now-"
        "unused import if the construction above is really gone"
    )
