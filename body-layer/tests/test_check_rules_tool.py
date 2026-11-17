"""`tools/check_rules.py` -- the rule checker (`[[BL-17]]`, "Rule checker,
without flying"). Runs the tool as a subprocess, the same way
`test_render_triggers.py` runs its tool. The wording check needs
audio-adapter's venv; these tests point `--adapter-python` at a missing
path so they cover the load and dry-run checks on their own."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent
_TOOL = _BODY_LAYER_ROOT / "tools" / "check_rules.py"


def _check(rules_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_TOOL),
            str(rules_dir),
            "--adapter-python",
            str(rules_dir / "no-such-python"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_the_shipped_rules_check_clean() -> None:
    result = _check(_BODY_LAYER_ROOT / "config" / "rules")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "wording not checked" in result.stderr


def test_each_kind_of_mistake_is_reported(tmp_path: Path) -> None:
    (tmp_path / "bad.lua").write_text(
        'when.speech("typo", "zap", "flight_control", function(s)\n'
        "  flight.increment_headng(10)\n"
        "end)\n"
        'when.speech("wrong_type", "zip", "flight_control", function(s)\n'
        '  local r = flight.increment_heading("ten")\n'
        "end)\n"
        'when.speech("bad_category", "zop", "flying", function(s) end)\n'
        'when.speech("no_switch", "zup", "always", function(s)\n'
        '  effector.write("no_such_switch", "on")\n'
        "end)\n",
        encoding="utf-8",
    )
    (tmp_path / "syntax.lua").write_text(
        'when.speech("x", "y", "always", function(s) say("x" end)\n',
        encoding="utf-8",
    )
    result = _check(tmp_path)
    assert result.returncode == 1
    out = result.stdout
    assert "syntax.lua:" in out and "')' expected" in out
    assert "rule 'typo'" in out and "increment_headng" in out and ":2:" in out
    assert "rule 'wrong_type': bad call to increment_heading()" in out
    assert "rule 'bad_category': when.speech: unknown category 'flying'" in out
    assert "rule 'no_switch': effector.write('no_such_switch', 'on')" in out
