---
name: bl7-mission-phase-design
description: BL-7 tool-freeze resolution and mission-phase/relevance design decisions, relevant to BL-8 and any future PB-9 work.
metadata:
  type: project
---

BL-7 (`plans/bl7-mission-phase-relevance/plan.md`, planned 2026-09-13) resolved the roadmap's
"get_mission_phase" stale flag as: **no new tool** — mission phase folded into `get_situation`'s
existing facts payload instead. Reasoning: `get_situation` is already the aggregate-sitrep tool;
mission phase is a single global value with no `id`, unlike `get_task_status` which genuinely
needs its own tool because there can be several pending tasks. The BL-6 tool-set freeze is about
the *tool inventory* not growing incidentally, not about a tool's facts payload staying frozen.

**Why:** avoids growing the frozen `TOOL_SET` for a value that fits an existing tool's shape
exactly; keeps the "freeze means don't grow incidentally, not don't ever add anything" reading
`AGENTS.md`/`tool_api.py`'s docstring intends.

**How to apply:** if a future milestone (BL-8, PB-9) proposes a new tool, first check whether the
value fits inside `get_situation`'s aggregate-sitrep shape (or another existing tool's shape)
before assuming a new `TOOL_SET` entry is needed — mirror this same reasoning, don't just add.

Design specifics worth knowing before planning BL-8:
- MI-6's `RuntimeMissionUnderstanding.key_locations` (`CompactLocation`) carries **no position**,
  only `id`/`kind`/`place_name` — relevance/proximity logic can only be scored against
  `route` waypoints, not named mission-critical locations, until MI-6 is revised or a
  `find_place`-based resolution layer is added. This is a real, currently-unclosed gap against
  `docs/concept/PETROBRAIN_SYSTEM.md`'s "target approaching a mission-critical area" framing.
- Route coordinates (`CompactRoutePoint.x`/`.y`, sourced from `.miz` `route.points[].x`/`.y`) map
  directly onto body-layer's `GeoPosition(x, z)` convention: DCS-native `x`=northing,
  `y`(miz field)=`z`(DCS native)=easting — already ED-documented and verified in
  `world-model/research/2026-09-02-m1-coordinate-transform.md`, no new transform needed to
  compare a mission-interpreter route point against a live ownship/contact position.
- Mission-interpreter's compact JSON artifact (`--emit-compact`) is consumed by body-layer as a
  **file read + hand-parsed JSON**, never a Python import — mission-interpreter is not the
  world-model exception root `CLAUDE.md`'s "Module independence" section carves out.
- BL-7 introduced the first live-state-tracking module outside `belief/contacts.py`/`tasks.py`
  (`belief/mission_phase.py`'s `MissionPhaseTracker`) and deliberately copied
  `EnrichmentContext.ownship`'s write-thread/read-thread split to avoid a third instance of the
  sqlite/cross-thread-mutation defect class already hit twice (BL-2 Stage 6, BL-5's `situation`
  crash, both documented in `body-layer/ROADMAP.md`).
