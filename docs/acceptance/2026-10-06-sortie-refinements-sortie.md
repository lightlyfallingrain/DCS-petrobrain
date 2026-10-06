# Sortie refinements sortie — `describe`, group watch, sweeping `scan ahead`

**Cockpit card (published):** https://claude.ai/artifact/RueFQ6R3BZB7vZgfEugorQ — the same content,
laid out for reading in glances. This file stays the source of truth.

Three of the four change requests from your 2026-10-05 debrief
(`docs/acceptance/2026-10-05-sortie-feedback.md`, items 2, 3 and 4). Item 1 — the location-fragment
rewrite — is **not** in this and is still its own branch.

**Every command in this card was executed and its real output pasted, except where a line says
UNVERIFIED.** The only things labelled UNVERIFIED are the ones that need DCS running on the Windows
box, which cannot be run from here.

---

## Which branch to fly

**Preferred: `main`, after this merges.**

```sh
git checkout main && git pull
```

The merge is not automatic — `body-layer/tests/test_callouts.py` conflicts against `main` and has
to be resolved by reading, so the merge is a deliberate step someone takes rather than something
that has already happened. Check that `main` actually carries these three items before flying it.

**If you want to fly it before the merge: `feature/sortie-refinements`.**

```sh
git checkout feature/sortie-refinements && git pull
```

Two things you give up by flying the branch instead of merged `main`, because the branch forked
before them (both merged overnight, 2026-10-06):

- the callout observability gate — on the branch, unprompted callouts **can** still name clock
  hours 5/6/7;
- the stamped sortie logs — the branch's `run-scripts/run-crew-text.sh` still writes
  `--speech-log ~/dcs-speech.jsonl`, not `logs/dcs-speech.jsonl`. Verified by diffing the script
  against `main`.

## Running it

UNVERIFIED (needs the Windows box and DCS — not runnable from here). The usual script, unchanged by
this branch:

```sh
./run-scripts/run-crew-text.sh
```

Its flags were checked against the logger's own `--help` on this branch — `--crew-text`,
`--f10-commands`, `--speech-audio`, `--speech-input`, `--speech-log` all still exist and still parse.

**One thing that is easy to get wrong when speaking commands: do not start a command with
"Petrovich".** A transmission that begins with the wake word is routed to the brain as free speech;
a transmission without it is matched against the command vocabulary. Say *"Describe."*, not
*"Petrovich, describe."*

---

## 1. `describe` now works wherever `report` did

**Voice only — there is no F10 button for this one.**

| say | expect |
|---|---|
| *"Describe."* | the full contact rundown, identical to *"Report."* |
| *"Describe contacts."* | the same |
| *"Describe eleven o'clock."* | the **eleven o'clock** report |

That third row is the exact phrase you spoke at t_sim 258 on 2026-10-05 and that fell through
unrecognised. Note it resolves to the *clock* report rather than the all-contacts one — that is
correct and deliberately more specific, the same way *"report eleven o'clock"* already behaved.

**Desk check you can run before you fly, on the Mac, no DCS needed.** Run this from the repo root
of your own checkout:

```sh
cd audio-adapter && PYTHONPATH=src .venv/bin/python -c "
from command_matcher import match_transcript
for t in ('describe', 'describe contacts', \"describe eleven o'clock\", 'describe the mission to me'):
    print(f'{t!r:28} -> {match_transcript(t).token}')
"
```

Executed against this branch's code, real output:

```
'describe'                   -> report_all
'describe contacts'          -> report_all
"describe eleven o'clock"    -> report_clock_11
'describe the mission to me' -> None
```

