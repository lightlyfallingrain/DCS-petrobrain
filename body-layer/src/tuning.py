"""The behaviour-constant tuning loader -- `plans/configurable-constants/
plan.md` Stage 1. Every behaviour-affecting constant this project exposes
resolves to one of these accessors at module import, so the value is fixed
before anything else in the process runs (the module docstring's own
reasoning: body-layer binds constants by value at import -- `from belief.
decay import OBSERVED_WINDOW_S` in `contacts.py` -- so a later `setattr` on
the defining module never reaches an importer that already ran. Resolving
at the declaration, not after, is the only workable choice).

**The file path comes from `PETROBRAIN_TUNING`, read once, lazily, on the
first accessor call or `validate_against_defaults()` call -- never from a
CLI flag.** `argparse` in `main()` runs after every import has completed,
so a `--tuning PATH` flag would be parsed too late to affect anything it
named, and would fail silently. Put this lapse condition here, not only in
the plan, per the plan's own "Risks & Unknowns": if a future change reads
the path from `argparse` instead, every override becomes a silent no-op.

**Decision 4 REVISED (plan, 2026-10-15): every bad value warns and
continues on the code default. Nothing refuses to start.** The one
exception the plan's Decision 4a resolves: `PETROBRAIN_TUNING` named but
the file is missing or unreadable is *also* not fatal -- it warns loudly
(the whole override set is absent, not one key) and runs on defaults, same
as every other case. There is no case in this module that raises past
accessor/`validate_against_defaults()` call time.

**The one cross-key coupling this loader knows about (review's Required
Fix 1, `plans/configurable-constants/review.md`): `belief.decay`'s
`OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` invariant.** `OBSERVED_WINDOW_S`
is `len(perception.gaze.SCAN_PLAN) * perception.gaze.FOCUS_DWELL_S`, not a
key of its own, so no per-key `lo`/`hi` bound can see the coupling between
`perception.gaze.FOCUS_DWELL_S`, `perception.gaze.SCAN_PLAN`, and
`belief.decay.POSITION_HALF_LIFE_S` -- two overrides that are each inside
their own declared bounds can still violate it, and `belief.decay` used to
enforce it with a bare `assert`, i.e. a disguised refusal to start, exactly
the thing Decision 4 REVISED exists to prevent. `_check_scan_decay_coupling`
below is the fix: a single targeted check for this one known relationship
(not a general cross-key framework, out of scope per the review), run from
inside `real`/`sequence` for exactly these three keys, before either of
`perception.gaze`'s two accessor calls returns -- it has to run there,
not in `belief.decay` where the invariant conceptually lives, because
`perception.gaze` resolves first (`belief.decay` imports from it) and
`belief.decay` cannot react to a problem after `perception.gaze` has
already bound its `Final` constants. It peeks at
`belief.decay.POSITION_HALF_LIFE_S`'s raw override value directly, by key,
with no import of `belief.decay` needed -- the same technique
`validate_against_defaults` already uses against `config/defaults.toml`'s
full registry. When the combination would violate the invariant, every one
of the three keys that the override file actually set is rejected and
falls back to its code default -- never a clamped or invented middle
value -- which necessarily restores the invariant, because any of the
three keys *not* in the override file was already at its own code default,
and the code defaults are asserted safe in `belief.decay` itself (that
assert stays, and still fails loudly, because a *default* combination
that violates the invariant is a genuine programming error, not a bad
tuning file).

**Two registries, for two different questions:**

- The *live registry* (`_State.claimed`, `.resolution`) is built
  progressively as each accessor call executes during import -- it only
  knows about keys some already-imported constant has claimed.
- `validate_against_defaults()` cross-checks the *override file's* keys
  against `config/defaults.toml`, the committed, generated, complete
  registry -- independent of import order. This is what catches a
  misspelled or renamed key: no accessor call will ever claim it, so only
  a check against the full registry can tell the pilot his edit did
  nothing, rather than crediting an unimported module.

Type/bounds checks happen **inside** the accessor that owns the key
(`real`/`whole`/`fraction`/`table`/`sequence`), because the accessor must
return a definite value immediately -- there is no later pass that could
retroactively change what a `Final` constant was bound to. Unknown-key
detection happens only in `validate_against_defaults()`, because no
accessor is ever called with a misspelled key -- nothing here could catch
that from inside an accessor.
"""

