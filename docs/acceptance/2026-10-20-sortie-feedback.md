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

## F6 — A12: no "taking fire" for obvious gunfire and SAM launches at ownship

User, verbatim:

> A12 did get a report or two of "someone firing", but no reports of obvious gunfire at ownship.
> I can see tracers and SAM launches, but no report. Scan left (to enemy dircetion) commanded.
> (most recent logs)

**Investigated** (run `20261020-165724`, the live collector, and `dcs.log`):

- DCS → collector works: `dcs.log` shows 147 Hook polls carrying shots in that run, and the live
  collector's `/firing/latest` held `Ground-1-3` (Leopard-2A5) `targets_ownship: true` and
  `Vulcan-3` firing — ~1.0 km at ~9:30 o'clock and ~1.3 km at ~8 o'clock.
- Body-layer never turned them into "taking fire", for two independent reasons:
  1. **The shooters were outside his current gaze.** Of ~470 detection rows for each shooter,
     ~390 were rejected at the `gaze` gate (looking at 11–1 o'clock, often through `sight_narrow`,
     which has no peripheral vision). The emitter bypass skips only range/size and forest; gaze,
     cockpit mask, optic FOV and terrain are never bypassed (`perception/visibility.py`).
  2. **Even when he did see a shooter, "taking fire" is only possible if he could not have seen it
     without the muzzle flash.** `naked_eye_source.py` sets `targets_ownship` only when
     `result.emitter_kind is not None`, i.e. when the emitter *bypass was needed*. A tank in plain
     view at 1 km is an ordinary admission, so it becomes a plain contact and never "taking fire".
     The close, obvious shooter is exactly the one that cannot trigger the call.
- **SAM launches are not reported by design yet**: `LAUNCH_SMOKE` (`BL-B74`) is named in
  `perception/emitters.py` but not built.

### F6 — follow-up (user, 2026-10-20)

> Should fire aimed at you be noticed wherever he's looking -> no. current behaviour correct in
> that way.
>
> I flew a little bit more (probably same log files), commanded observ off and scan left.
> Petrovich should definetely see the unit firing at me

So reason 1 (gaze gating) is **correct behaviour**, by the user's decision. The later stretch —
`observ off`, `scan left`, shooter on the left — is the case that must produce "taking fire".

**What the logs show for that stretch** (`observ on` → `observ off` at sim 303 s, `scan left` at
318 s; logs end at 334 s): the gaze cycled 9/10/11 o'clock with the naked eye and binoculars, as
commanded. `Ground-1-3` (the Leopard firing at ownship) was **admitted once**, at 303 s and 1,073 m,
as an ordinary contact (`CONTACT_14`, presence tier). **It was never a firing contact**, because a
shooter at 1 km is visible without its muzzle flash, so the emitter bypass was never needed and
`targets_ownship` stayed false (reason 2 above). That is the defect to fix. Whether it should
also have been admitted more often in 318–334 s cannot be settled from the trace: the rows record
the gaze hour and the true bearing but not the body-relative azimuth, and heading samples are
sparse. Ownship turned from about 244° to 193° in that window, which moves a target at 185° true
from about 10 o'clock to 12, out of the left scan.

## F4/F5 — plan amendments (user, 2026-10-20)

Against the first plan (`plans/9k113-narrow-search/plan.md`, three simplifications flagged):

> 1 - "Scan left" gets no narrow at all -> yes, split as suggested.
> 2 - I'd have it sweep narrow along the flight direction. -> yes, exactly, wide and narrow. Note
> that wide is ~binocular level, but stabilized and better at low light. So, if OBSERV is ON, and
> looking at there 9K113 can, prefer wide over binoculars. Binoculars are good for quick look
> because 9K113 slew takes time.
> 3 - use 9K113 for that band as well. That is often the ATGM attack range.
>
> BL-B74 -> later, leave

1. A commanded sector straddling ±60° is split: the sight (narrow) searches the in-regard part,
   eyes/binoculars the rest.
2. With no commanded sector, the sight searches along the flight direction, wide and narrow.
   **New rule:** with OBSERV on and the direction within the sight's regard, prefer sight-wide over
   binoculars (wide ≈ binocular magnification, but stabilised and better in low light);
   binoculars remain for a quick look, because slewing the 9K113 takes time.
3. The 2.3–5.6 km band is searched with the 9K113 too — *"often the ATGM attack range"*.

`BL-B74` (SAM launch smoke) stays in the backlog.

## F6 — live check while paused (user, 2026-10-20)

> regarding incoming fire, DCS is paused right now and I see incoming tracer fire at 0 o'clock.

