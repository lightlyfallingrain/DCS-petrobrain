---
name: watch-reporting-design
description: Watch-reporting plan (2026-09-24) — the speech allowlist that made three of four triggers already-built or already-silent, the belief-keyed engagement envelope, and the range/altitude/LOS threat test, and the per-field null rule a blanket policy got backwards.
metadata:
  type: project
---

`plans/watch-reporting/plan.md`, planned 2026-09-24 against `feature/binocular-optic` merged into a
worktree. Five load-bearing findings worth keeping, because each one inverted what the brief assumed.

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

**4. Three independent ways to be safe, ANDed — and two rounds of misreading that nearly deleted one
of them.** The threat test is `range_min <= r <= range_max` AND `agl >= alt_min` AND
`los_clear(threat, ownship)`: out of range, under the floor, behind a ridge. None substitutes for
another.

**The misread, because the failure mode is the reusable part:** a summarising web fetch flattened the
Hoggit table's altitude cell `0 - 6500` into "6500 maximum". From that false input I reasoned
correctly to the wrong conclusion *twice* — first "gate on the ceiling", then "drop the column
entirely, it can never bind". The real answer was "gate on the floor". Once the data was actually
extracted (`body-layer/data/threat_envelopes.json`, 28 entries), it settled in one query: **12 of 19
SAMs carry a non-zero floor; 0 of 6 AAA and 0 of 3 MANPADS do.** Radar-guided SAMs suffer ground
clutter; optically/IR-aimed weapons do not. And the floors sit at NOE altitudes a Mi-24P flies
(SA-13 23 m, SA-8 15 m, Roland 9 m), so flying low is a real defence against SAMs and no defence at
all against guns — a per-type distinction that falls out of `agl >= alt_min` with no `if floor == 0`
branch.

**Rule:** never let a summarised fetch stand in for literal table cells when the cells are the design
input. A range rendered as a single number is the specific tell. Get the data extracted first; it
answers in one query what two rounds of argument got wrong.

**Corollary worth its own line — a blanket null rule can be right for one field and inverted for its
neighbours.** The payload said "a null MUST degrade to no warning, never to a default". True for
`range_max_m`; **backwards** for `alt_min_m`, where it would mean an unknown floor *protects* you.
Conservative direction differs per field: unknown reach → silence, unknown floor/min-range → assume
no protection. SA-2 is the case that forces the split — null min range and null floor but a real
51.9 km reach, which an entry-wide rule would have thrown away.

**LOS is a precondition for radar tracking, not a terrain nicety** (user). Consequence: losing LOS
*ends* the threat state and clears a standing warning — the duck-behind-a-ridge behaviour, and the
best acceptance test in the milestone. It is symmetric with perception: `line_of_sight_clear` already
gates every sighting, so one primitive answers both "can he see it" and "can it see him".

**The LOS test inherits belief uncertainty, and the fix is the binocular-sweep answer again**: sample
at the believed position plus two lateral offsets at `±last_position_uncertainty_m`, and fail *open*
(any clear sample ⇒ LOS). Costs are asymmetric — a false warning costs a glance, a missed one costs
the aircraft. `last_position_uncertainty_m` is metres of position error and is the right field here;
the Stage-3b trap was reading it as a *bearing* error, which is a different mistake.

**5. `TranscriptEvent`'s flat per-command fields stopped scaling at slot two.** `bearing_degrees` was
one; a descriptor/clock/range command would have made four mutually-exclusive columns. Replaced with
a single `slots: dict[str, int | str]`. The moment to generalise a wire shape is when the second
instance appears, not the fourth — and it was cheap here only because both ends are Mac-local
processes restarted together.

**Wiring detail that avoids an import cycle:** `enrichment.py` imports `contacts.py`, so
`ContactStore.tick` can never take an `EnrichmentContext`. Pass the whole `OwnshipState` (position
plus `alt_agl_m`; `contacts.py` already imports from `perception.source`) and
**inject `los_clear` as a callable** closed over `conn`/`theatre` in `logger.run_once`. Keeps
`contacts.py` free of world-model imports, keeps the new blocks in the five-block loop with their
free `EVENT_COOLDOWN_S`, and lets fixtures test hysteresis with a lambda instead of a terrain
database. **Reusable pattern** for anything else that wants a world-model fact inside `contacts.py`.

**How to apply:** when a plan turns on tabulated external data, get it extracted and query it before
reasoning about what the numbers mean — "this value can never bind, so drop it" is a seductive
argument and it was wrong here twice, purely because the input was pre-digested. Separately, and
still sound: check whether an already-built primitive (LOS here) models the real mechanism better
than a table does — then *add* it, do not let it displace the table.

See also [[project_bl4_attention_events]], [[project_callout_scheduling_design]],
[[project_movement_detection_design]], [[project_voice_command_completeness]].
