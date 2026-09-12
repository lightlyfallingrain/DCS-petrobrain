"""`.miz` zip reading: open the archive, parse `mission` and
`l10n/DEFAULT/dictionary` via the vendored Lua parser, resolve every
`DictKey_*` reference tree-wide, and build the typed `RawMission`
intermediate representation (`miz.tree`).

No model/LLM involved -- deterministic parser only, per "code owns truth."
Kneeboard images are passed through as opaque zip-member paths; their
content is never read or parsed here (no OCR/VLM, per the plan's Stage 2
scope).

This parser is written against one real sample mission
(`mission-interpreter/research/samples/Mission 02-Bagram.miz`, gitignored,
see `mission-interpreter/research/2026-09-12-miz-validation-against-real-
sample.md`) -- expect it to need adjustment once tried against a second
mission file/DCS version, per the plan's own risk note. Fields not present
in the real sample are treated as optional with a sensible default rather
than a hard parse failure, so a merely-differently-populated mission
doesn't crash the whole parse.
"""

from __future__ import annotations

import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from _vendor.dcs_lua import loads
from miz.dictionary import resolve_dict_keys
from miz.tree import (
    BriefingText,
    Coalition,
    Country,
    Group,
    RawMission,
    Route,
    RoutePoint,
    TriggerRule,
    TriggerZone,
    TriggerZoneVertex,
    Unit,
)

_MISSION_MEMBER = "mission"
_DICTIONARY_MEMBER = "l10n/DEFAULT/dictionary"
_THEATRE_MEMBER = "theatre"
_KNEEBOARD_PREFIX = "KNEEBOARD/"

#: Real coalition sides + unit-category keys confirmed against the sample
#: (`mission.coalition.<side>.country[N].<category>.group[]`). A category
#: this parser doesn't know about is skipped with no group produced for it
#: -- see `_parse_country`.
_COALITION_SIDES = ("blue", "red", "neutrals")
_UNIT_CATEGORIES = ("helicopter", "plane", "vehicle", "ship", "static")


class MizParseError(RuntimeError):
    """Raised when a `.miz` file is missing an expected zip member or the
    Lua parse itself fails -- distinct from an individually-optional field
    being absent inside `mission`, which is tolerated (see module
    docstring)."""


def read_miz(path: str | Path) -> RawMission:
    """Read and parse a `.miz` file into a `RawMission`."""
    mission_lua, dictionary_lua, theatre_text, kneeboard_images = _read_zip_members(
        path
    )

    try:
        mission_root = loads(mission_lua)
    except SyntaxError as exc:
        raise MizParseError(f"failed to parse the 'mission' Lua table: {exc}") from exc
    try:
        dictionary_root = loads(dictionary_lua)
    except SyntaxError as exc:
        raise MizParseError(
            f"failed to parse the 'l10n/DEFAULT/dictionary' Lua table: {exc}"
        ) from exc

    if "mission" not in mission_root:
        raise MizParseError(
            "'mission' Lua file did not assign a top-level 'mission' variable"
        )
    dictionary: dict[str, str] = dictionary_root.get("dictionary", {})

    mission_tree = resolve_dict_keys(mission_root["mission"], dictionary)
    return _build_raw_mission(theatre_text, mission_tree, kneeboard_images)


def _read_zip_members(path: str | Path) -> tuple[str, str, str, tuple[str, ...]]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        for required in (_MISSION_MEMBER, _DICTIONARY_MEMBER):
            if required not in names:
                raise MizParseError(
                    f"'.miz' archive is missing required member {required!r}"
                )
        mission_lua = archive.read(_MISSION_MEMBER).decode("utf-8")
        dictionary_lua = archive.read(_DICTIONARY_MEMBER).decode("utf-8")
        theatre_text = (
            archive.read(_THEATRE_MEMBER).decode("utf-8").strip()
            if _THEATRE_MEMBER in names
            else ""
        )
        kneeboard_images = tuple(
            sorted(
                name
                for name in names
                if name.startswith(_KNEEBOARD_PREFIX) and not name.endswith("/")
            )
        )
    return mission_lua, dictionary_lua, theatre_text, kneeboard_images


def _build_raw_mission(
    theatre_text: str, mission: Mapping[str, Any], kneeboard_images: tuple[str, ...]
) -> RawMission:
    # `mission["theatre"]` (real bytes confirm this key exists inline too,
    # not just the zip-root `theatre` file) is preferred when present since
    # it's part of the substituted tree already; fall back to the zip-root
    # file otherwise.
    theatre = str(mission.get("theatre", theatre_text)) or theatre_text

    coalition_root: Mapping[str, Any] = mission.get("coalition", {})
    coalitions = tuple(
        _parse_coalition(side, coalition_root[side])
        for side in _COALITION_SIDES
        if side in coalition_root
    )

    triggers_root: Mapping[str, Any] = mission.get("triggers", {})
    trigger_zones = tuple(
        _parse_trigger_zone(z) for z in _as_ordered_list(triggers_root.get("zones", {}))
    )

    trigger_rules = tuple(
        _parse_trigger_rule(r) for r in _as_ordered_list(mission.get("trigrules", {}))
    )

    briefing = BriefingText(
        description_text=mission.get("descriptionText"),
        description_blue_task=mission.get("descriptionBlueTask"),
        description_red_task=mission.get("descriptionRedTask"),
        description_neutrals_task=mission.get("descriptionNeutralsTask"),
        sortie=mission.get("sortie"),
    )

    return RawMission(
        theatre=theatre,
        date=dict(mission.get("date", {})),
        weather=dict(mission.get("weather", {})),
        coalitions=coalitions,
        trigger_zones=trigger_zones,
        trigger_rules=trigger_rules,
        briefing=briefing,
        kneeboard_images=kneeboard_images,
        trig_raw=dict(mission.get("trig", {})),
        raw=mission,
    )


