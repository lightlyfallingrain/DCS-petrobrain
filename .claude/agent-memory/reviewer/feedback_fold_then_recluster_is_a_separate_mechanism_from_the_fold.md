---
name: feedback_fold_then_recluster_is_a_separate_mechanism_from_the_fold
description: a position-mutating fold/merge inside ingest() can have consequences that surface one tick later inside reconcile()'s own, separately-gated clustering -- check the second mechanism directly, don't assume the fold's own gates (e.g. D6) bound it
metadata:
  type: feedback
---

When a mechanism inside `ContactStore.ingest` moves a contact's *fused position* (not just its
record contents), the consequence is not confined to `ingest`'s own decision rule or its own
gates. The very next `ContactStore.tick()` call re-clusters *all* currently tracked contacts from
scratch, purely by position (`groups._cluster_contacts`, single-link union-find, no class or
air-defence awareness at all) — so a position nudge inside `ingest` can pull an entirely unrelated,
never-itself-ambiguous contact into a `Group` one tick later, through a different code path with
different (or no) gates.

**Why this matters for review, not just for the mechanism's own correctness**: BL-12 Stage 3's D6
carve-out (air-defence resolves through the classification lattice, not `profile_for`) is correctly
built and correctly gates the *fold* itself — verified by mutation, the carve-out test fails exactly
as predicted when the resolution path is swapped. But D6's hard gate (Stage 1 test 3,
air-defence-confirmation) only runs inside `reconcile`'s *phase 2* (property match — a cluster with
zero member overlap against a remembered group). The absorption this finding describes resolves
through *phase 1* (overlap match, since the widened cluster already shares most of its members with
an existing group), which carries **no** class/air-defence/displacement check whatsoever. So "the
fold's own safety gate is correct" and "the fold's downstream consequence is safe" are two different
claims, and verifying the first by mutation does not verify the second — they live in different
functions, reached by different reconcile phases.

**How to apply:** when a change mutates fused-position state inside one function, trace what the
*next* tick's own, separately-triggered mechanisms (reconciliation, re-clustering, re-scoring) do
with that new position — don't assume the gates reviewed in the function that moved the position
also bound what happens to it afterward. Reproduce the downstream consequence directly (a real run,
not an inference from "D6 passed its own test") before concluding a safety-relevant carve-out is
unaffected by a second-order effect discovered elsewhere in the same stage.
