"""Parses the startup-loaded sequence files (`config/sequences/*.md`) --
`plans/effector-sequences/plan.md`, "File formats (Stages 1-2)" and D5.

**Pure, startup-time parsing. No engine, no poll-loop wiring** (Stage
2's `belief.effector_engine` consumes what this returns) -- this
module's only job is to turn a directory of markdown-table files into
`dict[(aircraft, role, trigger), SequenceFile]`, validated against an
already-resolved `effector_registry.EffectorDef` mapping.

**A bad file is never fatal** (D5): each file is validated alone and a
bad one is dropped with every error collected (not just the first);
every other file still loads. `load_sequences` never raises on bad
*content*.

Two tables per file (plan): a 2-column header table naming exactly
`aircraft` / `petrovich-role` / `run-on-trigger` (the key for duplicate
detection, not the filename), and a 5-column data table
`condition | effector | value | petrovich-says | comment`. Each data
row is one of:

- a **switch row** -- `effector`/`value` name a registry entry and one
  of its `values`; `condition`, if present, is `<effector> = <value>`
  or `<effector> != <value>`, checked against the same registry;
- a **wait row** -- `condition` is `wait_s(<n>)`, every other cell
  blank;
- a **say-only row** (effector blank, `petrovich-says` set) -- reserved
  and rejected this cut (D7's seam: "say-only rows arrive with the
  guidance-unit-ready trigger").

`KNOWN_TRIGGERS` is this module's own source of truth for which
`run-on-trigger` values are recognised. Stage 2's `EffectorTrigger` enum
must stay in sync with it -- there is deliberately only one place this
list is spelled out."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from belief.effector_registry import EffectorDef

#: The trigger names a sequence file's `run-on-trigger` header cell may
#: name, this cut (plan decision 2, explore-notes decision 2: "yes,
#: BL-B66 first, expand later"). Stage 2's `EffectorTrigger` enum is
#: expected to have exactly one member per name here.
KNOWN_TRIGGERS: Final[frozenset[str]] = frozenset(
    {"takeoff", "observ-on", "observ-off", "weapons-arm", "weapons-safe"}
)

_REQUIRED_HEADER_KEYS: Final[tuple[str, ...]] = (
    "aircraft",
    "petrovich-role",
    "run-on-trigger",
)
_DATA_COLUMNS: Final[tuple[str, ...]] = (
    "condition",
    "effector",
    "value",
    "petrovich-says",
    "comment",
)

_WAIT_ROW_RE = re.compile(r"^wait_s\(\s*([0-9]+(?:\.[0-9]+)?)\s*\)$")
_CONDITION_RE = re.compile(r"^(\S+)\s*(!=|=)\s*(\S+)$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")


@dataclass(frozen=True, slots=True)
class Condition:
    """One row's gate, evaluated against the observed cockpit readback
    at the moment the row is reached (plan R5/D3) -- Stage 2's job, not
    this module's; this module only validates that `effector`/`value`
    are names the registry actually knows."""

    effector: str
    op: Literal["=", "!="]
    value: str


@dataclass(frozen=True, slots=True)
class SwitchRow:
    condition: Condition | None
    effector: str
    value: str
    petrovich_says: str
    comment: str


@dataclass(frozen=True, slots=True)
class WaitRow:
    wait_s: float


Row = SwitchRow | WaitRow


@dataclass(frozen=True, slots=True)
class SequenceFile:
    aircraft: str
    petrovich_role: str
    trigger: str
    rows: tuple[Row, ...]
    source_path: Path


@dataclass(frozen=True, slots=True)
class SequenceError:
    """One loader finding, collected rather than raised (D5). `line` is
    the 1-indexed source line of the markdown table row that triggered
    it when known, `None` for a file-level or header-level problem."""

    file: str
    line: int | None
    reason: str


def _parse_tables(text: str) -> list[list[list[str]]]:
    """Splits a markdown document into its pipe-delimited tables. Each
    table is a list of rows, each row a list of trimmed cell strings; a
    separator row (`| --- | --- |`, optionally with alignment colons) is
    dropped, not returned as a row. Anything outside a `|...|` line (an
    HTML comment, blank lines, prose) ends the current table."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("|") and line.endswith("|") and len(line) >= 2:
            cells = [c.strip() for c in line[1:-1].split("|")]
            if all(_SEPARATOR_CELL_RE.fullmatch(c) for c in cells):
                continue
            current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _parse_header(
    filename: str, table: list[list[str]]
) -> tuple[list[SequenceError], dict[str, str]]:
    if not table:
        return [
            SequenceError(file=filename, line=None, reason="header table is empty")
        ], {}
    head_row = [c.lower() for c in table[0]]
    if head_row != ["file-param", "for"]:
        return [
            SequenceError(
                file=filename,
                line=None,
                reason=f"header table must start with 'file-param | for', got {table[0]!r}",
            )
        ], {}

    values: dict[str, str] = {}
    for row in table[1:]:
        if len(row) != 2:
            return [
                SequenceError(
                    file=filename, line=None, reason=f"malformed header row: {row!r}"
                )
            ], {}
        key, value = row
        values[key] = value

    missing = [k for k in _REQUIRED_HEADER_KEYS if k not in values]
    extra = [k for k in values if k not in _REQUIRED_HEADER_KEYS]
    if missing or extra:
        return [
            SequenceError(
                file=filename,
                line=None,
                reason=(
                    f"header must have exactly {_REQUIRED_HEADER_KEYS}; "
                    f"missing={missing}, extra={extra}"
                ),
            )
        ], {}

    trigger = values["run-on-trigger"]
    if trigger not in KNOWN_TRIGGERS:
        return [
            SequenceError(
                file=filename,
                line=None,
                reason=f"unknown trigger {trigger!r}; known triggers: {sorted(KNOWN_TRIGGERS)}",
            )
        ], {}

    return [], values


