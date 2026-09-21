"""Tests for `perception.object_model.profile_for`.

Mirrors `test_association.py`'s fixture-only, no-network-I/O posture --
`object_model.py` is pure data plus a lookup function.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from perception.object_model import (
    DEFAULT_OP_CLASS,
    DEFAULT_SIZE_M,
    ObjectTypeProfile,
    apparent_extent_m,
    profile_for,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"

#: Known L/W/H triple with `L != W` -- `plans/aspect-aware-profiles/plan.md`'s
#: own mandated test rule: `apparent_extent_m` must be exercised at a
#: non-axis-aligned angle (45 deg), not just 0/90, since those two are
#: exactly the fixed points of `sin`/`cos` that hid the original
#: cubic-fallback bug (see that plan's "Correction, coordinator review"
#: section). `length_m=10` (long axis), `width_m=4` (narrow axis),
#: `height_m=6` (taller than the narrow axis, shorter than the long one),
#: so the `max(projected_width, height)` branch is exercised meaningfully
#: at more than one angle.
_DIMENSIONED_PROFILE = ObjectTypeProfile(
    size_m=10.0, op_class="OP_TEST", length_m=10.0, width_m=4.0, height_m=6.0
)

#: A profile with no measured dimensions at all -- the common case for
#: every un-migrated row in the real tables.
_UNDIMENSIONED_PROFILE = ObjectTypeProfile(size_m=5.5, op_class="OP_TEST")


def test_apparent_extent_nose_on_is_the_narrow_width() -> None:
    # aspect=0: viewed from directly ahead/astern -- the narrow width
    # dominates, and it's still less than height, so height wins.
    assert apparent_extent_m(_DIMENSIONED_PROFILE, 0.0) == pytest.approx(6.0)


def test_apparent_extent_broadside_is_the_long_length() -> None:
    # aspect=90: broadside -- the full length dominates over height.
    assert apparent_extent_m(_DIMENSIONED_PROFILE, 90.0) == pytest.approx(10.0)


def test_apparent_extent_at_45_degrees_is_the_true_trig_projection() -> None:
    # The mandated non-axis-aligned check. At 45 deg the projected width is
    # length*sin(45)+width*cos(45) = 10*0.70711 + 4*0.70711 = 9.8995, still
    # more than height (6.0), so this is the value that must come out --
    # NOT a naive average of the 0/90 answers (8.0) and NOT the un-projected
    # size_m (10.0), either of which a broken formula could coincidentally
    # produce.
    expected = 10.0 * abs(math.sin(math.radians(45.0))) + 4.0 * abs(
        math.cos(math.radians(45.0))
    )
    assert expected == pytest.approx(9.8994949)
    assert apparent_extent_m(_DIMENSIONED_PROFILE, 45.0) == pytest.approx(expected)


def test_apparent_extent_at_135_degrees_mirrors_45() -> None:
    # A second non-axis-aligned angle, on the other side of broadside --
    # |sin|/|cos| make this symmetric with the 45 deg case.
    assert apparent_extent_m(_DIMENSIONED_PROFILE, 135.0) == pytest.approx(
        apparent_extent_m(_DIMENSIONED_PROFILE, 45.0)
    )


@pytest.mark.parametrize("aspect_deg", [0.0, 30.0, 45.0, 60.0, 90.0, 135.0, 180.0])
def test_apparent_extent_without_dimensions_returns_size_m_unchanged(
    aspect_deg: float,
) -> None:
    # Regression guard for the original cubic-fallback defect: a profile
    # with no measured dimensions must return plain size_m at EVERY aspect
    # tested, including 45 deg -- 0/90 alone would have hidden the bug (see
    # the plan's "Correction, coordinator review" section: the cube formula
    # agreed with size_m only at those two fixed points and diverged by up
    # to 41% everywhere else).
    assert apparent_extent_m(_UNDIMENSIONED_PROFILE, aspect_deg) == pytest.approx(5.5)


def test_apparent_extent_with_dimensions_but_unknown_aspect_returns_size_m() -> None:
    # aspect_deg=None ("unknown aspect this tick") must not be coerced to a
    # guessed angle -- falls back to size_m even though real dimensions
    # exist, exactly like the no-dimensions case above.
    assert apparent_extent_m(_DIMENSIONED_PROFILE, None) == pytest.approx(10.0)


@pytest.mark.parametrize("aspect_deg", [0.0, 30.0, 45.0, 60.0, 90.0, 135.0, 180.0])
def test_every_unmigrated_table_row_is_unaffected_by_aspect(aspect_deg: float) -> None:
    # Full sweep over every real, currently-shipped profile except the two
    # S-300 rows this pass migrated -- confirms the ~150 unmigrated rows'
    # source-literal ObjectTypeProfile(size_m=X, op_class=Y) calls really do
    # carry no dimensions, at a real non-axis-aligned angle, not just 0/90.
    sample_object_types = [
        "Ural-4320",
        "T-72B",
        "Infantry AK-74",
        "5p73 s-125 ln",
        "Kub 2P25 ln",
        "Shilka",
        "MOSCOW",
    ]
    for object_type in sample_object_types:
        profile = profile_for(object_type)
        assert apparent_extent_m(profile, aspect_deg) == pytest.approx(profile.size_m)


def test_s300_40b6m_tr_has_real_dimensions_and_op_lrsam() -> None:
    # The tall-mast row this pass migrated -- see body-layer/research/
    # 2026-09-21-s300-radar-dimensions.md for sourcing.
    profile = profile_for("S-300PS 40B6M tr")

    assert profile.length_m == pytest.approx(10.0)
    assert profile.width_m == pytest.approx(3.0)
    assert profile.height_m == pytest.approx(24.0)
    assert profile.op_class == "OP_LRSAM"


def test_s300_64h6e_sr_has_real_dimensions_and_op_lrsam() -> None:
    # The low-trailer row this pass migrated -- see body-layer/research/
    # 2026-09-21-s300-radar-dimensions.md for sourcing.
    profile = profile_for("S-300PS 64H6E sr")

    assert profile.length_m == pytest.approx(13.2)
    assert profile.width_m == pytest.approx(3.0)
    assert profile.height_m == pytest.approx(10.0)
    assert profile.op_class == "OP_LRSAM"


# The fixture's "ground" bucket is a full enumeration of every real
# `dcs_object_type` in the 595-row catalogue that is neither a ship, a WWII
# unit, nor an aircraft (see the fixture's own `_comment` for exactly how
# that categorization is done, independent of what perception.object_model
# currently classifies -- the thing the previous version of this fixture got
# wrong). Measured against that full 316-type population when this floor was
# set: 190 classified (~60.1%, see test_coverage_floor_against_real_type_
# sample below). The floor is set well below that measured rate -- a
# *regression guard*, not a target -- so it has room to move (a future
# keyword edit shifting a handful of matches, or DCS adding/renaming a few
# types on a future TSV refresh) without failing on noise, while still
# catching a real regression (e.g. the reporting-name table being silently
# reverted, broken, or its data file emptied -- which would drop coverage
# by tens of points, not a couple).
#
# Deliberately scoped to the "ground" bucket only, not a blended percentage
# across every bucket in the fixture -- a blended number is exactly the
# metric that hid this module's original ground-unit coverage gap (measured
# ~21% against the full real catalogue) behind a healthier-looking overall
# number, since aircraft/WWII/deliberately-out-of-scope types this module
# never targets dominated the denominator. See
# aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md's
# Addendum for that history. The 60.1% figure above is this session's own
# independently-recomputed measurement (a full-enumeration script against
# the same 595-row catalogue, not a curated sample) -- close to but not
# bit-identical to the research doc's previously-recorded 64.5%, expected
# for the same reason that doc's own two prior estimates (21% vs 24%)
# didn't match exactly either: both are honest, independently-derived
# ground/air/wwii categorizations of the same underlying data, not the same
# script. `perception.object_model` and `perception.reporting_names`
# themselves were not touched to produce this number.
_MIN_GROUND_COVERAGE_FRACTION = 0.5


def test_unmatched_object_type_falls_back_to_default_profile() -> None:
    profile = profile_for("SomeUnrecognizedUnit-99")

    assert profile.size_m == DEFAULT_SIZE_M
    assert profile.op_class == DEFAULT_OP_CLASS


def test_truck_keyword_matches_ural() -> None:
    # Worked example table in plans/pb1.5-naked-eye-detection/plan.md's
    # Proposed Defaults section: Ural truck -> 6 m / OP_TRUCK.
    profile = profile_for("Ural-4320")

    assert profile.size_m == 6.0
    assert profile.op_class == "OP_TRUCK"


def test_armored_keyword_matches_t72() -> None:
    # Worked example table: T-72 -> 7 m / OP_ARMORED.
    profile = profile_for("T-72B")

    assert profile.size_m == 7.0
    assert profile.op_class == "OP_ARMORED"


def test_infantry_keyword() -> None:
    # Worked example table: infantry -> 1.8 m.
    profile = profile_for("Infantry AK-74")

    assert profile.size_m == 1.8
    assert profile.op_class == "OP_INFANTRY"


def test_sa3_keyword() -> None:
    # Worked example table: SA-3 launcher -> 9 m. "SA-3 Launcher" is not a
    # real DCS object_type (that was the bug this test used to mask, see
    # test_ship_keyword below) -- "5p73 s-125 ln" is the real SA-3 launcher
    # type name from ED's own type list (aircraft-layer/research/
    # 2026-09-09-object-model-keyword-coverage.md).
    profile = profile_for("5p73 s-125 ln")

    assert profile.size_m == 9.0
    assert profile.op_class == "OP_SRSAM"


def test_sa6_keyword_is_mrsam_not_srsam() -> None:
    # SA-6 (Kub) is the table's one OP_MRSAM entry, distinct from the other
    # SA-*/OP_SRSAM rows -- worth a direct check since it's easy to
    # copy-paste the wrong class when re-deriving a keyword. Real DCS type
    # name: "Kub 2P25 ln" (launcher component).
    profile = profile_for("Kub 2P25 ln")

    assert profile.op_class == "OP_MRSAM"


def test_sa6_keyword_does_not_match_unrelated_kubelwagen() -> None:
    # "kub " (with trailing space) was chosen specifically to avoid matching
    # "Kubelwagen_82" (a real DCS type -- a WWII-era civilian car, nothing to
    # do with the Kub/SA-6 SAM system). Regression guard against a future
    # edit narrowing this back to a bare "kub" substring.
    profile = profile_for("Kubelwagen_82")

    assert profile.op_class == DEFAULT_OP_CLASS


def test_lookup_is_case_insensitive() -> None:
    profile = profile_for("ural-4320")

    assert profile.op_class == "OP_TRUCK"


def test_hyphenated_zu23_keyword_is_not_split_by_a_word_tokenizer() -> None:
    # This is the reason object_model.py uses substring containment rather
    # than association.py's word-tokenized ([a-z0-9]+) overlap: a tokenizer
    # would split "ZU-23" into "zu"/"23" and lose the compound identifier.
    profile = profile_for("ZU-23 Emplacement")

    assert profile.op_class == "OP_ZU23"


def test_shilka_keyword_takes_precedence_over_generic_class() -> None:
    profile = profile_for("ZSU-23-4 Shilka")

    assert profile.op_class == "OP_SPAAG"


def test_ship_keyword() -> None:
    # "Grisha corvette" (the string this test used to assert against) is not
    # a real DCS object_type -- it's Petrovich's *reporting name* for the
    # real type "ALBATROS" (aircraft-layer/research/
    # 2026-09-09-object-model-keyword-coverage.md). It matched the old
    # keyword table ("corvette" was one of six English hull-class words) by
    # construction, which is exactly why the table's real defect --
    # `object_type` never carries an English hull-class word, so OP_SHIP was
    # unreachable against real data -- went undetected. "MOSCOW" (the real
    # DCS type for the Slava-class cruiser) is used here instead so this
    # test would actually fail if OP_SHIP regresses to keying on
    # reporting-name-shaped words again.
    profile = profile_for("MOSCOW")

    assert profile.size_m == 100.0
    assert profile.op_class == "OP_SHIP"


def test_ship_keyword_matches_second_real_type_name() -> None:
    # A second, differently-shaped real ship object_type (a hyphenated,
    # lowercase, multi-word compound rather than a single uppercase token)
    # so this category isn't anchored on only one naming style.
    profile = profile_for("leander-gun-achilles")

    assert profile.op_class == "OP_SHIP"


def test_reporting_name_resolution_classifies_an_irregular_raw_type() -> None:
    # "CHAP_T90M" contains no raw-table keyword substring at all (no
    # "t-90" -- the raw type name is irregular), which is exactly the
    # coverage gap the reporting-name table closes: it resolves to
    # Petrovich's reporting name "T-90M" (regular) and matches there.
    profile = profile_for("CHAP_T90M")

    assert profile.size_m == 7.0
    assert profile.op_class == "OP_ARMORED"


def test_reporting_name_resolution_matches_a_truck_named_reporting_name() -> None:
    # "ATZ-5" itself contains no raw-table keyword ("ural" is not a raw
    # substring of "ATZ-5"), but its reporting name is "Ural fuel truck".
    profile = profile_for("ATZ-5")

    assert profile.size_m == 6.0
    assert profile.op_class == "OP_TRUCK"


def test_raw_table_takes_precedence_over_reporting_name_table() -> None:
    # "MOSCOW" already matches the raw table's "moscow" OP_SHIP keyword.
    # Its reporting name ("Slava cruiser") would also match a hull-class
    # word if the reporting-name table had one -- this asserts the raw
    # table is tried first and wins, per profile_for's documented order.
    profile = profile_for("MOSCOW")

    assert profile.op_class == "OP_SHIP"


def test_wwii_reporting_name_does_not_get_classified_by_a_modern_keyword() -> None:
    # "Bedford_MWD" resolves (via the mapping) to reporting name "Old
    # military truck" -- WWII, but it contains the same "truck" substring
    # the modern-unit OP_TRUCK keyword uses. The WWII-prefix guard in
    # profile_for must skip the whole reporting-name pass for this type, or
    # this would wrongly return OP_TRUCK.
    profile = profile_for("Bedford_MWD")

    assert profile.op_class == DEFAULT_OP_CLASS


def test_ss26_launcher_is_truck_not_sam() -> None:
    # SS-26 (Iskander) is a surface-to-*surface* ballistic missile TEL, not
    # a SAM -- classifying it OP_SRSAM/OP_MRSAM just because its reporting
    # name ends in "launcher" would be the same domain-mismatch trap as the
    # original OP_SHIP bug (see object_model.py's
    # _REPORTING_NAME_KEYWORD_PROFILES docstring).
    profile = profile_for("CHAP_9K720_HE")

    assert profile.op_class == "OP_TRUCK"


def test_unmapped_type_still_falls_back_to_raw_table_behaviour() -> None:
    # Not in the reporting-name mapping at all -- must behave exactly as it
    # did before that mapping existed (raw-table match, here none, so
    # default).
    profile = profile_for("SomeFutureDCSUnit-2027")

    assert profile.op_class == DEFAULT_OP_CLASS


def test_coverage_floor_against_real_type_sample() -> None:
    """Per-entry regression guard plus a **per-bucket** coverage measurement,
    against `tests/fixtures/object_type_coverage_sample.json`'s committed
    sample of real DCS `object_type` strings (see that file's `_comment` and
    `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`
    for provenance). This is the test the review required: a measurement
    against real data, not a fabricated string that would pass even if the
    underlying keyword table stopped matching anything real (exactly how
    the old `test_ship_keyword` masked the OP_SHIP domain-mismatch bug that
    fix addressed).

    Bucketed rather than one blended percentage, because a blended number is
    exactly what hid this module's original ground-unit coverage gap: the
    "78% fallback" headline looked like it meant "mostly unclassified junk",
    when the residual was actually 132 aircraft (never targeted) + 56 WWII
    units (deliberately excluded) + 276 modern ground units (thinly covered,
    ~21% -- the real gap). See the research doc's Addendum.

    - `"ground"` (every real `dcs_object_type` that is neither a ship, a
      WWII unit, nor an aircraft -- combat vehicles/systems this module
      targets *and* real ground/support types it deliberately hasn't
      attempted to classify, e.g. towed AA/mortar pieces, SAM-system radars
      beyond the one named in scope, static structures, airfield support
      equipment): the coverage floor applies here, and only here. This is a
      **full enumeration** of that real population (see the fixture's own
      `_comment`), not a curated sample -- every currently-unclassified real
      ground type carries `expected_op_class: null` here, so the coverage
      number below is an actual measurement, not a value pinned at 1.0 by
      construction (the defect this fixture used to have, and the reason it
      was rebuilt -- there used to be a separate `"ground_deferred"` bucket
      for the deliberately-uncovered types, excluded from this floor's
      denominator; folded into `"ground"` because "a real ground type we
      haven't classified yet" is exactly what this metric measures).
    - `"ship"`: already its own fully-covered category (not a "ground
      unit"), asserted at 100% as a plain regression guard, not the metric
      under test.
    - `"air"`, `"wwii"` (aircraft/helicopters/UAVs; ED's `"Old ..."`-prefixed
      WWII reporting names): must stay at the fallback. Reported/asserted
      separately, not blended into the ground floor, because covering them
      was never this module's goal -- see object_model.py's
      `_REPORTING_NAME_KEYWORD_PROFILES` docstring for the reasoning.

    Every entry is checked individually first (both the "should classify"
    and the "should legitimately fall back" cases), so this also catches a
    keyword accidentally over-matching an out-of-scope type -- e.g. a "Old
    military truck" WWII type wrongly picked up by a broad `"truck"`
    keyword aimed at modern units, or an aircraft type wrongly picked up by
    an armor keyword.
    """
    fixture = json.loads(
        (_FIXTURES_DIR / "object_type_coverage_sample.json").read_text()
    )
    entries = fixture["entries"]

    mismatches: list[str] = []
    classified_by_bucket: dict[str, int] = {}
    total_by_bucket: dict[str, int] = {}
    for entry in entries:
        object_type = entry["object_type"]
        bucket = entry["bucket"]
        expected_op_class = entry["expected_op_class"] or DEFAULT_OP_CLASS
        actual_op_class = profile_for(object_type).op_class
        if actual_op_class != expected_op_class:
            mismatches.append(
                f"{object_type!r} ({bucket}): expected {expected_op_class!r}, "
                f"got {actual_op_class!r}"
            )
        total_by_bucket[bucket] = total_by_bucket.get(bucket, 0) + 1
        if actual_op_class != DEFAULT_OP_CLASS:
            classified_by_bucket[bucket] = classified_by_bucket.get(bucket, 0) + 1

    assert not mismatches, "\n".join(mismatches)

    ground_classified = classified_by_bucket.get("ground", 0)
    ground_total = total_by_bucket.get("ground", 0)
    ground_coverage = ground_classified / ground_total
    assert ground_coverage >= _MIN_GROUND_COVERAGE_FRACTION, (
        f"modern-ground-unit coverage dropped to {ground_coverage:.3f} "
        f"({ground_classified}/{ground_total}), below floor "
        f"{_MIN_GROUND_COVERAGE_FRACTION}"
    )

    ship_classified = classified_by_bucket.get("ship", 0)
    ship_total = total_by_bucket.get("ship", 0)
    assert ship_classified == ship_total, (
        f"OP_SHIP coverage regressed: {ship_classified}/{ship_total} classified"
    )

    # air / wwii must stay entirely at the fallback -- any of these
    # unexpectedly getting classified means a keyword aimed at modern
    # ground units is over-matching out-of-scope real types.
    for out_of_scope_bucket in ("air", "wwii"):
        classified = classified_by_bucket.get(out_of_scope_bucket, 0)
        assert classified == 0, (
            f"{out_of_scope_bucket!r} bucket unexpectedly classified "
            f"{classified} entries -- a keyword is over-matching out-of-scope "
            f"types (see this test's docstring)"
        )


def test_bare_tank_keyword_is_not_reintroduced() -> None:
    """A bare "tank" substring must never classify a type as armour.

    Measured against all 595 real DCS unit type names, "tank" scored zero true
    positives and eight false positives: fuel trailers, fuel trucks, railway
    tank cars, and an aerial tanker. Real armour never carries "tank" in its
    DCS type name. This guards the deletion, since "tank" reads like an
    obviously-correct armour keyword to anyone extending the table.
    """
    for object_type in (
        "ATZ-60_TANK",
        "TZ-22_TANK",
        "M978 HEMTT Tanker",
        "S-3B Tanker",
        "Tankcartrinity",
        "German_tank_wagon",
    ):
        assert profile_for(object_type).op_class != "OP_ARMORED", object_type
