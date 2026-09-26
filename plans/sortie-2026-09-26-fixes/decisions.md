# Sortie 2026-09-26 fixes — user decisions

Direction given by the user after reading `diagnosis.md`. **These supersede two recorded decisions
in `plans/binocular-optic/plan.md` (D4 and D5); that file's own text stays as written, and this
file is what is in force.** Recorded in the user's own words because the reasoning is the part that
matters — both decisions turn on how a crew actually behaves, not on what is easiest to code.

## Decision 1 — observability gates callouts, but memory covers a brief occlusion

> *"not visible for few seconds, use memory. In normal case, Petrovich should not report on things
> he cannot observe. That is why a watched contact should get more frequent glances to see where it
> is and can we see more about it. This may be part of the attention grabbing behaviour that is not
> yet implemented."*

Three things, and the third is not part of this fix:

1. **The general rule is the no-omniscience invariant, applied to callouts**: he does not report on
   what he cannot observe. The crossing path currently has no visibility check at all
   (`route_event` does not even take an ownship parameter), which is the defect.
2. **A short occlusion is covered by memory, not silence.** A contact that slides behind the
   doorframe for a few seconds is still being tracked, and a callout from memory over that gap is
   correct crew behaviour. So the gate is not "visible this instant" — it is a grace window, and a
   contact unseeable for longer than that window stops being spoken about.
3. **The real answer to "how does a watched contact stay observable" is more frequent glances at
   it** — Petrovich looking at what he is watching often enough to keep the knowledge fresh, and to
   learn more about it. The user places this with *attention-grabbing behaviour, which is not yet
   implemented*. **It is therefore not part of this fix**; it is the mechanism that will later make
   the grace window rarely matter. Do not build it here, and do not tune the grace window as though
   it were a substitute for it.

**Why this is not a bare gaze-cone gate:** an earlier pass (`plans/callout-outside-gaze/debug.md`)
already fixed the "sounds like a fresh sighting" symptom with wording, which is why the user now
reports crossings as passing. Gating on the gaze cone alone would regress that — a watched contact
briefly out of the cone must still get its tracking update. The gate is about what is *unobservable*,
not about what is momentarily out of view.

## Decision 2 — an interrupted look is not a spent attempt, and not every command interrupts

> *"not every player command should lower the binoculars. Especially not those that are not
> understood."*
>
> - *"me '<something that STT got wrong>' > P 'say again' and does not interrupt anything"*
> - *"me 'follow <target>' > if binoculars were in use AND looking at <target> continue. If
>   binoculars were in use and NOT looking at <target> lower them to look at target, then judge if
>   binoculars should be used."*

Plus the recommendation the user accepted: **an interrupted look does not count as an attempt**, and
**re-eligibility gains a time basis** alongside range.

### This supersedes D4 ("A player command lowers them, unconditionally")

D4's reasoning was that "the pilot asking for something is prima facie evidence that what Petrovich
is doing matters less than what was just asked for". That holds for a command that was *understood*.
It does not hold for:

- **An utterance that was not understood.** "Say again" is not a new task — nothing was asked for
  yet, so there is nothing to prefer over the current look. Lowering the binoculars there destroys
  work in response to a recognition failure. This also has a cost the sortie makes concrete: the
  speech log shows 15 `say_again` and 12 `fallthrough` dispositions out of 128 utterances, so on the
  old rule roughly a fifth of all speech was interrupting a look for no reason at all.
- **A command that asks for what he is already doing.** `follow <target>` while glassing that same
  target is a request to continue, not to stop. Lowering and re-raising would be strictly worse than
  doing nothing.

So the rule becomes: **an understood command that redirects attention lowers the binoculars; one
that does not, does not.** The `follow <target>` case is specified by the user directly — if already
glassing that target, continue; if glassing something else, lower, re-point at the target, and then
re-judge whether binoculars are warranted for it (rather than assuming they are).

### This supersedes D5's "not a timer"

D5 chose range-based retry with an explicit rationale: *"a contact at constant range has not become
more identifiable and re-glassing it spends the budget on a question already answered."* That is
sound for a contact being **closed on**, and wrong for one being **watched or orbited** — which is
exactly the case the user called out ("not even for watched"). A watched contact held at roughly
constant range can never satisfy `RETRY_RANGE_FRACTION`, so under D5 alone it is locked out
permanently. Time-based re-eligibility is what unlocks it; range-based retry stays for the closing
case.

## Decision 3 — briefing-derived belief is knowledge, but it is pull-only

> *"exception to not reporting what is not seen: units believed to be at location based on mission
> briefing. Then belief is the state from mission briefing. Direct observation is impossible. Only
> report about such contacts if the player asks about them. Like 'target unit near <place> can we see
> them yet?' -> '<answer>'. Or 'where are <something>' -> 'beyond the hill at 2 o'clock'."*
>
> *"cannot answer state of units that are not visible, but can know where they are supposed to be,
> roughly. But only report if asked."*

This is an exception to Decision 1, and it is a **provenance** distinction rather than a visibility
one. The no-omniscience invariant bounds knowledge by what Petrovich *could perceive* — and a crew
briefing is something he perceived, before the flight. So briefing-derived belief is legitimate
knowledge he genuinely holds; it is simply knowledge of a different kind, and it comes with different
rules about when he may speak.

**Three constraints, all load-bearing:**

1. **Pull-only, never volunteered.** A briefing-derived contact must never produce a spontaneous
   callout — no crossing report, no sighting, nothing. It may only ever appear in an *answer* to
   something the player asked.
2. **Position roughly, state never.** He can say where a unit is *supposed* to be. He cannot say what
   it is doing, what condition it is in, or anything else that would require having looked at it.
   "Beyond the hill at 2 o'clock" is in bounds; "three trucks, stationary" is not, unless it was
   observed.
3. **The briefing is the state.** Its contents are the belief — not a prior to be refined by
   imagination. If the briefing is wrong or stale, he is wrong in exactly the way a real crewman
   briefed on bad intelligence would be, and that is correct behaviour, not a defect.

### What this changes about Fix A's design

**The observability gate belongs on the volunteering path, not on the answering path.** A gate that
simply suppresses every mention of an unobservable contact would also silence the legitimate answer
to "where are the trucks?", which is the opposite of what the user wants. So the two paths must be
distinguishable at the point the gate is applied — spontaneous callout versus response to a query.
Whichever placement the plan chooses for the gate has to preserve that distinction; a gate low enough
to catch both is the wrong gate.

### Scope note — most of this is not buildable yet

The pull-only answering behaviour needs three things this change set does not have: briefing-derived
contacts in belief at all (Mission Interpreter output reaching the body layer), free-text questions
("where are the trucks?" is not in the command vocabulary and is a `fallthrough` today), and terrain
knowledge to phrase "beyond the hill at 2 o'clock" (world-model ridges). **So Decision 3 is recorded
here as a constraint on Fix A's design, not as work in this change set.** What Fix A must do now is
avoid foreclosing it — do not build a gate that cannot later admit a pull-only answering path.

## What is in scope for the fix

- Observability gate on the crossing-callout path, with a grace window for brief occlusion (D1).
- An interrupted look no longer marks the target attempted (D2).
- Time-based re-eligibility alongside the existing range-based retry (D2).
- Command-dependent lowering: unrecognised speech does not interrupt; `follow <target>` continues if
  already glassing that target, otherwise re-points and re-judges (D2).

## What is explicitly out of scope

- **More frequent glances at a watched contact.** The user assigned this to attention-grabbing
  behaviour, not yet implemented. It is the durable fix for keeping a watched contact observable;
  this change set only stops him speaking about what he cannot see.