def _parse_data_table(
    filename: str, table: list[list[str]], registry: Mapping[str, EffectorDef]
) -> tuple[list[SequenceError], list[Row]]:
    if not table:
        return [
            SequenceError(file=filename, line=None, reason="data table is empty")
        ], []
    head_row = [c.lower() for c in table[0]]
    if head_row != list(_DATA_COLUMNS):
        return [
            SequenceError(
                file=filename,
                line=None,
                reason=f"data table header must be {_DATA_COLUMNS}, got {table[0]!r}",
            )
        ], []

    errors: list[SequenceError] = []
    rows: list[Row] = []
    for line_no, cells in enumerate(table[1:], start=2):
        if len(cells) != len(_DATA_COLUMNS):
            errors.append(
                SequenceError(
                    file=filename,
                    line=line_no,
                    reason=f"malformed row: expected {len(_DATA_COLUMNS)} cells, got {cells!r}",
                )
            )
            continue
        condition_s, effector_s, value_s, says_s, comment_s = cells

        wait_match = _WAIT_ROW_RE.match(condition_s)
        if wait_match is not None:
            if effector_s or value_s or says_s:
                errors.append(
                    SequenceError(
                        file=filename,
                        line=line_no,
                        reason=f"wait row must leave effector/value/petrovich-says blank: {cells!r}",
                    )
                )
                continue
            rows.append(WaitRow(wait_s=float(wait_match.group(1))))
            continue

        if not effector_s and says_s:
            errors.append(
                SequenceError(
                    file=filename,
                    line=line_no,
                    reason="say-only rows arrive with the guidance-unit-ready trigger",
                )
            )
            continue

        if not effector_s or not value_s:
            errors.append(
                SequenceError(
                    file=filename,
                    line=line_no,
                    reason=f"malformed row: a switch row needs both effector and value: {cells!r}",
                )
            )
            continue

        effector_def = registry.get(effector_s)
        if effector_def is None:
            errors.append(
                SequenceError(
                    file=filename,
                    line=line_no,
                    reason=f"unknown effector {effector_s!r}",
                )
            )
            continue
        if value_s not in effector_def.values:
            errors.append(
                SequenceError(
                    file=filename,
                    line=line_no,
                    reason=f"unknown value {value_s!r} for effector {effector_s!r}",
                )
            )
            continue

        condition: Condition | None = None
        if condition_s:
            cond_match = _CONDITION_RE.match(condition_s)
            if cond_match is None:
                errors.append(
                    SequenceError(
                        file=filename,
                        line=line_no,
                        reason=f"malformed condition: {condition_s!r}",
                    )
                )
                continue
            cond_effector, op, cond_value = cond_match.groups()
            cond_effector_def = registry.get(cond_effector)
            if cond_effector_def is None:
                errors.append(
                    SequenceError(
                        file=filename,
                        line=line_no,
                        reason=f"unknown effector {cond_effector!r} in condition",
                    )
                )
                continue
            if cond_value not in cond_effector_def.values:
                errors.append(
                    SequenceError(
                        file=filename,
                        line=line_no,
                        reason=f"unknown value {cond_value!r} for effector {cond_effector!r} in condition",
                    )
                )
                continue
            assert op in ("=", "!=")
            op_literal: Literal["=", "!="] = "!=" if op == "!=" else "="
            condition = Condition(
                effector=cond_effector, op=op_literal, value=cond_value
            )

        rows.append(
            SwitchRow(
                condition=condition,
                effector=effector_s,
                value=value_s,
                petrovich_says=says_s,
                comment=comment_s,
            )
        )

    if errors:
        return errors, []
    return [], rows


