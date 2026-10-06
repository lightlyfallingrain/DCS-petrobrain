# AA-4.2 — Stage 2 — the matcher and the command path

- [x] **Stage 2 — the matcher and the command path.** #status/done Merged 2026-09-20. The matcher moved to
  this subproject (plan's "Decision 4 REVISED"): body was going to hold a third hand-synced
  vocabulary copy, and whisper-specific normalisation — "180" for a spoken "one eight zero",
  repetition loops, "record" for "report" — is knowledge about the recogniser rather than about
  flying. Body keeps every decision with crew behaviour in it and still receives the raw
  transcript, so unmatched speech falls through to escalation unchanged.

  Review caught a real hole: whole-string scoring resolved "look at that" to a scan command at
  0.727, which would have executed. Fixed structurally rather than with a tighter floor —
  commands are word sequences, so score word sequences and count extra words against. Filler
  stripping followed, worth more than it looks because the ratio divides by the longer word
  count, so every unnecessary word depressed the score of the command meant.
