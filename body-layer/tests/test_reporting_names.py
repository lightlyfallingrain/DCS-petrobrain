"""Tests for `perception.reporting_names.reporting_name_for`.

Mirrors `test_object_model.py`'s fixture-only, no-network-I/O posture -- this
module is pure data (a committed TSV) plus a lookup function.
"""

from __future__ import annotations

from perception.reporting_names import reporting_name_for


def test_known_type_resolves_to_its_real_reporting_name() -> None:
    # "5p73 s-125 ln" -> "SA-3 launcher" is one of the rows this module's
    # data file (data/dcs_type_to_reporting_name.tsv) is built from --
    # see aircraft-layer/research/2026-09-09-object-model-keyword-
    # coverage.md for provenance.
    assert reporting_name_for("5p73 s-125 ln") == "SA-3 launcher"


def test_lookup_is_case_insensitive() -> None:
    assert reporting_name_for("5P73 S-125 LN") == "SA-3 launcher"


def test_unmapped_type_returns_none() -> None:
    # Not a real DCS object_type -- must degrade to None, not raise, so
    # object_model.py's fallback-to-raw-table behaviour has something to
    # fall back from.
    assert reporting_name_for("SomeFutureDCSUnit-2027") is None


def test_irregular_type_resolves_to_a_regular_reporting_name() -> None:
    # The exact case object_model.py's reporting-name table exists for:
    # "CHAP_T90M" (irregular raw type) -> "T-90M" (regular reporting name).
    assert reporting_name_for("CHAP_T90M") == "T-90M"


def test_wwii_type_resolves_to_its_old_prefixed_reporting_name() -> None:
    # ED's own WWII-era-unit naming convention -- object_model.py's guard
    # relies on this literal "Old " prefix being present.
    assert reporting_name_for("Bedford_MWD") == "Old military truck"
