# Sortie feedback, 2026-10-20

Observations from flying the "Open Flight Tests" card
(results: `2026-10-20-open-flight-tests-results.md`). Captured verbatim before any
exploration or fix, per root `CLAUDE.md` "Flight feedback is captured, then explored,
then planned".

**Stack this flight:** collector, audio capture, audio-adapter (Piper TTS + whisper.cpp
`b5454` CPU build, `ggml-small.en`) all on Windows alongside DCS; brain-layer + Ollama on
the Mac. Speech recognition had moved from the Mac to the Windows CPU the same day.

## User, verbatim

> observations:
>
> * Responce latency is too high, it can take several seconds to get readback.
> * Player: "Petrovich, <free text>" -> result "say again". These should go to brain and
>   result in response from brain, possibly free text. Though, I don't think thats been
>   implemented yet.

## F1 — readback latency of several seconds

Not yet explored. Open: which stretch of the chain the seconds are in (PTT release →
whisper on the Windows CPU while DCS runs → transcript poll → match → Piper synthesis →
playback), and whether it was this slow when recognition ran on the Mac.

## F2 — "Petrovich, <free text>" gets "say again" instead of reaching the brain

Not yet explored. Note the card's own "Read once" section says the opposite should happen:
*"To reach the brain, start without a command word … or begin with `Petrovich, …`."* So this
is either a defect against built behaviour or the card over-claimed — to be established
before anything is designed.

**Established from the speech log** (`body-layer/logs/dcs-speech-20261020-162158.jsonl` on the
Windows clone): it is a defect against the design, not an unbuilt feature.

```
"Petrovich, where is mark one?"  verb_anchored=true  token=null  -> say_again
"Petrovich, where are we?"       verb_anchored=true  token=null  -> say_again
```

The design (`audio-adapter/src/vocabulary.py`, `ROUTING_TOKENS` comment) says a transmission
beginning with `wake_petrovich` *"is free speech for the brain layer"*. But
`command_matcher.VERB_ANCHOR_WORDS` is derived from the first word of every phrasing, and
`wake_petrovich`'s phrasings are `"petrovich"` / `"hey petrovich"` — so the wake word itself
counts as a command verb. `voice_commands.classify_response` then sees "anchored, no command
matched" and answers "say again", which is the rule for a fumbled command. Only speech with
**no** anchor at all falls through to the brain. The wake word therefore does the opposite of
its job. Related, not the same: `BL-B52` (wake word strips a report's slots), `AA-B4` (anchor on
sentence position — the same log also anchors `"Eta-Chron."` and `"Check it."`).

Separately, earlier the same day body-layer on Windows logged `background brain reply poll
failed (retrying)` / connection refused — the brain is on the Mac, so even correctly routed
speech would have reached nothing unless body-layer's brain URL points at the Mac.
