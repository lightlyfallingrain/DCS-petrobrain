---
name: srs-adapter-stt-riskiest-first
description: Slice 3 (inbound speech) is staged so an offline recognition bench against the user's own accent is a stop/go gate before any transit, PTT or body-layer work.
metadata:
  type: project
---

`plans/inbound-speech/plan.md` puts an offline recognition bench (`srs-adapter/tools/stt_bench.py`
over a corpus of the user's own recorded voice) as Stage 1 and an explicit **stop/go gate**. Nothing
about transit, PTT, or capture is built until it reads.

**Why:** the user has a Finnish accent and Windows speech recognition has already failed him once
(Intentions AI ATC) -- with *wrong words, not silence*. That is the only assumption the whole slice
rests on, and it is uniquely cheap to test: WAV files plus a binary on the Mac, no Windows, no DCS,
no HTTP. The bench also produces the measured confidence distribution that sets every threshold
constant in the matcher, so guessing those constants before it runs would be wasted work.

**The key reframing worth keeping:** the prior failure was *open dictation*. This is classification
over 15 closed tokens with three legal first words, attacked at three layers -- recogniser-level
constrained decoding (whisper.cpp `--grammar`, `System.Speech` `Choices`), a verb anchor that
refuses to match at all when the first word is not scan/watch/cancel, and stdlib `difflib` nearest-
phrase matching with a best-vs-second separation check. Different problem class, not the same thing
retried.

**How to apply:** when a milestone's value hinges on one unproven external capability, stage the
cheapest isolating test of it first and name it a gate in the plan -- and set thresholds from its
data rather than shipping guessed constants. See [[srs-adapter-audio-boundary]].
