---
name: voice-card-never-prefix-a-command-with-the-wake-word
description: In an acceptance card, write spoken commands WITHOUT "Petrovich" — a wake-word-prefixed transmission routes to the brain as free speech, not to the command matcher.
metadata:
  type: feedback
---

**When writing what the pilot should *say* in an acceptance card, never prefix the command with
"Petrovich".** `audio-adapter`'s `vocabulary.ROUTING_TOKENS` makes `wake_petrovich` the *tier
discriminator*: a transmission **beginning** with the wake word is free speech for the brain layer,
and one **without** it is matched against the command vocabulary. `server._handle_transcribe` feeds
the whole transcript to `match_transcript`, so the prefix is not stripped for you.

**Why:** found by running it while writing the 2026-10-06 sortie-refinements card.
`match_transcript("Petrovich, describe.")` → `token=None`; `match_transcript("describe")` →
`report_all` at ratio 1.0. A card saying *"say 'Petrovich, describe'"* would have failed on the
pilot's first attempt, and it reads completely natural — this is exactly the
confidently-wrong-command class this role's own brief warns about, and the only thing that caught
it was executing the probe instead of describing what should work.

Two more things the same probe surfaced, worth knowing before writing the card rather than after:

- **A trailing period is harmless** (`"describe."` → `report_all`), so quoting commands as sentences
  in a card is fine.
- **A more specific token wins.** `"describe eleven o'clock"` resolves to `report_clock_11`, not
  `report_all` — correct, but say so in the card or it reads as a miss.

**How to apply:** before writing any spoken utterance into a card, run it through
`cd audio-adapter && PYTHONPATH=src .venv/bin/python -c "from command_matcher import
match_transcript; print(match_transcript('<utterance>').token)"` and paste the output. Also prefer
the **F10 path** as the primary in-flight test wherever one exists (`watch_nearest` and the whole
`scan_*` family have buttons; `report_all` and `follow` are voice-only) — it takes speech
recognition out of the loop, so a failed test means the feature failed rather than the recogniser.
Related: [[feedback_name_the_acceptance_boundary_when_the_observable_is_an_absence]].
