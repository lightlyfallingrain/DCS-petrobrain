# Brain layer — exploration notes (2026-09-24)

`/explore` conversation with the user, held before any Architect pass, per
`.claude/skills/explore/SKILL.md`. **Everything below came from the user in this conversation, not
from the code** — where an existing design document says something different, this file is the newer
source and the concept doc is the thing that is out of date.

The brain layer was the bottleneck: four already-built things wait on it (free-text commands, BL-7's
mission-phase relevance, MI-5's question set, BL-8's conversational kneeboard), the seams have been
idle since BL-5a, and it was the only component with no plan file.

## The governing frame

> "Pilot is responsible for flying and navigation. Co-pilot is responsible for observation,
> detection and identification. For now, Petrovich is limited to co-pilot role."

This is the boundary the whole layer is scoped against.

## 1. The brain is not in the speech path

The single most consequential finding, and it contradicts `docs/concept/PETROBRAIN_RUNTIME.md`'s
"Runtime LLM role" section, which casts the model as the phrasing layer on every structured event.

> "for simple readbacks and contact reports, deterministic is sufficient, no need for brain
> phrasing. Faster is better with simple things. Brain is needed for judgement things like that
> 'keep an eye on that shilka'."

So there are **two loops, not one pipeline**:

- **Fast, deterministic, unchanged.** Contact reports, readbacks, clock/range, threat callouts.
  Sub-second. Never touches a model. This is everything `belief/speech.py` already does.
- **Slow, deliberative.** Judgement only. 5–10 s is acceptable, longer for hard questions
  ("even longer for hard tasks/questions"), and Petrovich says **"stand by"** when a reply will take
  a while. Latency acceptability is to be settled by flying, not by argument: *"We'll need to test
  that by flying missions."*

The practical consequence: **most brain output is a write into the deterministic task/attention
store, not an utterance.** The brain decides; the body speaks. That is cheaper, faster, and keeps
the no-omniscience gate where it already is.

## 2. What the brain is actually for

The user's own list, in his order:

- **World geometry and what it means.** *"most important thing is understanding where the target is
  in the world and where ownship is in the world and what that means in terms of mission geometry."*
- **Reference resolution against shared crew context.** "where is the T-72?" → *which* T-72 → belief
  + memory → location → world-model enrichment → phrasing:
  > "It's 10 o'clock, 2 km, north of V, between road and hill, moving east"
- **Mission-relevant judgement.** Which units matter: if escorting X, whether anything threatens X.
- **Refusal with a reason** — `"unable <reason>"` when an order cannot be fulfilled.
- **Autonomous reporting of active danger to us.**

## 3. Misrecognition and confirmation

- STT clearly failed → **"say again"**.
- Partially heard, not sure → **"Confirm `<command>`?"**
  - player "yes / affirm / confirm" → act
  - player "no / negative" → continue current action, wait for a new command

This retires the earlier "silence is honest, a guessed response is not" rule as the *only* answer.
Silence stays honest for *nothing heard*; a half-heard command gets a confirmation request instead.

**Same mechanism resolves ambiguous referents.** Two plausible T-72s in memory → he **asks which
one, giving the options** ("the one by the village, or the one on the road?"), rather than picking
the most recent silently.

Both paths are the `awaiting_reply_id` / `awaiting_reply_to` round trip already designed into
`belief/escalation.py`'s `BrainClient` at BL-5a and never once exercised. Slice 1 exercises it twice.

## 4. Conversational memory is in scope

"Keep an eye on him" … two minutes … "Still there?" — the pronoun must survive, and "still there"
must resolve without naming anything.

> "yes. That should be part of mission memory."

`EscalationPayload` today carries no conversational history at all — only the current utterance plus
a `situational_header`. This is a real addition, and it belongs with BL-8's memory layer rather than
being invented separately inside the brain.

## 5. Interrupt and resume is a stack — and it is in scope

> "active danger is always priority. Interrupt current action, report and watch active threat until
> clear (report when clear), then resume interrupted action."

Four states in one sentence: suspend, report, watch-until-clear, report-clear, resume. `TaskStore`
has no suspend/resume today. **`plans/watch-reporting/plan.md` (`threat.py`) is the mechanism this
sits on**, which reorders the backlog: watch-reporting is not an *alternative* to starting the brain
layer, it is underneath it.

## 6. What "active danger" means — and the tracer finding

Consult `docs/concept/threat-levels.md` for the priority table; it is the deterministic relevance
data, not brain judgement.

