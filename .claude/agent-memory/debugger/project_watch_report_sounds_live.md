---
name: watch-report-sounds-like-live-sighting
description: CONTACT_RANGE_CROSSED speaks with no gaze/freshness marker, so a watched-contact belief update can read as a fresh sighting off-gaze -- not a gate bug.
metadata:
  type: project
---

`belief/contacts.py::ContactStore.tick`'s watched-contact blocks (`CONTACT_MOTION_CHANGED`,
`CONTACT_RANGE_CROSSED`, `CONTACT_ENGAGEMENT_CHANGED` -- `_WATCHED_ONLY_KINDS` in
`belief/callouts.py`) are gated on `attention in ("watch", "priority")` and on belief freshness
(`certainty_of(...) in ("observed", "tracked")`, i.e. seen within `POSITION_HALF_LIFE_S` = 30s) --
**never on current gaze**. This is correct by design (`plans/watch-reporting/plan.md`): a watched
contact's range/motion/engagement update should keep coming even while Petrovich is looking
elsewhere.

`CONTACT_RANGE_CROSSED` renders through `belief/speech.py::_contact_report_text` with **no
distinguishing lead/clause at all** (Decision 3, "the range is the news... this is the user's
example verbatim" -- pinned by
`tests/test_speech.py::test_route_event_contact_range_crossed_speaks_with_no_affixes`). Its
sibling kinds do carry a marker (`CONTACT_MOTION_CHANGED`'s `event_clause`, `CONTACT_ENGAGEMENT_
CHANGED`'s `"Danger, "`/`"Safe from "` lead) -- `CONTACT_RANGE_CROSSED` alone is
indistinguishable from a live `CONTACT_DETECTED`/`CONTACT_REACQUIRED` callout.

**Symptom this produces**: a callout like "ground 10 o'clock, 2 km" while the pilot has commanded
a scan in a completely different direction (e.g. `scan right`), sounding like a fresh off-gaze
detection. It is not -- see [[project_naked_eye_gaze_gate_is_correct]]. Before assuming a gaze/
perception defect for an unprompted contact callout, check whether the event kind is one of
`_WATCHED_ONLY_KINDS` first; if so, the mechanism is belief-driven and gating it on gaze would be
wrong (it would hide a legitimate watch update the moment the player looks away).

**Escalation note**: reversing `CONTACT_RANGE_CROSSED`'s wording (adding a "still tracking" style
lead) requires rewriting the pinned Decision-3 test -- per `AGENTS.md`'s escalation rule
("existing tests must be rewritten rather than extended"), that's a user call, not something
Debugger should patch unilaterally. See `plans/callout-outside-gaze/debug.md`.
