---
name: bl-b23-contact-store-pruning-approved
description: BL-B23 (lost contacts excluded from group clustering) reviewed APPROVED clean — how the leader-coherence question resolves and the measurement reproduction technique used
metadata:
  type: project
---

`fix/contact-store-pruning` (90057c4) reviewed APPROVED, no required fixes. `ContactStore.tick`
filters its `GroupStore.reconcile` input to `certainty_of(contact, now_sim) != "lost"`, reusing
`belief.decay`'s existing lifecycle ladder — no new field, `_contacts` untouched.

**The leader-coherence question (does a group whose leader goes `lost` stay coherent) resolves
without touching `groups.py`, and the reason is specific**: `leading_contact_id` is never read off
persisted `Group` state when rendering a disclosure — `speech.py`'s `render_group_disclosure`/
`group_membership_state` recompute it fresh every call via `_leading_index(member_contacts)`, and
only *compare* it against the persisted `last_spoken_leading_contact_id` to decide whether a
"leader changed" delta should fire. So a lost leader dropping out of the next `reconcile()` cluster
is indistinguishable, downstream, from a leader lost to an ordinary spatial split — the same delta
path already handles both. Worth re-checking this exact mechanism (persisted-vs-recomputed leader
id) any time a future change touches which contacts reach `reconcile`.

**Measurement reproduction technique**: built an independent benchmark script (not reusing the
implementer's fixture code) against `test_contacts._observation`, calling `GroupStore.reconcile`
directly with an unfiltered contact list for the "before" shape and `ContactStore.tick()` for
"after". Got 70.16/405.98 ms (claimed 69.15/402.99) and 1.26 ms at n=1200 (claimed 1.40 ms) — within
noise, confirms the claimed table is a real apples-to-apples reproduction of the original
Performance Reviewer numbers, not cherry-picked.

**One discovered-but-unfiled gap**: implementer found and correctly left alone a pre-existing
`association_over_time` defect (two close contacts become ambiguous reacquisition candidates for
each other after a long gap) — recorded in `implementation.md`'s "Notable Discoveries" and two test
docstrings, but not given its own `BL-B<n>`. Flagged as optional (BL-B24, next free id) rather than
required — adequately recorded, just not top-level discoverable from `BACKLOG.md`.

See [[pb2_contactstore_thread_safety]] and [[pb2_belief_invariants]] for other `ContactStore`
load-bearing invariants re-checked here (no-omniscience boundary, dual-field pattern) — both held,
neither touched by this diff.
