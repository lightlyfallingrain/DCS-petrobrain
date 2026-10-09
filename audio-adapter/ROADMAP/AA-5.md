# AA-5 — `silence` command phrase wiring

- [x] **`silence` command phrase wiring — DONE, merged with body-layer's `feature/silence-
  command` (tip `de6c530`).** #status/done #needs-flight `"silence"`/`"be quiet"`/`"shut up"` added to
  `vocabulary.VOICE_ONLY_TOKENS`/`PHRASES`, reachable through the existing `match_transcript` →
  `classify_response` → `handle_transcript` pipeline — no new ingress path, no `command_matcher.py`
  change. Bare `"quiet"` was in the original four-candidate set and was dropped after actually
  running the matcher: at a 0.889 `difflib.SequenceMatcher` ratio from the ordinary word
  `"quite"`, it would have false-anchored `"quite a nice day for flying today"` as a command
  (`VERB_ANCHOR_WORDS` is derived from each phrase's first word; see `body-layer/ROADMAP.md`'s
  entry and `NOTES.md` for the generalised lesson). Marked unbenched in `vocabulary.py`'s own
  comment, same convention as `cancel_scan`/`cancel_watch`. 219 passed/1 skipped,
  `ruff`/`mypy --strict` clean. **No live acceptance yet** — see `body-layer/ROADMAP.md`'s
  live-acceptance debt list, since this is reached only via the body-layer dispatcher and the two
  halves share one sortie's worth of verification.
