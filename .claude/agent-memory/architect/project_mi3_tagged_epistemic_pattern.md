---
name: project_mi3_tagged_epistemic_pattern
description: MI-3's Tagged[T] epistemic-status wrapper pattern, chosen over world-model's per-field-name dict-map precedent, and why
metadata:
  type: project
---

MI-3 (`plans/mi3-mission-understanding-schema/plan.md`) introduces the FACT/OBSERVATION/
INFERENCE/ASSUMPTION/UNKNOWN epistemic tag as a generic wrapper dataclass, `Tagged[T]` (`value`,
`epistemic_status`, `basis: tuple[str, ...]`), applied uniformly to every top-level
`MissionUnderstanding` field and every `mission_phases`/`important_locations` list item —
`mission-interpreter/src/schema/tags.py`.

**Why not reuse `world-model/src/store/models.py`'s `StoredFeature` precedent** (a plain dataclass
plus parallel `provenance: dict[str, str]` / `confidence: dict[str, str]` maps keyed by field
name)? That pattern works for flat, independently-fetched rows. `MissionUnderstanding` is a nested
tree where individual *list items* (one `known_threats` entry vs. another, once MI-4 adds real
inference) need independent epistemic status — a flat `dict[str, str]` keyed by field name can't
express "item 3 of this list is INFERENCE, item 4 is FACT." The concept docs' own example (each
statement carrying `epistemic_status`/`confidence`/`basis` inline) already matched this need more
closely than the per-field-map convention did.

**How to apply:** any future schema design in this project that needs per-item (not per-field)
provenance/confidence should default to a generic wrapper like `Tagged[T]`, not the `StoredFeature`
dict-map style — reserve the dict-map style for flat, independently-fetched records only.

**Also flagged, unresolved:** MI-3 deliberately broadens "OBSERVATION" beyond
`docs/concept/PETROBRAIN_SYSTEM.md`'s literal definition ("perceived during the mission" — a
runtime concept) to mean "resolved by consulting the World Model" (a pre-mission GIS correlation,
still deterministic, no model judgment). This is a stated interpretation call on a draft/
provisional concept doc, not a re-verified fact — worth checking whether MI-4/BL-7 usage confirms
or strains this reading. See [[project_pb2_next_milestone]] for where BL-7 sits in the schedule.
