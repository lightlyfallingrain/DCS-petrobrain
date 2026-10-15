---
name: mission-restart-stale-belief
description: A huge, symmetric position-error tripwire (hundreds of km, all contacts converging on one point) is a stale ContactStore surviving a DCS mission restart, not a coordinate/fusion bug -- check t_sim for a backward jump before chasing geometry.
metadata:
  type: project
---

2026-10-15 sortie: belief-truth tripwire fired at ~532 km against a 10 km cap, across four
contacts clustered within 0.1% of each other in range/bearing. Two plausible-looking hypotheses
(coordinate-frame/projection-origin bug; `object_id` reuse colliding two real objects within one
mission) were both wrong. The real cause: the collector process was never restarted across a DCS
mission reload, so `t_sim` reset from ~1635s back to 0.0 partway through the log, and
`ConsolePerceptionRunner`'s entire belief state (`ContactStore`, which nests `GroupStore`, plus
`TaskStore`, `optic_state`, `attack_run_state`, `mission_phase_tracker`, `scan_plan`,
`attitude_history`, both perception sources' own `_object_id_to_last_observation_id` dedup maps)
carried straight through into the new mission. Every tripwire-firing contact in the "new" flight
already existed before the reset; zero were founded fresh. The new mission's own far-away real
objects were correctly rejected by the player-bubble filter and never reached belief -- perception
was fine throughout. The tripwire itself was correct and should not be changed.

**Diagnostic signature to check first, before chasing geometry**: when a huge position error is
*symmetric* across many unrelated contacts (same bearing/range from ownship, to within a fraction
of a percent) rather than scattered, suspect one shared stale/wrong *input* (observer, or in this
case the whole contact population) rather than N independent fusion failures. Check whether the
session's own `t_sim` ever goes backward -- nothing in `logger.py`/`belief/contacts.py` detects
this today (confirmed by grep, no monotonic/mission-id/reconnect check exists anywhere), so a
restarted DCS mission with the collector process left running is silently treated as a
continuation of the same flight.

**Logging gotcha that cost real time**: `detection_trace_writer.py`'s `_entry_to_dict` omits a
`None`-valued field from the JSON line entirely (absent-not-null convention) -- a text search for
`"field_name"` only finds rows where that field has a *concrete* value, which is the exact opposite
of what "field is None" means. Don't grep for a key's presence to find rows where it's null;
derive "no verdict" from the `outcome` field instead (e.g. gate-4's `None` verdict produces the
same rejection `outcome` as `False`, with the live-LOS fields simply absent).

See [[position-belief-runaway-sept24-incident]] for the earlier, unrelated defect this tripwire was
actually built to catch (a slow fusion drift, not a mission-boundary issue) -- don't assume a new
tripwire firing is a regression of that fix without checking first.
