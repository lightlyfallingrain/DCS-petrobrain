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
