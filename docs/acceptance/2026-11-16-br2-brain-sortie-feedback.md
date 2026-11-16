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

## Open for the explore conversation

To be settled with the pilot before any plan — see the conversation of 2026-11-16.
