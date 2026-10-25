# AA-B7 — The wake word anchors as a command verb, so "Petrovich, …" gets "say again"

- [~] **AA-B7 — A transmission that begins with the wake word must reach the brain as free speech;
  today it is answered "say again".** #status/in-review #needs-flight Sortie feedback F2,
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
  - `[[BL-B52]]` — the wake word strips a report's slots. Closed by this decision: a prefixed
    `report` now goes to the brain, so there are no slots to lose.
  - The same flight, separately: body-layer on Windows logged `background brain reply poll failed
    (retrying)` / connection refused, because the brain runs on the Mac. Correctly routed speech
    also needs body-layer's `--brain-url` pointed at the Mac.

  ## Decided (user, 2026-10-25)

  Asked whether `"Petrovich, scan left"` still runs the command:

  > A. "[hey, ]Petrovich" at start is intentionally the keyword that means free text for the brain.
  > Petrovich later in the sentence does not trigger that.

  ## Fix (branch `fix/aa-b7-wake-word-routing`)

  `command_matcher.match_transcript` checks the opening word(s) before verb anchoring: `petrovich`
  or `hey petrovich` (after filler is stripped, so "um, Petrovich" counts) returns
  `verb_anchored=False`, which body-layer's `classify_response` already routes to the brain. No
  body-layer change. The name is fuzzy-matched at `WAKE_FLOOR` = 0.8 — admits whisper's
  `petrovitch`, rejects `petro`/`petrol`/`pedro`; not yet measured on the user's voice.

  | said | before | after |
  |---|---|---|
  | "Petrovich, where are we?" | say again | brain |
  | "Petrovich, scan left" | say again | brain |
  | "Petrovich, report left" | `report`, slots lost | brain |
  | "scan left, Petrovich" | `scan_left` | `scan_left` |
  | "good morning Petrovich" | greeting | greeting |

  Not decided by this fix: `[[AA-B4]]` (positional anchoring) is untouched; it still matters for
  unprefixed speech like `"Eta-Chron."`.

  **Open (flight):** "Petrovich, where are we?" is answered by the brain in his own words (card
  A14). Needs body-layer's `--brain-url` pointed at the Mac.
