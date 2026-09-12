"""`.miz` zip reading -> typed `RawMission` intermediate representation.

See `reader.read_miz` for the entry point and `tree` for the dataclasses it
produces. This module's output is not yet filtered for author-only
knowledge (`filter.crew_available.filter_crew_available` does that) or
interpreted into a Mission Understanding (a future stage, not built yet).
"""

from miz.reader import MizParseError, read_miz
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

__all__ = [
    "BriefingText",
    "Coalition",
    "Country",
    "Group",
    "MizParseError",
    "RawMission",
    "Route",
    "RoutePoint",
    "TriggerRule",
    "TriggerZone",
    "TriggerZoneVertex",
    "Unit",
    "read_miz",
]
