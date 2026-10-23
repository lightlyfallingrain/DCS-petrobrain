"""Loads the curated effector registry (`config/sequences/effectors.toml`)
against the generated raw dump (`config/effectors-raw.toml`) --
`plans/effector-sequences/plan.md`, "File formats (Stages 1-2)" and D5.

**Pure, startup-time loading. No engine, no poll-loop wiring** (that is
Stage 2, `belief.effector_engine`) -- this module's only job is to turn
two TOML files into a `dict[str, EffectorDef]` a sequence file (or,
later, the engine) can look a friendly name up in.

**A bad curated entry is never fatal** (D5: "a bad curated entry drops
that entry, and any sequence file using it becomes a bad file in turn").
`load_registry` never raises on bad *content* -- a missing
`source_element`, an unresolved join, a bad `values` table, or two
entries colliding on the same `(device, cmd, arg)` triple each drop
*that* entry and are reported as one `RegistryError` each, while every
other entry still loads. The one case that is not entry-scoped is a
raw-dump or curated file that cannot be read or parsed as TOML at
all -- that returns an *empty* registry with one file-level
`RegistryError`, which is deliberately the same shape as "every entry
was individually bad": a sequence file that references any effector
will fail its own "unknown effector" check against the empty dict and be
dropped in turn by `effector_sequences.load_sequences`, which is exactly
D5's "disables every sequence" -- no separate fatal-file flag is needed
to get that behaviour.

Only `OSError`/`tomllib.TOMLDecodeError` are caught here; anything else
(a bug in this module) is a real exception and should not be silently
swallowed."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

#: Where `generate_effector_registry.py --write` (Stage 0) puts the
#: generated dump, relative to this file
#: (`body-layer/src/belief/effector_registry.py` -> `body-layer/config/
#: effectors-raw.toml`).
DEFAULT_RAW_DUMP_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "effectors-raw.toml"
)

#: Where the hand-written curated registry lives
#: (`body-layer/config/sequences/effectors.toml` -- corrected 2026-10-23
#: from `body-layer/sequences/`, see `explore-notes.md`'s "File locations"
#: section).
DEFAULT_CURATED_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "sequences"
    / "effectors.toml"
)


@dataclass(frozen=True, slots=True)
class EffectorDef:
    """One resolved curated entry -- device/cmd/arg are the raw numbers
    `source_element` (plus `index`) resolved to, never typed into the
    curated file directly."""

    name: str
    source_element: str
    device: int
    cmd: int
    arg: int
    values: dict[str, float]
    unverified: bool = False


@dataclass(frozen=True, slots=True)
class RegistryError:
    """One loader finding, collected rather than raised (D5). `scope`
    distinguishes a whole-file problem (`"raw-dump"`/`"curated-file"`,
    `name` is `None`) from one bad curated entry (`"entry"`, `name` is
    the curated effector name)."""

    scope: Literal["raw-dump", "curated-file", "entry"]
    name: str | None
    reason: str


def _read_toml(
    path: Path, scope: Literal["raw-dump", "curated-file"]
) -> tuple[dict[str, Any] | None, RegistryError | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, RegistryError(
            scope=scope, name=None, reason=f"cannot read {path}: {exc}"
        )
    try:
        return tomllib.loads(text), None
    except tomllib.TOMLDecodeError as exc:
        return None, RegistryError(
            scope=scope, name=None, reason=f"cannot parse {path} as TOML: {exc}"
        )


def _resolve_entry(
    name: str, entry: Any, raw_elements: Mapping[str, Any]
) -> EffectorDef | RegistryError:
    if not isinstance(entry, dict):
        return RegistryError(scope="entry", name=name, reason="entry is not a table")

    source_element = entry.get("source_element")
    if not isinstance(source_element, str) or not source_element:
        return RegistryError(
            scope="entry", name=name, reason="missing or empty 'source_element'"
        )

    element = raw_elements.get(source_element)
    if not isinstance(element, dict):
        return RegistryError(
            scope="entry",
            name=name,
            reason=f"source_element {source_element!r} not found in the raw dump",
        )

    index = entry.get("index", 0)
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        return RegistryError(
            scope="entry",
            name=name,
            reason=f"'index' must be a non-negative integer, got {index!r}",
        )

    cmds = element.get("cmds")
    args = element.get("args")
    device = element.get("device")
    if (
        not isinstance(cmds, list)
        or not isinstance(args, list)
        or not isinstance(device, int)
    ):
        return RegistryError(
            scope="entry",
            name=name,
            reason=f"source_element {source_element!r} has a malformed raw entry "
            "(missing/invalid device/cmds/args)",
        )
    if index >= len(cmds) or index >= len(args):
        return RegistryError(
            scope="entry",
            name=name,
            reason=f"'index' {index} is out of range for {source_element!r} "
            f"(cmds has {len(cmds)}, args has {len(args)})",
        )
    cmd = cmds[index]
    arg = args[index]
    if not isinstance(cmd, int) or not isinstance(arg, int):
        return RegistryError(
            scope="entry",
            name=name,
            reason=f"source_element {source_element!r} has a non-integer cmd/arg at index {index}",
        )

    values = entry.get("values")
    if not isinstance(values, dict) or not values:
        return RegistryError(
            scope="entry", name=name, reason="missing or empty 'values' table"
        )
    resolved_values: dict[str, float] = {}
    for value_name, raw_value in values.items():
        if (
            not isinstance(value_name, str)
            or isinstance(raw_value, bool)
            or not isinstance(raw_value, (int, float))
        ):
            return RegistryError(
                scope="entry",
                name=name,
                reason=f"'values' entry {value_name!r} must map to a number, got {raw_value!r}",
            )
        resolved_values[value_name] = float(raw_value)

    unverified = entry.get("unverified", False)
    if not isinstance(unverified, bool):
        return RegistryError(
            scope="entry",
            name=name,
            reason=f"'unverified' must be a bool, got {unverified!r}",
        )

    return EffectorDef(
        name=name,
        source_element=source_element,
        device=device,
        cmd=cmd,
        arg=arg,
        values=resolved_values,
        unverified=unverified,
    )


def load_registry(
    raw_dump_path: Path = DEFAULT_RAW_DUMP_PATH,
    curated_path: Path = DEFAULT_CURATED_PATH,
) -> tuple[dict[str, EffectorDef], list[RegistryError]]:
    """Returns `(registry, errors)`. `registry` holds every curated entry
    that resolved cleanly; `errors` is every finding, file-level or
    entry-level. Never raises on bad content (D5) -- see the module
    docstring for the one case (`raw_dump_path`/`curated_path`
    unreadable or unparsable) that is not entry-scoped."""
    raw_doc, raw_error = _read_toml(raw_dump_path, "raw-dump")
    if raw_error is not None:
        return {}, [raw_error]
    assert raw_doc is not None
    raw_elements = raw_doc.get("elements")
    if not isinstance(raw_elements, dict):
        return {}, [
            RegistryError(
                scope="raw-dump",
                name=None,
                reason=f"{raw_dump_path} has no [elements] table",
            )
        ]

    curated_doc, curated_error = _read_toml(curated_path, "curated-file")
    if curated_error is not None:
        return {}, [curated_error]
    assert curated_doc is not None
    curated_entries = curated_doc.get("effectors")
    if not isinstance(curated_entries, dict):
        return {}, [
            RegistryError(
                scope="curated-file",
                name=None,
                reason=f"{curated_path} has no [effectors] table",
            )
        ]

    errors: list[RegistryError] = []
    resolved: dict[str, EffectorDef] = {}
    for name, entry in curated_entries.items():
        result = _resolve_entry(name, entry, raw_elements)
        if isinstance(result, RegistryError):
            errors.append(result)
        else:
            resolved[name] = result

    # Collision check: two curated entries resolving to the same
    # (device, cmd, arg) triple (D5) -- neither silently wins, both are
    # dropped and reported, the same "neither wins" posture
    # `effector_sequences.load_sequences` applies to a duplicate
    # (aircraft, role, trigger) triple.
    by_triple: dict[tuple[int, int, int], list[str]] = {}
    for name, resolved_entry in resolved.items():
        triple = (resolved_entry.device, resolved_entry.cmd, resolved_entry.arg)
        by_triple.setdefault(triple, []).append(name)
    for triple, names in by_triple.items():
        if len(names) <= 1:
            continue
        for name in names:
            others = [n for n in names if n != name]
            errors.append(
                RegistryError(
                    scope="entry",
                    name=name,
                    reason=f"(device, cmd, arg) = {triple} collides with {others}",
                )
            )
            del resolved[name]

    return resolved, errors
