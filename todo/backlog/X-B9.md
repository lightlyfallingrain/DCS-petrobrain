# X-B9 — Per-module security review

- [x] **X-B9 — Per-module security review, same shape: findings to a document, document becomes a backlog
  item. DONE 2026-10-16 — all six subprojects.** #status/done User, 2026-09-25.

  **The two closing passes. No exploitable vulnerability in either**, under the user's own scoping
  (single-user, LAN-only, under active development — a survey for real exposure, not a hardening
  audit):

  - **brain-layer** (`brain-layer/research/2026-10-16-security-audit.md`) — the audit that mattered
    most, since this is the only component taking **model output** as an input to behaviour. Both
    founding rules hold **structurally rather than by docstring claim**: the model never writes what
    Petrovich says, and `reply.because` was traced to exactly **one** reader in the whole body-layer
    tree — the D10 validator's own substring check — never reaching speech, overlay or any
    downstream log. Two low/low items filed: `[[BR-B2]]`, `[[BR-B3]]`.
  - **mission-interpreter** (`mission-interpreter/research/2026-10-16-security-audit.md`) — the one
    subproject parsing files it did not write. Confirmed clean on every shape worth worrying about:
    no `extractall` (no zip-slip), no `eval`/`pickle`/`yaml.load`, no SSRF (both HTTP clients hit
    fixed localhost URLs, never mission-derived), and the coordinate-leak boundary is structural —
    `EnrichedThreatSignal` has no x/z field, so a future bug cannot leak one. Items filed:
    `[[MI-B1]]` (the real finding: `TriggerZone.hidden` parsed and never consulted, needing an
    investigator pass rather than a guess) and `[[MI-B2]]`.

  **One finding is about this process rather than about code**, and is worth carrying: `[[BR-B3]]`
  is verbatim the Stage 2 review's own unfiled *Finding 2* from 2026-09-25 — written as a
  recommendation, never turned into a backlog item, and therefore sitting in prose for three weeks
  where nothing could schedule it. The *"findings become a backlog item"* half of this entry is the
  rule it slipped past.

  **State measured 2026-10-16**, same shape as `[[X-B8]]`'s table: aircraft-layer
  (`research/2026-09-26-security-review.md`), audio-adapter
  (`docs/reviews/security-audit-audio-adapter.md`), world-model and body-layer (both
  `research/2026-10-05-security-audit.md`) are done; **brain-layer and mission-interpreter have
  no whole-subproject pass**. `[[X-B12]]` closed into this item.

  For brain-layer specifically this is the survey that has never run over the one component that
  takes **model output** as input — the closed-set validator is the designed defence, and nothing
  has audited it as a whole rather than per feature. Same reasoning and same module list. Note the standing scoping the
  user set when re-enabling the role: single-user, LAN-only, under active development — so this is
  a survey for real exposure, not a hardening audit. The per-feature pass has already found one
  genuine item this way (a service binding all interfaces for no benefit), which is the argument
  for doing it systematically.
