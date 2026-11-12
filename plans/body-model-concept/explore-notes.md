# Explore notes — Petrovich's body: eyes, hands, mouth, brain

Started 2026-11-12, during `BL-B106` (async speech). Prompted by the question "have we discussed
and written down the eyes/mouth/hands concept?" — answer: discussed 2026-10-20
(`docs/acceptance/2026-10-20-sortie-feedback.md` §F8, three standing-direction lines), planned in
`plans/async-speech/plan.md`, **never written as a concept**. `docs/concept/PETROBRAIN_SYSTEM.md`
and `PETROBRAIN_RUNTIME.md` describe software layers, not Petrovich's body.

## What was already recorded (2026-10-20, user, verbatim)

> Petrovich cannot speak two things at one time, he only has one mouth. But mouth is independent
> of eyes and arms. He can look at things while speaking, can manipulate cockpit while speaking and
> brain can reason about something while other parts (layers) do their own things.

Standing direction from that day: speech async; one mouth, utterances serialised; layers talk to
each other asynchronously, a blocking cross-layer call needs a stated reason.

## 2026-11-12 — the resource model (user, verbatim)

> All actions that Petrovich does require one or more of eyes, hands, mouth, brain.
> Eyes can focus on one thing at a time. Looking out using any optic category (only one optic at a
> time), reading switch state, reading lamp state. Reading instrument values.
> Mouth can speak one thing at a time.
> There are two hands. 9K113 needs them both, except for missile pylon switch and radiator reset
> that can be done while the other hand operates slew control. Binoculars need both hands. Switch
> flip needs one hand. Flight controls need both hands, but can for short period do with one hand.
> Brain could do multiple things in parallel, if there is processing power available, but that is
> computer setup limited.
>
> Eyes, hands, mouth and brain can operate indepentently of each other.
> Scanning, tracking, attack run etc need eyes.
> Reading cockpit switch, lamp, gauge, instrument states needs eyes.
> Manipulating cockpit effectors needs one hand.
> When in control of helicopter, cyclic always requires one hand. Collective normally takes the
> other hand, but can for a while free it to flip a switch.
> Anything Petrovich speaks needs the mouth.
> Naked eye usage needs only eyes, no hands. Any non-naked-eye optic requires both hands.
> Kneeboard (=mission memory) would also need eyes and one hand, though first we just need to get
> the mission memory available and working and worry about this later.

## 2026-11-12 — second pass (user, verbatim)

Shown: a resource table with `?` cells and five cockpit questions (busy-resource preemption; does
a switch flip need eyes; peripheral vision inside an optic; how long one-handed flying lasts; who
says "stand by").

> the ? entries:
> -  9K113 pylon switch / radiator reset -> no eyes needed, Petrovich would know from muscle
>    memory. But cannot look at the missile selector lamps without eyes.
> - flip switch -> need eyes, except the pylon switch and radiator reset when using 9K113
> - fly: cycling -> no eyes needed for the cyclic, but eyes needed for aircraft attitude and
>   flight instruments
>
> Cyclic can be operated by either hand, we don't need to model which hand is free.
>
> 9K113 track + read lamp: eyes must leave sight. Track lost? -> eyes must leave to read lamp,
> but can then immediately return to 9K113. Track not lost, but slewing paused while looking
> away.
>
> The questions:
> 1 - "unable" when attack run. Exception: change missile pylon. Exception: OBSERV OFF -command,
>     ends 9K113 usage immediately. If using 9K113 but not in attack run, then queues action
>     after current look finishes (in a few seconds). General logic: finish current look, then
>     eyes/hand off for action, then return to 9K113 and continue. So as not to interrupt a look
>     and also not undue wait on action.
> 2 - generally eye are needed. Muscle memory will do for missile pylon and radiator reset. Also
>     all collective/cyclic buttons by muscle memory.
> 3 - blind outside optic
> 4 - few to several seconds. Cyclic *always* uses one hand. Therefore need to put hand back is
>     determined by need to change collective value.
> 5 - when expected delay is no more that a few seconds, queue (no brain needed). If longer
>     delay is needed, then "stand by". When queued item actioned, then readback on it.

