---
name: recurring-threadinghttpserver-shared-state-race
description: Shared mutable state crossing a ThreadingHTTPServer/background-thread boundary with no lock has now recurred across 5+ features, usually caught at Reviewer (sometimes later) rather than designed in from the start — process debt worth a check earlier in the sequence
metadata:
  type: project
---

Every time this project builds a service that combines `ThreadingHTTPServer` (or any
request-per-thread server) with a background worker thread touching the same mutable object,
the first draft ships without a lock, and a later role — usually Reviewer, running a real stress
test rather than reading the code — finds a reproducible crash or race. Recurring occurrences
found in agent memory as of this note (2026-11-16):

- `reviewer/project_pb2_contactstore_thread_safety.md` — body-layer `ContactStore` (poll thread vs
  REPL thread).
- `debugger/project_repl_thread_sqlite_reuse.md` — body-layer console REPL splitting a
  `sqlite3.Connection`/`EnrichmentContext` across threads.
- `reviewer/feedback_reproduce_thread_safety_claims_dont_just_read_them.md` — the general lesson,
  minted after a specific case: reading for a missing lock does not find a real crash; a short
  stress script does, in minutes.
- `implementer/project_mi2_world_enrichment.md` — world-model's HTTP server could not safely use
  `ThreadingHTTPServer` over one shared `sqlite3.Connection`; caught by the implementer before
  Reviewer this time (the one occurrence found *before* this stage).
- `reviewer/feedback_aircraft_hardening_accept_race_required_fix.md` (aircraft-layer-hardening) —
  an `accept()` guard's shutdown-classification claim was empirically racy.
- **RC-1 (raster-chart-viewer, 2026-11-16, this feature)** — `TileCache`'s `_total_bytes` counter
  and its `_enforce_cap`/eviction sweep had no lock around them despite being written from both
  `ThreadingHTTPServer` request threads and the background `WarmupScheduler` thread; Reviewer
  reproduced a real `FileNotFoundError` crash (31/3200 writes) with a direct stress test, not by
  reading the code — required fix, fixed with one `threading.Lock`, re-reviewed and approved.

**Why this is process debt, not just code debt.** Five-plus independent features have shipped
this same shape of defect at implementation time, and the catch has landed at Reviewer (or later)
in most of them — meaning each one cost a full extra review round-trip that a design-time check
could have prevented. The one counter-example (MI-2) was caught by the implementer itself, by
writing a real multi-threaded test early rather than trusting the design.

**Recommendation for whoever reads this next**: the project's architect/implementer role files
could gain a standing checklist item — "does this design put a background thread and a
request-serving thread (or any two threads) against the same mutable object? If so, say in the
plan/implementation log whether it is locked and how that was verified (a real stress test, not
a read)" — rather than relying on Reviewer to keep independently rediscovering the same category.
This is a candidate for an earlier gate (Architect's plan checklist, or Implementer's own
self-check before handoff) rather than a permanent Reviewer tax.
