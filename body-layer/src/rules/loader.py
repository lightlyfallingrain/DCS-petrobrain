"""Reads `config/rules/*.lua` in sorted order and collects what each file
registered, or why it could not be loaded (`plans/speech-rules/plan.md`
Stage 1b item 2). Knows nothing about the Lua *mechanics* beyond calling
`RuleSandbox`'s own methods, and nothing about the action registry at
all -- `engine.py` supplies `env_builder`, which is what actually wires a
file's `when.speech` calls into this module's `RawRegistration`/
`RuleLoadError` sinks, and layers the rule API/action tables on top of
`RuleSandbox.base_env()`.

**A whole file's registrations are discarded together on any load-time
failure** (D6: "a Lua syntax error, or an error while the file runs at
load → that file's rules are discarded") -- a file loads in its own
environment table, so one bad file never touches another's."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rules.sandbox import (
    RuleBudgetExceeded,
    RuleCompileError,
    RuleRuntimeError,
    RuleSandbox,
)

#: `config/rules/` -- always-on default (`--rules-dir`'s own default,
#: `body.py`), mirroring `belief.effector_registry.DEFAULT_SEQUENCES_DIR`'s
#: shape exactly.
DEFAULT_RULES_DIR: Path = (
    Path(__file__).resolve().parent.parent.parent / "config" / "rules"
)


@dataclass(frozen=True)
class RuleLoadError:
    """One load-time failure. `rule_id` is `None` for a file-level failure
    (a syntax error, or an error raised by the file's own top-level code
    outside any handler) -- the only cases this module itself produces;
    `engine.py`'s duplicate-id pass is what later produces one with a
    `rule_id` set."""

    file: str
    rule_id: str | None
    reason: str


@dataclass(frozen=True)
class RawRegistration:
    """One `when.speech(id, pattern, category, handler)` call that ran
    cleanly (`category` added D16/U19). `handler` is the Lua function
    value, opaque to this module -- `engine.py` is what calls it, with a
    slots table, at dispatch time.

    `category` defaults to `"always"` only so this module's own tests
    (`test_rules_loader.py`), which exercise a deliberately simplified
    fake env builder that predates categories and never constructs this
    with one, do not need to supply it -- the real env builder
    (`engine.py`'s `_build_when_table`) always sets it explicitly,
    already validated against `rules.gates.GATE_REGISTRY`."""

    id: str
    pattern: str
    handler: Any
    file: str
    category: str = "always"


#: What `engine.py` passes in: given this file's own label plus the two
#: sinks this load should append into, build and return a restricted
#: `_ENV` table (based on `RuleSandbox.base_env()`) whose `when.speech`
#: global appends a `RawRegistration`/`RuleLoadError` into the matching
#: sink for every call the file makes while it runs.
EnvBuilder = Callable[[str, list[RawRegistration], list[RuleLoadError]], Any]


def load_rules(
    rules_dir: Path,
    sandbox: RuleSandbox,
    env_builder: EnvBuilder,
    instruction_budget: int,
) -> tuple[list[RawRegistration], list[RuleLoadError]]:
    """Loads every `*.lua` file directly under `rules_dir`, sorted by
    filename for a deterministic load order (and so a second run with no
    file changes always produces the same `RuleSet.version`). A missing
    `rules_dir` loads as zero files, zero failures -- the same "additive,
    no rules shipped yet behaves exactly like today" posture Stage 1b's
    own acceptance test pins, not a reportable error; `--rules-dir`'s own
    default always points at a real, committed directory."""
    registrations: list[RawRegistration] = []
    failures: list[RuleLoadError] = []
    if not rules_dir.is_dir():
        return registrations, failures
    for path in sorted(rules_dir.glob("*.lua")):
        file_label = path.name
        file_registrations: list[RawRegistration] = []
        file_failures: list[RuleLoadError] = []
        env = env_builder(file_label, file_registrations, file_failures)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            failures.append(RuleLoadError(file_label, None, f"could not read: {exc}"))
            continue
        try:
            chunk = sandbox.compile(source, file_label, env)
            with sandbox.run_with_budget(instruction_budget):
                chunk()
        except (RuleCompileError, RuleRuntimeError, RuleBudgetExceeded) as exc:
            # The whole file is discarded -- any registrations it made
            # before the failure are dropped too (D6).
            failures.append(RuleLoadError(file_label, None, str(exc)))
            continue
        registrations.extend(file_registrations)
        failures.extend(file_failures)
    return registrations, failures
