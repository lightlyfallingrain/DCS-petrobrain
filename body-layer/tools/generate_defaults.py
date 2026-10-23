"""Regenerate `body-layer/config/defaults.toml` from the `tuning.*`
declarations in `src/**/*.py` -- `plans/configurable-constants/plan.md`
Stage 1. Never hand-edit `defaults.toml`: it is a *rendering* of the code,
never the authority, and `tests/test_tuning_defaults_toml.py`'s staleness
test fails CI if this script's output no longer matches the committed file.

**AST, not import.** Importing every tunable module to read `tuning.real(...)`
calls as they execute would itself depend on `PETROBRAIN_TUNING` being unset
in the generator's own environment, and would require every module's other
imports (world-model seam, etc.) to succeed just to read a literal. Scanning
the source as text/AST needs none of that.

**What it extracts per declaration:**

- the fully-qualified key and default value -- the call's own first two
  positional arguments;
- `lo`/`hi` (when present) and `status` -- the call's keyword arguments;
- the description -- the first sentence of the contiguous `#:` comment
  block immediately above the assignment (plan, "Where provenance lives").

Usage (from `body-layer/`):

    python tools/generate_defaults.py              # check only, exit 1 if stale
    python tools/generate_defaults.py --write       # regenerate config/defaults.toml
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
_DEFAULTS_TOML_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "defaults.toml"
)

#: `tuning.*` accessor names this generator understands. `whole` is not
#: used by any constant converted so far but is included for forward
#: compatibility -- the generator should not need a second commit the day
#: Stage 3 first uses it.
_ACCESSOR_NAMES = {"real", "whole", "fraction", "table", "sequence"}

#: Splits on a sentence-ending period: not preceded or followed by a
#: digit (so "0.1" never splits), optionally followed by closing markdown
#: markup (`**`, a backtick), then whitespace or end of string -- and not
#: inside a double-quoted span (an even number of `"` must follow), so a
#: quoted pilot verbatim's own full stop does not end the comment's
#: sentence. The parity rule assumes balanced quotes in each block;
#: `test_generate_defaults_first_sentence.py` holds every declaration to it.
_SENTENCE_SPLIT = re.compile(
    r'(?<!\d)\.(?:\*\*|`)?(?=\s|$)(?=(?:[^"]*"[^"]*")*[^"]*\Z)'
)


@dataclass(frozen=True)
class Declaration:
    key: str
    default: Any
    lo: float | None
    hi: float | None
    status: str
    description: str


def _literal(node: ast.expr) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_literal(elt) for elt in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _literal(k): _literal(v)
            for k, v in zip(node.keys, node.values)
            if k is not None
        }
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _literal(node.operand)
        return -inner if isinstance(inner, (int, float)) else inner
    raise ValueError(f"unsupported literal node: {ast.dump(node)}")


def _first_sentence(comment_block: str) -> str:
    """Markup the split consumed after the period (`.**`, `` .` ``) closes
    a span: if that span opened the sentence it wrapped the whole of it
    and both ends are dropped, otherwise it is put back after the period.
    Markup *before* the period -- `` `SLEW_AZ_DPS`. `` -- is the sentence's
    own and is never touched."""
    text = comment_block.strip()
    match = _SENTENCE_SPLIT.search(text)
    if match is None:
        return text
    sentence = text[: match.start()].strip()
    closing = match.group(0)[1:]
    if closing and sentence.startswith(closing):
        return sentence[len(closing) :].strip() + "."
    return sentence + "." + closing if sentence else sentence


def _join_comment_lines(parts: list[str]) -> str:
    """Join a `#:` block's own lines back into prose. A hand-wrapped
    backtick-quoted dotted path (`` `perception.estimation. `` on one line,
    `` BEARING_SIGMA_DEG` `` on the next) must rejoin with no space, or the
    inserted space reads as a sentence break at the embedded "estimation."
    -- tracked by backtick parity across the accumulated text, since every
    other line boundary in this project's `#:` prose is an ordinary word
    wrap that does want a space."""
    result = ""
    backtick_open = False
    for part in parts:
        if result and not backtick_open:
            result += " "
        result += part
        if part.count("`") % 2 == 1:
            backtick_open = not backtick_open
    return result


def _comment_block_above(lines: list[str], lineno: int) -> str:
    """`lineno` is 1-indexed, the first line of the assignment statement.
    Walk upward collecting contiguous `#:` lines (this project's provenance
    marker, distinct from a plain `#` implementation note), stopping at
    the first line that is not one, or at a blank `#:` paragraph break --
    this project's own convention for separating one constant's bullet
    from a shared intro paragraph above it (see e.g. `belief.attack_run`'s
    three attack-run gates, each a bullet under one shared intro)."""
    collected: list[str] = []
    i = lineno - 2  # 0-indexed line directly above the assignment
    while i >= 0:
        stripped = lines[i].strip()
        if stripped == "#:":
            break
        if stripped.startswith("#:"):
            collected.append(stripped[2:].strip())
            i -= 1
        else:
            break
    collected.reverse()
    return _join_comment_lines(collected)


def _call_target(node: ast.expr) -> str | None:
    """`tuning.real(...)` -> `"real"`, anything else -> `None`."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "tuning"
        and node.func.attr in _ACCESSOR_NAMES
    ):
        return node.func.attr
    return None


