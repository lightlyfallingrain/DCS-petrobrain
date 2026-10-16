# X-B8 — Per-module performance review

- [x] **X-B8 — Per-module performance review, findings written to a document, and that document becomes a
  backlog item. DONE 2026-10-16 — all six subprojects.** #status/done User, 2026-09-25; the last two
  ran the same day the user asked for them (*"queue perf and security scans on both MI and brain
  layer"*).

  **The two closing passes, and what each returned:**

  - **brain-layer** (`brain-layer/research/2026-10-16-performance-review.md`) — **APPROVED —
    MONITOR, no new findings.** Its existing per-feature reviews had already been written against
    real sockets, including an accept-then-never-answer listener, so the whole-subproject framing
    found no gap. `handle()`/`poll_replies()` measured at **0.088 ms** max against a deliberately
    wedged daemon, against **5015 ms** before that fix. Reply queue is a bounded
    `deque(maxlen=64)`; the job slot is newest-wins with no unbounded structure.
    **This is the one subproject where `X-B8`'s own premise did not hold** — its per-feature passes
    had looked at the whole module both times, not just the diff.
  - **mission-interpreter** (`mission-interpreter/research/2026-10-16-performance-review.md`) —
    **APPROVED — MONITOR**, one credible finding now `[[MI-B3]]`: enrichment issues one serialized
    HTTP call per item with no batching, and **nobody has ever counted a real mission's enrichable
    items**, so the review published a sensitivity table rather than a total. Measured in passing:
    `.miz` parse 2.37 ms, HTTP transport 0.29 ms/call — neither is the cost.

  **Items filed from the two passes**, per this entry's own *"that document becomes a backlog
  item"*: `[[MI-B3]]`. brain-layer needed none — its two MONITOR items were already tracked.

  **State measured 2026-10-16** (the user asked whether this was done — it is not, and the honest
  answer is two thirds):

  | subproject | whole-subproject performance pass |
  |---|---|
  | aircraft-layer | `research/2026-09-26-performance-review.md` |
  | audio-adapter | `docs/reviews/perf-review-audio-adapter.md` |
  | world-model | `research/2026-10-05-performance-review.md` |
  | body-layer | `research/2026-10-05-performance-review.md` |
  | **brain-layer** | **none** — only per-feature passes under `plans/brain-layer/` |
  | **mission-interpreter** | **none** |

  `[[X-B12]]` closed into this item on 2026-10-16, so this is the only place the remaining two are
  tracked. Note brain-layer is the one with a live model call in the loop, which makes it the more
  interesting of the two for this role. Each subproject reviewed in its own right —
  `world-model/`, `aircraft-layer/`, `body-layer/`, `audio-adapter/`, `brain-layer/`,
  `mission-interpreter/` — rather than only the per-feature passes that have run since
  2026-09-24. Those per-feature passes found real things (LOS sampled before the range gate; a
  wedged-brain poll costing 5015 ms every cycle), but they only ever look at what one branch
  touched.
