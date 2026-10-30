"""Staleness guard for `config/sequences/triggers.md` -- same pattern as
`test_tuning_defaults_toml.py`:
regenerates in memory via the tool's own check mode and fails if the
committed file no longer matches `belief.effector_sequences.
EffectorTrigger`/`TRIGGER_INFO`, rather than drifting silently. It
depends on code only -- not on the Windows-only raw dump or the
hand-edited sequence config -- so it can and must pass without either."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from belief.effector_sequences import TRIGGER_INFO, EffectorTrigger

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent


def test_triggers_md_matches_the_generator() -> None:
    result = subprocess.run(
        [sys.executable, str(_BODY_LAYER_ROOT / "tools" / "render_triggers.py")],
        cwd=_BODY_LAYER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "config/sequences/triggers.md is stale -- run "
        "`python tools/render_triggers.py --write` and commit the result:\n"
        f"{result.stdout}{result.stderr}"
    )


def test_every_trigger_has_a_non_empty_description() -> None:
    assert set(TRIGGER_INFO) == set(EffectorTrigger)
    for trigger, info in TRIGGER_INFO.items():
        assert info.description.strip() != "", f"{trigger} has an empty description"
