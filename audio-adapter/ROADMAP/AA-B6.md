# AA-B6 — The whisper prompt carries every recognised word, and stays in sync by test

- [x] **AA-B6 — `to_prompt()` lists every vocabulary word; a test enforces the sync.**
  #status/done #needs-flight Merged 2026-10-23 (`0fbbfee5`, branch `fix/stt-prompt-vocab-sync`).

  User, 2026-10-23: *"STT correctness is poor. There's quite many incorrect transcriptions of what I
  speak."* Whisper on the Mac; failures arrive as "say again", and *"depends a lot on the words I
  used"*. Direction: *"fix the prompt"* and *"make keeping the command vocabulary in sync between
  code and STT prompt a rule. Reviewer needs to catch it if they diverge."*

  **Cause.** The prompt sampled the first phrasing of 24 of 66 tokens. Everything added after the
  2026-09-19 bench at 15 tokens — silence, engage, disengage, set target, drop target, follow,
  describe — and every slot word (SAM, AAA, truck, guns, closer…) never reached whisper. Logged
  symptoms: "silence" → "violence", "SAM ahead" → "same ahead".

  **Fix.** Every distinct word of `PHRASES` plus the slot tables, once, space-joined: 133 GPT-2
  tokens against whisper.cpp's 224 cap (the front is dropped past it). Bench, 252-clip corpus,
  `small.en`:

  | prompt | correct | wrong command | p90 |
  |---|---|---|---|
  | old (24 sampled) | 248 | 2 | 2.10 s |
  | phrase fragments | 247 | 2 | 1.98 s |
  | **word list** | **249** | 2 | **0.86 s** |

  The corpus predates the new commands: this shows no regression on the old ones, not the gain on
  the new. **Open (flight):** silence / set target / SAM / engage / describe recognised. The
  2026-10-19..21 flights wrote no `dcs-speech-*.jsonl`, so start body-layer with `--speech-log`.

  **The rule** lives in `test_vocabulary.py` (fails on any missing phrasing or slot word, or an
  over-budget prompt), `.claude/agents/reviewer.md` (the half a test cannot see: a word that never
  reached the tables), and `audio-adapter/CLAUDE.md`. A hook was not added — the commit gate already
  runs the test.

  **If still poor after the flight:** record clips of the new commands, then bench `medium.en`
  (on disk) and `large-v3-turbo` against them.
