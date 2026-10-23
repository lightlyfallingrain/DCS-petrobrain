"""Loads the curated effector registry (`config/sequences/<aircraft-dir>/
effectors.toml`) against the generated raw dump (`config/effectors-raw/
<aircraft-dir>.toml`) -- `plans/effector-sequences/plan.md`, "File formats
(Stages 1-2)", D5 and R13 (per-aircraft layout).

**Pure, startup-time loading. No engine, no poll-loop wiring** (that is
Stage 2, `belief.effector_engine`) -- this module's only job is to turn
two TOML files into a `dict[str, EffectorDef]` a sequence file (or,
later, the engine) can look a friendly name up in.

**A bad curated entry is never fatal** (D5: "a bad curated entry drops
that entry, and any sequence file using it becomes a bad file in turn").
`load_registry` never raises on bad *content* -- a missing
`source_element`, an unresolved join, or a bad `values` table each drop
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

**Per-aircraft (R13, user direction 2026-10-23: "effectors.toml has to be
aircraft specific ... better to be ready now")**: `load_registries_by_
aircraft` discovers one registry per subdirectory of `config/sequences/`,
each loaded independently via `load_registry` against `config/
effectors-raw/<dirname>.toml` -- a bad registry in one aircraft directory
disables only that aircraft's sequences, never another's. `aircraft_dir_
name` is the single place a sequence file's `aircraft` header value
(e.g. `"Mi-24P"`) is mapped to its directory name (`"mi-24p"`) --
`effector_sequences.py` imports it rather than lower-casing its own copy.

**Collision rule (R13, superseding Stage 1's "drop both"): first wins.**
When two curated entries in the same registry resolve to the same
`(device, cmd, arg)` triple, the one that appears first in the TOML
file (the order `tomllib` preserves) is kept; every later one is dropped
and reported. User, verbatim: "keep first."

Only `OSError`/`tomllib.TOMLDecodeError` are caught here; anything else
(a bug in this module) is a real exception and should not be silently
swallowed."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

#: Where the generated raw dumps (`generate_effector_registry.py
#: --write`, Stage 0) live, one file per aircraft directory name
#: (`config/effectors-raw/<aircraft-dir>.toml`) -- moved here from a
#: single flat `config/effectors-raw.toml` by R13 (Stage 2, 2026-10-23).
DEFAULT_RAW_DUMP_DIR = (
    Path(__file__).resolve().parent.parent.parent / "config" / "effectors-raw"
)

#: Where the per-aircraft curated/sequence directories live
#: (`config/sequences/<aircraft-dir>/`) -- moved here from a flat
#: `config/sequences/` by R13. `aircraft_dir_name(aircraft)` gives the
#: subdirectory name for a given sequence file's `aircraft` header value.
DEFAULT_SEQUENCES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "config" / "sequences"
)


def aircraft_dir_name(aircraft: str) -> str:
    """The one place a sequence file's `aircraft` header value (e.g.
    `"Mi-24P"`) is mapped to its config-directory name (`"mi-24p"`) --
    lower-casing, nothing else (R13: "use what the sequence header
    already says ... mapped to the directory ... by lower-casing").
    `effector_sequences.py` imports this rather than re-deriving it."""
    return aircraft.lower()


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
    raw_dump_path: Path,
    curated_path: Path,
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
    # (device, cmd, arg) triple -- first wins (R13, user: "keep first"),
    # superseding Stage 1's "drop both". `resolved.items()` iterates in
    # the curated TOML's own file order (the order `tomllib` parsed
    # `curated_entries`, which `_resolve_entry` preserved into
    # `resolved` above), so `names[0]` below is genuinely "declared
    # first in the file", not an arbitrary dict-iteration artifact.
    by_triple: dict[tuple[int, int, int], list[str]] = {}
    for name, resolved_entry in resolved.items():
        triple = (resolved_entry.device, resolved_entry.cmd, resolved_entry.arg)
        by_triple.setdefault(triple, []).append(name)
    for triple, names in by_triple.items():
        if len(names) <= 1:
            continue
        winner, *losers = names
        for loser in losers:
            errors.append(
                RegistryError(
                    scope="entry",
                    name=loser,
                    reason=(
                        f"(device, cmd, arg) = {triple} already claimed by "
                        f"{winner!r} (first wins)"
                    ),
                )
            )
            del resolved[loser]

    return resolved, errors


def load_registries_by_aircraft(
    sequences_dir: Path = DEFAULT_SEQUENCES_DIR,
    raw_dump_dir: Path = DEFAULT_RAW_DUMP_DIR,
) -> dict[str, tuple[dict[str, EffectorDef], list[RegistryError]]]:
    """Returns one `load_registry` result per aircraft directory under
    `sequences_dir` (R13), keyed by that directory's own name (already
    the lower-cased form `aircraft_dir_name` produces, since the
    directory *is* the key). For aircraft directory `<name>`, the raw
    dump is expected at `raw_dump_dir/<name>.toml` and the curated file
    at `sequences_dir/<name>/effectors.toml` -- a missing raw dump is not
    a special case, it is simply an unreadable `raw_dump_path`, reported
    by `load_registry` the same way any other missing raw dump is (D5).

    Each aircraft directory's registry is loaded fully independently --
    a bad registry under `mi-24p/` cannot affect a hypothetical `mi-8/`
    registry loaded in the same call."""
    result: dict[str, tuple[dict[str, EffectorDef], list[RegistryError]]] = {}
    if not sequences_dir.is_dir():
        return result
    for aircraft_dir in sorted(p for p in sequences_dir.iterdir() if p.is_dir()):
        curated_path = aircraft_dir / "effectors.toml"
        raw_dump_path = raw_dump_dir / f"{aircraft_dir.name}.toml"
        result[aircraft_dir.name] = load_registry(raw_dump_path, curated_path)
    return result
