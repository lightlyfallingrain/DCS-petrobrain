# AA-B7 — The wake word anchors as a command verb, so "Petrovich, …" gets "say again"

- [ ] **AA-B7 — A transmission that begins with the wake word must reach the brain as free speech;
  today it is answered "say again".** #status/open #needs-flight Sortie feedback F2,
  `docs/acceptance/2026-10-20-sortie-feedback.md`. Sequenced by the user: *"F2 - after 9K113 fixes
  are merged"* — the 9K113 work (`[[BL-B89]]`) merged 2026-10-25, so this is due.

  ## What happens

  From the 2026-10-20 speech log (`body-layer/logs/dcs-speech-20261020-162158.jsonl`, Windows
  clone):

  ```
  "Petrovich, where is mark one?"  verb_anchored=true  token=null  -> say_again
  "Petrovich, where are we?"       verb_anchored=true  token=null  -> say_again
  ```

  A defect against the design, not an unbuilt feature. `audio-adapter/src/vocabulary.py`'s
  `ROUTING_TOKENS` comment says a transmission beginning with `wake_petrovich` *"is free speech for
  the brain layer"*. But `command_matcher.VERB_ANCHOR_WORDS` is derived from the first word of every
  phrasing, and `wake_petrovich`'s phrasings are `"petrovich"` / `"hey petrovich"` — so the wake word
  itself is a command verb. `body-layer`'s `voice_commands.classify_response` then sees "anchored,
  no command matched" and applies the fumbled-command rule. Only speech with **no** anchor at all
  falls through to the brain, so the wake word does the opposite of its job.

  Checked 2026-10-25: nothing merged since has changed this (`command_matcher.py`'s only later
  change is `[[BL-B89]]` Stage 2's `look`/`sight` slot branch).

  ## What it blocks

  Card item A14 (the brain answering in his own words) on the 2026-10-20 open-flight-tests card,
  and in practice every brain question, since "Petrovich, …" is the documented way to ask one.
  `[[BR-2]]` (the tool path) matters only once speech arrives.

  ## Related, not the same

  - `[[AA-B4]]` — anchor a verb on sentence position, not the word alone. The same log also anchors
    `"Eta-Chron."` and `"Check it."`. A fix here may fall out of AA-B4, or AA-B4 may build on it;
    decide in the plan.
  - `[[BL-B52]]` — the wake word strips a report's slots.
  - The same flight, separately: body-layer on Windows logged `background brain reply poll failed
    (retrying)` / connection refused, because the brain runs on the Mac. Correctly routed speech
    also needs body-layer's `--brain-url` pointed at the Mac.

  ## Not yet explored

  The intended routing is written in `vocabulary.py`, so the fix's direction is clear. What is not
  settled is the edge: does `"Petrovich, scan left"` still run the command, or go to the brain?
  Ask before building.
