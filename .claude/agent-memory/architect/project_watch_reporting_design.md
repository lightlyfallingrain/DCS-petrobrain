---
name: watch-reporting-design
description: Watch-reporting plan (2026-09-24) — the speech allowlist that made three of four triggers already-built or already-silent, the belief-keyed engagement envelope, and the range/altitude/terrain AND that a summarised fetch nearly broke.
metadata:
  type: project
---

`plans/watch-reporting/plan.md`, planned 2026-09-24 against `feature/binocular-optic` merged into a
worktree. Four load-bearing findings worth keeping, because each one inverted what the brief assumed.

**1. `callouts._TEMPLATED_KINDS` is the speech allowlist, and it is the first thing to read before
planning any "Petrovich should say X" milestone.** It holds only
`{CONTACT_DETECTED, CONTACT_REACQUIRED, CONTACT_CLASSIFICATION_CHANGED}`. Consequences that were not
visible from the event list alone: reacquisition **already speaks for every contact** (a requested
trigger that was already done), and `CONTACT_MOTION_CHANGED` **fires and has never been spoken**
(`movement-detection` built the event and stopped). Attention today changes *ordering*
(`callout_priority`'s `-attention_rank`), never *eligibility* — so "watched contacts report
themselves" is the project's first watched-only speech.

**Why:** the brief said three of four triggers "have machinery", which was true of the *events* and
false of the *speech*. Reading the event list and the attention field would have produced a plan that
duplicated reacquisition and missed that motion was silent.

**How to apply:** for any reporting milestone, check the allowlist and the priority key before
believing an event reaches the pilot.

**2. Gate placement is a real choice, and this plan used both.** Motion is gated at the *speech*
layer (event stays universal, `callouts.tick` filters on effective attention) following
`CONTACT_CARDINALITY_CHANGED`'s "real event, never spoken" precedent. The two new kinds are gated at
*emission*, because their per-contact bookkeeping is only meaningful for a watched contact and
emitting theatre-wide would flood `store.events`. Seeding conventions came out opposite and both
matter: range-crossing seeds silently (or `follow` blurts the range the readback just gave), engagement
seeds as "outside" (so recognising a SAM you are already inside fires).

**3. The envelope lookup's *signature* is the no-omniscience guard.** `belief/threat.py`'s
`envelope_for(classification: ClassificationBelief)` structurally cannot be handed ground truth,
because it does not accept the type that carries it. Presence/unknown → `None`: a dot has no envelope.
The class-level rollup is **derived at import** by joining threat rows through
`perception.object_model`'s existing keyword table, so class membership has exactly one definition and
cannot drift. Fell out of that: our `OP_SRSAM` bucket spans SA-3 (~18 km) to SA-13 (~5 km), a 4×
spread — the class-level warning is early and wrong in magnitude by construction.

**Why:** `body-layer/ROADMAP.md`'s deferred threat-band item warns that computing this from ground
truth would be "an omniscience backdoor wearing a prioritisation label — and an invisible one".

**4. Three independent ways to be safe, ANDed — and a two-round misread that nearly deleted one of
them.** The threat test is `range_min <= r <= range_max` AND `alt_min <= h <= alt_max` AND
`los_clear(threat, ownship)`. Range, altitude and terrain answer different questions and none
substitutes for another.

**The misread, because the failure mode is the reusable part:** a summarising web fetch flattened the
Hoggit table's altitude cell `0 - 6500` into "6500 maximum". On that premise I reasoned — correctly,
from a false input — that ceilings never bind for a Mi-24P and the column should be dropped entirely.
The user had the literal table open and corrected it: **it is a band**, and both ends matter. A
Shilka's `0 - 6500 ft` means *no floor* (flying low buys nothing against it) while a system with a
genuine floor is defeated by flying under it. That per-type distinction is the tactical payload, and
it falls out of `alt_min <= h <= alt_max` with no `if floor == 0` branch. Even the ceiling binds:
6,500 ft is ~2,000 m, squarely inside this aircraft's range, unlike the 150,000 ft an S-300 suggested.

**Rule:** never let a summarised fetch stand in for literal table cells when the cells are the
design input. A range rendered as a single number is the specific tell. Ask the user to paste.

The LOS half of that reasoning survived and is worth keeping: `perception.geometry.line_of_sight_clear`
(wrapping world-model's `query.line_of_sight`) was already in-process and already gating every
sighting, so the terrain term is **symmetric with perception** — he cannot see through terrain,
neither can the SAM, one primitive answers both. It also subsumes the stale-contact cry-wolf case.

Ingest `radar_range_m` (separate from and *longer* than weapon range — being tracked is not being
shootable; the future "he's looking at us" warning lives here) and `acquire_time_s`, and say loudly
that nothing consumes them, or a reviewer deletes one and misuses the other.

**Wiring detail that avoids an import cycle:** `enrichment.py` imports `contacts.py`, so
`ContactStore.tick` can never take an `EnrichmentContext`. Pass a bare `GeoPosition` for ownship and
**inject `los_clear` as a callable** closed over `conn`/`theatre` in `logger.run_once`. Keeps
`contacts.py` free of world-model imports, keeps the new blocks in the five-block loop with their
free `EVENT_COOLDOWN_S`, and lets fixtures test hysteresis with a lambda instead of a terrain
database. **Reusable pattern** for anything else that wants a world-model fact inside `contacts.py`.

**How to apply:** when a plan turns on tabulated external data, get the literal cells in front of you
before reasoning about what the numbers mean — the "this value can never bind, drop it" argument is
seductive and was wrong here precisely because the input was pre-digested. Separately, and still
sound: check whether an already-built primitive (LOS here) models the real mechanism better than a
table does — just add it, do not let it displace the table.

See also [[project_bl4_attention_events]], [[project_callout_scheduling_design]],
[[project_movement_detection_design]], [[project_voice_command_completeness]].
