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

## Explore, round 2 — direction and the examples, verbatim

**Direction — the brain's primary role is free text and complex questions/commands:**

> *"this is correct and key feature. The deterministic tools already exist and I can use them.
> Brain must be able to use the same tools (to get information or act on what I said), but the
> primary role os free-text and complex questions or complex commands. To answer/act brain needs
> access to the complete tool set, that is why it's needed. Prioritize Stage 5 free-text. These
> "Petrovich, what is on left" should be treated more as examples in testing basic
> functionality."*

**Briefed (expected) units:**

> *"1 - expected units (via briefing (or reports by other units if ever implemented)) are
> important. That's how you get an advance waring and can either avoid or cautiously advance."*

**"Between us and the target area":**

> *"2 - that's an example, don't have to build that exact case. However, I'd except take straight
> line from current position to target and a corridor about 2 km wide on either side. Report units
> within that corridor and known units taht could engage us from outside that corridor. I'd need to
> know if there are friendlies and where so I don't mistake them for enemy. Big terrain only,
> villages yes, roads no."*

**Next waypoint:**

> *"3 - compass heading, like 315 degrees."*

**"Scan along the route to waypoint 3":**

> *"4 - That would utilize the existing scan tools. Say, we're en route to WP3, then it's ahead and
> scan would be fairly normal scan ahead up to WP3 distance and report what you see. On the other
> hand, we could be en route to WP2 and WP3 could be 20 turn right at WP2 and then 5 km straigh.
> Then scan for WP3 would mean scan between WP2 and WP3. Again using existing scan tools, that'd be
> scan 12, 1, 2 o'clock or something like that."*

**"Where are the air defences":**

> *"5 - by danger. <where> = e.g. 11 o'clock, south of village. Always o'clock and distanve, but
> landmark reference is good additional info."*

**What this settles, as read (not yet a plan):**

- **BR-2's priority changes: Stage 5 free-text (`say`) first.** The template forms (D7 1–4) and
  the phrasebook-equivalent questions ("what's on the left") become basic-function tests, not the
  milestone's point. The brain needs the **complete** tool set, both to learn and to act.
- **Briefed units are first-class knowledge**, spoken as briefed/expected and kept distinct from
  seen. They are the advance warning. Reports from other units would be the same kind of source,
  if ever built.
- **Friendlies and their positions are needed knowledge**, to avoid mistaking them for enemy.
- **Corridor questions:** straight line from ownship to the target, about 2 km either side. Units
  inside it, plus known units outside it that could engage. Big terrain and villages; no roads. An
  example of the reasoning wanted, not a case to build specifically.
- **Headings to a waypoint are compass degrees** ("315").
- **Route scans compose the existing scan tools** from route geometry: ahead to the waypoint when
  it is the next one, or the clock sector covering a later leg.
- **Threat lists sort by danger.** Every position is clock + distance, plus a landmark where one
  helps ("11 o'clock, south of the village").

**Correction, same day — friend or foe is not known yet:**

> *"IFF is not build yet, we don't yet know the difference between friendly and enemy unit. Will
> later."*

So "friendlies and where they are" (round 2, question 2) is a **future need that depends on IFF**,
`[[BL-B12]]` (deferred), not something Stage 5 can deliver. Until then a free-text answer must not
call a seen unit friendly or enemy unless a source actually says so.

## Goal-check questions answered — 2026-11-16, verbatim

Goal-aligner's nine questions (`plans/brain-tool-calls/alignment.md`, "Goal check — 2026-11-16
(Stage 5 free text, reprioritised)", on `feature/br2-free-text`), and the pilot's answers:

> *"Q1 - never hidden units. briefing only units, as recommended.*
> *Q2 - that would be usefull, yes.*
> *Q3 - start over*
> *Q4 - Not sure, needs flights to get a feel of it. Report groups. Near to far, air defense gets
> emphasis. Up to 5km, not beyond that, and make it a configurable variable.*
> *Q5 - yes. Dangerous units first, those that could engage us, after that near to far as I said in
> Q4*
> *Q6 - in that example I meant mission briefing target - but this is just an example, do not take
> it as specs for building it*
> *Q7 - "seen earlier"*
> *Q8 - explore this with me*
> *Q9 - as he finds them - but this is just an example, do not take it as specs for building it*
>
> *Do not build anything yet, this needs more exploring."*

The questions, for reference: Q1 hidden/late-activation units as briefed threats; Q2 briefed
friendlies before IFF; Q3 an answer cut off by an urgent callout; Q4 longest answer; Q5 "by
danger" order; Q6 what "the target" is; Q7 wording for a unit seen earlier; Q8 whether the
complete tool set still keeps weapons, sight and flying fixed-phrase only; Q9 route-scan reporting.

