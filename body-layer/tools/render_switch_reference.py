"""Renders `body-layer/config/sequences/mi-24p/switch-reference.md`, a
human-readable reference of every Mi-24P control the generated raw dump
(`config/effectors-raw/mi-24p.toml`) knows about, for someone writing or
editing a sequence file in `config/sequences/mi-24p/*.md` -- user
direction, 2026-10-23 (`plans/effector-sequences/explore-notes.md`'s
"File locations and the switch reference"): *"build a full list of
switches that are available. Save to file so I can reference it when
building/modifying sequence files."*

**Per-aircraft paths (R13, Stage 2, 2026-10-23)**: still hard-coded to
the one aircraft that exists (`"mi-24p"`), same posture as `generate_
effector_registry.py`'s own `--scripts-dir` default -- adding a second
aircraft directory is a path-constant change here, not a redesign,
since this tool already takes its three paths as module constants
rather than deriving them from a scan.

Same generator convention as `tools/generate_defaults.py`: a static
read of the two already-committed TOML files (never executes anything
-- there is nothing to execute here), check mode by default, `--write`
to regenerate, a GENERATED header naming the source DCS build and the
raw dump's own sha256 so the reference and the dump it was rendered
from can never silently diverge, and deterministic output (sorted by
device id, then seat, then element name) so a regeneration diffs
cleanly. `tests/test_render_switch_reference.py` is this tool's own
staleness guard, the same pattern `tests/test_tuning_defaults_toml.py`
gives `generate_defaults.py`.

Usage (from `body-layer/`):

    python tools/render_switch_reference.py            # check only, exit 1 if stale
    python tools/render_switch_reference.py --write    # regenerate config/sequences/mi-24p/switch-reference.md
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent
_RAW_DUMP_PATH = _BODY_LAYER_ROOT / "config" / "effectors-raw" / "mi-24p.toml"
_CURATED_PATH = _BODY_LAYER_ROOT / "config" / "sequences" / "mi-24p" / "effectors.toml"
_OUTPUT_PATH = (
    _BODY_LAYER_ROOT / "config" / "sequences" / "mi-24p" / "switch-reference.md"
)

#: Matches the raw dump's own `# Source: ..., DCS <build>` header comment
#: (`generate_effector_registry.py`'s own render), so this tool never
#: hard-codes a build string of its own.
_BUILD_RE = re.compile(r"^#\s*Source:.*,\s*DCS\s+(\S+)\s*$")


@dataclass(frozen=True, slots=True)
class _Element:
    name: str
    device: int
    device_name: str
    label: str
    shape: str
    seat: str
    seat_explicit: bool
    cmds: list[int]
    args: list[int]
    arg_values: list[float] | None


def _read_build(raw_dump_text: str) -> str:
    for line in raw_dump_text.splitlines():
        match = _BUILD_RE.match(line.strip())
        if match is not None:
            return match.group(1)
    return "<unknown>"


def _load_elements(raw_doc: dict[str, Any]) -> list[_Element]:
    elements_table = raw_doc.get("elements", {})
    elements: list[_Element] = []
    for name, entry in elements_table.items():
        elements.append(
            _Element(
                name=name,
                device=entry["device"],
                device_name=entry["device_name"],
                label=entry["label"],
                shape=entry["shape"],
                seat=entry["seat"],
                seat_explicit=entry["seat_explicit"],
                cmds=entry["cmds"],
                args=entry["args"],
                arg_values=entry.get("arg_values"),
            )
        )
    return elements


def _curated_by_source_element(curated_doc: dict[str, Any]) -> dict[str, list[str]]:
    """`source_element` -> every curated friendly name that resolves to
    it, in declaration order. More than one name can resolve to the same
    element (e.g. different `index` positions), so this is a list, not a
    single name."""
    by_source: dict[str, list[str]] = {}
    for friendly_name, entry in curated_doc.get("effectors", {}).items():
        source_element = entry.get("source_element")
        if isinstance(source_element, str):
            by_source.setdefault(source_element, []).append(friendly_name)
    return by_source


def _element_name_cell(name: str) -> str:
    """Renders an element name so a leading space -- real in this dump,
    `clickabledata.lua`'s own `" CONTROL-COVER-PRIORITY-PTR"` -- stays
    visible rather than being swallowed by markdown/terminal whitespace
    collapsing."""
    if name.startswith(" "):
        return f"`{name}`  _(leading space)_"
    return f"`{name}`"


def _seat_cell(element: _Element) -> str:
    qualifier = "explicit" if element.seat_explicit else "defaulted"
    return f"{element.seat} ({qualifier})"


def render_markdown(
    elements: list[_Element],
    curated_by_source: dict[str, list[str]],
    *,
    build: str,
    raw_dump_sha256: str,
) -> str:
    lines = [
        "# Mi-24P switch reference",
        "",
        "GENERATED by `body-layer/tools/render_switch_reference.py`. DO NOT HAND-EDIT.",
        f"Source: `config/effectors-raw.toml` (sha256 `{raw_dump_sha256}`), DCS {build}.",
        "Regenerate with: `python tools/render_switch_reference.py --write`",
        "",
        "**To add a new effector:** copy the element name from a row below exactly --",
        "including a leading space, when a row shows one -- into",
        "`config/sequences/effectors.toml` as that entry's `source_element`.",
        "",
        "The **Curated as** column names the friendly name(s)",
        "`config/sequences/effectors.toml` already exposes for that control, if any --",
        "blank means it is not yet in the curated registry and a sequence file",
        "cannot reference it until it is.",
        "",
    ]

    by_device: dict[int, list[_Element]] = {}
    device_names: dict[int, str] = {}
    for element in elements:
        by_device.setdefault(element.device, []).append(element)
        device_names[element.device] = element.device_name

    for device in sorted(by_device):
        device_elements = by_device[device]
        lines.append(f"## Device {device} -- {device_names[device]}")
        lines.append("")
        for seat in sorted({e.seat for e in device_elements}):
            lines.append(f"### {seat.capitalize()} seat")
            lines.append("")
            lines.append(
                "| Element | Label | Seat | Shape | Cmds | Args | Arg values | Curated as |"
            )
            lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
            seat_elements = sorted(
                (e for e in device_elements if e.seat == seat), key=lambda e: e.name
            )
            for element in seat_elements:
                curated_names = ", ".join(
                    f"`{n}`" for n in curated_by_source.get(element.name, [])
                )
                arg_values_cell = (
                    str(element.arg_values) if element.arg_values is not None else ""
                )
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _element_name_cell(element.name),
                            element.label,
                            _seat_cell(element),
                            element.shape,
                            str(element.cmds),
                            str(element.args),
                            arg_values_cell,
                            curated_names,
                        ]
                    )
                    + " |"
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render() -> str:
    raw_dump_text = _RAW_DUMP_PATH.read_text(encoding="utf-8")
    raw_doc = tomllib.loads(raw_dump_text)
    curated_doc = tomllib.loads(_CURATED_PATH.read_text(encoding="utf-8"))

    elements = _load_elements(raw_doc)
    curated_by_source = _curated_by_source_element(curated_doc)
    build = _read_build(raw_dump_text)
    raw_dump_sha256 = hashlib.sha256(raw_dump_text.encode("utf-8")).hexdigest()

    return render_markdown(
        elements, curated_by_source, build=build, raw_dump_sha256=raw_dump_sha256
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write config/sequences/mi-24p/switch-reference.md; without this, only check staleness",
    )
    args = parser.parse_args()

    rendered = _render()

    if args.write:
        _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _OUTPUT_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {_OUTPUT_PATH}")
        return 0

    current = _OUTPUT_PATH.read_text(encoding="utf-8") if _OUTPUT_PATH.exists() else ""
    if current != rendered:
        print(
            f"{_OUTPUT_PATH} is stale -- run with --write to regenerate",
            file=sys.stderr,
        )
        return 1
    print(f"{_OUTPUT_PATH} is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