(The one substitution between what is printed above and what was run: the interpreter was resolved
by absolute path, because the verification ran in a worktree that has no `.venv` of its own. The
code under it was this branch's.)

That last row is the point of the fourth case — an ordinary sentence containing the word still has
to **not** fire.

## 2. `watch` / `follow` now tags the whole group

**Two ways in, and the F10 one is the more reliable in-flight test** (no speech recognition in the
loop):

- **F10 → Petrovich → Watch → Nearest** (menu labels read off the shipped hook script)
- or say *"Watch nearest."*, *"Follow group."*, *"Follow truck."*, *"Follow armor three o'clock."*

**What to listen for.** When the contact he lands on belongs to a real multi-member group, the
readback changes shape entirely:

| situation | what he says |
|---|---|
| two-member group | *"Watching two."* |
| three | *"Watching three."* |
| four | *"Watching four."* |
| more than twelve | *"Watching many."* |
| single, ungrouped contact | the old wording, e.g. *"Watching T-72, 12 o'clock, 0.5 kilometres…"* |

Those strings are the renderer's real output, run directly.

**The count is the number he actually marked, not the group's nominal size.** This is the fix the
security review asked for: previously the line would have spoken the intended count without checking
it. If the group has lost members since its last reconcile, fewer get marked and he says the smaller
number — and if only one is left to mark, he falls back to the single-contact wording rather than
claiming four. **So a group of four that reads back *"Watching three."* is correct behaviour, not a
miscount.**

**The tag is a one-time snapshot, by your own direction** (*"Tag once, static."*). A unit that joins
that group *after* you gave the command is **not** watched. One that leaves stays watched. If a late
arrival goes unreported, that is the design, not a defect.

## 3. `scan ahead` sweeps 11 → 12 → 1

- **F10 → Petrovich → Scan → Ahead**, or say *"Scan ahead."* / *"Look ahead."*

Previously `ahead` was a fixed stare at 12. It now steps **one hour at a time** — 11, 12, 1, 11, … —
which is your own constraint: *"still one clock hour at a time. A sweeping scan like any other scan,
repeating loop 11-12-1 o'clock."*

The numbers, read off the code:

- legs `(11, 12, 1)`, dwell **2.0 s** per leg, so **each hour is revisited every 6 s**;
- the cone itself is **unchanged** at ±15°. This is not a widened cone, and the DCS LOS query cone
  is untouched.

**What should be better:** something drifting into the edges of the forward arc now gets looked at
instead of being missed beside a fixed 12 o'clock stare.

**What is the honest cost, and worth watching for:** 12 o'clock is now dwelled on a third as much,
so a contact dead ahead may be called a beat later than it used to be. If that feels wrong in the
air, say so — the dwell/revisit interval is an open question, not a settled number.

---

## The known limitation — `BL-B41`. Read this before scoring item 2.

**This is the one thing on this branch that could read as a bug, and it is a real, filed, known
gap.** It is bounded and it is narrower than either failure it sits between, but it is live.

The callout keeper for a watched group is elected **per contact**, while what the suppression
removes is **per event**. So: when every member of a watched group is eligible, but the elected
keeper happens to have **no event of that kind on that tick**, the other members' events of that
kind have already been consumed and **that kind goes unreported for the whole group**.

Concretely: **if a watched convoy starts moving and you hear nothing about movement, that is
`BL-B41` — not a new defect.** Say so in the debrief and it goes on the existing item rather than
starting a fresh hunt.

**The refinement that matters for scoring it: the observable is not silence.** In the reproduction,
the group's own disclosure line still fired for an unrelated reason. So *"the group said something"*
is **not** evidence that the movement report survived. What is lost is that kind's content, not
every utterance about the group.

What is largely self-protecting, so you are unlikely to lose it: range crossings correct themselves
a poll or two later when the keeper crosses the same kilometre mark, and where weapon envelopes are
known the widest-envelope member — the most dangerous one — is always the keeper, so engagement
calls are mostly safe. The genuinely exposed case is a **partial motion transition inside a
co-located cluster**.

The fix is a per-event election, and it is deliberately **not** on this branch: it is the same
redesign the merged observability gate needs for its own matching silence mode, and doing them apart
would mean designing it twice. Filed together on `BL-B41`.

## One performance item to listen for (MONITOR, no change made)

A commanded `scan ahead` now changes the gaze direction on ~66% of polls instead of ~1%, because the
direction cycles instead of sitting still. Per-poll CPU is unchanged and the push itself is sub-
millisecond locally, ~5-10 ms over the LAN. But the aircraft-layer HTTP client's timeout is 2.0 s
with no connection reuse, so **that 2 s tail is now reachable ~66× more often while a commanded
`scan ahead` is running**.

If you get a periodic ~2 s stall in reporting, specifically *during* a commanded `scan ahead`, that
is this — the network tail, not the sweep itself. Worth one line in the debrief if you see it; it
strengthens an already-owned item to shorten those timeouts.

For reference, free scan already sweeps ±105° and already pushes on ~50% of polls, and the
2026-10-05 timing measurements were taken under free scan — so this moves `scan ahead` toward a
baseline that was already measured, rather than into new territory.

---

## What will sound different from last sortie but is **not** this branch

Two other features merged overnight. Do not score them here, and do not re-read them from this card
— each has its own:

- **No unprompted callout names clock hours 5, 6 or 7 any more** —
  `docs/acceptance/2026-10-06-callout-observability-sortie.md`
- **The sortie logs are now per-flight stamped files under `body-layer/logs/dcs-*-<stamp>.jsonl`** —
  `docs/acceptance/2026-10-06-bl11-tick-cost-sortie.md`

Both are on `main`. Neither is on `feature/sortie-refinements` (see "Which branch to fly").

---

## Pass criteria

This passes if:

1. *"Describe."*, *"Describe contacts."* and *"Describe eleven o'clock."* all do what the `report`
   equivalents do.
2. A `watch nearest` / `follow` that lands on a real group reads back a **count** — and the count
   matches the number of things that subsequently behave as watched, with a smaller count or the
   single-contact wording accepted as correct rather than as a miscount.
3. `scan ahead` visibly sweeps rather than stares, and nothing dead ahead is lost badly enough to be
   worse than the old fixed stare.
4. Nothing regressed in contact reporting generally.

A `BL-B41` observation (a watched group losing one kind of report) does **not** fail this card — log
it against `BL-B41`.

## The acceptance boundary — what no fixture here could have caught

Everything above was verified on fixtures, bench probes and the real renderers. What that
structurally cannot reach:

- **Whether `describe` survives this speaker's accent through Whisper.** The phrase table and the
  matcher are proved; the recogniser is not. These two phrasings were added on 2026-10-05, so the
  recorded corpus predates them — they are unbenched, and their recognition accuracy on your voice
  is unmeasured. A phrase that matches perfectly from text can still never arrive.
- **Whether real in-flight groups are the size this was reasoned about.** The watched-group cost and
  the readback's usefulness both scale with group size, and the real distribution is unmeasured — 8
  was a stated assumption, not an observation.
- **Whether the 6 s revisit interval on `ahead` is right.** It is arithmetic from two constants, not
  a judgement about what a gunner should do. Only the cockpit says whether it feels like scanning or
  like dithering.
- **Whether the 2 s HTTP tail actually bites over the LAN.** Measured over loopback only. The figure
  that matters is p99 on the real network.
- **`BL-B41`'s real frequency.** Reproduced in a constructed state; how often a co-located watched
  cluster has a quiet keeper in flight is unknown.

The 2026-09-16 precedent is why this section exists: the F10 vocabulary passed DoD on fixtures and
the next sortie found two defects no fixture could see — `Scan` driving the wrong subsystem
correctly, and a raw task id spoken aloud, which is only a defect when a human *hears* it.
