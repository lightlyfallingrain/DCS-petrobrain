---
name: object-permanence-join-split-misattribution
description: a self-maintained object_id->contact_id cache is only sound if it also knows how to lose confidence across a cluster split that resolves on an admitted/rejected poll boundary
metadata:
  type: feedback
---

When an implementer invents a persistent `object_id -> contact_id` cache to bridge a gap where
belief retains no ground-truth DCS id (the no-omniscience boundary), check whether the upstream
perception layer already does **majority-overlap voting across cluster splits/merges**
(`perception/naked_eye_source.py` point 6 in this codebase, `BL-B76`). If it does, a same-poll
"split, and the split-off child is rejected rather than admitted" is a real gap the new cache
cannot see: the cache only updates from `ADMITTED` rows, so a rejected row for an `object_id` that
just split away from the cache's recorded contact gets silently attributed to the old contact
instead.

**Why:** found reviewing `BL-B76` Step 1 (`body-layer/src/belief_truth_log.py`,
`_update_object_id_contact_cache`/`_object_ids_for_contact`). The implementer's own docstring
claimed a stale cache entry "can only ever cause a miss... never a wrong contact's rejection being
attributed to this one" — true for the DCS-object_id-reuse risk they explicitly accepted, but not
for the split case, which their own "Notable Discoveries" section separately flagged as a *future*
risk while the in-code claim asserted it away in the present tense. Two claims in one PR,
contradicting each other, and only one of them visible to a reader six months later (the
docstring, not the implementation note).

**How to apply:** when a new join is invented specifically because an existing, more sophisticated
correlation mechanism (majority-overlap voting, continuity scoring, etc.) is "too big a change to
reach into" for this task's scope, go read that existing mechanism's own docstring anyway — it
usually names the exact failure mode the simplified join reintroduces. Don't accept "sound enough
to ship" as a conclusion until you've checked it against the one subsystem the implementer
themselves pointed at as the harder, correct version. See also
[[verify-by-mutation-per-entry]] and `CLAUDE.md`'s "Before concluding something is undocumented" —
same shape: a docstring's "X, so Y" is two claims, and "Y never happens" is the one that needs
independent verification, not the easier-to-check "X is true."
