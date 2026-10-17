"""`mission_memory` -- BL-8's append-only, per-sortie record of what
Petrovich saw, marked, attacked and was shot at (`plans/bl8-mission-memory/
plan.md`). A sibling of `belief/` and `perception/`, not a module inside
`belief/` (Decision 1): memory is a record *of* belief, and it outlives the
contacts it records.

**Import direction is structural, not conventional.** `mission_memory` may
import `belief`. No module in `belief/` may import `mission_memory`, with
exactly one carved exception: `belief/tool_api.py` (Stage 5). Enforced by
`tests/test_mission_memory_import_direction.py`.
"""

from __future__ import annotations
