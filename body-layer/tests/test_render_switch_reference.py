"""Staleness guard for `config/sequences/switch-reference.md` -- same
pattern as `test_tuning_defaults_toml.py`: regenerates in memory via the
tool's own check mode and fails if the committed file no longer matches
`config/effectors-raw.toml` and `config/sequences/effectors.toml`,
rather than drifting silently."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent


def test_switch_reference_matches_the_generator() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(_BODY_LAYER_ROOT / "tools" / "render_switch_reference.py"),
        ],
        cwd=_BODY_LAYER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "config/sequences/switch-reference.md is stale -- run "
        "`python tools/render_switch_reference.py --write` and commit the result:\n"
        f"{result.stdout}{result.stderr}"
    )
