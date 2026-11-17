"""Check `config/rules/*.lua` without flying (`[[BL-17]]`, "Rule checker,
without flying"). User: *"Syntax check and type check to catch errors while
editing the rule lua files, without actually flying."*

Four checks, each reported as `file: rule 'id': message` (a Lua error's own
message carries the line number):

1. **Lua syntax and load errors** -- every file is loaded in the same
   sandbox body-layer uses.
2. **`when.speech` declarations** -- duplicate id, unknown category, a bad
   argument count; the loader's own checks, unchanged.
3. **Wording** -- the pattern grammar and the collision check `PUT /rules`
   runs, offline, through audio-adapter's own
   `tools/check_rule_patterns.py` (a subprocess, not an import -- the
   subprojects stay independent). Skipped with a warning when
   audio-adapter's venv is missing.
4. **Handlers, by dry run** -- every handler is called with sample slot
   values from step 3 (each directive alternative, each slot form),
   against the real actions on a throwaway `CrewConsole` that is flying
   (and, separately, hovering), and once more with every action answering
   `ok = false`, so both branches of `if not r.ok then ...` run. Catches a
   misspelt action, a wrong argument, `nil` arithmetic, a `digits()` of a
   string, and an `effector.write` naming an effector or value the
   registry does not have. A branch none of the samples reaches is not
   checked -- this is a dry run, not a type checker.

Exit status: 0 clean, 1 errors found.

    cd body-layer && .venv/bin/python tools/check_rules.py [RULES_DIR]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _BODY_LAYER_ROOT / "src"
_WORLD_MODEL_SRC_DIR = _BODY_LAYER_ROOT.parent / "world-model" / "src"
for _path in (_SRC_DIR, _WORLD_MODEL_SRC_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from belief.ai_pilot_wheel import ParkedFlightState
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.effector_engine import AIRCRAFT
from belief.effector_registry import (
    aircraft_dir_name,
    load_registries_by_aircraft,
)
from rules.actions import ACTION_NAMESPACES, Action, ActionContext
from rules.engine import (
    RULE_DISPATCH_INSTRUCTION_BUDGET,
    CompiledLuaRule,
    RuleSet,
)
from rules.loader import DEFAULT_RULES_DIR
from rules.sandbox import RuleSandbox

_ADAPTER_ROOT = _BODY_LAYER_ROOT.parent / "audio-adapter"
_ADAPTER_PYTHON = _ADAPTER_ROOT / ".venv" / "bin" / "python"
_ADAPTER_TOOL = _ADAPTER_ROOT / "tools" / "check_rule_patterns.py"

#: The flight states a handler is dry-run in. Held values are set so the
#: real actions take their success path; the category gate itself is not
#: run (a dry run checks the handler, not who may call it).
_FLYING = ParkedFlightState(
    parked_active=True,
    ai_mode="FLT",
    held_heading=120.0,
    held_altitude=300.0,
    held_altitude_ref="R",
    held_speed=150.0,
)
_SCENARIOS: tuple[tuple[str, ParkedFlightState, bool], ...] = (
    ("flying", _FLYING, False),
    ("hovering", replace(_FLYING, ai_mode="HVRT"), False),
    ("every action fails", _FLYING, True),
)


@dataclass(frozen=True)
class Finding:
    file: str
    rule_id: str | None
    message: str

    def render(self) -> str:
        where = f" rule '{self.rule_id}':" if self.rule_id else ""
        return f"{self.file}:{where} {self.message}"


def _first_line(exc: Exception) -> str:
    # A Lua error carries a stack traceback after the first line; the first
    # line already names the file and line number.
    return str(exc).splitlines()[0] if str(exc) else type(exc).__name__


def _failing_namespaces() -> dict[str, tuple[Action, ...]]:
    def fail(_ctx: ActionContext, _args: dict[str, object]) -> dict[str, object]:
        return {"ok": False, "reason": None}

    return {
        namespace: tuple(replace(action, invoke=fail) for action in actions)
        for namespace, actions in ACTION_NAMESPACES.items()
    }


def _check_wording(
    rule_set: RuleSet, adapter_python: Path
) -> tuple[list[Finding], dict[str, list[dict[str, Any]]] | None, str | None]:
    """Runs audio-adapter's pattern checker. Returns findings, per-rule
    samples, and a warning when the check could not run at all."""
    if not adapter_python.is_file():
        return (
            [],
            None,
            (
                f"wording not checked: {adapter_python} not found "
                "(build audio-adapter's .venv to enable it)"
            ),
        )
    payload = [
        {"id": rule_id, "pattern": pattern, "category": category}
        for rule_id, pattern, category in rule_set.ids_and_patterns()
    ]
    proc = subprocess.run(
        [str(adapter_python), str(_ADAPTER_TOOL)],
        check=False,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=_ADAPTER_ROOT,
        env={"PYTHONPATH": str(_ADAPTER_ROOT / "src"), "PATH": "/usr/bin:/bin"},
        timeout=120,
    )
    if proc.returncode != 0:
        return [], None, f"wording not checked: pattern checker failed:\n{proc.stderr}"
    result = json.loads(proc.stdout)
    files = {rule.id: rule.file for rule in rule_set.rules.values()}
    findings = [
        Finding(files.get(item["id"], "?"), item["id"], item["reason"])
        for item in result["rejected"]
    ]
    return findings, result["samples"], None


def _slot_sets(
    rule: CompiledLuaRule, samples: dict[str, list[dict[str, Any]]] | None
) -> Iterator[tuple[str, dict[str, Any] | None]]:
    if samples is None:
        # No wording check, so no slot values: a rule with slots cannot be
        # dry-run meaningfully (`check` warns), one without still can.
        if "<" not in rule.pattern:
            yield "(no slots)", None
        return
    if not samples.get(rule.id):
        yield "(no slots)", None
        return
    for sample in samples[rule.id]:
        yield sample["utterance"], sample["slots"] or None


def _dry_run(
    rules_dir: Path, samples: dict[str, list[dict[str, Any]]] | None
) -> list[Finding]:
    registries = load_registries_by_aircraft()
    registry, _errors = registries.get(aircraft_dir_name(AIRCRAFT), ({}, []))
    findings: list[Finding] = []
    reported: set[tuple[str, str]] = set()
    current: dict[str, str] = {}

    def report(message: str) -> None:
        key = (current["rule"], message)
        if key not in reported:
            reported.add(key)
            findings.append(Finding(current["file"], current["rule"], message))

    def request_effector_write(
        name: str, value: str, _says: str | None
    ) -> dict[str, object]:
        effector = registry.get(name)
        if effector is None or value not in effector.values:
            report(
                f"effector.write({name!r}, {value!r}): no such effector/value "
                f"in {aircraft_dir_name(AIRCRAFT)}/effectors.toml"
            )
            return {"ok": False, "reason": "UNKNOWN_EFFECTOR"}
        return {"ok": True, "reason": None}

    def on_rejected_call(action: str, why: str) -> None:
        report(f"bad call to {action}(): {why}")

    for label, state, all_fail in _SCENARIOS:
        console = CrewConsole(store=ContactStore())
        sandbox = RuleSandbox()
        ctx = ActionContext(
            console=console,
            request_effector_write=request_effector_write,
            on_rejected_call=on_rejected_call,
        )
        namespaces = _failing_namespaces() if all_fail else ACTION_NAMESPACES
        rule_set = RuleSet.load(rules_dir, sandbox, namespaces, ctx)
        sink = rule_set._sink_holder
        for rule in rule_set.rules.values():
            current["file"], current["rule"] = rule.file, rule.id
            for utterance, slots in _slot_sets(rule, samples):
                console.parked_flight_state = state
                sink.lines = []
                try:
                    lua_slots = sandbox.table_from(slots) if slots else sandbox.table()
                    with sandbox.run_with_budget(RULE_DISPATCH_INSTRUCTION_BUDGET):
                        rule.handler(lua_slots)
                except Exception as exc:  # noqa: BLE001 -- report every failure
                    message = _first_line(exc)
                    if (rule.id, message) not in reported:
                        reported.add((rule.id, message))
                        findings.append(
                            Finding(
                                rule.file,
                                rule.id,
                                f'{message} (dry run: "{utterance}", {label})',
                            )
                        )
                finally:
                    sink.lines = None
    return findings


def check(rules_dir: Path, adapter_python: Path) -> tuple[list[Finding], list[str]]:
    sandbox = RuleSandbox()
    ctx = ActionContext(console=CrewConsole(store=ContactStore()))
    rule_set = RuleSet.load(rules_dir, sandbox, ACTION_NAMESPACES, ctx)
    findings = [
        Finding(failure.file, failure.rule_id, failure.reason)
        for failure in rule_set.failures
    ]
    warnings: list[str] = []
    wording, samples, warning = _check_wording(rule_set, adapter_python)
    findings.extend(wording)
    if warning is not None:
        warnings.append(warning)
        warnings.append("rules with slots were not dry-run (no sample values)")
    findings.extend(_dry_run(rules_dir, samples))
    return findings, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "rules_dir",
        nargs="?",
        type=Path,
        default=DEFAULT_RULES_DIR,
        help="directory of *.lua rule files (default: config/rules)",
    )
    parser.add_argument(
        "--adapter-python",
        type=Path,
        default=_ADAPTER_PYTHON,
        help="audio-adapter's Python, for the wording check",
    )
    args = parser.parse_args(argv)
    if not args.rules_dir.is_dir():
        print(f"{args.rules_dir}: not a directory", file=sys.stderr)
        return 1
    files = sorted(p.name for p in args.rules_dir.glob("*.lua"))
    findings, warnings = check(args.rules_dir, args.adapter_python)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for finding in findings:
        print(finding.render())
    if findings:
        print(f"{len(findings)} problem(s) in {len(files)} rule file(s)")
        return 1
    print(f"ok: {len(files)} rule file(s) checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
