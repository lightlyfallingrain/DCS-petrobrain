# MI-B3 — World enrichment issues one serialized HTTP call per item, and the real count is unmeasured

- [ ] **MI-B3 — `world_enrich/enrich.py` issues one fully serialized HTTP GET per route waypoint,
  named group, trigger zone and threat signal, with no batching and no memoization. At
  world-model's own measured per-call cost this plausibly accounts for tens of seconds of
  mission-interpreter's 1:12–3:19 wall clock — but no real mission's enrichable-item count has ever
  been counted.** #status/open Filed 2026-10-16 from the whole-subproject performance review
  (`mission-interpreter/research/2026-10-16-performance-review.md`), verdict **APPROVED — MONITOR**.

  **What was measured this pass, and what was not.** Measured: the `.miz` parse is 2.37 ms on the
  committed fixture, and HTTP transport overhead is 0.29 ms per call against a local double —
  neither is the cost. Cited rather than re-derived: world-model's `describe_position` is
  **136.8 ms mean / 497.7 ms p95** against the real `syria-full` store
  (`world-model/research/2026-10-05-performance-review.md`, finding 2). **Not measured: how many
  enrichable items a real mission actually has** — the pilot's own test missions
  (`MI24-outpost-M03/04/06.miz`) and the Bagram sample are absent from every checkout, so the review
  published a per-item-count sensitivity table instead of a total. That restraint is the right call
  and is why this item leads with the measurement rather than the fix.

  **So the work is, in order:** count the items against a real multi-leg Syria mission; only if the
  count justifies it, fan the calls out concurrently from mission-interpreter's side (a thread pool)
  **rather than adding a batch endpoint to world-model's server** — the server is single-threaded by
  design because one instance shares one non-thread-safe `sqlite3.Connection`, so the concurrency
  belongs on the client.

  **Double-gated, and the second gate matters more than the first**: mission-interpreter's output
  currently reaches **no pilot-reachable path** — `mission_phase` touches four body-layer files and
  none of `attention.py`, `callouts.py` or `crew_console.py`. Until that changes, this is minutes
  of *desk* wait before a sortie, not anything the pilot feels in the cockpit. Worth knowing before
  anyone optimises it.
