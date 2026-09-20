"""Regression tests for `tests/fixtures/vision_calibration.json`.

The fixture carries two source sets. The **authoritative** one
(`source_set == "png-2026-09-17"`, `authoritative == True`) is a nine-range
ladder -- 503 m to 8.89 km, one 12-unit complex, four optics per range,
each range's ground truth taken from an F10 ruler frame -- captured as
lossless PNGs and graded from native-resolution crops. The other
(`jpeg-2026-09-17`) is the earlier compressed-JPEG set, kept for provenance
and deliberately excluded from every assertion below: its artefacts hid
roughly one tier of detail, which is exactly why a first pass concluded
that class was never resolvable at any range.

`visibility.py`'s three angular-radius constants were derived *from* the
authoritative rows on 2026-09-17, so these tests are a conformance check on
that derivation, not an independent confirmation of it. What they are for
is the next edit, not this one: the moment someone changes
`LOWRES`/`MEDRES`/`HIRES_ANGULAR_RADIUS_RAD`, `BINOCULAR_RANGE_MULTIPLIER`
or `NAKED_EYE_RANGE_CAP_M`, `test_computed_tier_matches_ground_truth` fails
and names the range that stopped matching what the screenshots show.

1. `test_fixture_loads_and_has_records` / `test_fixture_record_is_well_formed`
   -- structural checks: required keys present, `objects` non-empty,
   `grades` drawn from the defined vocabulary (or `null`).
2. `test_object_model_resolves_every_object_type` -- smoke check only;
   `profile_for` never raises, so this catches a typo'd/empty unit name,
   not a wrong class (see the research doc's `object_type` provenance
   note).
3. `test_computed_tier_matches_ground_truth` -- the real assertion.
   For every authoritative record, `visibility._achieved_tier` must return
   the tier the screenshots actually show through binoculars at that range.
4. `test_jpeg_set_is_excluded_and_understates` -- pins *why* the superseded
   set is excluded, so a future reader does not "fix" the fixture by
   folding those rows back in: at two of its four ranges the JPEG grade is
   strictly worse than what the PNG ladder shows at a comparable or longer
   range, which is only explicable as compression loss.
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
        "source_set",
        "authoritative",
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


def _authoritative_records() -> list[dict[str, Any]]:
    """The `png-2026-09-17` ladder -- the only rows any threshold claim is
    allowed to rest on. See the module docstring for why the JPEG set is
    excluded rather than merged in."""
    return [r for r in _load_records() if r["authoritative"]]


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


#: **The 8.0-multiplier excursion is over, 2026-09-20.** For part of this
#: design slice `BINOCULAR_RANGE_MULTIPLIER` was 8.0, which made four of
#: this test's own ranges (`C-3990m`, `C-2990m`, `C-1990m`, `C-1500m`)
#: genuinely disagree with the real screenshot ground truth -- this
#: module's own docstring predicts exactly that failure mode for exactly
#: that kind of edit, and those four cases were `xfail`ed rather than
#: edited, since editing the assertion or the fixture would have meant
#: asserting the screenshots show something they do not. The user's final
#: scope change for this slice put `BINOCULAR_RANGE_MULTIPLIER` back to
#: 4.0 -- independently derived this time (a Б-6 6x30's honest 6x
#: magnification times a stabilisation penalty, `optics.py`'s
#: `BINOCULAR_OPTIC` docstring has the arithmetic), not merely restored,
#: but numerically identical to the value every constant in this module
#: was calibrated against. **The `xfail` machinery is removed, not just
#: emptied**, and this file was verified green again by actually running
#: it (not assumed from the numbers matching on paper) -- see
#: `plans/detection-cones-slice1/implementation.md` for that verification.


@pytest.mark.parametrize("record", _authoritative_records(), ids=_record_id)
def test_computed_tier_matches_ground_truth(record: dict[str, Any]) -> None:
    """`_achieved_tier` must agree with what the screenshots show through
    binoculars at this range.

    Uses the *largest* recorded `size_m` in the record -- the
    easiest-to-classify object present, so the group's grade is the grade
    of its most legible member. The mapping from grade to tier is the
    lattice `classification.py` already defines: `speck_no_class` is
    presence (`lowres`), `class_recognizable` is `medres`,
    `type_recognizable` is `hires`.

    This is the test that will break when `visibility.py`'s constants are
    next edited, and the range it names is the range whose ground truth the
    edit contradicts."""
    expected_tier = _tier_for_grade(record["grades"]["binocular"])

    computed_tier, _confidence = visibility._achieved_tier(
        record["range_m"], _largest_size_m(record)
    )

    assert computed_tier == expected_tier, (
        f"at {record['range_m']} m the screenshots show "
        f"{record['grades']['binocular']!r} ({expected_tier}) through "
        f"binoculars, but visibility.py computes {computed_tier!r}"
    )


@pytest.mark.parametrize("record", _authoritative_records(), ids=_record_id)
def test_gate_admits_every_photographed_range(record: dict[str, Any]) -> None:
    """Every range in the ladder showed at least presence through
    binoculars, so `check_visibility`'s outer range gate must admit all of
    them -- including 8.89 km, which the pre-calibration
    `NAKED_EYE_RANGE_CAP_M` of 5000 m silently rejected.

    Recomputes the gate's own arithmetic rather than calling
    `check_visibility`, which would also need an ownship pose, a cockpit
    mask pass and a terrain-LOS database; the range term is the only part
    this ladder has ground truth for."""
    size_m = _largest_size_m(record)
    gate_range_m = min(
        visibility.NAKED_EYE_RANGE_CAP_M,
        (size_m / visibility.NAKED_EYE_GATING_ANGULAR_RADIUS_RAD)
        * visibility.BINOCULAR_RANGE_MULTIPLIER,
    )

    assert record["range_m"] <= gate_range_m, (
        f"{record['range_m']} m was photographed and plainly visible, but "
        f"the gate only reaches {gate_range_m:.0f} m for a {size_m} m object"
    )


def test_jpeg_set_is_excluded_and_understates() -> None:
    """Pins the reason the `jpeg-2026-09-17` rows are excluded from every
    threshold claim above, so nobody folds them back in as extra data.

    Both sets photographed the same kind of target complex on flat desert
    in clear weather. The JPEG set reports `speck_no_class` (presence only)
    at 955 m and 895 m; the lossless ladder reports `type_recognizable` at
    1000 m -- a better grade at a *longer* range, which no physical
    property of the scene explains. Compression loss does."""
    by_set: dict[str, dict[int, str | None]] = {}
    for record in _load_records():
        by_set.setdefault(record["source_set"], {})[record["range_m"]] = record[
            "grades"
        ]["binocular"]

    assert by_set["jpeg-2026-09-17"][955] == "speck_no_class"
    assert by_set["jpeg-2026-09-17"][895] == "speck_no_class"
    assert by_set["png-2026-09-17"][1000] == "type_recognizable"

    assert all(
        not r["authoritative"]
        for r in _load_records()
        if r["source_set"] == "jpeg-2026-09-17"
    )
