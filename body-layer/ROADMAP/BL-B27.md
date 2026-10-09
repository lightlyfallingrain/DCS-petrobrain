# BL-B27 — `say again` fires on unaddressed cockpit speech

- [ ] **BL-B27 — `say again` fires on ordinary cockpit speech that was never addressed to
  Petrovich.** #status/open Found in the 2026-10-05 sortie's speech log, not reported by the pilot — four
  interruptions in 70 minutes, so it is a polish item rather than a defect that spoiled the flight.

  `"Peace."` (confidence **1.00**), `"All right."`, `"See you again."` and `"Can I sell it?"` all
  produced `say_again` — Petrovich audibly asking the pilot to repeat something that was not a
  command. `"Yes."` by contrast fell through silently, which is correct.

  **So the two non-command paths disagree**, and that is the actual bug: some unrecognised
  utterances fall through (right) and others reach the say-again band (wrong). This is the same
  class as the bare `"quiet"` phrase dropped during the `silence` work — a confident recognition of
  something that was never addressed to him — and the fix is likely a floor on what may reach the
  say-again band at all, not a threshold tweak. Do not fix it by raising `CONFIRM_FLOOR`:
  `"Peace."` scored 1.00.

  Log: `~/dcs-speech.jsonl`, and the analysis in
  `aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md`.
