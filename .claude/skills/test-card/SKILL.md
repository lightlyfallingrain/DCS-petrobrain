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

**The card cannot collect anything, so do not build it as if it can.** It is a prompt list read in
the cockpit; the answers come back in conversation afterwards. This was learned twice in one day
(2026-09-23). First the user pointed out that a checkbox is not an answer to an open question —
*"yes/no is not an answer to an open ended question, would need a textbox"* — so text fields were
added. They persist to `localStorage`, which lives in the pilot's browser and is unreadable from
here, and the next message was the correction that matters: *"input fields on cards are useless
unless you can read them. I can write my notes directly here too."*

So the card's job is to **ask the right questions in the right order**, not to receive answers:

- **Phrase every open item as a question with a speakable answer.** *"How long from release to
  readback?"* — not *"Latency acceptable?"*. The pilot reads it, observes it, and says the number
  later. The phrasing is the whole contribution: a badly-phrased item produces a vague answer no
  matter what widget sits next to it.
- **The checkbox is a place-keeper, not a record.** Its only job is surviving a five-minute
  interruption so the pilot knows which items they have already covered. It is fine for that and
  should not be asked to do more.
- **The bring-back list is the actual mechanism.** It is what gets read out afterwards, so it
  carries the real questions — keep it short enough to answer from memory in one sitting.

Never add a text input, a form, a copy-to-clipboard block or a download. Anything the page appears
to save is lost, and a control that looks like it captured an observation is worse than no control
at all: it takes a real answer and quietly discards it.

**One block marked as the prize.** There is almost always a single measurement worth more than the
rest, and saying so changes what gets done when attention runs short. On the Stage 6 card it was
the detection ranges — never flown, and the input several downstream milestones were waiting on.

**A bring-back list.** One line per block, plus an explicit invitation: *anything that surprises you
is worth more than anything on this list.* Several of this project's most important corrections
arrived that way rather than in answer to a question.

## Checking it before publishing

- **Every command run**, or labelled `UNVERIFIED` where it genuinely cannot be (needs Windows,
  needs DCS, needs a sortie). Both are fine; a confident guess is not.
- **Every command carries the directory it runs in**, whenever a card spans more than one
  subproject. The voice card put the collector and the capture process in one Windows block, both
  prefixed `set PYTHONPATH=src` and neither with a `cd` — so the second was run from the first
  one's directory and died on `ModuleNotFoundError`, mid-test. Each subproject has its own `src`,
  and `PYTHONPATH=src` means nothing without knowing where you are standing. A block of commands
  that silently assumes the previous block's working directory is a card that only works for
  whoever wrote it.
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

Include the persistence script for the checkboxes; it is a dozen lines and it is the difference
between a card the user ticks through and a card they lose their place in. **Checkboxes only** —
see above for why the page must not appear to save anything else:

```js
const KEY='<test-name>';
const saved=JSON.parse(localStorage.getItem(KEY)||'{}');
document.querySelectorAll('input[type=checkbox][data-k]').forEach(b=>{
  if(saved[b.dataset.k]) b.checked=true;
  b.addEventListener('change',()=>{
    const s=JSON.parse(localStorage.getItem(KEY)||'{}');
    s[b.dataset.k]=b.checked; localStorage.setItem(KEY,JSON.stringify(s));
  });
});
```

## Afterwards

The card is a view, like the status page. The **source of truth stays in
`docs/acceptance/`** — the card is generated from it and may be republished as the test changes.
When results come back, they go into the roadmap and the relevant research note, not into the card.

Publish with `favicon: 🚁`, a one-sentence `description`, and **always pass the artifact's `url`
when updating an existing card** — artifact identity follows the file path, and republishing
without it creates a second card while the user's link goes stale.
