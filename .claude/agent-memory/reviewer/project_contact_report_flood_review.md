---
name: project_contact_report_flood_review
description: contact-report-flood (merge-echo CONTACT_DETECTED suppression) review outcome and how to verify a deviation's "always strictly later-founded" claim
metadata:
  type: project
---

APPROVED WITH MINOR FIXES. `fix/contact-report-flood` (`d8be11e`, impl commit `c3bf79b`) adds
`contacts_plausibly_same` (generalises `passes_gate`'s calibrated gate to contact-vs-contact, no
new constant) and a `CalloutScheduler._render_event` suppression scoped to `CONTACT_DETECTED`
only.

**The implementer deviated from the plan's literal text** (added `other.first_seen_sim <
this_contact.first_seen_sim`), discovered because the plan's own named six-vehicle cluster,
probed directly against the real `CalloutScheduler`, produced *zero* spoken lines without it
(every same-poll peer saw every other as a live plausibly-same contact and all mutually
suppressed) — worse than the flood it fixes. Verified the deviation's safety by tracing the
mechanism in `naked_eye_source.py`: a merge-echo's suppressing survivor is always founded in an
earlier poll than the re-split that produces the echo, because clustering runs once per poll, so
excluding same-poll peers costs nothing against the real mechanism. **Technique worth repeating**:
when a fix adds a condition "because X always holds," trace the actual state machine rather than
trusting the stated invariant — here it held for every path, including the degenerate "merge
survivor has no prior identity" case.

**Real-path test check**: `CONTACT_REACQUIRED`-exemption test drives the real
`store.ingest`/`tick`/`scheduler.tick()` chain (not a directly-constructed `Event`) — this is the
standard to hold scoping-exemption tests to; a test that builds the `Event` by hand would not
prove the dispatcher itself routes correctly.

**Gap found**: plan's own Staging step 4 ("add one line to BL-B24 and
contact-duplication-ambiguity-runaway noting this mutes the symptom but doesn't resolve the root
policy") was never done — `implementation.md` states the right conclusion in prose, but the two
backlog/plan files a future root-policy fix would actually read were untouched. A staging
deliverable stated in the plan is not satisfied by restating it in the implementation log; check
the actual target file.

**Honest plan-vs-measurement gap, not a defect**: the plan's "at most 2, not 6" acceptance number
for the named cluster was a narrative estimate; the real retrospective measurement against
sortie-1004 gives 4 spoken + 1 suppressed for that cluster (every genuine simultaneous sighting
heard once, the one genuine echo suppressed) — a better outcome than the plan's number implies,
but literally a miss of the stated bound. Implementer disclosed this plainly; judged acceptable,
flagged as optional documentation only.