**What this settles, as read (not yet a plan):**

- **Briefed threats come from the briefing text only, never from hidden or late-activation
  units.** Briefed friendlies, positioned, are useful even before IFF; a seen unit is still never
  called friendly.
- **An interrupted answer starts over** after the urgent callout.
- **Lists report groups,** dangerous units first (those that could engage us, type and range from
  the threat-levels table), then near to far, with air defence emphasised. **Range cut-off 5 km,
  a configurable value** (a body-layer tunable). Length to be judged from flights.
- **A unit not seen now is "seen earlier".**
- **Q6 and Q9 are examples, not specs** (briefing target; contacts called as found).
- **Q8 is open, to explore with the pilot.**
- **Nothing is built until exploring is done.**

## Explore, Q8 — what the brain may do, verbatim

Asked: with BL-16 making Petrovich fly, how flying, the 9K113 sight and weapons, and scanning
should work through the brain, and where a real crew draws the line.

**The general goal:**

> *"First, general goal. If I had the compute power, I'd have the brain handle a lot of the things
> that deterministic code now does. But I need a fast response and do not want to rely on cloud
> LLM's (to save on costs). Therefore deterministic actions exist for most of the things that
> repeat often and can be done deterministically. The benefit on an LLM would be natural speech
> and interaction, mimicking a human co-pilot.*
>
> *Now, since there's limited compute, the LLM used is small to be fast. But the goal kinda is the
> same. Mimick a human pilot - copilot communication and operation. That is why the brain needs
> access to the tool set. It must be able to get information it needs and command the body layer
> to do things. Numeric values included.*
>
> *Now, the brain cannot do anything it pleases, there is only a given toolset available that the
> body layer has."*

**The four questions:**

> *"Q1 - Normal use case is deterministic commands: "turn left 20". "Petrovich, get us behind the
> ridge on right", would be brain stuff, but also much more complex that makes sense at this time.
> Flight commands are expected to be deterministic at this stage. At some point, we'll need
> instructions like, fly to a certain point, but whether that is deterministic, brain, or
> combination of both needs to be determined later.*
> *Q2 - sight, yes. Brain should be able to read weapon statuses.*
> *Q3 - brain should be able to read scan data and command scans*
> *Q4 - There is no definitive line. With a human copilot, everything would happen from just
> talking to each other. We have to balance between fast, deterministic but inflexible solution
> and flexible but slow LLM guided actions/speech."*

**What this settles, as read (not yet a plan):**

- **The brain is the human-copilot conversation; deterministic commands are the fast path for
  what repeats.** Both reach the same body-layer tool set. The tool set is the boundary of what the
  brain can do, and the brain can both read and command through it, **numeric values included**.
- **Flying stays deterministic for now** ("turn left 20" is a fixed command). Terrain-reasoning
  flight ("get us behind the ridge") is out of scope at this time. "Fly to a point" is a later
  decision: deterministic, brain, or both.
- **The 9K113 sight is open to the brain.** This revises the BR-2 plan's U2 exclusion of
  `observ_on`/`observ_off`/`point`.
- **Weapon status is readable by the brain.** *Read as read-only: the answer does not open arming
  or engaging, so `weapons_armed`/`weapons_safe`/`engage`/`disengage` stay fixed-phrase until
  the pilot says otherwise.*
- **Scans: the brain reads scan data and commands scans.** The scan family is today missing from
  the brain's command allowlist by omission, not decision.
- **There is no fixed line between brain and deterministic paths.** It is a speed-versus-
  flexibility balance, decided case by case.

## Exploring closed — 2026-11-16

> *"BR-2 exploration done, queue architecht after BL-16 merges."*

Next: Architect re-plans BR-2 (Stage 5 free text first) on `feature/br2-free-text`, from this
document and `plans/brain-tool-calls/alignment.md`'s 2026-11-16 goal check, **after
`feature/bl16-takeover-fix` merges.** Plan only; nothing built until the plan is approved.

**Re-ordered the same day:** *"schedule AC-B12 before BR-2"*. BR-2's re-plan now waits for
`[[AC-B12]]` (splitting Export.lua into modules) as well: BL-16 takeover fix → AC-B12 → BR-2.

**Dequeued later the same day:** *"dequeue BR-2"*. BR-2's re-plan is **no longer queued** after
AC-B12 or anything else; it starts only on the user's word. Exploring stays closed and its results
stand (this document, and the goal check on `feature/br2-free-text`).
