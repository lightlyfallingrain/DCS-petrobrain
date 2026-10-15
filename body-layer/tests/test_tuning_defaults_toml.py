"""Staleness guard for `config/defaults.toml` -- `plans/configurable-
constants/plan.md`, "Where provenance lives": "A test fails if the
generated file is stale." Regenerates in memory from the current source
and compares against the committed file; a calibration commit that
forgets to regenerate fails this, rather than drifting silently."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent


def test_defaults_toml_matches_the_generator() -> None:
    result = subprocess.run(
        [sys.executable, str(_BODY_LAYER_ROOT / "tools" / "generate_defaults.py")],
        cwd=_BODY_LAYER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "config/defaults.toml is stale -- run "
        "`python tools/generate_defaults.py --write` and commit the result:\n"
        f"{result.stdout}{result.stderr}"
    )