> "any type of air defence is a threat. Priority danger only if it engages us. Most likely case is
> AAA and there Petrovich can see the tracers visually with naked eyesight. Since in such situation
> we'll be flying evasive manouvres, the unit probably will quickly be out of sight. Then belief of
> unit location + world data + ownship position → LOS → still danger/not danger. Also believed
> type/class weapons range → danger/no danger."

Two things fall out, and both matter:

- **Being engaged is *perceivable*, not inferred.** Tracers are a real visual channel — the same
  status as the naked-eye detection channel, not a synthetic proxy. Radar lock and launch warning
  are not perceivable and must not be used.
- **Threat assessment survives losing sight, by degrading honestly.** Once evasive manoeuvring
  breaks the sighting, "is it still dangerous?" is answered from *belief* — last-known position,
  world-model LOS, and the believed type's weapon envelope — not from truth. This is the
  no-omniscience invariant doing real work rather than merely being respected.

`threat-levels.md` already anticipates the hard case: *"unit was actively tracking us, lost track,
now no LOS → still urgent if LOS reacquired."*

**Open technical question for the Investigator, before any design depends on it:** whether firing
events are exportable at all (`S_EVENT_SHOT` in the mission scripting sandbox, reachable over the
`net.dostring_in` bridge that has been shipping at 1 Hz since 2026-09-13 and already carries unit
velocity). If they are, they must be **gated on LOS and visual range** exactly as the naked-eye
channel is — an ungated shot event would make Petrovich aware of every gun in the theatre.

## 7. No omniscience about our own flight

Escort tracking was probed directly: is a co-pilot allowed to simply know where his own flight is,
from radio calls and briefed timing?

> "no-omniscience applies. Asking another unit over the radio 'where are you?' would solve this, but
> it's not supported at the moment (wingbrain would solve this problem)."

So escort watch reduces to **threats detected near the position X was last seen at, degrading as
that belief ages** — the same decay as any other contact. This is a genuine reduction in what escort
watch can deliver, recorded here so it is not rediscovered as a defect later. The radio-query route
belongs to the far-future "wingman brain" direction already parked in `todo/todo.md`.

## 8. The mission briefing (late milestone, user-raised)

Raised by the user unprompted at the end of the conversation, and deliberately scheduled late.

> "Player and Petrovich should go over the mission briefing. That's an opportunity for the player to
> present important information or constraints. Since MI uses the more capable ollama model, this
> should use that as well, only then swap. It's like the crew does this together at a table, not in
> the helicopter. DCS has very poor briefing tool, so do this as first thing when the mission
> starts. Player can skip briefing if he wants to."

Covering: mission goal · flight plan · landmarks along the flight plan and in the target area ·
known and expected enemies · known and expected friendlies · weapons layout · weather.

Notable: it runs on the **capable** model (as the Mission Interpreter does), on the ground,
before the swap to the fast runtime model — which is exactly the model-swap-at-briefing/on-ground
constraint the compute topology already assumes. It is also the natural consumer of MI-5's question
set, which has been built and unwired since 2026-09-12.

## Explicitly deferred in this conversation

| Deferred | User's words |
|---|---|
| Tasks accepted but not yet startable (e.g. "scan around V" held until LOS opens, announcing itself when it does) | "defer" — so for now this is an immediate `"unable, no line of sight"` |
| Co-pilot advising the pilot ("break right", "don't cross that ridge") | "yes, but defer" — confirms an advisory channel is wanted eventually, just not now |
| Chattiness when nothing is happening (periodic "still on him, no change") | "for now silent, defer chatty" |

The first of these is worth flagging as the largest single deferral: the LOS-deferred scan was the
user's own illustrating example in the conversation, and it is being held back deliberately rather
than because it was unwanted.

## Still unanswered, and it will be felt early

**Petrovich cannot see damage.** "Is it dead yet?" → "no, but smoking" is not answerable from the
current feed: `WorldObjectSample` carries id, type, coalition, lat/lon/alt, heading and unit_name —
no life, no fire, no smoke. Routes are `Unit.getLife()` over the mission-sandbox bridge (same
channel as velocity), or object-disappearance as a coarse and late proxy. Neither yields "smoking".

This was raised in the conversation and not resolved. It should be probed before the brain plan
promises the answer, because it is the most natural question a pilot asks after a strike, and a
brain that cannot answer it will feel broken exactly where it matters most.
