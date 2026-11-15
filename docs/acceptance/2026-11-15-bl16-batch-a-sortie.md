# BL-16 parked mode, batch A: acceptance sortie (2026-11-15)

**Artifact (cockpit-readable card):** https://claude.ai/artifact/4LzaK1cWJVsayFpYVbTscE
**Card source:** `docs/acceptance/2026-11-15-bl16-batch-a-card.html`
**Branch to fly:** `main` (merge `c38740d0`, pushed `c9bc6b32`)

What is under test, verbatim from `plans/flight-control/dod-batch-a.md` "Acceptance testing":
Flight P-ICS (operator-seat ICS trigger, arg 856), Flight P0 (the seven-row AI-wheel probe,
`Export.probe-ai-pilot-wheel.lua`, its own DCS session since it replaces the production
Export.lua), Flight P1 (activation on park, altitude nudge, no speech).

The prize is P0-1: whether `list_indication(6)` carries the AI readback text with the command
(right) wheel closed. The readback (left) overlay is always on while the AI flies (user,
2026-11-15: *"There is no way to turn it off"*), so the question is only whether Petrovich can
read it without opening the command menu.

Results go to `body-layer/ROADMAP/BL-16.md` and
`aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md`, not into the card.