def _as_ordered_list(value: Any) -> list[Any]:
    """DCS's Lua tables use `[1]`, `[2]`, ... integer keys for what are
    really arrays; the vendored parser (`_vendor.dcs_lua.loads`) returns
    these as plain dicts keyed by int, not Python lists. This normalizes
    either shape (dict-of-ints or an already-empty-list `{}`) into an
    order-preserving list."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value[key] for key in sorted(value.keys())]
    return []


def _parse_coalition(side: str, node: Mapping[str, Any]) -> Coalition:
    countries = tuple(
        _parse_country(c) for c in _as_ordered_list(node.get("country", {}))
    )
    return Coalition(side=side, countries=countries)


def _parse_country(node: Mapping[str, Any]) -> Country:
    groups: list[Group] = []
    for category in _UNIT_CATEGORIES:
        category_node = node.get(category)
        if not isinstance(category_node, dict):
            continue
        for group_node in _as_ordered_list(category_node.get("group", {})):
            groups.append(_parse_group(group_node, category))
    return Country(
        name=str(node.get("name", "")),
        country_id=int(node.get("id", 0)),
        groups=tuple(groups),
    )


def _parse_group(node: Mapping[str, Any], category: str) -> Group:
    route_node = node.get("route")
    route = _parse_route(route_node) if isinstance(route_node, dict) else None
    units = tuple(_parse_unit(u) for u in _as_ordered_list(node.get("units", {})))
    return Group(
        group_id=int(node.get("groupId", 0)),
        name=str(node.get("name", "")),
        category=category,
        hidden=bool(node.get("hidden", False)),
        hidden_on_planner=bool(node.get("hiddenOnPlanner", False)),
        hidden_on_mfd=bool(node.get("hiddenOnMFD", False)),
        late_activation=bool(node.get("lateActivation", False)),
        route=route,
        units=units,
        raw=node,
    )


def _parse_unit(node: Mapping[str, Any]) -> Unit:
    return Unit(
        unit_id=int(node.get("unitId", 0)),
        name=str(node.get("name", "")),
        type=str(node.get("type", "")),
        x=float(node.get("x", 0.0)),
        y=float(node.get("y", 0.0)),
        raw=node,
    )


def _parse_route(node: Mapping[str, Any]) -> Route:
    points = tuple(
        _parse_route_point(p) for p in _as_ordered_list(node.get("points", {}))
    )
    return Route(points=points)


def _parse_route_point(node: Mapping[str, Any]) -> RoutePoint:
    return RoutePoint(
        x=float(node.get("x", 0.0)),
        y=float(node.get("y", 0.0)),
        alt=float(node.get("alt", 0.0)),
        alt_type=str(node.get("alt_type", "")),
        speed=float(node.get("speed", 0.0)),
        type=str(node.get("type", "")),
        action=str(node.get("action", "")),
        eta=float(node.get("ETA", 0.0)),
        eta_locked=bool(node.get("ETA_locked", False)),
        raw=node,
    )


def _parse_trigger_zone(node: Mapping[str, Any]) -> TriggerZone:
    # DCS ships this key genuinely misspelled -- "verticies", not
    # "vertices". Do not respell it; see `miz.tree.TriggerZone`'s docstring.
    vertices_node = node.get("verticies")
    vertices = (
        tuple(
            TriggerZoneVertex(x=float(v.get("x", 0.0)), y=float(v.get("y", 0.0)))
            for v in _as_ordered_list(vertices_node)
        )
        if vertices_node is not None
        else None
    )
    radius = node.get("radius")
    return TriggerZone(
        zone_id=int(node.get("zoneId", 0)),
        name=str(node.get("name", "")),
        kind=int(node.get("type", 0)),
        x=float(node.get("x", 0.0)),
        y=float(node.get("y", 0.0)),
        radius=float(radius) if radius is not None else None,
        vertices=vertices,
        hidden=bool(node.get("hidden", False)),
        raw=node,
    )


def _parse_trigger_rule(node: Mapping[str, Any]) -> TriggerRule:
    conditions = tuple(_as_ordered_list(node.get("rules", {})))
    actions = tuple(_as_ordered_list(node.get("actions", {})))
    return TriggerRule(
        predicate=str(node.get("predicate", "")),
        comment=str(node.get("comment", "")),
        eventlist=str(node.get("eventlist", "")),
        conditions=conditions,
        actions=actions,
    )
