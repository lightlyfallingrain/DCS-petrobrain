"""Query API: `describe_position`, the milestone deliverable, plus
`find_place_by_name` (`plans/bl5-tool-api/plan.md`'s name->position lookup).

See `describe.describe_position` for the contract this implements --
`plans/m5-first-persistent-model/plan.md` "`describe_position` contract".
"""

from .describe import describe_position
from .search import PlaceMatch, find_place_by_name

__all__ = ["PlaceMatch", "describe_position", "find_place_by_name"]
