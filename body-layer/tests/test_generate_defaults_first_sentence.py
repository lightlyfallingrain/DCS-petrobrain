"""`tools/generate_defaults.py`'s first-sentence extraction, case by case.

`config/defaults.toml` renders only the first sentence of each `#:` block,
so an extraction bug silently rewrites what the pilot reads.
`test_tuning_defaults_toml.py` cannot catch one: it proves the committed
file matches a fresh regeneration, which a generator bug passes on both
sides. `[[BL-B80]]` v2 review, finding 1, found two such bugs at once.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent


def _generator() -> ModuleType:
    path = _BODY_LAYER_ROOT / "tools" / "generate_defaults.py"
    spec = importlib.util.spec_from_file_location("generate_defaults", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_defaults"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    return _generator()


def test_period_inside_a_quoted_verbatim_does_not_end_the_sentence(
    gen: ModuleType,
) -> None:
    # SEEN_AIM_HEIGHT_OFFSET_M's comment rendered as `... verbatim: *"no idea.`
    block = 'Pilot, verbatim: *"no idea. let\'s assume on ground"*). Later.'
    assert gen._first_sentence(block) == (
        'Pilot, verbatim: *"no idea. let\'s assume on ground"*).'
    )


def test_closing_backtick_before_the_period_is_kept(gen: ModuleType) -> None:
    # SLEW_EL_DPS rendered as "same source as `SLEW_AZ_DPS." -- span unclosed.
    block = "Elevation's own rate -- same source as `SLEW_AZ_DPS`. Later."
    assert gen._first_sentence(block) == (
        "Elevation's own rate -- same source as `SLEW_AZ_DPS`."
    )


def test_opening_backtick_at_the_start_is_kept(gen: ModuleType) -> None:
    block = "`seen_world_direction`'s own correction. Later."
    assert gen._first_sentence(block) == "`seen_world_direction`'s own correction."


def test_bold_wrapping_the_whole_first_sentence_is_dropped(
    gen: ModuleType,
) -> None:
    assert gen._first_sentence("**Bold lead.** Later.") == "Bold lead."


def test_bold_closing_after_the_period_mid_sentence_is_put_back(
    gen: ModuleType,
) -> None:
    assert gen._first_sentence("A **bold end.** Later.") == "A **bold end.**"


def test_decimal_point_does_not_split(gen: ModuleType) -> None:
    assert gen._first_sentence("Default 0.5 s here. Later.") == "Default 0.5 s here."


def test_every_declaration_comment_has_balanced_double_quotes(
    gen: ModuleType,
) -> None:
    """The quote rule counts `"` parity to the end of the block, so one stray
    `"` would invert it for every period before it."""
    src = _BODY_LAYER_ROOT / "src"
    decls = gen.collect_declarations()
    assert decls, "found no tuning declarations -- the scan itself is broken"
    offenders: list[str] = []
    checked = 0
    for path in sorted(src.rglob("*.py")):
        lines = path.read_text().splitlines()
        for lineno, line in enumerate(lines, start=1):
            if "= tuning." not in line:
                continue
            checked += 1
            block = gen._comment_block_above(lines, lineno)
            if block.count('"') % 2:
                offenders.append(f"{path.relative_to(_BODY_LAYER_ROOT)}:{lineno}")
    assert checked == len(decls), (checked, len(decls))
    assert not offenders, f"odd number of double quotes in: {offenders}"
