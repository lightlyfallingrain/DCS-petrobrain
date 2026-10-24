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

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

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


#: Shapes confirmed live as an absolute set (`performClickableAction(cmd,
#: value)` always leaves the control at `value`, regardless of where it
#: was) -- plan S4.3: "true only for `default_2_position_tumb`, the one
#: helper shape whose ... is confirmed live ... all six shipped
#: effectors, BL-B66." A row's implicit self-check (R12) may write on an
#: *unknown* readback only for an effector whose `shape` is in this set --
#: every other shape (buttons, covers, springloaded, 3-position,
#: multiposition, axes) is not absolute until a later research note
#: confirms it live and widens this tuple. Widening is a one-line change
#: here, each widening with its own `aircraft-layer/research/` note.
_ABSOLUTE_WRITE_SHAPES: Final[frozenset[str]] = frozenset({"default_2_position_tumb"})


@dataclass(frozen=True, slots=True)
class EffectorDef:
    """One resolved curated entry -- device/cmd/arg are the raw numbers
    `source_element` (plus `index`) resolved to, never typed into the
    curated file directly. `shape` is copied straight from the raw
    dump's own element (so the provenance survives); `absolute_write`
    is derived from it, never stored, so widening `_ABSOLUTE_WRITE_
    SHAPES` changes every existing `EffectorDef`'s answer with no reload."""

    name: str
    source_element: str
    device: int
    cmd: int
    arg: int
    values: dict[str, float]
    shape: str
    unverified: bool = False

    @property
    def absolute_write(self) -> bool:
        """`True` only for a shape confirmed live as an absolute set
        (plan S4.3) -- a fail-safe for sequence files that may name *any*
        switch, not new reach: sequencing a non-absolute control (press +
        release) is not designed here. See `_ABSOLUTE_WRITE_SHAPES`."""
        return self.shape in _ABSOLUTE_WRITE_SHAPES


@dataclass(frozen=True, slots=True)
class RegistryError:
    """One loader finding, collected rather than raised (D5). `scope`
    distinguishes a whole-file problem (`"raw-dump"`/`"curated-file"`/
    `"polled-file"`, `name` is `None`) from one bad entry (`"entry"`,
    `name` is the curated effector/indicator name). `"polled-file"` is
    `load_polled_config`'s own (S4.4a) -- a separate scope from
    `"curated-file"` so a reader can tell "bad effectors.toml" apart from
    "bad polled.toml" without parsing `name`."""

    scope: Literal["raw-dump", "curated-file", "polled-file", "entry"]
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

    shape = element.get("shape")
    if not isinstance(shape, str) or not shape:
        return RegistryError(
            scope="entry",
            name=name,
            reason=f"source_element {source_element!r} has no 'shape'",
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
        shape=shape,
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


#: `load_polled_config`'s own cap (plan S4.4a): "required ∪ config, max 64
#: in total" -- the same wire bound `watch_args`/`SequenceFile.read_args`
#: use, stated again here rather than imported (no shared constant across
#: these three load-time call sites in this file's own module, by the
#: project's "no reinventing the wheel" rule's own exception clause: each
#: side states its bound once, held equal only where a parity test can
#: check it -- here, nothing crosses a subproject boundary, so this is a
#: plain duplicate literal, not a parity-tested pair).
_MAX_POLLED_ARGS: Final[int] = 64

_INDICATOR_NAME_RE: Final[re.Pattern[str]] = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True, slots=True)
class PolledSet:
    """The final resolved continuous-poll set (plan S4.4a) -- `args` is
    ordered (code-required first, then `polled.toml`'s own file order,
    per `effectors` then `indicators`), `names` is `{arg: name}` for
    logging ("polling N args: observ(886), align_lamp(898), ...")."""

    args: tuple[int, ...]
    names: Mapping[int, str]