def _load_one_file(
    path: Path, registry: Mapping[str, EffectorDef]
) -> tuple[list[SequenceError], SequenceFile | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [
            SequenceError(file=path.name, line=None, reason=f"cannot read file: {exc}")
        ], None

    tables = _parse_tables(text)
    if len(tables) != 2:
        return [
            SequenceError(
                file=path.name,
                line=None,
                reason=f"expected exactly 2 markdown tables (header, data), found {len(tables)}",
            )
        ], None
    header_table, data_table = tables

    header_errors, header = _parse_header(path.name, header_table)
    if header_errors:
        return header_errors, None

    data_errors, rows = _parse_data_table(path.name, data_table, registry)
    if data_errors:
        return data_errors, None

    return [], SequenceFile(
        aircraft=header["aircraft"],
        petrovich_role=header["petrovich-role"],
        trigger=header["run-on-trigger"],
        rows=tuple(rows),
        source_path=path,
    )


def load_sequences(
    sequences_dir: Path, registry: Mapping[str, EffectorDef]
) -> tuple[dict[tuple[str, str, str], SequenceFile], list[SequenceError]]:
    """Returns `(sequences_by_key, errors)`, keyed by
    `(aircraft, petrovich_role, trigger)` -- the plan's "key for
    duplicate detection (not the filename)". `switch-reference.md` (the
    generated human-readable control list, not a sequence file) is
    skipped by extension-and-name rather than by content sniffing. Every
    `*.md` file is read regardless of load order (sorted, for
    determinism); a duplicate key across two or more files drops every
    file sharing it, with one error per dropped file (plan: "both files
    rejected -- neither silently wins")."""
    errors: list[SequenceError] = []
    parsed: list[tuple[Path, SequenceFile]] = []

    for path in sorted(sequences_dir.glob("*.md")):
        if path.name == "switch-reference.md":
            continue
        file_errors, sequence_file = _load_one_file(path, registry)
        if file_errors:
            errors.extend(file_errors)
            continue
        assert sequence_file is not None
        parsed.append((path, sequence_file))

    by_key: dict[tuple[str, str, str], list[tuple[Path, SequenceFile]]] = defaultdict(
        list
    )
    for path, sequence_file in parsed:
        key = (
            sequence_file.aircraft,
            sequence_file.petrovich_role,
            sequence_file.trigger,
        )
        by_key[key].append((path, sequence_file))

    result: dict[tuple[str, str, str], SequenceFile] = {}
    for key, entries in by_key.items():
        if len(entries) > 1:
            names = sorted(path.name for path, _ in entries)
            for path, _ in entries:
                others = [n for n in names if n != path.name]
                errors.append(
                    SequenceError(
                        file=path.name,
                        line=None,
                        reason=f"duplicate (aircraft, role, trigger) {key} also defined in {others}",
                    )
                )
            continue
        ((path, sequence_file),) = entries
        result[key] = sequence_file

    return result, errors
