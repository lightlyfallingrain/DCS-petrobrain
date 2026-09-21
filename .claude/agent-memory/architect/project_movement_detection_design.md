---
name: movement-detection-design
description: Movement-detection plan (2026-09-22) — velocity enters via a third Hook script on the mission-scripting bridge, the gate lives in perception so the vector never reaches belief, and MOTION_HALF_LIFE_S was already waiting in decay.py
metadata:
  type: project
---

Movement detection (`plans/movement-detection/plan.md`) resolves the user's 2026-09-20 perceptual
design into a build. The load-bearing structural decisions:

- **The velocity vector never leaves `perception/`.** `perception/motion.py` computes the
  apparent-angular-rate gate; only a tri-state `Observation.apparent_motion: bool | None` crosses
  into `belief`. This turns "omniscience removed by the gate, not the source" from a convention
  into a module boundary. Same shape as `check_visibility` over `LoGetWorldObjects`.
- **`MOTION_HALF_LIFE_S = 60.0` already existed, unconsumed, in `body-layer/src/belief/decay.py`**,
  with a docstring explicitly reserving it for a future motion estimate on `Contact`. Found by
  grepping the decay ladder before finalising — the role rule that exists because object-permanence
  needed three revisions for missing exactly this. No existing constant changed value.
- **The join key between mission scripting and `LoGetWorldObjects` is `UnitName`**, not the
  `pairs()` key (export-side index, no scripting-side equivalent) and never positional proximity.
  Costs an additive Export.lua field. `Object.getID()` may collapse this later if probed.
- **Velocity gets its own endpoint (`/unit_velocity/latest`), not a merge into
  `/world_objects/latest`** — merging would put two different sim times under one timestamp and
  destroy the dual-clock provenance.
- **Sim time must be stamped inside the scripting state with `timer.getTime()`**, not in the Hook
  with `DCS.getRealTime()`. `f10_command.py` had no cheap sim clock from Hook state and stamps wall
  clock; copying that pattern here would break replay determinism.
- **The `t` in `s = v·t` cancels** — both sides of the threshold comparison carry it. An implementer
  reaching for the inter-poll `dt` would make the verdict poll-rate-dependent. The ~1 s window is
  derivation, belongs in a comment, not a constant.

**Why:** the four open questions the roadmap left (where velocity enters, batching, what movement
is downstream, whether attention-capture is in slice) all turn on keeping the truth-in /
perception-limited-out boundary at a module edge rather than inside a function.

**How to apply:** when a later slice adds another DCS-truth-derived perceptual property (fog,
lights/flashes, attention capture), put the gate in `perception` and let only the judgement cross;
and check `decay.py`'s table first — `GENERAL_AREA_HALF_LIFE_S` is still sitting there unconsumed
for BL-3's `general_area`. See [[project_bl4_attention_events]], [[project_cones_slice2_design]].
