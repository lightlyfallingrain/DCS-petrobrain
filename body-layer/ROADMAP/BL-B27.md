# BL-B27 — `say again` fires on unaddressed cockpit speech

- [x] **BL-B27 — DROPPED 2026-10-16 by user direction: the diagnosis was wrong about what the
  recognitions were.** #status/done

  **His words:** *"BL-B27 -> this is actually incorrect STT, not background speech. A different
  thing, different problem. Drop this."*

  **What that overturns.** This entry read the four utterances as *ordinary cockpit speech that was
  never addressed to Petrovich* — background talk leaking into the command path — and concluded the
  two non-command paths disagreed about what may reach the say-again band. The pilot, who was in the
  cockpit, says the recognitions were simply **wrong transcriptions**: `"Peace."` at confidence
  1.00, `"See you again."`, `"Can I sell it?"` are not things he said and went unaddressed, they are
  what the recogniser produced from something else. **So the band is not the defect, and a floor on
  what may reach it would be a fix aimed at a symptom of a different problem.**

  Worth keeping as a reasoning lesson rather than deleting: the evidence was a speech log, not the
  cockpit, and a confident transcription read as *"he said this and it wasn't for Petrovich"* when
  the actual reading was *"he said something else entirely"*. A log cannot distinguish those two;
  only the person who was speaking can. The entry was filed from the log alone, and the pilot had
  not reported it.

  **Not re-filed.** Recognition accuracy already has its own home — the recogniser was chosen on its
  **wrong-command count** rather than on accuracy (`small.en`: zero confident wrong commands against
  `tiny.en`'s seven), and `[[AA-4.7]]`'s latency work plus the audio-adapter's own vocabulary items
  are where STT behaviour is tracked. If a wrong transcription ever causes a wrong *action* rather
  than a spurious *"say again"*, that is the bug worth filing, and it is a different one. Original
  entry follows.

- [>] **(original, superseded)** `say again` fires on ordinary cockpit speech that was never addressed to
  Petrovich. Found in the 2026-10-05 sortie's speech log, not reported by the pilot — four
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
