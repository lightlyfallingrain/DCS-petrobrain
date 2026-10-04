---
name: redundant-group-disclosure-round2-approved
description: Round-2 follow-up (shared merge-echo predicate, BL-B25, bookkeeping) for fix/redundant-group-disclosure reviewed APPROVED clean
metadata:
  type: project
---

Round 2 of `fix/redundant-group-disclosure` (commit `9adaccf`, over round 1's `4d81c43`) actioned
all three of round 1's Optional Refinements and was reviewed APPROVED, no required fixes.

What it did: extracted the merge-echo condition `_render_event` and
`_already_reported_member_ids` both restated character-for-character into one shared
`_is_merge_echo_of_earlier_contact(contact, store, now_sim)` in `body-layer/src/belief/
callouts.py`; filed the round-1 current-tick-re-evaluation residual as `BL-B25`
(`body-layer/BACKLOG.md`); added bookkeeping to `body-layer/ROADMAP.md`, `BL-B24`, and
`plans/contact-duplication-ambiguity-runaway/plan.md` mirroring `fix/contact-report-flood`'s own
`3884840`.

How I verified the refactor was behaviour-preserving, not just claimed: read all three sites
(helper + both former call sites) against the commit's parent and confirmed argument-level
equivalence — `_already_reported_member_ids`'s old `other.id != contact_id` (dict key) vs. the
helper's `other.id != contact.id` only holds because `store.contact(contact_id).id == contact_id`
always, which I checked by reading `ContactStore.contact`'s lookup-by-id semantics rather than
assuming it. 1414 passed/4 xfailed unchanged confirms it empirically too.

Checked `BL-B25`'s numbering by listing every `BL-B<n>` in `body-layer/BACKLOG.md` and sorting
numerically (not eyeballing the file tail) — confirmed 24 was the prior max.

One cosmetic-only finding, not a required fix: `implementation.md`'s own addendum labels the two
non-predicate findings "Item 2" (bookkeeping) and "Item 3" (residual), which is the reverse order
from how `review.md`'s own Optional Refinements list them — content maps correctly, only the
numbering label is swapped. Also noted the sortie-1004 "strictly earlier founding only" rationale
stayed only at the `_render_event` call site, not the shared helper's docstring — a real but minor
discoverability gap for a reader arriving via the group-disclosure path, flagged optional only.

See [[project_contact_report_flood_review]] for the first fix this one's bookkeeping pattern
mirrors, and `plans/redundant-group-disclosure/review.md` for the full round-1 and round-2 text.
