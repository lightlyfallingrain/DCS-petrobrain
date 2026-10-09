# BL-B40 — The last 1.6× of `group_salient_ids`' hoist

- [ ] **BL-B40 — The last 1.6× of `group_salient_ids`' hoist is located but not worth taking yet.** #status/open
  Found by the [[BL-11]] performance pass, 2026-10-06 (`plans/bl11-tick-cost/performance-review.md`),
  which **declined the code change and recorded the number instead** — filed here so the analysis is
  not lost rather than because it should be done.

  `clustering.py:195-196`'s `angular_separation_rad` rebuilds each candidate's observer-relative
  difference vector **per pair** — the one per-candidate quantity Stage 2 left inside the O(n²) loop.
  Hoisting it (keeping `atan2(|cross|, dot)` verbatim, output bit-identical) measures **8.0× at 58 k
  pairs** against the shipped 5.1×, i.e. exactly the 8.1× the original note predicted.

  **Why it is not worth doing now, with the arithmetic**: the whole term is **1.1 ms in situ**, so
  1.6× saves ~0.4 ms of a 12.6 ms poll against a 1,000 ms budget. Revisit only if the realised
  period starts overrunning — and note the pass's own finding that the ratio **saturates at 5.1×
  from ~2,500 pairs upward** and is still 5.1× at 169 k pairs, nearly double the sortie's ~96 k, so
  a bigger mission does not make this term grow back into relevance.

  **The real tail is elsewhere**: the residual 2 % of polls that overrun 1.0 s is entirely
  `describe_position` at ~57–85 ms/call, which costs the same cold, warm, 1 m apart or within one
  cell. That is a `query.describe` question, not more body-layer caching.
