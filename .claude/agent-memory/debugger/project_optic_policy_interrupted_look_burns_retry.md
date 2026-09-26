---
name: optic-policy-interrupted-look-burns-retry
description: optic_policy.decide marks a look-target attempted the moment a look STARTS, and lower_binoculars (called on every player command) can end it early with no distinction from a completed look -- one interrupted look can permanently lock a stalled-range contact out of binoculars.
metadata:
  type: project
---

`belief/optic_policy.py`'s `is_worth_a_look`/`can_still_improve`/`attempted_at_range_m` mark every
`LookTarget` a look covers as attempted **the instant `decide()` transitions into `GLASSING`**, by
design (`is_worth_a_look`'s own docstring: "a look marks every contact it covers as attempted the
moment it starts... so if the stop condition asked 'is this still worth a look', every look would
end on the poll after it began" -- a real conflation a test caught during Stage 2/3b).

That marking is correct when the look reaches its own natural end (`look_is_finished`: recognition
succeeded, nothing left to improve, or `MAX_LOOK_S` expired). **It is not distinguished from a look
`lower_binoculars` ends early** -- and `lower_binoculars` fires on *any* player command
(`crew_console.py`'s own docstring: "new command from player lowers binoculars... not per command
type"), so a routine voice command landing one or two seconds into a look burns the same
`RETRY_RANGE_FRACTION` (0.8, i.e. must close 20% closer) budget as a fully completed one -- with
**no time-based re-eligibility at all**. A watched contact under sustained observation rather than
being closed on (an orbit, a stand-off) can sit at essentially constant range for the rest of the
encounter, so one interrupted look near the start of an engagement can permanently foreclose ever
raising binoculars on that contact again.

Confirmed against a real sortie's belief-truth log (`~/dcs-belief-truth.jsonl`, not in the repo):
44 of 52 contacts had at least one row inside `improvement_window_m`'s presence->class window
(500-1750 m), several sat there for 200-1200+ simulated seconds and never advanced past
`PRESENCE` -- far more opportunity than the ~16s `SCAN_CYCLE_PERIOD_S` cadence should have needed
to eventually succeed, if the retry budget weren't getting burned early. Reproduced without any
store/log, purely against `decide`/`lower_binoculars`, in
`tests/test_optic_policy.py::test_a_command_interrupted_look_is_not_permanently_burned` (currently
failing).

**Not a plan reversal** -- `plans/binocular-optic/plan.md`'s attempted-marking rule presupposes a
look that ran; nothing says an early-terminated look should count the same. This is a real
interaction gap between two separately-correct decisions (Stage 2's phase-cycle marking rule, and
the later "any command lowers binoculars" rule) that were never cross-checked against each other.

See `plans/sortie-2026-09-26-fixes/diagnosis.md` for the full writeup, including why a fix needs
the user's input (it touches the phase-cycle design directly, not just a threshold).
