# BL-B32 — `POST /speak` synthesizes TTS inside the poll body

- [ ] **BL-B32 — `audio-adapter`'s `POST /speak` synthesizes TTS synchronously, inside the poll
  body.** #status/open Found by the 2026-10-05 performance pass
  (`body-layer/research/2026-10-05-performance-review.md`). `audio-adapter/src/server.py:190`
  synthesizes before responding, and body-layer's `push_speech` runs inside `drain_events`, inside
  the poll body — so **every spoken callout blocks perception on speech synthesis**, and it stalls
  exactly the polls right after Petrovich notices something. Magnitude unmeasured (no TTS engine in
  the agent's sandbox). Crosses the body-layer/audio-adapter seam, so it is an Architect question
  (async synthesis, or a fire-and-forget hand-off), not a local edit. Not folded into [[BL-11]]
  for that reason.
