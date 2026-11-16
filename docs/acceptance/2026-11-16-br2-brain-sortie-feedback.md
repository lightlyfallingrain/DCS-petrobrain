# BR-2 brain — first live test, sortie feedback 2026-11-16

**Status: captured, not yet explored.** Per root `CLAUDE.md` "Flight feedback is captured, then
explored, then planned": nothing here is a decided fix. Test card being flown:
`docs/acceptance/2026-11-13-br2-brain-tool-calls-sortie.md`. Branch flown: `main`.

## What the pilot brought back, verbatim

> *"# testing brain"*

Log, as pasted (body-layer's normal log; `->` lines are the player's own transcribed speech, added
2026-11-16 on `fix/body-log-player-speech`):

```
-> "radio check", confidence 0.77
Loud and clear.
ground, 2 o'clock, 2.5 kilometres.
-> "Metrovids describe right", confidence 0.48
Say again?
long range SAM, 2 o'clock, 2.5 kilometres.
ground, 2 o'clock, 2.5 kilometres.
Couple contacts, 3 o'clock, 2.5 kilometres.
-> "Petrovich where are we", confidence 0.87
Which one -- OP_GROUPSOMETHING, observed, currently visible, 2 o'clock, 2.4 km., or OP_LRSAM, observed, currently visible, 2 o'clock, 2.4 km., or OP_GROUPSOMETHING, observed, currently visible, 1 o'clock, 2.4 km.?
live LOS coverage gap: naked-eye gate-4 evaluations started receiving no live verdict this sortie (world-model's offline LOS primitive is no longer used as a fallback -- affected candidates are rejected, not approximated); see the end-of-run summary for the final totals
ground, 1 o'clock, 2 kilometres, moving.
ground, 11 o'clock, 2 kilometres.
-> "Petrovich what do you see hit", confidence 0.89
Which one -- OP_GROUPSOMETHING, observed, currently visible, 11 o'clock, 1.3 km., or OP_GROUPSOMETHING, tracked, last seen 32s ago, 4 o'clock, 1.8 km., or OP_GROUPSOMETHING, tracked, last seen 44s ago, 5 o'clock, 3.4 km.?
unit 12 o'clock, 0.5 kilometres is truck.
background brain reply poll failed (retrying)
background brain reply poll failed (retrying)
-> "Petrovich what do you see on the left", confidence 0.91
Stand by.
Which one -- OP_TRUCK, tracked, last seen 18s ago, 2 o'clock, 0.5 km., or OP_GROUPSOMETHING, tracked, last seen 58s ago, 5 o'clock, 3.1 km.?
```

> *"\"Petrovich what do you see hit\" had ./run-brain.sh running"*
> *"\"Petrovich what do you see on the left\" had ./run-brain.sh --decider tool_loop"*

## What the code says about each line — facts checked 2026-11-16, not yet a diagnosis

1. **"where are we" and "what do you see hit" went to the old BR-1 decider, not BR-2.**
   `./run-brain.sh` without `--decider tool_loop` runs BR-1's classify/discriminate decider
   (`brain-layer/src/decider.py`), whose only outcomes are `PICK` / `ASK` / `CONFIRM` / `UNABLE`
   over contact candidates. So "which one" was the only shape it could give, whatever was asked.
   The test card warns about the flag. This makes these two answers a finding about the old path
   and about how easy the wrong launch is, not about BR-2's tool loop. ("where are we" was before
   the noted "hit" run; same launch assumed, not confirmed.)
2. **Only one utterance reached BR-2's tool loop: "what do you see on the left".** It answered
   "Stand by." then "Which one -- …" over two contacts at **2 and 5 o'clock**. Neither is on the
   left. A contact at 11 o'clock had been called out about a minute earlier.
3. **The brain's contact tools cannot filter by side.** `get_contacts` takes `filter` = all /
   visible / watched; `find_contact` takes classification text only
   (`body-layer/src/belief/tool_api.py`). "On the left" can only be honoured if the model filters
   clock positions itself from the results.
