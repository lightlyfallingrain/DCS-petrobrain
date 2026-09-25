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

---

# Attack run (user-raised, 2026-09-24, same session)

Raised by the user after the conversation above, as *"one important feature"*. Recorded here
because it is the first request that exercises every part of the frame above at once — and because
two parts of it change decisions already made today.

## The shape, in the user's own terms

Player: **"engaging `<target>` `<where>` [`<weapon>`]"**, where weapon is guns / rockets /
missiles / bombs.

1. Brain resolves *which unit* `<target>` is, then commands **attack-run `<target>`** to body.
2. Body puts an automatic **watch** on that target.
3. Readback: *"attack run `<target>` `<where>`"*.
4. Petrovich then **guides the pilot onto the target by frequent callouts**, whose register changes
   as the run develops:

   | phase | what he says |
   |---|---|
   | far | "10 o'clock, 2 km, edge of forest" · "11 o'clock, 2 km" · "12 o'clock, 1.5 km" |
   | close, boresight-relative | "10 degrees left, 15 degrees down, edge of forest" · "5 degrees left, 10 degrees down, 1 km" · "at nose, 5 degrees down, 800 m" |
   | lined up | "lined up, 700 m" |
   | after | "hit" / "missed, aim higher" · "target smoking / on fire / destroyed" |
   | re-attack | "target not hit, attack again?" → yes: keep the run and the watch · no: stop the run, **keep the watch** |

   The user's own note on the lined-up call: *"with rockets/gun attack run is almost never exactly
   boresight, it has to take trajectory into account, that's pilots job."* So "lined up" means
   *aligned in azimuth on the target*, not *the weapon will hit* — ballistics stay with the pilot,
   deliberately.

## What this changes

### 1. It is the sharpest case yet of "the brain is not in the speech path"

The brain does exactly one thing here: resolve `<target>` from `"engaging the tank by the village"`
into a contact id, once, before the run starts. **Everything after that is deterministic geometry
at a high callout rate** — bearing, range, boresight-relative azimuth and elevation, and a
world-model semantic fragment. None of it may go through a model: a 5–10 s deliberation budget is
fine for "where is the T-72", and fatal for "at nose, 5 degrees down, 800 m" during a gun run.

This is the two-loop split from §1 above, applied where the latency actually bites.

### 2. Boresight-relative callouts are buildable today — the data is already there

*Verified rather than assumed.* `OwnshipState` (`body-layer/src/perception/source.py`) already
carries `pitch_deg` and `bank_deg` alongside `heading_true_deg`, converted from the aircraft
layer's radians, **with both sign conventions confirmed against DCS by the user on 2026-09-17**
(positive pitch = nose up, positive bank = right wing down). That was banked for cockpit
visibility; it is exactly what "10 degrees left, 15 degrees down" needs, and it means this
vocabulary costs geometry and phrasing, not a new data channel.

What is genuinely new is the *register*: `belief/speech.py` speaks o'clock and kilometres because
the pilot wants relative position. Attack run needs a second vocabulary — signed degrees off the
nose, in two axes — and a rule for when to switch from one to the other. The switch point is a real
design question (range? angular rate? the moment the target enters the windscreen?), not a constant
to pick casually.

### 3. It makes the damage probe a prerequisite, not reconnaissance

*"hit" / "missed" / "target smoking / on fire / destroyed"* and *"target not hit, attack again?"*
all require perceiving what the strike did. That is precisely what
`aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md` is probing,
and today it is recorded as optional recon with the outcome unknown.

It is not optional any more. **Attack run cannot deliver its last three lines without it**, and if
the probe comes back negative on damage the feature ships with a hole exactly where the pilot is
paying most attention.

**The hardest part is not "hit" — it is "missed, aim higher".** Knowing *that* a round connected is
plausibly answerable (a life-fraction drop, or `S_EVENT_HIT`). Knowing *where the rounds went* when
they did not connect is a different problem with no identified channel at all: it needs the impact
point relative to the target, which nothing in the probe covers. Flagged now rather than discovered
during implementation. A defensible first version says "missed" and stops there, and only offers a
correction if a real impact-point signal turns up.

### 4. It carves out the advisory channel that was deferred four hours earlier

Earlier in this same conversation the user deferred the co-pilot advising the pilot — *"break
right", "don't cross that ridge"* — with *"yes, but defer"*. **Attack-run guidance is that channel**:
"10 degrees left, 5 degrees down" is an instruction to fly, not an observation.

