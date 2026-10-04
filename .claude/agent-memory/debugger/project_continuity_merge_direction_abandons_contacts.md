---
name: continuity-merge-direction-abandons-contacts
description: naked_eye_source's majority-overlap continuity rule, applied to a merge of several already-separate contacts, silently abandons all but the winner
metadata:
  type: project
---

`NakedEyePerceptionSource._build_observations`' object-permanence continuity
(`src/perception/naked_eye_source.py`, module docstring point 6) was built and tested for
*splitting* one parent cluster into children (`plans/group-contact-model/plan.md`'s Splitting
section). It was never analysed for the mirror case: several **already-independent,
already-identified** contacts' objects folding into one supercluster on a single poll (a gaze
sweep admitting one more real vehicle is enough). The majority-overlap vote can only inherit one
historical identity; every other contact involved is simply abandoned — no further updates, no
signal to `ContactStore` that its object moved rather than vanished. Reproduced live from a real
sortie (`plans/contact-report-flood/debug.md`): one tight scatter of 6 vehicles produced 5
contact ids and 6 separate "first sighting" callouts in 52 seconds this way.

**Why:** this is the third/fourth occurrence of the same mechanism class
([[project_contact_fragmentation_churn]] if that memory exists, else see
`plans/contact-fragmentation-at-range/debug.md` and
`plans/contact-duplication-ambiguity-runaway/debug.md`). Each prior pass concluded the fix is a
policy decision (what should happen to a merge's discarded identities), not a mechanical bug, and
escalated to Architect rather than patching. This pass confirms that reading holds for the merge
direction too — reproduced with a **clean majority vote, no tie to break**, so "pick a better
tie-break" is not the lever.

**How to apply:** if dispatched on a future "duplicate contact" / "flood of reports" complaint,
check whether real churn is happening (object↔contact id reassignment in the raw
`detection-trace.jsonl`, not `belief-truth.jsonl`'s own nearest-object join, which drifts and is
not reliable evidence on its own) before assuming it is a disclosure-policy question
(`plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md`'s "singular callout" framing
does NOT generalize — that was a different sortie with near-1:1 contacts:objects and almost no
re-founding). Do not patch `naked_eye_source`'s continuity vote or `ContactStore`'s ambiguity rule
as Debugger — escalate the actual policy call to Architect, same as the prior two passes.