4. **The "which one" options are tool summaries read aloud.** `render_disambiguation`
   (`body-layer/src/belief/speech.py`) speaks each candidate's `why` string, which is
   `_contact_summary` (`body-layer/src/belief/tools.py`): raw classification value, certainty word,
   "currently visible" / "last seen 32s ago", clock, range with one decimal and a trailing full
   stop. That text was written for the model to read, not for the pilot to hear.
5. **`OP_GROUPSOMETHING`, `OP_LRSAM`, `OP_TRUCK` are not mission unit names.** They are DCS's own
   Petrovich classification codes (`body-layer/src/belief/classification.py`), so this is not an
   author-only-knowledge leak. Normal callouts translate them ("ground", "long range SAM",
   "truck"). The brain path does not.
6. **"Metrovids describe right" (0.48)** — the wake word was misheard, so it was not addressed and
   got the honest "Say again?". **"what do you see hit"** — "hit" is a mis-transcription of
   something; the pilot can say what.
7. **"background brain reply poll failed (retrying)" twice** fell between the two brain launches,
   so it is very likely the brain being restarted to switch decider. Not yet confirmed.
8. **"live LOS coverage gap"** is the naked-eye line-of-sight feed from DCS, unrelated to the brain.
   Noted, not part of this feedback.

## Not covered by this flight

Of the card's 14 cases, only the "what do you see" shape reached BR-2's tool loop, once. Still
unflown: where-is-it by name, "where are we" through the tool loop, place questions, marks,
keep-an-eye-on, the three refusals.

## Explore, 2026-11-16 — the pilot's answers

**Found before asking.** The phrasebook already has `report left/right/ahead` (the `where` slot,
`[[BL-B28]]`, `audio-adapter/src/vocabulary.py` `RELATIVE_WORDS`). The brain's command allowlist
(`BRAIN_COMMANDS`, `body-layer/src/belief/tool_api.py`) has `report` with *"no place slot yet,
Stage 4"*, single clock hours 8–4 and eight compass directions, but **no left/right/ahead**. So
"what do you see on the left" had no command to become, against BR-2 plan D7's intent that most
questions *are* commands.

**Answers, verbatim:**

> *"3 - the gap is ok and expected. "Stand by" acknowledges the command so I know the answer is
> coming. That is good."*

> *"4 - "hit" was mistranscribe, I forgot the actual word."*

> *"2 - position and type/class."* — how a crewman tells contacts apart when he has to ask "which
> one". (Not certainty words, not "last seen 32s ago".)

> *"1 - short list of most important contacts. If there's nothing, say so. I already have the
> commands like "describe left" and I'll likely use those. But those same things must be
> actionable via brain. What the brain use cases actually are, are more complex questions and a
> more free-flow-human-like text output. See below"*

**The pilot's own examples of what the brain is for**, verbatim:

> - *"Petrovich, where is our next waypoint" -> "heading x, y km"*
> - *"Petrovich, scan along the route to waypoint 3" -> "scanning"*
> - *"Petrovich, what lies between us and target area?" -> "Friendly units near village at 1
>   o'clock, suspected enemy position beyond ridge 2 km not seen, lake at 4 km just before targeta
>   area"*
> - *"Petrovich, where are air defences?" -> "air defences, AAA at <where>, long range SAM at
>   <where>, ..."*

**What this settles, as read so far (not yet a plan):**

- **Every phrasebook command must also be reachable through the brain**, including the
  left/right/ahead report. The "which one" over right-side contacts for "on the left" is the
  defect to fix on that side.
- **A "which one" names each option by position and type**, in callout words, never `OP_*` codes,
  certainty words or seconds-since-seen.
- **"What do you see" answers are a short list of the most important contacts, or "nothing"** when
  there is nothing.
- **"Stand by" before a brain answer is right**, and the 2–6 s wait is acceptable.
- **The brain's real job is the complex question and the free-flowing answer**: route, mission
  intent, terrain and belief combined into one spoken sentence. That is BR-2 Stage 5 (`say`) and
  beyond, and it moves the weight of the milestone away from template forms.

**Found while asking about the examples:** body-layer already loads the mission route from
mission-interpreter's compact artifact and tracks waypoint progress
(`body-layer/src/belief/mission_phase.py`), and the artifact carries `expected_threats` from the
briefing. No brain tool exposes either yet.
