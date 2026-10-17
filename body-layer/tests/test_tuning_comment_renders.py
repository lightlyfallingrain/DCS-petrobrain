"""Guard against a cross-key constraint written where the renderer drops it.

`tools/generate_defaults.py` emits **only the first sentence** of a `#:`
comment block into `config/defaults.toml` -- that is deliberate (the pilot
reads a one-line description, not a design essay). The consequence is that
anything load-bearing written *after* the first sentence reaches nobody who
only reads the generated file.

**This has now happened twice, which is why it is a test rather than a note.**
`X-T26`'s review found `FIRE_LIFE_FRACTION_MAX`'s first sentence excluded by a
blank `#:` line, and `BL-B71` shipped
`GUIDANCE_OPTIC_MIN_INTERVAL_S`'s coupling to `HANDS_BUSY_DURATION_S` in its
*second* sentence -- a real constraint between two pilot-editable keys, stated
where the rendered file cannot carry it. Root `CLAUDE.md` names the trap by
name ("check the **rendered** `defaults.toml`, not the `#:` comment it was
generated from") and it recurred anyway, because the rule depends on a reader
remembering it at the moment their attention is on the constant's value.
Retro 2026-10-17, raised independently by the implementer and the reviewer.

**Deliberately narrow.** The check fires only when a later sentence names
*another declared tuning constant* -- i.e. a cross-key coupling, the one class
where a dropped sentence is a correctness problem rather than lost context.
Measured against `main` at the time of writing: a broad obligation-word check
(`must`/`never`/`cannot`) flagged 7 of 25 declarations, nearly all ordinary
explanatory prose, which is exactly the signal-to-noise that gets a test
deleted. This rule flagged **0 of 25**, and would have flagged
`GUIDANCE_OPTIC_MIN_INTERVAL_S` before its fix. A test that cries wolf is worse
than no test; this one is quiet until the specific defect reappears.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _BODY_LAYER_ROOT / "src"

#: An upper-snake identifier long enough not to match prose acronyms (`DCS`,
#: `TOML`, `LOS`). Candidates are then intersected with the set of names
#: actually declared through `tuning.*`, so a mention of a non-tunable
#: module constant is not a finding.
_IDENT = re.compile(r"\b[A-Z][A-Z0-9_]{4,}\b")


def _generator() -> ModuleType:
    """Import `tools/generate_defaults.py` as a module.

    The test reuses the generator's own `_SENTENCE_SPLIT` and
    `_comment_block_above` rather than re-implementing either: a second
    sentence-splitting rule that disagreed with the real one would make this
    test's verdict meaningless, which is the same "verify at the production
    site" point the test exists to enforce.
    """
    path = _BODY_LAYER_ROOT / "tools" / "generate_defaults.py"
    spec = importlib.util.spec_from_file_location("generate_defaults", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_defaults"] = module
    spec.loader.exec_module(module)
    return module


def _declaration_sites(
    gen: ModuleType,
) -> list[tuple[Path, str, str]]:
    """Every `NAME = tuning.<accessor>(...)` site, as (path, name, comment)."""
    sites: list[tuple[Path, str, str]] = []
    for path in sorted(_SRC_DIR.rglob("*.py")):
        lines = path.read_text().splitlines()
        tree = ast.parse("\n".join(lines))
        for node in ast.walk(tree):
            # Both forms occur: a bare `NAME = tuning.real(...)` and the
            # annotated `NAME: Final[float] = tuning.real(...)` this project
            # mostly uses. Matching only `ast.Assign` finds zero sites and
            # makes the whole check silently vacuous -- which is exactly what
            # the first draft of this test did, caught by its own
            # "found no tuning declarations" assertion.
            if isinstance(node, ast.Assign):
                targets: list[ast.expr] = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            else:
                continue
            if not isinstance(value, ast.Call):
                continue
            func = value.func
            if getattr(func, "attr", None) not in gen._ACCESSOR_NAMES:
                continue
            if getattr(getattr(func, "value", None), "id", "") != "tuning":
                continue
            target = targets[0]
            if not isinstance(target, ast.Name):
                continue
            sites.append(
                (path, target.id, gen._comment_block_above(lines, node.lineno))
            )
    return sites


def test_no_cross_key_constraint_hides_after_the_first_sentence() -> None:
    gen = _generator()
    sites = _declaration_sites(gen)
    assert sites, "found no tuning declarations -- the scan itself is broken"

    declared = {name for _, name, _ in sites}
    offenders: list[str] = []

    for path, name, comment in sites:
        sentences = gen._SENTENCE_SPLIT.split(comment.strip())
        head, tail = sentences[0], " ".join(sentences[1:])
        # Only a constraint the rendered file cannot carry *at all* is a
        # finding. A comment may legitimately mention a sibling key again in
        # its later prose, as long as the first sentence -- the only one the
        # generator emits -- already names it. Flagging the re-mention was
        # this test's second wrong draft: it reported
        # GUIDANCE_OPTIC_MIN_INTERVAL_S, whose rendered sentence does carry
        # the HANDS_BUSY_DURATION_S coupling.
        others = sorted(
            {
                m
                for m in _IDENT.findall(tail)
                if m in declared and m != name and m not in head
            }
        )
        if others:
            offenders.append(
                f"{path.relative_to(_BODY_LAYER_ROOT)}: {name}'s comment names "
                f"{', '.join(others)} after its first sentence, so the "
                f"constraint is dropped from config/defaults.toml"
            )

    assert not offenders, (
        "A cross-key constraint is stated where the generator cannot render it.\n"
        "The generator emits only the first sentence of a `#:` block, so move the\n"
        "coupling into that sentence (or restate it there), then regenerate with\n"
        "`python tools/generate_defaults.py --write` and check the rendered file:\n"
        + "\n".join(f"  - {o}" for o in offenders)
    )
