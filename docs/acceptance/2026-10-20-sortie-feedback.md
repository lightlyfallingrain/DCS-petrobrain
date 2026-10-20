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

**Clarified (user):** "readback" is PTT release to hearing his voice, and `radio check` felt as
slow as the rest — *"yes. Will need to compare with mac"*. So the delay is in the shared
recognise/route/speak chain, not in any one command's handling.

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

## F3 — Piper reads "~800 meters" as "tilde 800 meters"

User, verbatim:

> * Piper model reads "~800 meters" as "tilde 800 meters" -> replace"~" with "about" in all speech.

Unambiguous, fix given by the user — no exploration needed. Source is
`body-layer/src/belief/speech.py` `_round_enrichment_fragment` (`"(~400 metres)"`); `say`
silently skipped the tilde, Piper reads it.

## F4 — with OBSERV ON only the 9K113 wide setting is used, never narrow

User, verbatim:

> with OBSERV ON, 9K113 wide is used, but I have not seen narrow. Narrow is important, it's what
> allows detection and classification at distance.

Not yet explored. Card item A8 (9K113 sight).

**What the logs and code say** (detection traces on the Windows clone, samples per optic):

| run | sight_wide | sight_narrow |
|---|---|---|
| 160126 | 82034 | 2458 (~3 %) |
| 163625 | 16858 | **0** |

`belief/optic_policy.py` (the `observ on` branch): **wide is the sight's idle/search state;
narrow is used only for a *look* at a contact already detected** that passes `is_worth_a_look`
and the field-of-regard filter. Narrow is never used to search. So the contacts only narrow
could detect — the far ones — can never cause narrow to be selected, because nothing selects
narrow until something is already detected: a chicken-and-egg against exactly the use the user
describes (*"what allows detection and classification at distance"*).
