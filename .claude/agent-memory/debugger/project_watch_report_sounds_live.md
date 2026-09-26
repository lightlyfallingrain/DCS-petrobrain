---
name: watch-report-sounds-like-live-sighting
description: CONTACT_RANGE_CROSSED/MOTION_CHANGED/ENGAGEMENT_CHANGED never check current gaze or cockpit mask -- the 2025-09-25 wording fix (Getting closer/Moving away) solved "sounds like a fresh sighting" but not "spoken about a contact he cannot currently see" (2026-09-26 sortie, still open).
metadata:
  type: project
---

`belief/contacts.py::ContactStore.tick`'s watched-contact blocks (`CONTACT_MOTION_CHANGED`,
`CONTACT_RANGE_CROSSED`, `CONTACT_ENGAGEMENT_CHANGED` -- `_WATCHED_ONLY_KINDS` in
`belief/callouts.py`) are gated on `attention in ("watch", "priority")` and on belief freshness
(`certainty_of(...) in ("observed", "tracked")`, i.e. seen within `POSITION_HALF_LIFE_S` = 30s) --
**never on current gaze, FOV, or the cockpit mask**. `belief/speech.py::route_event` has no
`ownship`/gaze parameter at all, so it structurally cannot check either. This is correct by design
for the *ordinary* stale-but-recently-seen case (`plans/watch-reporting/plan.md`): a watched
contact's update should keep coming while Petrovich is looking elsewhere.

**Two sequential findings on this same mechanism, don't re-derive either:**

1. **2026-09-25** (`plans/callout-outside-gaze/debug.md`): `CONTACT_RANGE_CROSSED` rendered with
   no distinguishing lead at all, so it was word-for-word identical to a fresh
   `CONTACT_DETECTED`/`CONTACT_REACQUIRED` sighting. Fixed by wording alone (Decision 3 REVISED,
   `belief/speech.py`'s "Getting closer, "/"Moving away, " lead,
   `tests/test_speech.py::test_route_event_contact_range_crossed_says_which_way_it_crossed`) --
   deliberately *not* gated on gaze, since gating would hide a legitimate watch update the moment
   the player looks away.
2. **2026-09-26 sortie** (`plans/sortie-2026-09-26-fixes/diagnosis.md`): the wording fix works
   ("Crossings say which way -> yes") but the deeper gap it didn't touch is now reported directly:
   contacts **outside FOV** and **behind the cockpit mask** (`rear_cutoff_deg=130 deg`,
   `perception/cockpit_mask.py`) still get spoken. Confirmed against the real sortie's own
   belief-truth log (`gaze_label` vs. reported clock position mismatched on several
   `CONTACT_RANGE_CROSSED` lines, two of them dead astern) and reproduced synthetically in
   `tests/test_contacts.py::test_range_crossing_does_not_fire_for_a_contact_behind_the_cockpit_
   mask` (currently failing). **Not** the same bug as the already-fixed `los_masked_since_sim`
   bookkeeping issue on `CONTACT_ENGAGEMENT_CHANGED` (that one has a real LOS check with a reset
   bug; the range-crossing block has no visibility check of any kind to have a bookkeeping bug in).

Before assuming a gaze/perception defect for an unprompted contact callout, check whether the
event kind is one of `_WATCHED_ONLY_KINDS` first -- see [[project_naked_eye_gaze_gate_is_correct]]
for why the naked-eye detection gate itself is not the culprit.

**Escalation note, still live**: any fix needs to distinguish "recently tracked but looking
elsewhere" (fine, wording already covers it) from "currently behind the airframe" (a real
knowledge violation) -- a bare gaze-cone gate would regress finding 1's fix. This is a product
decision (`plans/sortie-2026-09-26-fixes/diagnosis.md` names it explicitly), not something to
patch unilaterally.
