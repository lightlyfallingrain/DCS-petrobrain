"""Tests for the plan's central invariant: hidden/late-activation groups
must never appear in the crew-available tree. The primary test here uses
the committed synthetic fixture (`fixtures/synthetic_mission.py`) rather
than the gitignored real sample, since this is the one property that must
be provable in every checkout -- see `plans/mission-interpreter/plan.md`'s
MI-1.5 stage description.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from conftest import REAL_SAMPLE_MIZ_PATH
from fixtures.synthetic_mission import (
    HIDDEN_GROUP_NAME,
    LATE_ACTIVATION_GROUP_NAME,
    MFD_HIDDEN_GROUP_NAME,
    PLANNER_HIDDEN_GROUP_NAME,
    VISIBLE_GROUP_NAME,
    write_synthetic_miz,
)

from filter.crew_available import CrewAvailableMission, filter_crew_available
from miz.reader import read_miz
from miz.tree import RawMission


def _all_group_names(raw: RawMission) -> list[str]:
    return [
        group.name
        for coalition in raw.coalitions
        for country in coalition.countries
        for group in country.groups
    ]


def _crew_available_group_names(crew_available: CrewAvailableMission) -> list[str]:
    names: list[str] = []
    for coalition in crew_available.coalitions:
        for country in coalition.countries:
            for group in country.groups:
                names.append(group.name)
    return names


def test_synthetic_fixture_drops_every_author_only_group(tmp_path: Path) -> None:
    raw = read_miz(write_synthetic_miz(tmp_path / "synthetic.miz"))

    # Sanity: the raw tree really does contain all five groups, including
    # the four author-only ones -- otherwise this test would trivially pass
    # by testing nothing.
    assert set(_all_group_names(raw)) == {
        VISIBLE_GROUP_NAME,
        HIDDEN_GROUP_NAME,
        PLANNER_HIDDEN_GROUP_NAME,
        MFD_HIDDEN_GROUP_NAME,
        LATE_ACTIVATION_GROUP_NAME,
    }

    crew_available = filter_crew_available(raw)
    crew_group_names = _crew_available_group_names(crew_available)

    assert crew_group_names == [VISIBLE_GROUP_NAME]
    for author_only_name in (
        HIDDEN_GROUP_NAME,
        PLANNER_HIDDEN_GROUP_NAME,
        MFD_HIDDEN_GROUP_NAME,
        LATE_ACTIVATION_GROUP_NAME,
    ):
        assert author_only_name not in crew_group_names


def test_synthetic_fixture_author_only_names_do_not_leak_anywhere_in_output(
    tmp_path: Path,
) -> None:
    """Belt-and-suspenders: not just "not in the group list" but "the
    string doesn't appear anywhere in the serialized crew-available
    object" -- guards against a future field accidentally re-embedding a
    hidden group's name (e.g. in a raw-passthrough field added later)."""
    raw = read_miz(write_synthetic_miz(tmp_path / "synthetic.miz"))
    crew_available = filter_crew_available(raw)

    serialized = repr(dataclasses.asdict(crew_available))
    for author_only_name in (
        HIDDEN_GROUP_NAME,
        PLANNER_HIDDEN_GROUP_NAME,
        MFD_HIDDEN_GROUP_NAME,
        LATE_ACTIVATION_GROUP_NAME,
    ):
        assert author_only_name not in serialized
    assert VISIBLE_GROUP_NAME in serialized


def test_synthetic_fixture_trigrules_and_trig_are_not_on_crew_available() -> None:
    """`CrewAvailableMission` must not expose `trigrules`/`trig` at all --
    a structural check, not a values check, since the plan requires these
    kept only as raw-tree data for research/debugging (Decision 1a,
    Decision 5)."""
    field_names = {f.name for f in dataclasses.fields(CrewAvailableMission)}
    assert "trigger_rules" not in field_names
    assert "trig_raw" not in field_names
    assert "raw" not in field_names


@pytest.mark.skipif(
    not REAL_SAMPLE_MIZ_PATH.exists(),
    reason="real sample mission not present locally (gitignored, see conftest.py)",
)
def test_real_sample_drops_every_author_only_group() -> None:
    raw = read_miz(REAL_SAMPLE_MIZ_PATH)
    crew_available = filter_crew_available(raw)

    raw_author_only_names = {
        group.name
        for coalition in raw.coalitions
        for country in coalition.countries
        for group in country.groups
        if group.hidden
        or group.hidden_on_planner
        or group.hidden_on_mfd
        or group.late_activation
    }
    assert len(raw_author_only_names) > 0  # sanity: the real sample exercises this

    crew_group_names = set(_crew_available_group_names(crew_available))
    assert crew_group_names.isdisjoint(raw_author_only_names)
