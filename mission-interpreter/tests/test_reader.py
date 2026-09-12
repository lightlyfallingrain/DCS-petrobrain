from __future__ import annotations

from pathlib import Path

import pytest
from conftest import REAL_SAMPLE_MIZ_PATH
from fixtures.synthetic_mission import (
    KNEEBOARD_IMAGE_PATH,
    THEATRE_NAME,
    write_synthetic_miz,
)

from miz.reader import read_miz


def test_reads_synthetic_fixture(tmp_path: Path) -> None:
    miz_path = write_synthetic_miz(tmp_path / "synthetic.miz")

    mission = read_miz(miz_path)

    assert mission.theatre == THEATRE_NAME
    assert mission.briefing.description_text == "Test briefing text."
    assert mission.briefing.description_blue_task == "Escort the convoy."
    assert mission.briefing.sortie == "Test Sortie"
    assert mission.kneeboard_images == (KNEEBOARD_IMAGE_PATH,)


def test_synthetic_fixture_groups_and_routes(tmp_path: Path) -> None:
    mission = read_miz(write_synthetic_miz(tmp_path / "synthetic.miz"))

    blue = next(c for c in mission.coalitions if c.side == "blue")
    (country,) = blue.countries
    assert len(country.groups) == 5  # all groups, hidden or not, at MI-1 stage

    visible = next(g for g in country.groups if g.name == "Visible Group")
    assert visible.route is not None
    (point,) = visible.route.points
    assert point.x == 10
    assert point.y == 20
    assert point.type == "Turning Point"
    (unit,) = visible.units
    assert unit.name == "Unit1"
    assert unit.type == "Mi-24P"


def test_synthetic_fixture_author_only_markers_are_parsed(tmp_path: Path) -> None:
    mission = read_miz(write_synthetic_miz(tmp_path / "synthetic.miz"))

    blue = next(c for c in mission.coalitions if c.side == "blue")
    (country,) = blue.countries
    groups_by_name = {g.name: g for g in country.groups}

    assert groups_by_name["Hidden Group"].hidden is True
    assert groups_by_name["Planner Hidden Group"].hidden_on_planner is True
    assert groups_by_name["MFD Hidden Group"].hidden_on_mfd is True
    assert groups_by_name["Late Activation Group"].late_activation is True
    assert groups_by_name["Visible Group"].hidden is False
    assert groups_by_name["Visible Group"].hidden_on_planner is False
    assert groups_by_name["Visible Group"].hidden_on_mfd is False
    assert groups_by_name["Visible Group"].late_activation is False


def test_synthetic_fixture_trigger_zones_including_misspelled_verticies_key(
    tmp_path: Path,
) -> None:
    mission = read_miz(write_synthetic_miz(tmp_path / "synthetic.miz"))

    zones_by_name = {z.name: z for z in mission.trigger_zones}
    circle = zones_by_name["Zone-Circle"]
    assert circle.kind == 0
    assert circle.radius == 50
    assert circle.vertices is None

    polygon = zones_by_name["Zone-Poly"]
    assert polygon.kind == 2
    assert polygon.vertices is not None
    assert len(polygon.vertices) == 2
    assert polygon.vertices[0].x == 1
    assert polygon.vertices[0].y == 2


def test_synthetic_fixture_trigrules_parsed_with_dictkey_resolved(
    tmp_path: Path,
) -> None:
    mission = read_miz(write_synthetic_miz(tmp_path / "synthetic.miz"))

    (rule,) = mission.trigger_rules
    assert rule.predicate == "triggerStart"
    (action,) = rule.actions
    assert action["predicate"] == "a_out_text_delay"
    # DictKey resolution runs over the whole tree, including trigrules'
    # action text -- not just the four briefing fields.
    assert action["text"] == "Radio call text"


@pytest.mark.skipif(
    not REAL_SAMPLE_MIZ_PATH.exists(),
    reason="real sample mission not present locally (gitignored, see conftest.py)",
)
def test_reads_real_sample_mission() -> None:
    mission = read_miz(REAL_SAMPLE_MIZ_PATH)

    assert mission.theatre == "Afghanistan"
    assert mission.date.get("Year") == 1979

    all_groups = [
        group
        for coalition in mission.coalitions
        for country in coalition.countries
        for group in country.groups
    ]
    assert len(all_groups) > 0
    assert any(group.late_activation for group in all_groups)
    assert any(group.hidden_on_planner for group in all_groups)

    assert len(mission.trigger_zones) > 0
    assert any(zone.vertices is not None for zone in mission.trigger_zones)

    assert len(mission.trigger_rules) > 0
    assert any(rule.predicate == "triggerStart" for rule in mission.trigger_rules)
