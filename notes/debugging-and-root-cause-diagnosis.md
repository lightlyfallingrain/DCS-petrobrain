# Debugging & Root-Cause Diagnosis

- **A confident, code-derived reproduction can be a real defect on an unreachable path, while the
  user's own one-line diagnosis names the path that actually fires.** The `position-belief-runaway`
  debug session's own hypothesis (ill-conditioned triangulation — near-parallel disagreeing looks
  intersecting far outside either input) reproduced the reported numbers exactly, and was fixed.
  But the pre-existing association gate in `association_over_time.passes_gate` already rejects
  that large a single-poll disagreement before it ever reaches fusion in production — a fact
  established only by tracing `ContactStore.ingest`'s call path, not by the reproduction script
  itself. The mechanism that actually produced the live 87.5 km callout was a slow directional
  drift (many small, individually-plausible steps, each passing every existing gate), which is
  exactly what the user's own diagnosis named: *"position uncertainty needs a gate, cannot be
  further than detection range."* That one line pointed at a missing invariant (nothing checked a
  fused position against physical detection range at all), not at a numerically fragile formula.
  Lesson: when a live defect prompts a debugging session, a hypothesis that reproduces the
  reported numbers under direct construction is not yet shown to be the *production* path — trace
  whether the gates the real pipeline runs the input through would actually let that input reach
  the reproduced code, and weigh a domain expert's structural diagnosis ("there's no gate for X")
  as seriously as a numerically-confirmed mechanism (`position-belief-runaway` debug report +
  review, 2026-09-25).