from __future__ import annotations

import difflib
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

#: The one environment variable this module reads. Not a CLI flag -- see
#: the module docstring and plan Decision 2.
_ENV_VAR = "PETROBRAIN_TUNING"

#: Where the generated, committed registry lives relative to this file
#: (`body-layer/src/tuning.py` -> `body-layer/config/defaults.toml`).
_DEFAULT_DEFAULTS_TOML_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "defaults.toml"
)

#: Calibration status, rendered on every key -- what tells the pilot
#: whether a number is worth fiddling with.
Status = Literal["measured", "derived", "judgement", "agreed-guess", "uncalibrated"]

FileStatus = Literal["unset", "missing", "unreadable", "loaded"]


@dataclass(frozen=True, slots=True)
class AppliedEntry:
    """An override that was read, validated, and is now the value in
    force."""

    key: str
    default: Any
    value: Any
    status: Status


@dataclass(frozen=True, slots=True)
class RejectedEntry:
    """A key the pilot's file mentioned whose value (or, for `reason ==
    "unknown key"`, whose very existence) could not be honoured -- the
    code default is in force instead. `reason` is one of "unknown key",
    "wrong type", "out of range", "unrecognised table entry" -- the
    classification the startup block and `--print-tuning` both render,
    per the plan's "Failure behaviour" distinction between a typo (the
    edit was never read) and an out-of-range value (the edit was read and
    rejected). "invariant violation" is the one addition past the plan
    (review's Required Fix 1): the key's own value was fine on its own
    terms, but combined with another key's override it would break the
    one cross-key coupling `_check_scan_decay_coupling` knows about --
    `detail` names the invariant and every key rejected alongside it."""

    key: str
    reason: Literal[
        "unknown key",
        "wrong type",
        "out of range",
        "unrecognised table entry",
        "invariant violation",
    ]
    detail: str
    default_in_force: Any


@dataclass(frozen=True, slots=True)
class DefaultedEntry:
    """A key with no override present -- the sparse-file normal case,
    never warned about (plan's "Failure behaviour" table)."""

    key: str
    default: Any
    status: Status


@dataclass
class Resolution:
    """The one object both the startup block and `--print-tuning` render
    from, so there is exactly one place that classifies a key, never two
    that could disagree (plan, "Making a rejection visible")."""

    tuning_path: str | None
    file_status: FileStatus
    applied: dict[str, AppliedEntry] = field(default_factory=dict)
    rejected: dict[str, RejectedEntry] = field(default_factory=dict)
    defaulted: dict[str, DefaultedEntry] = field(default_factory=dict)


@dataclass
class _State:
    path: Path | None
    file_status: FileStatus
    raw: dict[str, Any]
    flat: dict[str, Any]
    claimed: set[str]
    resolution: Resolution
    #: Set by `_check_scan_decay_coupling` the first time it runs (idempotent
    #: past that, since the check only needs to run once per process).
    cross_key_checked: bool = False
    #: Keys the coupling check has rejected -- consulted by `real`/
    #: `sequence` for exactly the three keys `_COUPLED_KEYS` names.
    cross_key_rejected: set[str] = field(default_factory=set)
    #: The shared rejection detail text for every key in `cross_key_rejected`
    #: -- one message, not one per key, since they are rejected together for
    #: the same reason.
    cross_key_detail: str = ""


_state: _State | None = None

#: Cache for `_defaults_registry()` -- the flattened `config/defaults.toml`,
#: read at most once per process, same lazy-singleton shape as `_state`.
_defaults_registry_cache: dict[str, Any] | None = None


