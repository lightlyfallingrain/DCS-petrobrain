# X-T9 — "full scan" vs "scan full" — no defect

- [x] **"full scan" vs "scan full" — no defect, closed 2026-09-26.** #status/done *"I noticed myself saying
  'full scan', but the recognized format is 'scan full'. Both would be good."* Both already work.
  Ran the matcher directly: `"full scan"`, `"scan full"` and `"scan all around"` each resolve to
  `scan_full` at `match_ratio=1.0`, verb-anchored (`full` is in `VERB_ANCHOR_WORDS`, derived from
  `PHRASES` rather than hand-listed, which is why it came for free). The impression comes from the
  **F10 menu's own shape** — `petrobrain-f10-commands-hook.lua:156` nests it as Scan → "Full", and
  `crew_console.py:183` labels the token `"full"` — so the menu reads as "scan full" and nothing
  else advertises the alternatives. Nothing to change in the recogniser; if anything is worth doing
  it is making the spoken phrasings discoverable somewhere, which belongs with [[BL-10]]/SRS free
  speech, not here.
