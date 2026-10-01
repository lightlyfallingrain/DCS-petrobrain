---
name: group-disclosure-range-retrigger
description: belief.groups.Group disclosure re-triggers on range/clock drift alone; fixed via a separate content_signature; the underlying cohesion math itself is fine
metadata:
  type: project
---

`belief/callouts.py::CalloutScheduler.tick`'s group-candidate dedup used to compare the *full*
rendered `render_group_disclosure` text against `Group.last_spoken_signature`. Since that text
always ends with a clock/range clause, and range drifts on nearly every tick a group is being
approached or departed, the entire composition got re-spoken every ~500 m of range change --
confirmed directly from a real sortie's spoken-line log (`dcs-belief-truth.jsonl`'s `kind:
"speech"` records), six identical lines over 56 s as the aircraft opened range. Fixed
(2026-10-01, `plans/group-undermerging/debug.md`) by adding `OutgoingSpeech.content_signature`
(the composition, with clock/range stripped out) and comparing/storing *that* instead of `text`.
Any future per-contact or per-event disclosure that embeds live, continuously-drifting facts
(range, bearing, anything from `relative_now`) into its spoken text should use the same
composition-vs-position split before wiring it into a dedup/repeat-suppression check, or it will
have the identical defect.

Separately: a position-uncertainty-budgeted cohesion test for `belief.groups._cluster_contacts`
was tried and reverted -- see [[groups-cohesion-uncertainty-budget-reverted]]. The real mechanism
behind "grouping seems to work better the closer I get" was investigated via direct trace replay
and found to be: the existing, *unmodified* clustering algorithm already converges to the correct
multi-member group once enough looks accumulate (no fix needed); the user's actual complaint,
confirmed by his own later-supplied spoken-line evidence, was entirely the range-retrigger bug
above, not a failure to aggregate.
