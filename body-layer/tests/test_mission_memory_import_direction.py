"""Decision 1's import direction is structural, not conventional:
`mission_memory` may import `belief`. No module in `belief/` may import
`mission_memory`, with exactly one carved exception: `belief/tool_api.py`
(Stage 5, not yet landed at the time of writing -- so today the allowed-
importer set is simply empty, which this test tolerates)."""

from __future__ import annotations

import re
from pathlib import Path

_BELIEF_DIR = Path(__file__).resolve().parent.parent / "src" / "belief"

#: `belief/tool_api.py` is the one carved exception (plan Decision 1): it
#: is a leaf, the composition root of the brain-facing surface, so a
#: second dependency there cannot create a cycle and cannot let a
#: written-down note re-enter belief's own reasoning path.
_ALLOWED_IMPORTERS = frozenset({"tool_api.py"})

_IMPORT_PATTERN = re.compile(r"^\s*(?:from|import)\s+mission_memory\b", re.MULTILINE)


def test_no_module_in_belief_imports_mission_memory_except_tool_api() -> None:
    violations = []
    for path in sorted(_BELIEF_DIR.glob("*.py")):
        if path.name in _ALLOWED_IMPORTERS:
            continue
        if _IMPORT_PATTERN.search(path.read_text()):
            violations.append(path.name)
    assert violations == [], (
        f"these belief/ modules import mission_memory, which only "
        f"belief/tool_api.py may do: {violations}"
    )