Derived rules (main loop's reading, to be confirmed):

- **Hands are a count (0/1/2 free), not left/right.** Cyclic = 1 hand, always, while in control.
  Collective = 1 hand, releasable; the need to put it back is "collective value must change", not
  a timer.
- **Muscle-memory actions need hands only, no eyes**: 9K113 pylon switch, radiator reset, every
  cyclic/collective button. Everything else on the panel needs eyes + 1 hand.
- **Eyes are one focus, blind outside it**: inside any optic, nothing outside the optic is
  perceived at all. Reading a lamp/gauge is a look like any other.
- **Looks are atomic**: a look in progress finishes; the action is inserted between looks, then
  the previous activity resumes. A 9K113 track survives an eyes-off look (slew paused, track
  kept).
- **Attack run is the one hard refusal**: "unable" to anything needing eyes/hands, except pylon
  change (muscle memory) and `OBSERV OFF` (ends 9K113 use immediately).
- **Queue vs "stand by"** is decided by expected delay: a few seconds → silent queue, readback
  when actioned; longer → "stand by" first, then readback when actioned.

## 2026-11-12 — third pass (user, verbatim)

Shown: three mock exchanges (switch request while on 9K113 outside an attack run; during an
attack run incl. pylon change and `OBSERV OFF`; while flying with hands full) and three questions
(the queue-vs-"stand by" threshold; his initiative vs the pilot's command; blind-in-optic limit).

> 1 - let's use ~5 s and make it configurable.
> 2 - my command first. Maybe threat level based logic later, not now.
> 3 - yes, limit optic usage. A quick naked eye glance around is needed every now and then. We
>     may already have that, btw.
>
> Note on collective. It does not need constant adjustments typically. Once in stable flight
> state, it usually just remains where is is. Manouvres need the collective as well as cyclic and
> pedals.

Derived:

- **Queue-vs-"stand by" threshold ≈ 5 s, a tunable** (`body-layer/src/tuning.py`, per the
  standing X-T26 rule).
- **Pilot command outranks Petrovich's own initiative**, always, for now. Threat-level ordering
  is a later refinement, explicitly not now.
- **Optic dwell is limited**: periodic naked-eye glance around. Check what already exists
  (`optic_policy.py`'s glass budget / scan plan) before adding anything.
- **Collective**: stable flight → hand effectively free; manoeuvres → both hands plus pedals.
  So "hands free while flying" is a function of flight state (stable vs manoeuvring), not a
  timer.

## 2026-11-12 — a sketch from the user (verbatim, left to Architect)

> We could have a solution like:
> ```
> {
> "eyes" : "none"/"9K113"/"scan"/"binoculars"/"effector"/...
> "hand1" : "cyclic"/"binocular"/"effector"/...
> "hand2" : "collective"/"binocular"/"effector"/...
> "mouth" : "speech"/none
> "brain" : "...."
> }
> ```
> Then any actions would need to check if it can proceed or get's queued. Urgent things bypass
> queue.
> Just a though, I leave it to architecht to define a good logic.

Two things in it that the derived rules above had not said: the body state is **one readable
record** naming what each resource is doing now (a state param in the `[[BL-B94]]` sense, so a
"what are you doing?" answer and the debug views can read it), and **urgent bypasses the queue**
(the mouth already has this: `bypass_gate`/`interrupt()`). Hands written as two named slots here;
the earlier direction was "we don't need to model which hand is free" — Architect reconciles
(a count is enough for arbitration; a named slot may still read better in the record).

## Open questions (to be answered in this conversation)

- Preemption/priority: what happens when a new action needs a resource that is busy — refuse
  ("unable, hands busy"), queue, or drop the current action? Does it depend on who asked (pilot
  command vs own initiative) or on what is running (attack run vs scan)?
- "Short period" with one hand on flight controls / collective freed "for a while": roughly how
  long, and what ends it?
- Eyes in an optic: does a threat outside the optic's field get noticed at all (peripheral), or
  only after coming off the optic?
- Eyes in 9K113 sight: reading a lamp/gauge means coming off the sight — does that drop the track?
- Brain: "stand by" — which part says it, and does the brain's limit ever make Petrovich slower
  in a way the pilot should hear about?
