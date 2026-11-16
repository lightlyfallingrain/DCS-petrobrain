---
name: feedback_reopen_zipfile_per_entry_within_one_call
description: A per-request "open a fresh resource handle" design can be correct ACROSS threads/requests and still be a real cost WITHIN a single call's own multi-item loop — check both separately, don't let the first verdict answer the second question.
metadata:
  type: feedback
---

On `raster-chart-viewer` (RC-1, 2026-11-16), `discovery.read_tile_bytes` opens a fresh
`zipfile.ZipFile` on every call, and its own docstring claims this is "negligible" next to the
~1.4MB inflate it's paired with. That claim is correct for the single-entry case (one tile, one
`ZipFile()` call) and **false** for every multi-entry call in the same codebase: a middle-zoom
request opens 16 entries, a small-mip-cold request 48-64, the full-tier warm-up/overview thousands
— and the SAME zip is reopened once per entry every time, because 4 of 5 terrains here have
exactly one zip per tier.

Measured: reusing one `ZipFile` across a 100-entry batch from the same real zip is **4.1x** faster
than the current fresh-open-per-entry code (1.84s vs 0.45s, byte-identical results). Isolated the
open cost is genuinely CPU-bound in Python's own central-directory parsing (not just I/O-bridge
latency): a local-disk 3072-entry zip costs ~7.7ms to open vs ~0.016ms for a 1-entry zip, confirmed
by timing many reps and comparing against a trivial zip, so this persists on fast native storage
too, not just the slow WSL-bridge path this review had to measure from.

**Why this matters as a reviewing habit, not just a one-off finding**: the Reviewer (previous role
in the chain here) had already checked the fresh-open-per-call design and correctly confirmed it
avoids the specific named hazard ("a shared `ZipFile` object across threads is not safe") — that
verdict is right and should not be revisited. But "safe across threads" and "cheap within one
call's own loop over many items that could share a handle" are two different questions, and a
reviewer answering the first can read as having answered the second. They didn't here — nothing in
the review or plan considered that a single request's own entry loop reopens the same zip
redundantly.

**How to apply:** whenever a "fresh resource per call" pattern is flagged/confirmed safe for
cross-thread reasons, separately check whether any *single* call site loops over multiple items
that could share that resource (same zip, same connection, same file handle) — and if so, measure
reuse scoped to just that one call/thread (never reintroducing the cross-thread hazard the original
design correctly avoided). This generalizes past zip files to any "open per request" resource:
DB connections, HTTP sessions, file handles — the safe-across-concurrency verdict and the
cheap-within-one-batch verdict are orthogonal and both need checking.

See also [[project_raster_chart_viewer_cache_sweep_batching]] for the sibling finding (full-
directory rescan on every write) from the same review — same role ("poor batching: item-by-item
where bulk applies"), different mechanism.
