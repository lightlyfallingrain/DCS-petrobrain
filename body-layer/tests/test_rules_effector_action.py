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
import threading
from pathlib import Path
from typing import cast

from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole, PendingEffectorWrite
from belief.effector_engine import EffectorRunState, advance, request_write
from belief.effector_registry import EffectorDef
from rules.actions import ACTION_NAMESPACES, ActionContext
from rules.engine import RuleSet, run_rule
from rules.sandbox import RuleSandbox

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
        '  local r = effector.write("no_such_effector", "on", "Hi.")\n'
        "  if not r.ok then say(unable(r.reason)) end\n"
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
        '  local r = effector.write("observ", "sideways", "Hi.")\n'
        "  if not r.ok then say(unable(r.reason)) end\n"
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
        '  local r = effector.write("observ", "on")\n'
        "  if not r.ok then say(unable(r.reason)) end\n"
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
        '  local r = effector.write("observ", "on", nil)\n'
        "  if not r.ok then say(unable(r.reason)) end\n"
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
        console.pending_effector_writes.append(
            PendingEffectorWrite(
                request_id="req-1", effector=name, value=value, says=says
            )
        )
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