def _flatten(raw: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """Dotted-key -> leaf-value map over a parsed TOML tree. A `dict` value
    is a table and is recursed into; anything else (float, int, bool, str,
    list) is a leaf, including a TOML array -- an array is never recursed
    into even though it may itself hold tables, because this project's
    array-valued keys (`sequence`) are always arrays of scalars."""
    flat: dict[str, Any] = {}
    for k, v in raw.items():
        dotted = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(_flatten(v, dotted))
        else:
            flat[dotted] = v
    return flat


def _lookup_raw(raw: Mapping[str, Any], dotted_key: str) -> Any:
    """Navigate a parsed TOML tree by a dotted key path. Returns a
    sentinel-free `None` on a path that does not exist -- callers that need
    to distinguish "absent" from "present and `None`" do not arise here,
    since TOML has no null literal."""
    node: Any = raw
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _build_state() -> _State:
    raw_path = os.environ.get(_ENV_VAR)
    if raw_path is None:
        return _State(
            path=None,
            file_status="unset",
            raw={},
            flat={},
            claimed=set(),
            resolution=Resolution(tuning_path=None, file_status="unset"),
        )

    path = Path(raw_path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return _State(
            path=path,
            file_status="missing",
            raw={},
            flat={},
            claimed=set(),
            resolution=Resolution(tuning_path=str(path), file_status="missing"),
        )

    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return _State(
            path=path,
            file_status="unreadable",
            raw={},
            flat={},
            claimed=set(),
            resolution=Resolution(tuning_path=str(path), file_status="unreadable"),
        )

    return _State(
        path=path,
        file_status="loaded",
        raw=raw,
        flat=_flatten(raw),
        claimed=set(),
        resolution=Resolution(tuning_path=str(path), file_status="loaded"),
    )


def _get_state() -> _State:
    global _state
    if _state is None:
        _state = _build_state()
    return _state


def reset_for_testing() -> None:
    """Drop the cached loader state so a test can simulate a fresh process
    under a different `PETROBRAIN_TUNING`. Production code never calls
    this -- the whole point of resolving once, lazily, is that a process
    never needs to reload."""
    global _state
    _state = None


def _coerce_number(raw_value: Any) -> float | None:
    """TOML int or float both accept as a number (an int override for a
    float key is fine); `bool` is rejected even though it is a `int`
    subclass in Python, and `str` is rejected -- a wrong-type override,
    not a value."""
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    return None


#: The one cross-key coupling this loader knows about -- see the module
#: docstring and `_check_scan_decay_coupling` below. Not a general
#: mechanism: these three dotted keys are named literally, nowhere else in
#: this module, and nothing generalises this to a second coupling without
#: writing a second named check.
_FOCUS_DWELL_S_KEY = "perception.gaze.FOCUS_DWELL_S"
_SCAN_PLAN_KEY = "perception.gaze.SCAN_PLAN"
_POSITION_HALF_LIFE_S_KEY = "belief.decay.POSITION_HALF_LIFE_S"
_COUPLED_KEYS = (_FOCUS_DWELL_S_KEY, _SCAN_PLAN_KEY, _POSITION_HALF_LIFE_S_KEY)


def _defaults_registry() -> dict[str, Any]:
    """The flattened, committed `config/defaults.toml` -- the same file
    `validate_against_defaults` reads, cached once per process. Used by
    `_check_scan_decay_coupling` to get each coupled key's code default
    without importing `perception.gaze`/`belief.decay` (which would defeat
    the point: `perception.gaze` is what is still resolving when this is
    called)."""
    global _defaults_registry_cache
    if _defaults_registry_cache is None:
        try:
            raw = tomllib.loads(_DEFAULT_DEFAULTS_TOML_PATH.read_text(encoding="utf-8"))
        except OSError:
            raw = {}
        _defaults_registry_cache = _flatten(raw)
    return _defaults_registry_cache


def _coupling_effective_value(state: _State, key: str) -> Any:
    """`key`'s raw override if the file supplies one, else its committed
    default from `config/defaults.toml`. Deliberately does not re-validate
    the override's own type/bounds here -- that is each key's own
    accessor's job, which runs its full check *before* consulting
    `cross_key_rejected` (see `real`/`sequence` below), so a value that is
    independently wrong-typed or out-of-range is still classified under
    that more specific reason, not this one."""
    if state.file_status == "loaded" and key in state.flat:
        return state.flat[key]
    return _defaults_registry().get(key)


def _check_scan_decay_coupling(state: _State) -> None:
    """The targeted fix for review's Required Fix 1: before either of
    `perception.gaze.FOCUS_DWELL_S`'s or `perception.gaze.SCAN_PLAN`'s own
    accessor call returns, check whether the combination they and
    `belief.decay.POSITION_HALF_LIFE_S` would resolve to violates
    `belief.decay`'s `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` invariant
    -- `OBSERVED_WINDOW_S` being `len(SCAN_PLAN) * FOCUS_DWELL_S`. Runs at
    most once per process (`state.cross_key_checked` guards it), triggered
    by whichever of the three keys' accessor call happens to run first.

    If the invariant would be violated, every one of the three keys that
    the override file actually sets is marked `cross_key_rejected` --
    never a subset chosen to be "the cause," and never a clamped or
    invented middle value -- so that the keys actually at fault
    (whichever they are) all fall back to their code defaults and the
    invariant is restored, per the reasoning in the module docstring.
    A key the file never mentions was already going to resolve to its own
    code default through the ordinary path, so marking only the
    file-mentioned keys here still produces "every one of the three keys
    is at its code default" as the end state -- exactly what the review's
    reproduction requires."""
    if state.cross_key_checked:
        return
    state.cross_key_checked = True
    if state.file_status != "loaded":
        return

    focus = _coupling_effective_value(state, _FOCUS_DWELL_S_KEY)
    scan_plan = _coupling_effective_value(state, _SCAN_PLAN_KEY)
    half_life = _coupling_effective_value(state, _POSITION_HALF_LIFE_S_KEY)
    if isinstance(focus, bool) or not isinstance(focus, (int, float)):
        return
    if not isinstance(scan_plan, list) or not all(
        isinstance(v, int) and not isinstance(v, bool) for v in scan_plan
    ):
        return
    if isinstance(half_life, bool) or not isinstance(half_life, (int, float)):
        return

    observed_window_s = len(scan_plan) * float(focus)
    if observed_window_s < float(half_life):
        return

    involved = sorted(
        key
        for key in _COUPLED_KEYS
        if state.file_status == "loaded" and key in state.flat
    )
    if not involved:
        # The violation comes entirely from code defaults, not from any
        # override -- a genuine programming error, not a bad tuning file.
        # Leave it alone; belief.decay's own hard assert (kept exactly for
        # this case) will fail loudly once it resolves.
        return
    state.cross_key_rejected.update(involved)
    state.cross_key_detail = (
        "belief.decay's OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S invariant "
        f"would be violated (OBSERVED_WINDOW_S = len(SCAN_PLAN) * "
        f"FOCUS_DWELL_S = {observed_window_s!r} >= POSITION_HALF_LIFE_S = "
        f"{half_life!r}); rejected together with: {involved} -- code "
        "defaults in force for all of them"
    )


def real(key: str, default: float, *, lo: float, hi: float, status: Status) -> float:
    """A scalar float tunable. Composition: the override replaces the
    default if present and valid; otherwise the default stays in force,
    reported per the plan's "Failure behaviour" table."""
    state = _get_state()
    if key in _COUPLED_KEYS:
        _check_scan_decay_coupling(state)
    state.claimed.add(key)
    if state.file_status != "loaded" or key not in state.flat:
        state.resolution.defaulted[key] = DefaultedEntry(key, default, status)
        return default

    raw_value = state.flat[key]
    value = _coerce_number(raw_value)
    if value is None:
        state.resolution.rejected[key] = RejectedEntry(
            key,
            "wrong type",
            f"expected a number, got {type(raw_value).__name__} {raw_value!r}",
            default,
        )
        return default
    if not (lo <= value <= hi):
        state.resolution.rejected[key] = RejectedEntry(
            key, "out of range", f"{value!r} out of range [{lo}, {hi}]", default
        )
        return default
    if key in state.cross_key_rejected:
        state.resolution.rejected[key] = RejectedEntry(
            key, "invariant violation", state.cross_key_detail, default
        )
        return default

    state.resolution.applied[key] = AppliedEntry(key, default, value, status)
    return value


def whole(key: str, default: int, *, lo: int, hi: int, status: Status) -> int:
    """A scalar int tunable. A float override for an int key is a type
    mismatch, not a truncation -- `30.0` for a key declared `whole` is
    rejected, never floored to `30`."""
    state = _get_state()
    state.claimed.add(key)
    if state.file_status != "loaded" or key not in state.flat:
        state.resolution.defaulted[key] = DefaultedEntry(key, default, status)
        return default

    raw_value = state.flat[key]
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        state.resolution.rejected[key] = RejectedEntry(
            key,
            "wrong type",
            f"expected a whole number, got {type(raw_value).__name__} {raw_value!r}",
            default,
        )
        return default
    if not (lo <= raw_value <= hi):
        state.resolution.rejected[key] = RejectedEntry(
            key, "out of range", f"{raw_value!r} out of range [{lo}, {hi}]", default
        )
        return default

    state.resolution.applied[key] = AppliedEntry(key, default, raw_value, status)
    return raw_value


def fraction(key: str, default: float, *, status: Status) -> float:
    """A scalar float tunable bounded to `[0.0, 1.0]` by definition --
    delegates to `real` with those bounds fixed, so there is exactly one
    place that validates a scalar float."""
    return real(key, default, lo=0.0, hi=1.0, status=status)


def sequence(key: str, default: tuple[int, ...], *, status: Status) -> tuple[int, ...]:
    """An array-valued tunable. Composition: replace wholesale -- there is
    no per-element merge, unlike `table`."""
    state = _get_state()
    if key in _COUPLED_KEYS:
        _check_scan_decay_coupling(state)
    state.claimed.add(key)
    if state.file_status != "loaded" or key not in state.flat:
        state.resolution.defaulted[key] = DefaultedEntry(key, default, status)
        return default

    raw_value = state.flat[key]
    if not isinstance(raw_value, list) or not all(
        isinstance(v, int) and not isinstance(v, bool) for v in raw_value
    ):
        state.resolution.rejected[key] = RejectedEntry(
            key,
            "wrong type",
            f"expected an array of whole numbers, got {raw_value!r}",
            default,
        )
        return default
    if key in state.cross_key_rejected:
        state.resolution.rejected[key] = RejectedEntry(
            key, "invariant violation", state.cross_key_detail, default
        )
        return default

    value = tuple(raw_value)
    state.resolution.applied[key] = AppliedEntry(key, default, value, status)
    return value


def table(
    key: str, default: Mapping[str, float], *, lo: float, hi: float, status: Status
) -> dict[str, float]:
    """A table-valued tunable. Composition: merge **per entry** -- an
    entry key with no match in `default` is rejected as its own key
    (`f"{key}.{entry_key}"`), that entry stays at its code default, and
    the rest of the table's valid entries still apply (plan's "Failure
    behaviour", table-entry row)."""
    state = _get_state()
    result = dict(default)

    raw_table = _lookup_raw(state.raw, key) if state.file_status == "loaded" else None
    if raw_table is None:
        for entry_key, entry_default in default.items():
            full_key = f"{key}.{entry_key}"
            state.claimed.add(full_key)
            state.resolution.defaulted[full_key] = DefaultedEntry(
                full_key, entry_default, status
            )
        return result

    if not isinstance(raw_table, dict):
        state.claimed.add(key)
        state.resolution.rejected[key] = RejectedEntry(
            key,
            "wrong type",
            f"expected a table, got {type(raw_table).__name__} {raw_table!r}",
            dict(default),
        )
        for entry_key, entry_default in default.items():
            full_key = f"{key}.{entry_key}"
            state.claimed.add(full_key)
            state.resolution.defaulted[full_key] = DefaultedEntry(
                full_key, entry_default, status
            )
        return result

    for entry_key, raw_value in raw_table.items():
        full_key = f"{key}.{entry_key}"
        state.claimed.add(full_key)
        if entry_key not in default:
            state.resolution.rejected[full_key] = RejectedEntry(
                full_key,
                "unrecognised table entry",
                f"not a recognised entry of {key} -- valid entries: {sorted(default)}",
                None,
            )
            continue
        value = _coerce_number(raw_value)
        if value is None:
            state.resolution.rejected[full_key] = RejectedEntry(
                full_key,
                "wrong type",
                f"expected a number, got {type(raw_value).__name__} {raw_value!r}",
                default[entry_key],
            )
            continue
        if not (lo <= value <= hi):
            state.resolution.rejected[full_key] = RejectedEntry(
                full_key,
                "out of range",
                f"{value!r} out of range [{lo}, {hi}]",
                default[entry_key],
            )
            continue
        result[entry_key] = value
        state.resolution.applied[full_key] = AppliedEntry(
            full_key, default[entry_key], value, status
        )

    for entry_key, entry_default in default.items():
        full_key = f"{key}.{entry_key}"
        if full_key not in state.claimed:
            state.claimed.add(full_key)
            state.resolution.defaulted[full_key] = DefaultedEntry(
                full_key, entry_default, status
            )

    return result


def _nearest_key(key: str, candidates: Mapping[str, Any]) -> str | None:
    matches = difflib.get_close_matches(key, list(candidates), n=1, cutoff=0.6)
    return matches[0] if matches else None


def validate_against_defaults(defaults_path: Path | None = None) -> Resolution:
    """The one guard against a misspelled, renamed, or never-existed key --
    see the module docstring's "Two registries" note on why this cannot be
    done inside an accessor. Call this once, after every tunable module
    has been imported (`main()`'s own first lines), and render the result
    with `render_startup_block`/`render_print_tuning`.

    Validates the override file's keys against `config/defaults.toml`,
    the committed, generated registry -- not against whatever this
    process happens to have imported, so there is no import-order
    dependency (plan, "Where the files live and how they compose")."""
    state = _get_state()
    if state.file_status != "loaded":
        return state.resolution

    if defaults_path is None:
        defaults_path = _DEFAULT_DEFAULTS_TOML_PATH
    try:
        defaults_raw = tomllib.loads(defaults_path.read_text(encoding="utf-8"))
    except OSError:
        defaults_raw = {}
    defaults_flat = _flatten(defaults_raw)

    unknown = sorted(set(state.flat) - state.claimed)
    for key in unknown:
        suggestion = _nearest_key(key, defaults_flat)
        if suggestion is not None:
            detail = f"did you mean {suggestion}? default {defaults_flat[suggestion]!r} in force"
        else:
            detail = "no similar key found in config/defaults.toml"
        state.resolution.rejected[key] = RejectedEntry(key, "unknown key", detail, None)

    return state.resolution


_BLOCK_RULE = "=" * 63


def render_startup_block(resolution: Resolution) -> str:
    """The startup block -- printed once, not interleaved with ordinary
    log lines (plan, "Making a rejection visible"). An empty `rejected`
    section reads as confirmation, not absence of information."""
    if resolution.file_status == "unset":
        return f"tuning: no override file ({_ENV_VAR} unset)"

    if resolution.file_status in ("missing", "unreadable"):
        # Decision 4a's resolution: a named-but-unreadable file is not
        # fatal, same policy as every other bad value (Decision 4
        # REVISED) -- but it is the one case where *all* overrides are
        # absent rather than one, so the message says so plainly rather
        # than looking like an ordinary single-key rejection.
        return (
            f"=== Petrobrain tuning ({_ENV_VAR}={resolution.tuning_path}) ===\n"
            f"WARNING: tuning file not readable at {resolution.tuning_path} "
            "-- no overrides are in force; every constant below is at its "
            "code default.\n"
            f"{_BLOCK_RULE}"
        )

    applied = sorted(resolution.applied.values(), key=lambda e: e.key)
    rejected = sorted(resolution.rejected.values(), key=lambda e: e.key)
    lines = [f"=== Petrobrain tuning ({_ENV_VAR}={resolution.tuning_path}) ==="]
    lines.append(f"applied ({len(applied)}):")
    for e in applied:
        lines.append(f"  {e.key}: {e.default!r} -> {e.value!r} ({e.status})")
    if rejected:
        lines.append(
            f"rejected ({len(rejected)}) -- code default is in force for these:"
        )
        for r in rejected:
            lines.append(f"  {r.key}: {r.reason}")
            lines.append(f"    ({r.detail})")
    else:
        lines.append("rejected (0)")
    lines.append(_BLOCK_RULE)
    return "\n".join(lines)


def render_print_tuning(resolution: Resolution) -> str:
    """`--print-tuning`'s full dump: the startup block, plus every key
    that is simply at its default -- the mechanical answer to "did it
    take effect," reading resolved values rather than file contents."""
    lines = [render_startup_block(resolution)]
    defaulted = sorted(resolution.defaulted.values(), key=lambda e: e.key)
    if defaulted:
        lines.append("")
        lines.append(f"at default ({len(defaulted)}):")
        for e in defaulted:
            lines.append(f"  {e.key}: {e.default!r} ({e.status})")
    return "\n".join(lines)
