---
name: bl2-contact-memory-design
description: BL-2/PB-2 planning decisions — belief/ package boundary, Percept truth-quarantine, emit_mode debounce fix, three-valued class gate, observation-id collision
metadata:
  type: project
---

BL-2 (`plans/pb2-contact-memory/plan.md`) draws the observation-vs-belief split as a **package
boundary**: `perception/` produces observations, new `belief/` consumes them. Contact identity
never reads `object_id` or `derived_world_position`; a `belief/percept.py` `Percept` projection
makes truth fields *structurally absent* from belief code rather than forbidden by comment.

**Why:** "Petrovich must never be omniscient" is CLAUDE.md's core invariant, and BL-2 is the first
place truth data and perceived data sit in the same record with a tracker tempted to use the
truth. A comment is not enforcement. Also: a passthrough of the DCS key would make Petrovich
incapable of ever confusing two identical trucks.

**How to apply:** any later feature that wants DCS truth in belief code must justify crossing the
`Percept` boundary explicitly. BL-9 (belief-vs-truth view) reads the raw observation log, not
source internals.

Three defects found in already-merged PB-1/PB-1.5 code while planning BL-2, all recorded in the
plan:
- **`Observation.id` collides across sources** — both channels mint `f"OBS_{n}"` from their own
  per-instance counter, so an append-only log keyed by id silently overwrites.
- **Source-level debounce starves the belief layer** — both channels emit only on *change*, so a
  statically visible object produces one observation ever and decays to "lost" while in plain
  sight. Fixed with an `emit_mode: "on_change" | "every_poll"` flag defaulting to the old
  behaviour, so no PB-1.5 test is rewritten. De-duplication belongs at the belief layer.
- **The ownship 50 m exclusion window graduates from silent gap to wrong belief** once memory
  exists — a contact goes "lost" exactly when the aircraft is closest to it (troop
  insertion/extraction). The real fix is the aircraft-layer ownship flag (backlog).

**Cross-channel fusion gate is three-valued** (compatible / unknown / incompatible) because
naked-eye emits `OP_TRUCK` and scope emits `"Ural truck"` — different vocabularies. `unknown`
neither blocks nor confirms; two or more gate-passing contacts → create a new contact (§2's
"prefer new over bad merge"). Consequence: weak vocabulary costs duplicate contacts, never a
silent bad merge.

Related: [[project_body_layer_api_decisions]], [[project_pb1_5_naked_eye_revision]].
