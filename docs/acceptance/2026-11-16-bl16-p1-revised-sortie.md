# BL-16 Stage P1 (revised), takeover and stabilisation: acceptance sortie (2026-11-16)

**Artifact (cockpit-readable card):** https://claude.ai/artifact/ASTZkpr1xRuaUhqR61jScf
**Card source:** `docs/acceptance/2026-11-16-bl16-p1-revised-card.html`
**Branch to fly:** `main`, after this DoD pass's auto-merge.

What is under test, verbatim from `plans/flight-control/dod-takeover.md` "Acceptance Testing
Plan — Flight P1 (revised)": the takeover trigger ("Request Aircraft Control", not any
park/unpark binding), the command menu's keep-open/reopen behaviour, whether the held altitude
actually converges to the altitude at the moment of takeover (via `none`/`quick`/`hold`), the
accepted ~100-150 m climb-then-descend transient on the hold path, the 852/952 diagnostic mirror
pair, and a clean unpark/re-park.

This replaces Batch A's own Flight P1 card
(`docs/acceptance/2026-11-15-bl16-batch-a-card.html`), whose detection (stick/pedal park) never
saw the real handover signal — see `docs/acceptance/2026-11-16-bl16-batch-a-feedback.md` for why.

The prize is block 3: whether the altitude the AI ends up holding actually matches the altitude
the pilot was at when he pressed the binding — the whole point of this revision — not merely
"did a correction path run."

Results go to `body-layer/ROADMAP/BL-16.md`, not into the card.
