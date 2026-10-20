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

## F5 — 9K113 wide pointed at -90°, outside its ±60° limit

User, verbatim:

> just a moment ago, 9K113 wide, but centre=-90 deg +/- 15 deg. 9K113 limit is +-60 deg.

**Cause, from the code — a real defect, not only a display one.** When `observ on` has nothing
worth a closer look, `optic_policy` returns `OpticDecision(optic=SIGHT_WIDE_OPTIC)` with **no aim**;
its comment says *"rest wide, pointed ahead"*. But `logger._apply_active_gaze` only overrides the
scan plan when the decision carries an aim, so with none the sight's boresight falls back to the
**head's o'clock scan cycle** — 9 o'clock is -90° ±15°, a clock hour. Perception then applies the
sight's magnification along that gaze: detections through a 9K113 at 90° off the nose, where the
mount cannot point. The ±60° field-of-regard filter guards only the choice of *look target*, not
this idle path. The idle aim is the same question as F4 ("where does the sight point when
nothing is detected yet"), so the two should be designed together.

## F4/F5 — exploration answers (user, 2026-10-20)

> "How would a real operator search with it? …" -> yes. use wide to orient and quick scan, narrow
> to look more closely and detect greater range.
>
> "What decides where narrow points when nothing has been detected yet? …" -> all of those.
> Priority: 1 commanded scan sector. Mission objective area if wihtin range, flight direction as
> normal default.
>
> "Should narrow also take over the close looks, as it does now? Or would wide be enough for
> contacts that are near?" -> use least capable optic that suffices.

Read together with the 2026-10-15 direction (§4 *"wide to find → narrow to classify → wide again
for surroundings"*, §8 *"wide↔narrow should use similar logic to naked eye and binocular usage"*,
§9 the sight is the baseline and the naked eye the brief interruption), this is consistent with it
and adds three things the build lacks:

1. **Narrow searches**, not only inspects: sweeps at distance are narrow; wide is for orienting
   and a quick scan.
2. **Where the idle sight points**, in priority order: commanded scan sector → mission objective
   area if within range → flight direction (default). Always inside the ±60° regard (F5).
3. **Looks use the least capable optic that suffices** — eye < binoculars < sight wide < sight
   narrow — rather than always narrow.

Known gap against (2): body-layer has **no mission objective area at runtime** — `grep -i
objective body-layer/src` finds only a comment. The Mission Interpreter's waypoints reach
`mission_phase` (BL-7), which is inert in flight.

## F4/F5 — settled (user, 2026-10-20)

> 2 - skip for now
> 1 - eyes/binocular when beyond 9K113 limits. Leave 9K113 at last position.
> 3 - yes, I'd use narrow much more, wide is for orientation to know where to point the narrow,
> or for close distance

1. **Commanded sector beyond ±60°**: that sector is scanned with eyes/binoculars; the sight stays
   at its last position (not re-aimed to the regard edge).
2. **Mission objective area**: skipped for now — aim priority is commanded sector → flight
   direction. Filed as a backlog item.
3. **Wide vs narrow share**: narrow carries the search; wide is brief — orientation (where to
   point narrow) or close range.
