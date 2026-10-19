---
name: project_bl15_mission_start_deep_analysis
description: BL-15 Stage 1 batch (mission-start signal, belief reset, Stage 3 theatre switching + loud refusal) deep analysis -- approved clean; log re-roll stamps are wall-clock only, no DCS-derived string ever reaches a log path.
metadata:
  type: project
---

Deep analysis (Mode 2) of the full BL-15 Stage 1 batch, `feature/bl15-mission-start`
(`ea5f77fc`), covering all three implementation batches and both Reviewer passes. See
[[project_bl15_mission_start_plan_review]] for the Mode 1 plan review this followed.

**Verified by reading the implemented code directly** (not by trusting either the Implementer's
notes or the Reviewer's account): the `THEATRE_PROJECTIONS` membership check in
`_maybe_switch_theatre` (`body-layer/src/logger.py`) strictly precedes both the path build and
`open_world_model`, matching `main()`'s own startup guard. The Reviewer's Batch 2 required fix
(`CrewConsole.drain_events`/`drain_brain` guarding on `self.refused`) is present and was
mutation-tested by the Reviewer; re-confirmed present here.

**New check, not previously exercised on this project**: whether a per-run log re-roll mechanism
lets an externally-sourced string (here, the DCS mission's `theatre`) leak into a log *filename*,
as opposed to the already-known theatre->world-model-path risk. It does not here --
`_reroll_run_logs`'s stamp is `time.strftime(...)` (wall-clock only) and the `*_base` paths are
fixed CLI values, untouched by anything arriving over the new UDP channel. Worth checking again
on any future feature that both (a) accepts an externally-sourced string and (b) rolls/renames a
log file on some trigger -- the two mechanisms existing independently doesn't mean they're
isolated from each other until actually traced.

**Risk acceptance scope note**: when an already-accepted risk (forged local loopback datagram ->
belief wipe, accepted 2026-10-19) gets a wider blast radius in a later stage of the same feature
(Stage 3 added "-> can also trigger loud refusal mode, not just a belief wipe"), that's worth a
one-line note in the deep-analysis report even though the acceptance itself doesn't need
re-raising -- the capability required is unchanged, so the trust-boundary reasoning still holds,
but a reader checking "what did I actually accept" should see what grew under it.
