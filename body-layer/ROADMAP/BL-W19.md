# BL-W19 — BL-7's phase data is unreachable in a sortie

- [>] **BL-7's phase data is unreachable in a sortie — found 2026-09-24, DEFERRED TO THE BRAIN (user, 2026-09-24).** #status/deferred
  `--mission-understanding` loads the artifact and `MissionPhaseTracker` updates every poll, but
  **nothing a pilot can reach in flight reads it.** `mission_phase` appears in four files
  (`console.py`, `tools.py`, `mission_phase.py`, `tool_api.py`) and in none of `attention.py`,
  `callouts.py` or `crew_console.py`. The phase-proximity tie-break is real but sits inside
  `_highest_attention_contact`, called only by `get_situation`, called only by the `--console`
  debug harness; the brain that would otherwise call the tool API is still `NullBrainClient`. So
  mission phase currently changes nothing about what Petrovich attends to or says on a `--crew-text`
  sortie. Two ways out, and they are not equivalent: a crew-facing way to *ask* (a `situation`
  command — cheap, but only surfaces phase when asked), or phase feeding attention/callout ordering
  directly (what BL-7's own plan implies, and what would make the tie-break matter unprompted).
  Pilot's report of the same gap: *"the commands to exercise it during mission do not exist yet."*
  Blocks the B half of `docs/acceptance/2026-09-24-mission-interpreter-sortie.md`.

  **Deferred deliberately, not forgotten.** User direction 2026-09-24: *"situation/phase — not
  needed yet, there is nothing that consumes it yet. Defer till brain."* Building a `situation`
  command now would produce a readout nothing acts on; phase earns its place once a brain is
  reasoning over it. Do not start this without the brain layer existing.

