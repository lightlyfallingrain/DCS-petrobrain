---
name: contact_report_flood
description: Merge-direction identity-abandonment plan (2026-10-04) — the merge was already analysed and approved; split-vs-echo is structurally indistinguishable; reuse the gate as a cross-contact check.
metadata:
  type: project
---

Plan at `plans/contact-report-flood/plan.md` (branch `fix/contact-report-flood`, tip `ae951f7` at
write time). Fourth occurrence of the same underlying engine
(`ContactStore.ingest`'s "2+ candidates → always new contact" rule, fed by a different trigger
each time) — see [[project_contact_dup_continuity_of_track]] for the third.

**Check whether a "new" problem was already analysed before treating it as unmodelled.**
`plans/group-contact-model/plan.md`'s "Merging into an existing group" section already argued the
merge-abandonment behavior is "exactly right epistemically" and this plan does not reopen that —
the debugger's framing ("never analysed by the original plan") was about the *callout* layer's
reaction, not the belief-side verdict, which was in fact already decided. Read a plan's own
rejected-alternatives sections (Splitting Option A/B here) before re-deriving the same argument;
Option A (delete-and-respawn) and Option B (group container with member ids) were both already
argued and rejected by name, with the same cost (thirteen consumers, five dangling surfaces) that
would recur if re-proposed now.

**Key structural finding, worth remembering for any future pass on this mechanism class: a
genuine split and a merge-echo re-split are indistinguishable at the perception layer, by
construction.** `naked_eye_source.py`'s merge step overwrites *every* absorbed member's
`_object_id_to_last_observation_id` entry to the survivor's new observation id, winners and losers
alike (module docstring point 6: "regardless of whether it was the winning vote"). So a later
re-split off that survivor has the exact same vote shape an ordinary, never-merged split would
have. Any belief-layer fix that tries to tell these apart needs new perception-layer plumbing
(e.g. propagating which ids were superseded, not just which one won) — which reopens "track
member identity," already rejected twice. The cheaper, honest move: accept the shared cost (an
occasional genuine split's own `CONTACT_DETECTED` goes silent too) rather than build the
classifier. State it as a cost, not a gap.

**Reusable pattern: generalise an existing percept↔contact gate to contact↔contact.**
`association_over_time.passes_gate`'s math (class-compatibility, then Mahalanobis against summed,
elapsed-inflated covariances) generalises cleanly to two `Contact`s via the already-existing
`_contact_covariance(contact, elapsed_s)` helper — no new constant, no new radius to calibrate.
Worth checking for this shape (an existing percept-vs-belief gate that a new cross-belief check
needs) before inventing a parallel one.

**`CALLOUT_MAX_AGE_S` (10s) is far shorter than `LOST_THRESHOLD_S` (120s) — this makes any
suppression keyed off "is the other contact not-yet-lost" effectively permanent, not a brief
delay.** A candidate retried every tick against a still-not-lost nearby survivor will always hit
`CALLOUT_MAX_AGE_S` and get silently dropped long before the 120s ladder matters — no separate
suppression-duration constant is needed, and don't add one expecting a "comes back after N
seconds" effect; it won't, because the aging-out always fires first.

**`CONTACT_DETECTED` vs `CONTACT_REACQUIRED` are mechanically disjoint by id-history, not just by
label** (`events.lifecycle_event_kind`): `CONTACT_DETECTED` only ever fires on a contact's
first-ever tick; `CONTACT_REACQUIRED` only when `previous_certainty == "lost"` for that *same*
id. A fix that should only touch "a brand-new id was minted" can scope to `CONTACT_DETECTED`
alone and leave genuine same-id reacquisition (the entire reason object-permanence correlation was
built) untouched, with no shared-code risk between the two branches.

**`ContactStore.ingest`'s gate-candidate loop never excludes `lost` contacts** — confirmed by
reading it, not assumed. BL-B23's "lost excluded from clustering" is a `belief.groups` reporting
concern, unrelated to this. A lost, merge-abandoned contact stays a permanently-live gate
candidate forever (nothing in `contacts.py` prunes anything, by design), which is a real amplifier
for BL-B24/`contact-duplication-ambiguity-runaway`'s still-open "2+ close candidates" policy —
but blanket-excluding `lost` contacts from the gate would break the deliberately-built "reacquire
after a long gap" story `OBJECT_ID_MEMORY_S`/`LOST_THRESHOLD_S` exist for. Don't reach for that
as a quick fix; it was considered and is wrong.

No graph query was possible this pass — `graphify-out/` did not exist in the worktree. Flag this
explicitly next time rather than silently skipping the step.
