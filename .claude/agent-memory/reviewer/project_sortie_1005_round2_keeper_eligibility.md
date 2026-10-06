---
name: sortie-1005-round2-keeper-eligibility
description: NEEDS FIXES — a per-group "keeper" suppression silenced watched peers when the keeper itself was ineligible; found by running the code, not reading it.
metadata:
  type: project
---

`feature/sortie-refinements` round 2 (`f955a73`, the Security/Performance change-request fixes).
Both fixes did what was asked and both new tests were non-vacuous. The finding was a **new silence
path the fix introduced**, not a failure to fix.

**The pattern, which generalises:** a de-duplication that elects **one representative per group**
and discards the rest must elect it from the set that is *eligible to speak*, not from the whole
group. `belief/callouts.py` suppressed `_WATCHED_ONLY_KINDS` events for every grouped member but
the "keeper" (`speech.py::group_callout_member_id`, widest threat envelope, falling back to
`min(member_contact_ids)`). The keeper was chosen with no regard for whether the keeper was
*watched*. The filter's own not-watched check then dropped the keeper's event while the peers were
already `_consumed`: **2 lines before the change, 0 after**.

**Why it mattered rather than being theoretical:** mixed-watched groups are the feature's own
accepted design — Item 3's scope is *"tag once, static"*, with a test asserting it
(`test_a_unit_that_joins_the_group_later_is_not_retroactively_watched`), and `GroupStore.reconcile`
rebuilds `member_contact_ids` every call while keeping the group id. So a watched group gains
unwatched members continuously. Two routes to an unwatched keeper: an air-defence contact joining a
truck convoy wins the envelope comparison outright (trucks/armour have no envelope); and the
fallback `min()` is **lexicographic** over unpadded `CONTACT_<n>` ids, so past nine contacts
`CONTACT_10 < CONTACT_2` and a later-joined member sorts first.

**How it was found — the method, since reading did not find it.** Reused the branch's own test
helper in a throwaway script, left the keeper unwatched, watched the peers, and printed
`spoken`; then disabled the suppression and printed it again to get the before/after. Three reads
of the diff had not surfaced it: every test in the suite watches *all* members, so the code and the
tests agreed with each other. **When a change elects a representative, construct the case where the
representative is the one that cannot act.** See [[feedback_boundary_only_tested_via_fixture]] —
same shape, a path correct only because no fixture entered it.

**Cross-branch check that paid off.** `git merge-tree --write-tree <tip> <sibling>` proved
`callouts.py` auto-merges with `fix/callout-observability-gate` *and* let me read the merged result:
the sibling's observability gate lands after the suppression and reproduces the identical silence
mode (unobservable keeper, peers already consumed). The sibling had solved exactly that for its own
group path — *"any one member observable is enough"* — so the eligibility-subset fix generalises to
both gates. It also refuted the implementation log's "should merge without conflict": six files
conflict, including `test_callouts.py`.

Also required: two docstrings asserting the pre-change behaviour (*"Never filtered by group
membership either"*, *"every other kind still competes … grouped contact or not"*) were left
standing four lines above the new paragraph that contradicts them.