Collector at that moment (sim 335.7 s): the only active firer was `Vulcan-2`,
`targets_ownship: false`, at 2.1 km and ~9 o'clock (true bearing 89°, ownship heading 187°). So
nothing the Hook reported matches tracers at 12 o'clock aimed at ownship. Either the shooter at 12
emits no `S_EVENT_SHOOTING_START` / `S_EVENT_SHOT` the Hook sees, or its event's `target` does not
name the player. The Hook resolves `targets_ownship` by comparing `event.target`'s name with the
player's, and for a nil target it answers false. Open.

**Correction (user):** *"0 o'clock -> 9 o'clock. that was my typo"*. So the tracers came from about
9 o'clock, and they match `Vulcan-2` (2.1 km, ~9 o'clock, firing). The collector had it as
**`targets_ownship: false`** while it was visibly firing at ownship. That is a third cause, in
the aircraft-layer Hook rather than body-layer. A tank (`Ground-1-3`) earlier resolved to `true`,
so the name comparison works in general. The likely reading is that an AAA gun's
`S_EVENT_SHOOTING_START` carries no `target` (nil, so false), but that is unverified: it is a
DCS-internals question for an investigator.

## F7 — settlement names in callouts are not useful

User, verbatim:

> I get call outs that refer to settlement by it's name. While correct, I notice that's not very
> usefull actually. Instead we could just replace names (that are often foreign and tell me nothing
> and take time to say) with "village" or "city"

**What exists:** the name comes from `body-layer/src/belief/enrichment.py` (`"near {name}
({distance}m)"`, `"inside {name}"`). Unnamed settlements already read as "a built-up area" or "an
unnamed settlement". world-model has a size word for some places but not all: OSM points carry
`place=city|town|village` as `subtype`, OSM settlement polygons carry `area_m2`, and DCS
`towns.lua` entries carry neither. Not yet explored with the user.

### F7 — settled (user, 2026-10-20)

Asked: (1) village/town/city or fewer, (2) keep the bracketed distance, (3) keep names anywhere,
(4) other named landmarks.

> 1 - village and town are enough
> 2 - drop
> 3 - mission memory
> 4 - use no name, just landmark feature like road, river etc

So in speech: "near a village" / "in the town", "near a road", "near a river" — no proper names
and no bracketed distance. Names are kept in mission memory (post-flight).

### F6 — visible unit firing at others (user, 2026-10-20)

Asked whether a unit he can see anyway, firing at someone else, should be an ordinary contact
report or be reported as firing:

> someone shooting is important, especially if they are close -> report

So a visible unit that is firing is reported as firing, whoever it is firing at. Because he can
see it, its type is spoken at the tier he already has; only the unseen, muzzle-flash-only case
stays "something firing, X o'clock" (direction only).

**Follow-up (user):** *"it may have been aiming at my wingman"*. That fits reading (a): the Hook
correctly resolved `Vulcan-2` as not targeting ownship. Under the "visible unit firing at others
→ report" decision, it should still have been reported as firing once he could see it (2.1 km,
9 o'clock, inside the commanded left scan). That case is being built on
`fix/taking-fire-visible-shooter`. This sortie's `debrief.log` (written at mission end) can confirm
the target.

