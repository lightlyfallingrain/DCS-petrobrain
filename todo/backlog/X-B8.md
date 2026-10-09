# X-B8 — Per-module performance review

- [ ] **X-B8 — Per-module performance review, findings written to a document, and that document becomes a
  backlog item.** #status/open User, 2026-09-25. Each subproject reviewed in its own right —
  `world-model/`, `aircraft-layer/`, `body-layer/`, `audio-adapter/`, `brain-layer/`,
  `mission-interpreter/` — rather than only the per-feature passes that have run since
  2026-09-24. Those per-feature passes found real things (LOS sampled before the range gate; a
  wedged-brain poll costing 5015 ms every cycle), but they only ever look at what one branch
  touched.
