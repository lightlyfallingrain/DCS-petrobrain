---
name: contact-ingest-association-unmeasured
description: ContactStore.ingest's association/continuity matching could not be microbenchmarked in a few minutes at 55 contacts x 500 ticks -- flagged for a future dedicated pass
metadata:
  type: project
---

While reviewing sortie-2026-09-26-fixes (a diff to `ContactStore.tick` and `optic_policy.decide`,
not `ingest`), I tried a full-pipeline microbenchmark (`ingest` + `tick`, 55 contacts, 500 simulated
ticks, one fresh observation per contact per tick) to sanity-check realistic-scale cost. It did not
complete in several minutes and was killed rather than chased down, since the cost lives entirely in
`ContactStore.ingest`'s pre-existing association/continuity matching -- code that sortie-2026-09-26-
fixes does not touch, so out of scope for that review.

**Not confirmed as a real problem** -- I did not isolate whether this is O(n^2) association matching
against a growing observation log, something in the synthetic benchmark's own construction (e.g.
re-ingesting a fresh percept per contact per tick may not match real traffic shape), or something
else. Recorded here as a flag, not a finding: **the next performance-reviewer or debugger pass on
body-layer should start by isolating and measuring `ContactStore.ingest` in isolation** (vary contact
count and observation-log length independently) before trusting that the per-tick belief path is
cheap end-to-end -- this review only cleared `tick`'s own gate logic and `optic_policy.decide`, not
the ingest step that runs immediately before both on every poll.

See [[cockpit-mask-gate-cost]] and [[optic-policy-dict-copy-cost]] for what *was* measured and
cleared in this same review.
