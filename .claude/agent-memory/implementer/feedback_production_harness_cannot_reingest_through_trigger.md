---
name: production-harness-cannot-reingest-through-trigger
description: when a production-mode measurement harness needs to simulate "the remembered contact was seen again" for a trigger wired into ContactStore.ingest, do not feed a second hand-built observation back through ingest -- it will open a second trigger check rather than advance the contact via continuity
type: feedback
---

On `BL-B111` Pass 3, building `tools/measure_expected_area_look.py
--production` (the real `ContactStore(expected_area_checks=True)` driving
`belief.expected_area`'s real trigger/`resolve_checks`), the natural move for
simulating "A was observed during the hold" looked like: ingest a second,
hand-built `Observation` at A's true position and check whether `a.
last_seen_sim` advanced. **This is wrong once the trigger being tested is
itself wired into `ingest`'s own gate-fold path**, and the wrongness is
silent: no exception, just a store with a second `ExpectedAreaCheck` open
against the same A instead of A's `last_seen_sim` moving.

**Why:** `ContactStore.ingest`'s amended trigger
(`eligible_trigger_target`/`a_out_of_view`) fires on *every* single-candidate
gate fold against an out-of-view, area-fits-one-look A, not only the first
one in a sortie -- correct production behaviour (two independent sightings
of the same remembered group both held at once is exactly what `MAX_OPEN_
CHECKS` exists to cap), but it means re-ingesting a matching percept opens a
*second* check rather than advancing the contact. In real flight this path
is instead reached through DCS object-id continuity, which short-circuits
*before* the gate/trigger logic runs at all -- and a synthetic measurement
harness's hand-built `Observation`s typically carry no continuity fields
(`continues_observation_id`/`derived_world_position` both `None`), so that
escape hatch is never available to a test harness either.

**How to apply:** when a production-mode harness needs to simulate "this
remembered entity was reconfirmed" against a store whose `ingest` has a
trigger wired into its gate-fold branch, do not re-ingest a matching
percept. Either (a) call the entity's own `record(percept)` method directly
(bypassing `ingest` entirely, the same effect continuity would have), or (b)
reuse whatever purely-geometric test the original architect's modelled
harness already used to decide "would this have been seen" (e.g. a gate/
`passes_gate` check against a snapshot) and treat that as the event, without
driving it through the store's own ingest path. Grep the trigger's own
precondition first (`eligible_trigger_target`-shaped) to see if it is
checked unconditionally on every gate fold, not just the first -- if so,
assume re-ingestion will misfire and verify by inspecting `store.checks`'
length after the "reconfirming" ingest call, not just trusting that the
contact's own `last_seen_sim` moved.
