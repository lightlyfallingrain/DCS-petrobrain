"""Petrovich HelperAI indication (`list_indication(HELPERAI_DEVICE_ID)`) wire
format schema.

`Export.lua` polls `list_indication(6)` on the same loopback socket and
throttle as the ownship telemetry and world-objects polls
(`LuaExportAfterNextFrame`, see `aircraft-layer/dcs-export/Export.lua`) and
pushes one JSON line per poll: a flat object carrying the poll's own
`t`/timestamp plus the raw `list_indication` return string verbatim, under
the key `indication`. `Export.lua` does zero tree parsing itself (this
file's "deliberately dumb" policy) -- `PetrovichIndicationSample.from_json_line`
is the only supported way to turn that wire text into the typed record the
rest of the pipeline works with, mirroring `TelemetrySample`'s and
`WorldObjectsSnapshot`'s role for their own wire formats.

Wire format of the `indication` string itself, confirmed live (not desk
research) per
`aircraft-layer/research/2026-09-08-pb1-live-spike-results.md` finding 1: a
**recursive** tree of blocks, not the flat one-block-per-controller shape an
earlier desk-research session anticipated for a different device. Each block
looks like:

    -----------------------------------------
    <name>
    <value-if-any>
    children are {
    ...nested blocks, recursively...
    }

`<value-if-any>` is omitted entirely (the block goes straight from `<name>`
to `children are {`) when that controller currently has no populated value
-- confirmed live for the `crosshair` subtree, which stayed `children are
{}` (present, no children) across ~4000 samples in the live spike. Only
leaf-ish nodes that DO carry a value are meaningful to this project (at
minimum `middle_list_text`/`lower_list_text`/`lower_lower_list_text`, e.g.
`"Ural truck"`) -- `parse_indication_text` below flattens the whole tree
into a `{name: value}` record containing only the populated nodes, at
whatever depth they appear, since callers don't need the tree structure
itself, just which named controllers are currently showing text.

This parser is a from-scratch recursive-descent implementation against the
wire format confirmed above -- not adapted from any reference
implementation, per `plans/pb1-perception-logger/plan.md` decision 5's
reimplement-not-adopt posture (that decision covered the flat kneeboard-style
format; this extends the same posture to the tree format the live spike
actually found).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

#: The literal delimiter line `list_indication` prefixes every block with.
DELIMITER: Final[str] = "-----------------------------------------"
#: The literal line that opens a block's children list, whether or not that
#: block also carried a `<value-if-any>` line before it.
_CHILDREN_MARKER: Final[str] = "children are {"
#: The literal line that closes a `children are {` block.
_CLOSE_MARKER: Final[str] = "}"


class PetrovichIndicationParseError(ValueError):
    """Raised when a HelperAI indication JSON line does not match the
    expected wire format. Malformed *tree* content inside a structurally
    valid JSON line is never raised for -- see `parse_indication_text`'s
    docstring on why that parser degrades gracefully instead."""


@dataclass(frozen=True, slots=True)
class PetrovichIndicationSample:
    """One parsed `list_indication(HELPERAI_DEVICE_ID)` poll: the poll's own
    dual-clock timestamps (mirrors `TelemetrySample`/`WorldObjectsSnapshot`'s
    provenance requirement) plus the flattened `{leaf_name: text}` record."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    fields: dict[str, str]

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> PetrovichIndicationSample:
        if "t" not in data:
            raise PetrovichIndicationParseError("missing required field(s): ['t']")
        model_time = _require_number(data, "t")

        raw = data.get("indication")
        if not isinstance(raw, str):
            raise PetrovichIndicationParseError(
                f"field 'indication' must be a string, got {type(raw).__name__}"
            )

        return PetrovichIndicationSample(
            dcs_model_time_s=model_time,
            received_wall_clock_s=received_wall_clock_s,
            fields=parse_indication_text(raw),
        )

    @staticmethod
    def from_json_line(
        line: str, *, received_wall_clock_s: float
    ) -> PetrovichIndicationSample:
        """Parse one newline-terminated (or bare) JSON line from Export.lua."""
        stripped = line.strip()
        if not stripped:
            raise PetrovichIndicationParseError("empty line")
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise PetrovichIndicationParseError(f"invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise PetrovichIndicationParseError(
                f"expected a JSON object, got {type(data).__name__}"
            )
        return PetrovichIndicationSample.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dcs_model_time_s": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "fields": dict(self.fields),
        }


@dataclass(frozen=True, slots=True)
class _IndicationNode:
    """One parsed tree block. Not exported -- only `parse_indication_text`'s
    flattened output is a supported public shape."""

    name: str
    value: str | None
    children: tuple[_IndicationNode, ...]


def parse_indication_text(raw: str) -> dict[str, str]:
    """Parse one raw `list_indication(HELPERAI_DEVICE_ID)` dump string into a
    flat `{leaf_name: text}` record, at minimum
    `middle_list_text`/`lower_list_text`/`lower_lower_list_text` when
    populated.

    Degrades gracefully rather than raising on unexpected structure --
    Export.lua pushes this string verbatim from a live, unverified-in-detail
    DCS internal, and a wrong assumption about one block's shape should drop
    that block (or, worst case, yield an empty record) rather than take down
    the whole parse. Lines outside a recognized block header/close-brace
    position are skipped defensively; a block missing its expected
    `children are {` marker is treated as childless rather than raising.
    """
    lines = raw.split("\n")
    nodes, _ = _parse_nodes(lines, 0)
    fields: dict[str, str] = {}
    _flatten(nodes, fields)
    return fields


def _flatten(nodes: tuple[_IndicationNode, ...], fields: dict[str, str]) -> None:
    for node in nodes:
        if node.value is not None:
            fields[node.name] = node.value
        _flatten(node.children, fields)


def _parse_nodes(
    lines: list[str], start: int
) -> tuple[tuple[_IndicationNode, ...], int]:
    """Parse zero or more sibling blocks starting at `lines[start]`, stopping
    at end-of-input or an unconsumed `}` (a parent block's close marker,
    left for the caller to consume). Returns `(nodes, next_index)`."""
    nodes: list[_IndicationNode] = []
    n = len(lines)
    i = start
    while i < n:
        line = lines[i]
        if line == "":
            i += 1
            continue
        if line == _CLOSE_MARKER:
            return tuple(nodes), i
        if line != DELIMITER:
            # Content outside a recognized block header -- skip defensively
            # rather than raise (see parse_indication_text's docstring).
            i += 1
            continue

        i += 1  # consume the delimiter line
        if i >= n:
            break
        name = lines[i]
        i += 1

        value: str | None
        if i < n and lines[i] == _CHILDREN_MARKER:
            value = None
            i += 1
        elif i < n:
            value = lines[i]
            i += 1
            if i < n and lines[i] == _CHILDREN_MARKER:
                i += 1
            # else: malformed (no children marker after a value line) --
            # keep the value, treat this block as having no children.
        else:
            value = None

        children, i = _parse_nodes(lines, i)
        if i < n and lines[i] == _CLOSE_MARKER:
            i += 1  # consume this block's own close marker

        nodes.append(_IndicationNode(name=name, value=value, children=children))

    return tuple(nodes), i


def _require_number(data: dict[str, Any], field: str) -> float:
    raw = data[field]
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise PetrovichIndicationParseError(
            f"field {field!r} must be a number, got {raw!r}"
        )
    return float(raw)
