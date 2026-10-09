---
name: explore
description: Dialogue with the user to surface lived-world knowledge before a consequential decision is settled
type: user-invocable
---

Hold an open conversation with the user before committing to a design. Usage: `/explore <topic>`, or
run it unprompted when the trigger below fires.

**Why this exists.** The user flies the Mi-24P. They know what a crew member sounds like, what the
SPU-8 does under the hand, what a target column looks like at 9 km. That knowledge is not in any
file here, and it is not retrievable by reading more code. Repeatedly in this project the decisive
input arrived *after* implementation started — and reversed it:

- Frequency injection was planned around for a whole slice before "I need to stay on the mission
  frequency and the Mi-24 does not handle multiple channels simultaneously" removed the option.
- The SPU-8 volume knob became the strongest argument for the SRS path. Nothing in the codebase
  could have suggested it.
- A calibration pass was completed, reviewed and merged against compressed screenshots before
  "I found a way to get good quality screenshots" invalidated its central finding.
- A contact-merge bug fix was reframed into a whole belief model by one sentence describing how
  recognition actually unfolds: *"there is something" → "many somethings" → "3 tanks and something
  else" → "not ifvs, but shilka"*.
- Two model revisions in, "it's about *angular* distance, not absolute" replaced the resolution
  model outright — with an apple-and-orange analogue that no amount of code reading would produce.

Every one of those was cheap to hear and expensive to discover late.

## When to run it

Before an Architect pass on anything **consequential**: a new subsystem, a data-model change, a
decision that is hard to reverse, or anything touching how Petrovich behaves in the cockpit.

**Do not run it on everything.** Applied to routine work it becomes friction and trains the user to
skip past it — the same failure mode `AGENTS.md`'s Effort/Value check warns about. A bug fix with an
obvious cause, a refactor, a documentation change: just do the work.

The strongest signal that it was needed is retrospective — if the user's next message after
implementation starts reverses a design assumption, that phase was skipped.

## How to run it

### First, find out what is already known — before the first question

**User direction, 2026-10-06.** In their words: this phase *"also needs graphify/grep use, to check
what we know currently from notes, roadmaps and memory files. So we don't unnecessarily spend effort
on exploring something that is already known, just not in context at that time."*

The failure is not forgetting a decision; it is that **a decision can be recorded and still absent
from the conversation**, so the user is asked to re-derive something they already settled — or worse,
work gets built against a direction that was already withdrawn in writing.

**The worked example cost a night.** The direction *"world model LOS must not be used… testing only"*
was captured verbatim in `docs/acceptance/2026-10-05-sortie-feedback.md` **before** four
whole-subproject review reports were written. None of them picked it up, and the milestones written
from them treated the silent fallback as something to make *observable* — the right fix for a
fallback allowed to exist, and the wrong one for a fallback that must not run. The user had to
restate it, and restating it is the symptom this step exists to remove.

So, before opening the conversation, spend two or three minutes on:

```sh
.claude/scripts/gq.sh "<the topic in the user's own words>"
```

and then, because the graph does not cover everything:

```sh
grep -rn "<key term>" todo/questions.md todo/backlog/ todo/todo/ .claude/agent-memory/  # out of corpus
grep -rn "<key term>" docs/acceptance/                                          # prior feedback
```

**Which instrument answers which question** — the split is in root `CLAUDE.md`, "Graph to find it,
`grep` to prove it is gone":

- **graph first** for *"where is this discussed, was this decided?"* — it covers `CLAUDE.md`,
  `AGENTS.md`, roadmaps, `NOTES.md`, `docs/`, research notes and the active plan.
- **`grep`** for `.claude/agent-memory/`, which is **deliberately outside the corpus**
  (`graph-corpus-files.sh:25`), and for any *"does anything still say X"* question, where a
  trustworthy negative is needed and the graph's negatives are documented unreliable.

**Then open the conversation with what you found, not with a blank question.** "Your 2026-10-05 note
already says offline LOS is testing-only — does that extend to X?" is a better first question than
"how should LOS work?", and it is the difference between the user teaching you something new and the
user repeating themselves. If the check turns up a decision that **already answers** the topic, say
so and skip the explore: that is the step working, not a reason to hold the conversation anyway.

**Keep it short.** This is a few minutes of looking, not an audit — the point is to arrive informed,
not to pre-empt the conversation. If the search is turning into a research project, that itself is
worth saying out loud.

**Open questions, not menus.** `AskUserQuestion`'s multiple choice is the wrong instrument here: it
can only surface options already thought of, and the valuable input is precisely what was not
thought of. Save the menus for settling a decision once its shape is understood.

**Ask about the world, not the software.** Not "should cardinality be a belief?" but "what does it
actually look like when you spot a group at distance — what comes first?" The user reasons fluently
about the cockpit and the airframe; make that the subject.

**Show something concrete early — it is an elicitation technique, not a deliverable.** Observing
concrete output is what cues recall; several of the examples above arrived exactly that way. A
rough thing shown early beats a polished thing shown late.

**Build mock-ups, diagrams and thought experiments freely for this** (user direction, 2026-09-18:
"mock graphics, generated images, imaginary thought experiments, etc. All such things help me
understand the concept and then process it"). This is not gold-plating — it is the cheapest way to
get the good input. What works here:

- **Scale diagrams.** An SVG or Canvas drawing of the actual geometry, to scale, with the numbers
  on it. The angular-separability correction would have surfaced far earlier from one picture of
  two units at 9 km versus 500 m.
- **Worked numeric tables.** A handful of rows across the real range of the parameter. Cheap to
  produce in a `python3` one-liner, and they make a wrong model obvious at a glance.
- **Mock output.** A transcript of what Petrovich would actually say under design A versus design
  B. Reading two sample callouts side by side settles arguments that paragraphs do not.
- **Artifacts** for anything worth interacting with — they are private by default, take one pass,
  and support zoom, drill-down and both themes. The project status page is the precedent.
- **Mermaid** for structure and state, inline or in an artifact.
- **Thought experiments and analogues — offer them, do not only ask for them.** The apple and the
  orange reframed an entire model. Propose a non-DCS situation with the same shape and let the user
  correct it; a wrong analogue is often more productive than a question, because correcting it is
  easier than generating one.

**Honest limit**: there is no image-generation model available here. "Generated images" in practice
means SVG, Canvas, HTML or Mermaid — which covers geometry, charts, mock interfaces and diagrams,
but not photographic or artistic renderings. Say so rather than promising a picture that will not
arrive.

**Follow the tangent.** If they start explaining how the SPU-8 works when asked about audio
routing, that digression is the point. Domain experts surface constraints by association, not by
answering in order.

**Ask what the analogue is.** "Is there a non-DCS situation like this?" produced the apple and the
orange, which reframed an entire model.

**Probe the physical.** What can the crew actually see, hear, reach, and do — and when. Those are
the constraints that invalidate designs, and they are invisible from inside the code.

**Stop when it turns speculative.** The value is in lived experience. Once the conversation moves to
what *might* be nice, the phase is done.

## Capturing it

Write what emerges into the plan or roadmap **as it emerges**, not afterwards — quote the user
directly where the phrasing carries the reasoning. This project's roadmap entries are load-bearing
precisely because they preserve *why*, including where an earlier pass was wrong.

Then proceed to Architect with the constraints in hand, and state in the plan which decisions came
from this conversation rather than from the code.
