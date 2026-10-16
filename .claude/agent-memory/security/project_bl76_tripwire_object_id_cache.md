---
name: project_bl76_tripwire_object_id_cache
description: BL-B76 attack-run tripwire security deep analysis — APPROVED, logging-only; the new object_id->contact_id cache in belief_truth_log.py is evict-on-read-only, same shape as belief.decay's accepted pattern, not a new risk.
metadata:
  type: project
---

BL-B76 ("widen attack-run LOS tripwire to split rejected/absent") passed security deep analysis
at `e6a77d8e` (feature/bl-b76-tripwire-rejected), APPROVED, no required fixes. Logging-only
change, confirmed by diff: only `body-layer/src/belief_truth_log.py` +
`tests/test_belief_truth_log.py` touched; `perception/visibility.py`, admission, `Contact`,
`belief/attack_run.py` all untouched — nothing computed here feeds back into perception/decision
logic.

**The evict-on-read-only cache shape is now used twice in this codebase, not once.**
`BeliefTruthLogWriter._object_id_to_contact_id`/`_object_id_last_seen_sim` (new) filters stale
entries only when read (`_object_ids_for_contact`, bounded by `OBJECT_ID_MEMORY_S`) but never
evicts them from the dict on write — a despawned unit's entry sits there forever. This is the
*same* shape `belief/decay.py:383-399`'s `object_id_continuity_valid` already uses against
`Contact.last_seen_sim`. Judged low-risk both times: dict size is bounded by the count of
*distinct* DCS `object_id`s a mission ever has (a finite ground-unit population), not by elapsed
time or poll count, so "unbounded-looking" is not actually unbounded in this project's context.
**If a future pass finds three+ of these, that stops being "reused pattern" and starts being
"nobody ever added an eviction sweep" — worth raising then, not now.**

**Sim-time-regression risk (`now_sim - last_seen_sim <= WINDOW`, negative elapsed still passes)
is systemic, not feature-specific.** No code in `logger.py`'s poll loop detects or resets on a
mission restart within a live process; `ContactStore.ingest`/`tasks.tick` make the same
monotonic-`t_sim` assumption project-wide, and `belief/decay.py` has the identical shape. Not a
finding against any one feature — if this is ever worth fixing, it is a whole-belief-layer
question, not a one-file patch.
