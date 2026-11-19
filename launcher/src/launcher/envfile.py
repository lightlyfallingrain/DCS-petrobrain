"""Read `run-scripts/petrobrain.env`: shell `export KEY=value` lines, no expansion.

The run scripts `source` the file themselves; the launcher only needs the values to display them,
to find `DEFAULT_SERVICES`, and to look up option values (`OPT_<SERVICE>_<FLAG>`).
"""

from __future__ import annotations

import re

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def parse_env(text: str) -> dict[str, str]:
    """Return KEY -> value for every assignment line, in file order. Later lines win."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE.match(line)
        if m is None:
            continue
        key, value = m.group(1), m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            # Unquoted: a trailing ` # comment` is a shell comment, not part of the value.
            value = re.sub(r"\s+#.*$", "", value)
        out[key] = value
    return out


def default_services(env: dict[str, str]) -> list[str]:
    """Names in `DEFAULT_SERVICES` (the 2026-11-17 spec's singular `DEFAULT_SERVICE` also read)."""
    raw = env.get("DEFAULT_SERVICES", env.get("DEFAULT_SERVICE", ""))
    return [name.strip() for name in raw.split(",") if name.strip()]
