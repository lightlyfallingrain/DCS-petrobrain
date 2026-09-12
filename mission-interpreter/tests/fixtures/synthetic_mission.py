"""A small, hand-authored `.miz`-shaped fixture, committed to the repo (not
gitignored) so parser/filter tests run in any checkout -- unlike
`mission-interpreter/research/samples/Mission 02-Bagram.miz`, which is
real third-party campaign content and gitignored (see the repo root
`.gitignore`).

Mirrors `body-layer/tests/fixtures/`'s convention: a committed synthetic
fixture standing in for real captured data, built to exercise every code
path the tests need without depending on anything not licensed for
redistribution.

Deliberately hand-typed Lua text (not built via the vendored
`_vendor.dcs_lua.serialize.dumps`) so this fixture stays readable as a
reference for the real schema shape (`mission-interpreter/research/
2026-09-12-miz-validation-against-real-sample.md`), independent of whatever
the vendored serializer happens to produce.

Exercises: DictKey resolution (briefing fields + one trigger-action text),
a visible group, one group for each of the four author-only markers
(`hidden`/`hiddenOnPlanner`/`hiddenOnMFD`/`lateActivation` -- `hiddenOnMFD`
is not exercised by the real sample at all, see the validation note, so
this fixture is its only test coverage), a circle and a polygon trigger
zone (the polygon using the real, misspelled `"verticies"` key), one
`trigrules` rule, and a kneeboard image path.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

THEATRE_NAME = "TestTheatre"

VISIBLE_GROUP_NAME = "Visible Group"
HIDDEN_GROUP_NAME = "Hidden Group"
PLANNER_HIDDEN_GROUP_NAME = "Planner Hidden Group"
MFD_HIDDEN_GROUP_NAME = "MFD Hidden Group"
LATE_ACTIVATION_GROUP_NAME = "Late Activation Group"

KNEEBOARD_IMAGE_PATH = "KNEEBOARD/IMAGES/page1.png"

_MISSION_LUA = """
mission =
{
    ["theatre"] = "TestTheatre",
    ["date"] = { ["Year"] = 2024, ["Month"] = 1, ["Day"] = 1 },
    ["weather"] = {},
    ["descriptionText"] = "DictKey_descriptionText_1",
    ["descriptionBlueTask"] = "DictKey_descriptionBlueTask_2",
    ["descriptionRedTask"] = "",
    ["descriptionNeutralsTask"] = "",
    ["sortie"] = "DictKey_sortie_3",
    ["trig"] = {},
    ["triggers"] =
    {
        ["zones"] =
        {
            [1] =
            {
                ["zoneId"] = 1,
                ["name"] = "Zone-Circle",
                ["type"] = 0,
                ["x"] = 100,
                ["y"] = 200,
                ["radius"] = 50,
                ["hidden"] = false,
            },
            [2] =
            {
                ["zoneId"] = 2,
                ["name"] = "Zone-Poly",
                ["type"] = 2,
                ["x"] = 300,
                ["y"] = 400,
                ["hidden"] = false,
                ["verticies"] =
                {
                    [1] = { ["x"] = 1, ["y"] = 2 },
                    [2] = { ["x"] = 3, ["y"] = 4 },
                },
            },
        },
    },
    ["trigrules"] =
    {
        [1] =
        {
            ["predicate"] = "triggerStart",
            ["comment"] = "test rule",
            ["eventlist"] = "",
            ["rules"] = {},
            ["actions"] =
            {
                [1] = { ["predicate"] = "a_out_text_delay", ["text"] = "DictKey_ActionText_9" },
            },
        },
    },
    ["coalition"] =
    {
        ["blue"] =
        {
            ["country"] =
            {
                [1] =
                {
                    ["id"] = 1,
                    ["name"] = "USA",
                    ["helicopter"] =
                    {
                        ["group"] =
                        {
                            [1] =
                            {
                                ["groupId"] = 1,
                                ["name"] = "Visible Group",
                                ["hidden"] = false,
                                ["hiddenOnPlanner"] = false,
                                ["hiddenOnMFD"] = false,
                                ["lateActivation"] = false,
                                ["route"] =
                                {
                                    ["points"] =
                                    {
                                        [1] =
                                        {
                                            ["x"] = 10,
                                            ["y"] = 20,
                                            ["alt"] = 500,
                                            ["alt_type"] = "BARO",
                                            ["speed"] = 50,
                                            ["type"] = "Turning Point",
                                            ["action"] = "Turning Point",
                                            ["ETA"] = 0,
                                            ["ETA_locked"] = true,
                                        },
                                    },
                                },
                                ["units"] =
                                {
                                    [1] = { ["unitId"] = 1, ["name"] = "Unit1", ["type"] = "Mi-24P", ["x"] = 10, ["y"] = 20 },
                                },
                            },
                            [2] =
                            {
                                ["groupId"] = 2,
                                ["name"] = "Hidden Group",
                                ["hidden"] = true,
                                ["hiddenOnPlanner"] = false,
                                ["hiddenOnMFD"] = false,
                                ["lateActivation"] = false,
                                ["units"] = { [1] = { ["unitId"] = 2, ["name"] = "HiddenUnit", ["type"] = "T-72", ["x"] = 1, ["y"] = 1 } },
                            },
                            [3] =
                            {
                                ["groupId"] = 3,
                                ["name"] = "Planner Hidden Group",
                                ["hidden"] = false,
                                ["hiddenOnPlanner"] = true,
                                ["hiddenOnMFD"] = false,
                                ["lateActivation"] = false,
                                ["units"] = { [1] = { ["unitId"] = 3, ["name"] = "PlannerHiddenUnit", ["type"] = "T-72", ["x"] = 2, ["y"] = 2 } },
                            },
                            [4] =
                            {
                                ["groupId"] = 4,
                                ["name"] = "MFD Hidden Group",
                                ["hidden"] = false,
                                ["hiddenOnPlanner"] = false,
                                ["hiddenOnMFD"] = true,
                                ["lateActivation"] = false,
                                ["units"] = { [1] = { ["unitId"] = 4, ["name"] = "MFDHiddenUnit", ["type"] = "T-72", ["x"] = 3, ["y"] = 3 } },
                            },
                            [5] =
                            {
                                ["groupId"] = 5,
                                ["name"] = "Late Activation Group",
                                ["hidden"] = false,
                                ["hiddenOnPlanner"] = false,
                                ["hiddenOnMFD"] = false,
                                ["lateActivation"] = true,
                                ["units"] = { [1] = { ["unitId"] = 5, ["name"] = "LateUnit", ["type"] = "T-72", ["x"] = 4, ["y"] = 4 } },
                            },
                        },
                    },
                },
            },
        },
        ["red"] = { ["country"] = {} },
        ["neutrals"] = { ["country"] = {} },
    },
}
"""

_DICTIONARY_LUA = """
dictionary =
{
    ["DictKey_descriptionText_1"] = "Test briefing text.",
    ["DictKey_descriptionBlueTask_2"] = "Escort the convoy.",
    ["DictKey_sortie_3"] = "Test Sortie",
    ["DictKey_ActionText_9"] = "Radio call text",
}
"""


def write_synthetic_miz(path: Path) -> Path:
    """Write the synthetic fixture as a real `.miz` (zip) file at `path`
    and return it, so tests can pass it straight to `miz.reader.read_miz`."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mission", _MISSION_LUA)
        archive.writestr("l10n/DEFAULT/dictionary", _DICTIONARY_LUA)
        archive.writestr("theatre", THEATRE_NAME)
        archive.writestr(KNEEBOARD_IMAGE_PATH, b"\x89PNG\r\n\x1a\nfake-png-bytes")
    return path
