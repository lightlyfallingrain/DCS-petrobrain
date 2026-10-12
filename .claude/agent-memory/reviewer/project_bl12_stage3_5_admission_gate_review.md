---
name: bl12-stage3-5-admission-gate-review
description: BL-12 Stage 3.5 (BL-B58) admission gate reviewed clean -- the "cannot evict or found" claim held under mutation of the co-member exemption, and the three user decisions (reset rule, BL-B59 disposition, BL-B50 recheck) all landed in the files themselves, not just the implementation log.
metadata:
  type: project
---

Reviewing `feature/bl12-group-contact-identity` at `005309c` (BL-12 Stage 3.5, the cohesion
admission gate, `BL-B58`): every claim in `implementation.md` reproduced directly rather than
accepted. Per-commit pytest counts (1677/4 at `7946c8d`, 1682/4 + 1 expected failure at `57f67d0`,
1683/4 at `005309c`) matched exactly via isolated `git archive` snapshots run from inside each
snapshot's own `body-layer`.

**The one claim worth remembering how it was tested**: "the gate structurally cannot evict or
found" rests entirely on one branch — prior co-members always get the ordinary, unaffected rule.
Mutating that branch out (always apply the admission inflation, even to co-members) broke exactly
the tests that silently depend on it (Rows A, B, F in `test_groups.py`), because Row A's own
assertion requires `CONTACT_1`/`CONTACT_2` — both carrying large fold budgets, both prior
co-members — to stay linked despite their own budgets. That is the exemption property, hiding
inside what reads as an "exclude the bad member" test. A reviewer who only read the assertion
(clusters == [{1,2,3}]) would not see that this is also the co-member-exemption's only coverage.

**Second thing worth keeping**: the implementer's claim that a new probe-signature fix "did not
change what the probe measures" was true here (one-line call update, `[]` for a new required
parameter, with a comment stating the probe's own purpose is unchanged) — confirmed by re-running
it and getting the pre-implementation numbers back exactly. Worth checking this kind of claim by
re-running rather than reading the diff, since a one-line fix is exactly the size of change that
could silently alter what's being measured.

See [[feedback_mutate_the_assertion_not_just_the_accessor]] (same lesson, different incident, same
stage's earlier commit) and [[project_bl12_clustering_seam]] (architect memory, the seam reasoning
this gate implements).
