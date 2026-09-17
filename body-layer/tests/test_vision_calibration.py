"""Regression tests for `tests/fixtures/vision_calibration.json` --
`plans/vision-range-calibration/plan.md` Pass 1.

**No behaviour change this pass** (plan's "No constant changes this pass",
user decision 2026-09-17): `perception/visibility.py` and
`perception/naked_eye_source.py` are untouched. This file exists to pin
what that unchanged code computes today against the 23-screenshot
ground-truth set, so a future edit to those modules' constants shows up as
a diff here rather than silently drifting, and so the known
code-vs-ground-truth divergence this milestone exists to document is
visible from the test file alone, not just from the research doc's prose.

Three things, matching the plan's "Regression tests" section exactly:

1. `test_fixture_is_well_formed` -- the fixture loads, every record has the
   required keys, `objects` is non-empty, `grades` only uses the defined
   vocabulary (or `null`), and `object_model.profile_for` does not raise on
   any referenced `object_type` (a smoke check against a typo'd unit name,
   not a classification-correctness claim -- `profile_for` always returns a
   profile, falling back to `object_model.DEFAULT_SIZE_M`/`DEFAULT_OP_CLASS`
   for an unmatched type rather than raising, so this only catches
   structural mistakes like an empty string).
2. `test_pin_todays_achieved_tier` -- for every record with a non-null
   `binocular` grade, pins `visibility._achieved_tier(range_m, size_m)`
   (using the *largest* recorded `size_m` in that record's `objects` list --
   the easiest-to-classify object, so if it doesn't resolve to a tier,
   nothing smaller in the group does either) to whatever tier the code
   actually returns today. A pin, not a correctness claim: its only job is
   to fail the moment someone edits `visibility.py`'s constants without
   updating this test.
3. `test_known_divergence_binocular_overclaims_class` -- explicitly asserts
   the documented gap between what `_achieved_tier` computes and what the
   screenshots showed: at every tested binocular range (895 m-2.42 km,
   spanning both Complex A and Complex B), ground truth topped out at
   `speck_no_class` (presence, no class ever resolved) while the code
   claims `medres` (class) or `hires` (type). This is a normal passing
   assertion on a *known* mismatch, not `xfail`/`skip` -- see the module
   docstring above and the plan's Regression tests section for why: a
   reader must be able to see the disagreement by reading the test, and if
   Pass 2's retune later makes this assertion wrong, that is the signal
   Pass 2 succeeded and this test needs deleting/updating as part of that
   change, not silently rotting green.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from perception import object_model, visibility

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_FIXTURE_PATH = _FIXTURES_DIR / "vision_calibration.json"

#: The grade vocabulary the plan's "Fixture format" section defines, plus
#: `null` for an optic not photographed at that range.
_VALID_GRADES: frozenset[str] = frozenset(
    {
        "nothing",
        "marginal_speck",
        "speck_no_class",
        "class_recognizable",
        "type_recognizable",
    }
)

_REQUIRED_RECORD_KEYS: frozenset[str] = frozenset(
    {
        "complex",
        "range_m",
        "bearing_deg_mag",
        "date",
        "conditions",
        "objects",
        "grades",
        "source_images",
        "conservative_note",
    }
)

_REQUIRED_GRADE_KEYS: frozenset[str] = frozenset(
    {"naked_eye", "binocular", "9k113_wide", "9k113_narrow"}
)

#: Maps a fixture grade to the `visibility._achieved_tier` tier name it
#: corresponds to, for comparing ground truth against computed output.
#: `"nothing"`/`"marginal_speck"` have no tier equivalent -- below even
#: `lowres` (bare presence) -- so they are intentionally absent from this
#: map; `_tier_for_grade` raises on them, which is by design (no fixture
#: record in this pass has a non-null `binocular` grade of `"nothing"` or
#: `"marginal_speck"`, so the divergence test never needs one).
_GRADE_TO_TIER: dict[str, str] = {
    "speck_no_class": "lowres",
    "class_recognizable": "medres",
    "type_recognizable": "hires",
}


def _load_records() -> list[dict[str, Any]]:
    with _FIXTURE_PATH.open() as f:
        data = json.load(f)
    records: list[dict[str, Any]] = data["records"]
    return records


def _tier_for_grade(grade: str) -> str:
    return _GRADE_TO_TIER[grade]


def _largest_size_m(record: dict[str, Any]) -> float:
    return float(max(obj["size_m"] for obj in record["objects"]))


def _record_id(record: dict[str, Any]) -> str:
    return f"{record['complex']}-{record['range_m']}m"


def test_fixture_loads_and_has_records() -> None:
    records = _load_records()
    assert len(records) > 0


@pytest.mark.parametrize("record", _load_records(), ids=_record_id)
def test_fixture_record_is_well_formed(record: dict[str, Any]) -> None:
    missing_keys = _REQUIRED_RECORD_KEYS - record.keys()
    assert not missing_keys, f"record missing keys: {missing_keys}"

    assert isinstance(record["objects"], list)
    assert len(record["objects"]) > 0
    for obj in record["objects"]:
        assert "object_type" in obj
        assert isinstance(obj["object_type"], str)
        assert obj["object_type"] != ""
        assert isinstance(obj["size_m"], (int, float))
        assert obj["size_m"] > 0

    grades = record["grades"]
    missing_grade_keys = _REQUIRED_GRADE_KEYS - grades.keys()
    assert not missing_grade_keys, f"record missing grade keys: {missing_grade_keys}"
    for optic, grade in grades.items():
        assert optic in _REQUIRED_GRADE_KEYS
        assert grade is None or grade in _VALID_GRADES, (
            f"{optic!r} grade {grade!r} is not in the defined vocabulary"
        )

    assert isinstance(record["source_images"], list)
    assert len(record["source_images"]) > 0


@pytest.mark.parametrize("record", _load_records(), ids=_record_id)
def test_object_model_resolves_every_object_type(record: dict[str, Any]) -> None:
    """Smoke check that the transcription didn't typo a unit name badly
    enough to break the lookup mechanism -- `profile_for` never raises (it
    falls back to `object_model.DEFAULT_SIZE_M`/`DEFAULT_OP_CLASS` for any
    unmatched string), so this only confirms every `object_type` is a
    non-empty string `profile_for` can accept, not that it resolves to a
    *correct* class -- see the research doc's "object_type provenance" note
    for which of these fall through to the default today."""
    for obj in record["objects"]:
        profile = object_model.profile_for(obj["object_type"])
        assert profile.size_m > 0
        assert profile.op_class != ""


@pytest.mark.parametrize(
    "record",
    [r for r in _load_records() if r["grades"]["binocular"] is not None],
    ids=_record_id,
)
def test_pin_todays_achieved_tier(record: dict[str, Any]) -> None:
    """Pins `_achieved_tier`'s current output for this record -- fails the
    moment `visibility.py`'s constants change without this test being
    updated, per the plan's "No constant changes this pass" decision. Not a
    correctness claim (see module docstring)."""
    tier, _confidence = visibility._achieved_tier(
        record["range_m"], _largest_size_m(record)
    )

    # Pinned today, 2026-09-17, against visibility.py as it stands
    # (LOWRES/MEDRES/HIRES_ANGULAR_RADIUS_RAD, BINOCULAR_RANGE_MULTIPLIER,
    # NAKED_EYE_RANGE_CAP_M all unchanged this pass):
    expected_tier_by_range_m = {
        1890: "medres",
        2420: "medres",
        955: "hires",
        895: "hires",
    }
    assert tier == expected_tier_by_range_m[record["range_m"]]


@pytest.mark.parametrize(
    "record",
    [r for r in _load_records() if r["grades"]["binocular"] is not None],
    ids=_record_id,
)
def test_known_divergence_binocular_overclaims_class(record: dict[str, Any]) -> None:
    """The central finding this milestone exists to document (plan's "The
    central finding" section): `visibility.py` models binocular
    observation, and at every binocular-photographed range in this dataset
    (895 m-2.42 km, both complexes), ground truth topped out at
    `speck_no_class` -- class was never actually resolved -- while
    `_achieved_tier` claims `medres` (class) or `hires` (type), 1-2 tiers
    more than the screenshots support. This assertion is expected to keep
    passing until Pass 2 retunes the constants; when it does, this test
    (not `visibility.py`) is what needs updating, and that update is itself
    the signal Pass 2 succeeded."""
    ground_truth_grade = record["grades"]["binocular"]
    assert ground_truth_grade == "speck_no_class", (
        "this dataset's binocular ground truth never exceeded "
        "speck_no_class at any tested range -- if a new row's grade is "
        "better than that, the divergence claim below may no longer hold "
        "for it and this test needs revisiting, not blind extension"
    )
    ground_truth_tier = _tier_for_grade(ground_truth_grade)

    computed_tier, _confidence = visibility._achieved_tier(
        record["range_m"], _largest_size_m(record)
    )

    assert computed_tier != ground_truth_tier
    assert ground_truth_tier == "lowres"
    assert computed_tier in ("medres", "hires")