def _scan_file(path: Path) -> list[Declaration]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))
    declarations: list[Declaration] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign) or node.value is None:
            continue
        accessor = _call_target(node.value)
        if accessor is None:
            continue
        call = node.value
        assert isinstance(call, ast.Call)

        positional = [_literal(a) for a in call.args]
        keywords = {
            kw.arg: _literal(kw.value) for kw in call.keywords if kw.arg is not None
        }

        key = positional[0]
        default = positional[1]
        if accessor == "table":
            # `table`'s default is a dict literal referenced by name in
            # practice (Stage 3); when it is an inline literal, _literal
            # already produced the dict above.
            pass

        lo = keywords.get("lo")
        hi = keywords.get("hi")
        status = keywords["status"]

        description = _first_sentence(_comment_block_above(lines, node.lineno))
        declarations.append(
            Declaration(
                key=key,
                default=default,
                lo=float(lo) if lo is not None else None,
                hi=float(hi) if hi is not None else None,
                status=status,
                description=description,
            )
        )

    return declarations


def collect_declarations() -> list[Declaration]:
    declarations: list[Declaration] = []
    for path in sorted(_SRC_DIR.rglob("*.py")):
        declarations.extend(_scan_file(path))
    declarations.sort(key=lambda d: d.key)
    return declarations


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise ValueError(f"unsupported TOML value: {value!r}")


def render_toml(declarations: list[Declaration]) -> str:
    lines = [
        "# Generated by body-layer/tools/generate_defaults.py. DO NOT HAND-EDIT.",
        "#",
        "# This file documents the code default for every tunable constant --",
        "# it is a rendering of the `tuning.*` declarations in src/, never the",
        "# authority. The authority is the code comment at the constant itself",
        '# (plans/configurable-constants/plan.md, "Where provenance lives").',
        "#",
        "# To override a value, copy the key you want into config/tuning.toml",
        "# (gitignored, created by you, sparse -- only the keys you change) and",
        "# set PETROBRAIN_TUNING=config/tuning.toml in your run command.",
        "",
    ]
    current_table: str | None = None
    for decl in declarations:
        *table_parts, _name = decl.key.split(".")
        table = ".".join(table_parts)
        if table != current_table:
            lines.append(f"[{table}]")
            current_table = table
        lines.append(f"# {decl.description}")
        bounds = f" | range: {decl.lo} .. {decl.hi}" if decl.lo is not None else ""
        lines.append(f"# status: {decl.status}{bounds}")
        lines.append(f"# source: {table.replace('.', '/')}.py:{_name}")
        lines.append(f"{_name} = {_toml_value(decl.default)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write config/defaults.toml; without this, only check staleness",
    )
    args = parser.parse_args()

    rendered = render_toml(collect_declarations())

    if args.write:
        _DEFAULTS_TOML_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DEFAULTS_TOML_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {_DEFAULTS_TOML_PATH}")
        return 0

    current = (
        _DEFAULTS_TOML_PATH.read_text(encoding="utf-8")
        if _DEFAULTS_TOML_PATH.exists()
        else ""
    )
    if current != rendered:
        print(
            f"{_DEFAULTS_TOML_PATH} is stale -- run with --write to regenerate",
            file=sys.stderr,
        )
        return 1
    print(f"{_DEFAULTS_TOML_PATH} is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
