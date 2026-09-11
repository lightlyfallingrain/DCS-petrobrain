"""Query API: `describe_position`, the milestone deliverable, plus
`find_place_by_name` (`plans/bl5-tool-api/plan.md`'s name->position lookup)
and `line_of_sight_clear` (`plans/world-model-los-generalization/plan.md`'s
ownship-agnostic point-A-to-point-B LOS primitive).

See `describe.describe_position` for the contract this implements --
`plans/m5-first-persistent-model/plan.md` "`describe_position` contract".
"""

from .describe import describe_position
from .line_of_sight import line_of_sight_clear
from .search import PlaceMatch, find_place_by_name

__all__ = [
    "PlaceMatch",
    "describe_position",
    "find_place_by_name",
    "line_of_sight_clear",
]