This is not a contradiction, and it should not be read as one. It is a **bounded first instance**:
advisory output confined to a single commanded manoeuvre, with the player having just declared the
intent, a named target, and an explicit end condition. That is much narrower than general flight
advice, and it is the natural shape for the advisory channel to be built in first. Recorded
explicitly so nobody later "discovers" the inconsistency and reopens the general deferral.

### 5. "Attack again?" is the same round trip as everything else

Third use of `awaiting_reply_id` / `awaiting_reply_to`, after confirm-a-doubtful-command and
disambiguate-a-referent. Same machinery, and the *"no"* branch carries a real detail worth keeping:
**stop the run, keep the watch.** The target does not stop mattering because this pass ended.

## Sequencing

This sits **after** BR-1 (the loop) and the damage probe, and it is a natural BR-2/BR-3 consumer
rather than a milestone of its own — the target-resolution half is BR-2's reference resolution with
a different verb, and the guidance half is deterministic body work that could be built in parallel
with either. It should not start before the probe answers, because the probe determines whether
this feature's most-watched moment is buildable at all.

## Three resolutions, same session — all three were open questions above

### The register switch is parameter-free, and falls out of the clock vocabulary

> "when target is 12 o'clock sector, use x degrees left/right. When outside 12 o'clock sector, use
> o'clock. km to m when distance <1km."

So the switch is **not a range threshold and needs no tuned constant**. The o'clock vocabulary
already partitions the horizon into twelve 30° sectors; the rule is simply *which sector the target
is in*:

| condition | azimuth said as |
|---|---|
| target inside the 12 o'clock sector (within ±15° of the nose) | signed degrees — "10 degrees left" |
| target in any other sector | the o'clock — "10 o'clock" |

Range is a separate, independent switch: **kilometres above 1 km, metres below it.** The two do not
have to change together, and this is why "10 o'clock, 2 km" and "at nose, 5 degrees down, 800 m"
are both natural while an intermediate mixture is not.

This also explains the elevation half by analogy: degrees down has no clock equivalent, so it
appears only once the azimuth has already switched to degrees — i.e. once the target is in the
windscreen, which is the only place a pilot can act on it anyway.

Worth noting what this avoids. The obvious design — pick a range at which the callout register
changes — would have needed a constant nobody could defend, and would have read wrong whenever
range and bearing disagreed (a target at 400 m and 4 o'clock is close but not being run in on).
Keying on the sector makes the vocabulary mean *"can you see it through the windscreen"*, which is
the thing the pilot is actually being helped with.

### Miss detection is deferred; hit and damage are kept

> "defer miss detection. Keep hit/damaged detection"

This settles the "missed, aim higher / lower / left / right" line above — it does not ship in the
first version. The reason it was flagged stands: knowing a round *connected* is plausibly
answerable, while knowing *where the rounds went when they did not* needs an impact point no
identified channel provides.

So the callout set narrows to **"hit"**, the damage-state family (**"target smoking / on fire /
destroyed"**), and **"target not hit, attack again?"** — which does not require knowing *why* it
was not hit, only that it was not. That distinction is what makes the re-attack prompt survive the
deferral while the correction advice does not.

The damage probe remains a prerequisite; nothing about this deferral relaxes that.

### Requested advisory, not autonomous advisory

> "attack run is *requested* advisory. Autonomous advisory is deferred."

**This is a better axis than the one drawn above**, and it replaces it. The earlier framing called
attack run a "bounded first instance" of the deferred advisory channel — bounded by scope, by a
named target and by an end condition. That reads as a partial exception carved out of a rule, which
invites exactly the later argument it was written to prevent.

The real distinction is **who initiated it**. The pilot said *"engaging"*. Everything Petrovich then
says about where to point the aircraft is an answer to a question that was asked — the same
category as a readback or a contact report, just continuous. What stays deferred is Petrovich
deciding *on his own* that the aircraft should be flown differently: "break right", "don't cross
that ridge", "we're drifting off the road". Nobody asked.

Stated as one line for whoever reads this next: **advisory output is allowed when the pilot
requested it and is still in the manoeuvre he requested it for; unrequested advisory is deferred.**
That rule decides future cases on its own, which the "bounded instance" framing could not.