def load_polled_config(
    polled_path: Path,
    registry: Mapping[str, EffectorDef],
    required: Mapping[int, str],
) -> tuple[PolledSet, list[RegistryError], list[str]]:
    """Returns `(polled_set, errors, warnings)` (plan S4.4a).

    `required` is `sight_effector.REQUIRED_POLLED_ARGS` (`{arg: reason}`,
    dict order = union order) -- always included, first. `errors` are
    collected D5-style (never raised, scope `"polled-file"`/`"entry"`);
    `warnings` are informational only and never set `config_error_pending`
    -- currently only "config omits required arg" messages, since the
    behaviour is already correct (required args poll regardless) and the
    warning only keeps the file honest as a reference.

    A **missing** `polled_path` is not an error -- required-only, per the
    plan ("A missing file is not an error: required-only, with an INFO
    log" -- the INFO log itself is the caller's job, `logger.py`'s
    startup banner). An unreadable/unparsable file *is* a `"polled-file"`
    D5 error, and the result is still required-only (never a partial
    config)."""
    required_order = list(required.keys())

    if not polled_path.exists():
        return PolledSet(args=tuple(required_order), names=dict(required)), [], []

    try:
        text = polled_path.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            PolledSet(args=tuple(required_order), names=dict(required)),
            [
                RegistryError(
                    scope="polled-file",
                    name=None,
                    reason=f"cannot read {polled_path}: {exc}",
                )
            ],
            [],
        )
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return (
            PolledSet(args=tuple(required_order), names=dict(required)),
            [
                RegistryError(
                    scope="polled-file",
                    name=None,
                    reason=f"cannot parse {polled_path} as TOML: {exc}",
                )
            ],
            [],
        )

    errors: list[RegistryError] = []
    names: dict[int, str] = dict(required)
    order: list[int] = list(required_order)
    config_covered: set[int] = set()

    effectors_entry = doc.get("effectors", [])
    if not isinstance(effectors_entry, list):
        errors.append(
            RegistryError(
                scope="polled-file",
                name="effectors",
                reason="'effectors' must be a list of effector names",
            )
        )
        effectors_entry = []
    for name in effectors_entry:
        if not isinstance(name, str):
            errors.append(
                RegistryError(
                    scope="entry",
                    name=str(name),
                    reason="effector name must be a string",
                )
            )
            continue
        effector_def = registry.get(name)
        if effector_def is None:
            errors.append(
                RegistryError(
                    scope="entry", name=name, reason=f"unknown effector {name!r}"
                )
            )
            continue
        arg = effector_def.arg
        config_covered.add(arg)
        if arg in names:
            if arg in required:
                # Already in the set via `required` -- the config's own
                # friendly name still wins for logging (plan's own
                # startup-line example names a required arg by its
                # config name, e.g. "ready_lamp(960)", not by its
                # required-reason string).
                names[arg] = name
            else:
                errors.append(
                    RegistryError(
                        scope="entry",
                        name=name,
                        reason=f"duplicate arg {arg} already polled",
                    )
                )
            continue
        names[arg] = name
        order.append(arg)

    indicators_entry = doc.get("indicators", {})
    if not isinstance(indicators_entry, dict):
        errors.append(
            RegistryError(
                scope="polled-file",
                name="indicators",
                reason="'indicators' must be a table",
            )
        )
        indicators_entry = {}
    for ind_name, ind_value in indicators_entry.items():
        if not isinstance(ind_name, str) or not _INDICATOR_NAME_RE.fullmatch(ind_name):
            errors.append(
                RegistryError(
                    scope="entry",
                    name=str(ind_name),
                    reason="indicator name must match [a-z0-9_]+",
                )
            )
            continue
        if ind_name in registry:
            errors.append(
                RegistryError(
                    scope="entry",
                    name=ind_name,
                    reason=f"indicator name {ind_name!r} clashes with an effector name",
                )
            )
            continue
        if not isinstance(ind_value, dict):
            errors.append(
                RegistryError(
                    scope="entry",
                    name=ind_name,
                    reason="indicator entry must be a table",
                )
            )
            continue
        ind_arg = ind_value.get("arg")
        if (
            isinstance(ind_arg, bool)
            or not isinstance(ind_arg, int)
            or not (0 <= ind_arg <= 4095)
        ):
            errors.append(
                RegistryError(
                    scope="entry",
                    name=ind_name,
                    reason=f"indicator 'arg' must be an int in 0..4095, got {ind_arg!r}",
                )
            )
            continue
        config_covered.add(ind_arg)
        if ind_arg in names:
            if ind_arg in required:
                names[ind_arg] = ind_name
            else:
                errors.append(
                    RegistryError(
                        scope="entry",
                        name=ind_name,
                        reason=f"duplicate arg {ind_arg} already polled",
                    )
                )
            continue
        names[ind_arg] = ind_name
        order.append(ind_arg)

    warnings = [
        f"polled.toml does not list arg {arg} ({reason}); polling it "
        "anyway because code reads it"
        for arg, reason in required.items()
        if arg not in config_covered
    ]

    if len(order) > _MAX_POLLED_ARGS:
        # Required args are never dropped; overflow config entries are
        # dropped from the end of the file (plan S4.4a).
        required_set = set(required_order)
        kept: list[int] = []
        dropped: list[int] = []
        config_entries = [a for a in order if a not in required_set]
        keep_count = _MAX_POLLED_ARGS - len(required_set)
        kept_config = config_entries[:keep_count] if keep_count > 0 else []
        dropped = config_entries[len(kept_config) :]
        kept = required_order + kept_config
        for arg in dropped:
            errors.append(
                RegistryError(
                    scope="entry",
                    name=names.get(arg),
                    reason=f"arg {arg} dropped: polled set exceeds the "
                    f"{_MAX_POLLED_ARGS}-arg cap",
                )
            )
        order = kept
        names = {arg: names[arg] for arg in order}

    return PolledSet(args=tuple(order), names=names), errors, warnings