**Confirmed from this sortie's `debrief.log`** (written 18:06 at mission end): at sim 335.461 the
Vulcan with mission ID 434 (`Vulcan-2`, matching the collector's `since_sim`) started shooting at
**Mi-24P mission ID 447, the wingman**. The player is mission ID 344, pilot name "sg". So
`targets_ownship: false` was correct, and the Hook is not at fault. Between 322 and 333 s a
different Vulcan (433) was shooting at the player, and a Leopard-2A5 (368) at 344 s.

## F4/F5 — second amendment round (user, 2026-10-20)

Against the amended plan (wide 2.3–5.6 km, narrow 5.6–13.6 km, binoculars beyond ±60°), and the
finding that today's binocular search for left/right/full sweeps around dead ahead:

> * fix the binocular search sector.
> * 9K113: there are many situations where scan beyond 5.6 km is much less useful than 2.3-5.6.
>   Various reasons why LOS can be blocked, weather, etc. Should use narrow also indide 5.6 km
>   _as needed_
> * wait for BL-B66

1. Fix the existing binocular search's sector centre too (not only the new sight call sites).
2. Narrow is not confined to beyond 5.6 km — it is used inside 5.6 km "as needed". What "as
   needed" keys on is being explored.
3. Attack-run guidance's sight-wide-over-binoculars preference waits for `BL-B66` (slew time), so
   the preference and its quick-look exception land together.

Default search width with nothing commanded — full ±60° regard — was recommended and not objected
to; proceeding with it.

### F4/F5 — "as needed" settled (user, 2026-10-20)

Options offered: A — narrow sweeps both bands, near first, wide only to orient; B — terrain-aware
(concentrate near when a ridge closes the far band); C — weather-aware.

> approved. There's already item about taking waether into account, link C with that.
> B would be a natural consequence of angles. Wherever the 9K113 happens to be pointing, if terrain
> blocks there's no LOS. However if there's something nearside on that terrain it can be seen. B
> can be left till later.

A is built now. C is linked to the existing weather/light/vegetation item (`BL-B22`'s "Detection
under real world conditions" section). B is deferred: perception already handles it per look
(no LOS behind terrain, nearside visible). What is deferred is only the search pattern adapting
its depth to terrain.

## F4 — narrow looks (user, 2026-10-20)

Implementation found that sight *looks* always resolve to wide: "worth a look" is decided from
naked-eye/binocular thresholds, so a contact beyond binocular classification range is never worth
a sight look, and narrow never classifies.

> The narrow thing. Fix it, otherwise the whole point of narrow is missed.

## F1 — latency settled (user, 2026-10-20, next flight)

> 1 - responsiveness is much better when whisped (and audio adapter) run on mac -> this settles it,
> I'll prioritize whisper (=audio adapter) and brain to run on mac. They must not be dependent on
> mac, but I'll mostly use them on Mac.

## F8 — "set target" acknowledged late and as an attack run

User, verbatim:

> * Me: "set target, armor, 12 o'clock"
> * several seonds pass, I make U-turn to stay safe
> * Petrovich acknowledges target Leopard 2 at 12 o'clock.
>    * but this is several seconds late. I've already U-turned, there's nothing at 12 o'clock now.
>    * Petrovich acknowledges attack run. This should not happen, this was selectling target, not
>      attack run.

Not yet explored.

### F8 — explored (user, 2026-10-20)

Asked: (1) were the exact words "Attack run, …" or "Attack run off"? (2) should a late readback
give current or original position? Also offered a speech log with queued/spoken timestamps.

> 1 - nope.
> 2 - current inforamtion, not old. Though the real problem here is the many second delay
> Yes and timestamps. Could also add latency measurements and logs

1. The exact "attack run" wording isn't remembered, so that part is unresolved until the
   instrumentation shows what was spoken.
2. A readback reflects **current** information at the moment it is spoken, not when the command
   was handled. But the real problem is the multi-second delay.
3. Build: per-utterance timestamps (queued, spoken) plus end-to-end latency measurement and logs
   across the voice chain (PTT release → STT → body-layer → speech queue → TTS → playback), so the
   delay can be located.

### F8 — plan decisions (user, 2026-10-20)

On `plans/voice-latency-instrumentation/plan.md`'s four decisions: (1) re-render the current
position in `select_target` only or in every positional readback; (2) log the command token, or
thread the full template; (3) add a playback-start feedback seam now; (4) log failed STT/TTS
attempts.

> 1 - all of them
> 2 - cheap
> 3 - measure first
> 4 - yes

### F4 — wide sweep band (user, 2026-10-20)

Asked whether wide should orient over the same 2.3–5.6 km band as the first narrow pass, or over
the whole 2.3–13.6 km:

> wide sweep -> it makes sense to use it up to where it can bring information, be it detection or
> classification. At greater distances it cannot, narrow can.

So the wide sweep's far edge is wide's own useful reach (the farther of its detection and
classification reach, from the existing optic calibration), not the 5.6 km binocular boundary.
Beyond that reach only narrow brings information.

### F2 — sequencing (user, 2026-10-20)

> F2 - after 9K113 fixes are merged

Fix F2 (a transmission starting "Petrovich" routes to the brain) once `feature/9k113-narrow-search`
has merged. That unblocks card item A14.

## F4 — BL-B85 is required, not backlog (user, 2026-10-20)

Reviewer and security filed `BL-B85` as non-blocking: a contact whose classification never
advances is re-granted sight looks indefinitely and starves the search cycle.

> BL-B85 is required for 9K113, we can't just indefinately look at one thing. Needs a timer value
> or the like that forces moving on.

So it is built into `feature/9k113-narrow-search` before merge. A contact that has had its sight
time without progressing has to give way to the search (and to other contacts) for a while: a
tunable time bound, not an open-ended re-grant.

## F5 — the 9K113 vertical limits are boresight-relative (user, 2026-10-20)

On the elevation-regard fix (sweep steps below −15° dropped, so the near band drops out above
~625 m AGL), and BL-B86 (the whole free-scan search stops above ~3.6–4 km AGL):

> 9K113 angular (vertical) limits
>
> * they are *boresight* relative. nose low position at high altitude would allow a near scan. Nose
>   high at low alt would limit near scan. It is *not* about distance, but *angles relative to
>   boresight*.

The +20°/−15° (and ±60°) limits are relative to the aircraft's boresight, so pitch (and bank)
matter. A distance/altitude rule is the wrong model.
