# MI-3 — First Mission Understanding schema

- [x] **MI-3 — First Mission Understanding schema (no model synthesis).** #status/done Done
  (`plans/mi3-mission-understanding-schema/plan.md`): `src/schema/` hand-maps MI-1.5's
  crew-available tree + MI-2's `EnrichedMission` into a new, versioned `MissionUnderstanding`
  dataclass tree (`SCHEMA_VERSION = 1`), populating only `theatre`/`ownship`/`route`/a mechanical
  `mission_phases` skeleton (`TakeOff*` -> DEPARTURE, `Land` -> RETURN, everything else left
  unpopulated rather than guessed)/`important_locations` (named `Group`/`TriggerZone` entities whose
  `world_ref.name_matches` is non-empty -- not route waypoints, which the pipeline doesn't resolve
  names for). Every populated field is tagged `FACT` or `OBSERVATION` via the new `Tagged[T]`
  epistemic-tagging mechanism (`src/schema/tags.py`), never `INFERENCE`/`ASSUMPTION` -- proven by a
  dedicated invariant test. Required adding `Unit.skill` to `miz/tree.py` (real-bytes-confirmed
  field, per the investigator's `research/2026-09-12-player-slot-skill-field.md`) so ownship
  resolution can scan for `skill in ("Player", "Client")`; 0 or >=2 matches resolve to `UNKNOWN`
  rather than guessing. `purpose`/`task`/`known_threats`/`player_intent` are declared on the schema
  but deliberately left unpopulated -- MI-4's job once a capable model exists. Does not change what
  MI-4 should be, but confirms `Tagged[T]` as the one epistemic-tagging convention MI-4/5/6 should
  reuse rather than reinvent.
