"""`tools/render_switch_reference.py`'s "Values" column -- the compact
human-readable rendering of `generate_effector_registry.py`'s `values`
field (2026-10-23 follow-up). The staleness test itself is
`test_render_switch_reference.py`; this covers `_format_value_range`/
`_format_values_cell` directly, same `importlib.util` pattern
`test_generate_effector_registry.py` uses."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent


def _renderer() -> ModuleType:
    path = _BODY_LAYER_ROOT / "tools" / "render_switch_reference.py"
    spec = importlib.util.spec_from_file_location("render_switch_reference", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["render_switch_reference"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return _renderer()


def test_short_discrete_list_is_spelled_out(mod: ModuleType) -> None:
    vr = {"kind": "discrete", "values": [0.0, 1.0], "momentary": True}
    assert mod._format_value_range(vr) == "0/1 momentary"


def test_negative_discrete_list_is_spelled_out(mod: ModuleType) -> None:
    vr = {"kind": "discrete", "values": [-1.0, 0.0, 1.0], "momentary": False}
    assert mod._format_value_range(vr) == "-1/0/1"


def test_fractional_discrete_list_keeps_decimals(mod: ModuleType) -> None:
    vr = {"kind": "discrete", "values": [0.0, 0.5], "momentary": False}
    assert mod._format_value_range(vr) == "0/0.5"


def test_long_discrete_list_is_shown_as_a_step_count(mod: ModuleType) -> None:
    vr = {
        "kind": "discrete",
        "values": [round(k * 0.1, 1) for k in range(11)],
        "momentary": False,
    }
    assert mod._format_value_range(vr) == "0-1 (11 steps)"


def test_continuous_with_gain(mod: ModuleType) -> None:
    vr = {"kind": "continuous", "min": 0.0, "max": 1.0, "gain": 0.1}
    assert mod._format_value_range(vr) == "0-1 continuous (gain 0.1)"


def test_continuous_without_gain(mod: ModuleType) -> None:
    vr = {"kind": "continuous", "min": -1.0, "max": 1.0, "gain": None}
    assert mod._format_value_range(vr) == "-1-1 continuous"


def test_unknown_shows_its_reason(mod: ModuleType) -> None:
    vr = {"kind": "unknown", "reason": "no parseable arg_lim field"}
    assert mod._format_value_range(vr) == "unknown: no parseable arg_lim field"


def test_values_cell_is_blank_for_none_or_empty(mod: ModuleType) -> None:
    assert mod._format_values_cell(None) == ""
    assert mod._format_values_cell([]) == ""


def test_values_cell_single_action_has_no_action_prefix(mod: ModuleType) -> None:
    values = [{"kind": "discrete", "values": [0.0, 1.0], "momentary": False}]
    assert mod._format_values_cell(values) == "0/1"


def test_values_cell_multi_action_is_labelled_per_action(mod: ModuleType) -> None:
    values = [
        {"kind": "discrete", "values": [0.0, 1.0], "momentary": True},
        {"kind": "continuous", "min": 0.0, "max": 1.0, "gain": None},
    ]
    assert (
        mod._format_values_cell(values)
        == "action 0: 0/1 momentary; action 1: 0-1 continuous"
    )
