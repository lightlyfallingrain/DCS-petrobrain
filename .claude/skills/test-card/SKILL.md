---
name: test-card
description: Publish an artifact card for a test the user has to perform — in-flight, on Windows, or anywhere a terminal is not in reach
type: user-invocable
---

Build and publish an artifact page for a test **the user must carry out themselves**. Usage:
`/test-card <what is being tested>`.

The trigger is simple: whenever a Definition of Done pass, a milestone, or a stage produces
acceptance work only the user can do — a sortie, a Windows session, anything needing their hands or
their judgement — that work gets a card. Not a section in a plan file they would have to find and
scroll, and not a wall of chat they would have to keep in a second window while flying.

## Why an artifact rather than a markdown file

The user is flying an aircraft, or sitting at a different machine. A card has to survive being read
in glances, in a second monitor, possibly in VR. That is a design problem, not a formatting one:
large type, one idea per block, checkboxes that persist so a five-minute interruption does not lose
their place.

The first card (`docs/acceptance/2026-09-18-stage6-sortie.md` → published 2026-09-20) was built
from an existing markdown flight card and the difference was immediate — the user's words were
"excellent, we should use those regularly". The markdown was complete and correct and still
unusable at the controls.

## What a card must contain

**The branch, first.** The user tests in the main checkout and does not use worktrees, so the card
must open with which branch to check out and the command to do it — `git checkout <branch>`. Work
that has not merged yet lives somewhere specific, and "it's ready" is not actionable if they cannot
tell what to check out. This is the most common thing a card can silently omit, because whoever
writes it already knows the answer.

**Setup, verbatim and verified.** Every command exactly as it must be typed, with the paths and
flags this repository uses today. Run them, or mark them unverified. This role has a documented
history of publishing commands that were never executed — see `.claude/agents/dod.md` — and a card
is the worst place for it, because the failure lands when the user is least able to debug.

**What is *not* testable, stated early.** The Stage 6 card had to say plainly that voice commands
could not be tested because Windows capture was not built. Without that the user would have spent
flight time on it. Absence of a feature is information; omitting it wastes the scarcest resource in
the exercise, which is their time in the seat.

**Per block: do / expect / record.** Three labelled parts, always in that order. "Expect" carries
the number or behaviour that would mean it worked — a card without expectations makes the user
judge against memory. "Record" is the list of specific observations wanted back.

**Record items come in two shapes, and using the wrong one loses the answer.** Found the hard way
on the voice card (user, 2026-09-23): *"there are checkboxes for open ended questions, yes/no is
not an answer to an open ended question"*. Every item had been a checkbox, so *"time from release
to readback, roughly"* offered a tick — which records that the pilot looked, and throws away the
number, which was the entire point of asking.

- **A check** is for something that either happened or did not. *"Did a full press ever execute a
  command"*. A checkbox is exactly right.
- **A note** is for a value, a duration, a range, a judgement, or anything phrased as *how much*,
  *how long*, *which*, or *does it feel*. It needs a **text field**. This is most of what a card
  actually wants back — the numbers and the impressions are what no test could produce, and they
  are precisely the items a binary loses.

When writing a block, read each item back as a question and ask what a truthful answer looks like.
If the answer is a word or a number, it is a note.

**One block marked as the prize.** There is almost always a single measurement worth more than the
rest, and saying so changes what gets done when attention runs short. On the Stage 6 card it was
the detection ranges — never flown, and the input several downstream milestones were waiting on.

**A bring-back list.** One line per block, plus an explicit invitation: *anything that surprises you
is worth more than anything on this list.* Several of this project's most important corrections
arrived that way rather than in answer to a question.

## Checking it before publishing

- **Every command run**, or labelled `UNVERIFIED` where it genuinely cannot be (needs Windows,
  needs DCS, needs a sortie). Both are fine; a confident guess is not.
- **Conflicts between tests surfaced.** The Stage 6 card nearly told the user to run the PTT probe
  as a rider on the same flight — but `Export.probe-ptt.lua` replaces the production `Export.lua`
  and kills the collector, so it needs its own session. That kind of conflict is invisible unless
  you check what each test actually swaps out.
- **Expectations are numbers where numbers exist.** "Presence at 9 330 m, class at 2 000 m, type at
  1 000 m" is checkable in the cockpit. "Detection should work" is not.

## Building it

Load the `artifact-design` skill first, as any artifact requires. Keep the family resemblance to
the existing cards — Barlow Condensed display, Source Sans body, JetBrains Mono for commands — but
the palette should suit *reading in a cockpit*: dark ground, amber instrument accent, a distinct
colour for the "record this" rail.

Include the persistence script; it is a dozen lines and it is the difference between a card the
user ticks through and a card they lose their place in. **It has to cover the text fields too** —
a typed observation lost to a stray reload is worse than an unticked box, because the box can be
re-checked from memory and the number cannot:

```js
const KEY='<test-name>';
const saved=JSON.parse(localStorage.getItem(KEY)||'{}');
const save=(k,v)=>{
  const s=JSON.parse(localStorage.getItem(KEY)||'{}');
  s[k]=v; localStorage.setItem(KEY,JSON.stringify(s));
};
document.querySelectorAll('input[type=checkbox][data-k]').forEach(b=>{
  if(saved[b.dataset.k]) b.checked=true;
  b.addEventListener('change',()=>save(b.dataset.k,b.checked));
});
document.querySelectorAll('textarea[data-k],input[type=text][data-k]').forEach(f=>{
  if(saved[f.dataset.k]) f.value=saved[f.dataset.k];
  f.addEventListener('input',()=>save(f.dataset.k,f.value));
});
```

A note item is a label plus a field, styled to match the checkbox rail:

```html
<li class="note-item">
  <label for="a2">Time from release to readback, roughly</label>
  <input type="text" data-k="a2" id="a2" placeholder="e.g. half a second">
</li>
```

Give text fields a `placeholder` that shows the *shape* of the wanted answer — a duration, a range,
a word. It costs nothing and it is the difference between "about half a second" and "yes".

## Afterwards

The card is a view, like the status page. The **source of truth stays in
`docs/acceptance/`** — the card is generated from it and may be republished as the test changes.
When results come back, they go into the roadmap and the relevant research note, not into the card.

Publish with `favicon: 🚁`, a one-sentence `description`, and **always pass the artifact's `url`
when updating an existing card** — artifact identity follows the file path, and republishing
without it creates a second card while the user's link goes stale.
