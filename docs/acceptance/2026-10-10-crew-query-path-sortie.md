# Sortie card — BL-13, the crew query path (`report` / `describe`)

**Published as an artifact for reading in the cockpit:**
https://claude.ai/artifact/9HbtGBzw9hLXNCTqLeVoRp — this file stays the source of truth and the
card is generated from it.

**Branch: `feature/bl13-crew-query-path`** (tip `3b1d1df`).

```sh
cd /Users/sg/Code/DCS-petrobrain && git checkout feature/bl13-crew-query-path
```

The repo root is your checkout and nothing else moves it, so the branch name above is the only
thing that leads you to this work.

**What you are judging:** whether a *summary* answer beats the enumeration it replaced — and
whether 10 seconds of Petrovich talking is too long in a hover.

**What nobody here could check:** nothing on this branch has ever talked to a live DCS session. No
agent in this project can reach one. Everything below marked "ground check" was run on the Mac
against this branch's own code; everything marked **UNVERIFIED** needs the Windows box, DCS, or
your ears, and is written from the code rather than from a run.

---

## Before you fly

Launch as usual — **UNVERIFIED**, these are your own scripts and none of them can run here (they
need `run-scripts/petrobrain.env`, the Windows collector, and a microphone):

```sh
cd run-scripts
./run-audio-adapter.sh      # Mac: TTS out + Whisper in
./run-brain.sh              # Mac: Ollama-backed brain
./run-crew-text.sh          # Mac: the crew itself
./run-audio-capture.sh      # Windows: push-to-talk capture
```

Nothing new is required for BL-13 — no new flag, no new process. The slotted command rides the
speech path that is already there.

### Two ground checks you can run on the Mac without DCS, if you want them

Both were run on this branch; the output below is the real output.

```
$ cd audio-adapter && PYTHONPATH=src .venv/bin/python -c "
from command_matcher import match_transcript as m
for t in ['report left', 'report right', \"describe armor two o'clock near\"]:
    r = m(t); print(t, '->', r.token, r.slots)
"
report left -> report {'relative': 'left'}
report right -> report {'relative': 'right'}
describe armor two o'clock near -> report {'descriptor': 'armor', 'clock': 2, 'band': 'near'}
```

```
$ cd body-layer && PYTHONPATH=src:../world-model/src .venv/bin/python -c "
from belief.decay import OBSERVED_WINDOW_S
from belief.speech import render_report_summary
def f(c, clock=2, rng=1000.0, lo=1, hi=1, ago=0.0, i='x'):
    return {'id': i, 'classification': {'level': 'class', 'value': c},
            'last_seen_ago_s': ago, 'cardinality': {'lo': lo, 'hi': hi},
            'relative_now': {'clock_position': clock, 'range_m': rng, 'bearing_deg': 60.0}}
scene = [f('OP_INFANTRY', 1, 900, 3, 4, 0.0, 'a'), f('OP_LRSAM', 3, 1800, 1, 1, 110.0, 'b')]
print(render_report_summary(scene, band_label='inside 2 kilometres', stale_window_s=OBSERVED_WINDOW_S).text)
"
About four units, 1 o'clock through 3 o'clock, inside 2 kilometres, and one long range SAM. The long range SAM is a couple minutes old.
```

---

## How to say it — two rules, both measured

**1. Do not prefix a command with the wake word.** Measured on this branch:

| transmission | result |
|---|---|
| `report left` | `report`, `{'relative': 'left'}` — correct |
| `Petrovich, report left` | `report`, **`slots=None`** — the direction is lost, you get the whole scene |

A transmission beginning with the wake word routes to the brain as free speech; only an unprefixed
one reaches the command matcher. Say **"report left"**, not "Petrovich, report left".

**2. The *what* word must be one of exactly seven, singular.** `armor` · `truck` · `infantry` ·
`sam` · `aaa` · `ship` · `group`. Measured, same branch:

| you say | what he hears |
|---|---|
| `report truck near` | `{'descriptor': 'truck', 'band': 'near'}` — correct |
| `report trucks near` | `{'band': 'near'}` — **the *what* is silently dropped** |
| `report tanks near` | `{'band': 'near'}` — dropped |
| `report armour north` | `{'sector': 'north'}` — dropped (British spelling) |
| `report air defence near` | `{'band': 'near'}` — dropped |

This degrades honestly — you get a *wider* answer, never a wrong one — but it is worth knowing
before you wonder why "report trucks near" told you about everything. Your own grammar request used
"trucks" and "air defence", so this gap is in your vocabulary and not in his; it is a candidate
backlog item rather than something built today.

---

## Test cases

### 1. The D13 answer shape — the one that matters

You chose summary over enumeration from two mocks on the ground. This is the first time you hear it
from the real system.

| say | expect |
|---|---|
| `report` | the whole scene as one summary utterance, not a list of groups |
| `report two o'clock` | count, dominant class, bearing span, distance band — a *pointer* |
| `describe two o'clock near` | the same, narrowed to inside 2 km |

**Shape, rendered from the real renderer** (ground check, Mac, this branch):

```
About eight units, mostly infantry, 1 o'clock through 2 o'clock, inside 2 kilometres. Still checking the truck group.   [18 words]
One truck, at 2 o'clock, inside 2 kilometres.                                                                          [8 words]
Eight units, mostly infantry, 1 o'clock through 2 o'clock, inside 2 kilometres, and one short range SAM.                [17 words]
Last I saw, about four units, mostly armor, 2 o'clock through 3 o'clock, inside 2 kilometres.                           [16 words]
```

**Judge:** does it aim your eyes? Is a count plus a bearing span plus a band enough to know where
and what to look for, or do you find yourself asking a second question every time?

### 2. Plan Q3 — is 25 words (~10 s) too long in a hover? **Your decision, and it is not a dial**

`REPORT_SUMMARY_MAX_WORDS = 25` was calibrated from the length of the mock you picked, read on the
ground. If 10 s is too much mid-hover the obvious move is to halve it to ~13 — and that is **not a
tuning change on this code**:

- the pointer alone — count, direction, band — is already **11–13 words**;
- the freshness marker is a further **7–8**;
- so at 13 the constant would stop being a budget on the summary and become a budget on the
  droppable tail only. Every stale-air-defence answer would overrun by about half.

That forces a choice only you can make: a shorter marker form, or redocumenting the constant, or
deciding which of pointer-versus-honesty yields in a hover. **Flagged here rather than left for you
to discover by lowering the number and finding it did nothing.**

**Judge:** time one answer in a hover. Too long / about right / could be longer.

### 3. The freshness marker over the intercom

You chose *"only hedge what matters"* — a stale **air defence** contact is marked, a stale truck
speaks unqualified, and you accepted that some stale belief is therefore spoken in present tense.

Rendered from the real renderer (ground check):

```
About four units, 1 o'clock through 3 o'clock, inside 2 kilometres, and one long range SAM. The long range SAM is a couple minutes old.   [25 words]
About nine units, 1 o'clock through 4 o'clock, inside 2 kilometres, and one short range SAM, one long range SAM. The air defence is a couple minutes old.   [28 words]
```

The wording ladder is *"under a minute old"* → *"about a minute old"* → *"a couple minutes old"*,
off a rounded minute count, so no rung states an age it cannot support.

**Judge:** does it read naturally as a sentence a crewman would say? Does it fire at the right
times, or does it hedge things you would rather he just told you?

### 4. `report left` / `report right` — these have never worked

Before this branch, measured on the base commit:

```
report left   -> token='report_bearing_e'     # "report east" — a silent wrong direction, at 0.75
report right  -> token=None                   # nothing at all
```

That is `BL-B28`, and it was worse than the backlog item said: not a missing right-hand form but a
*wrong-direction match*. If you heard a "report east, confirm?" prompt on an earlier sortie after
saying "report left", that is what it was.

| say | expect |
|---|---|
| `report left` | contacts in the left wedge only — never anything about east |
| `report right` | contacts in the right wedge |
| `report ahead` | the forward wedge |

`left`/`right` use the same wedge table `scan left` uses, so the two commands agree about what
"left" means by construction.

### 5. `describe` with slots

The `describe` synonym shipped earlier but only covered the bare form: every slotted phrase said
with `describe` failed where the identical phrase said with `report` worked. Now both verbs are
interchangeable everywhere.

| say | expect |
|---|---|
| `describe left` | same as `report left` |
| `describe two o'clock near` | same as `report two o'clock near` |
| `describe group far` | same as `report group far` |

### 6. Your own example, verbatim

Your grammar request's own example, measured on this branch:

```
report 2 o'clock close     -> {'clock': 2, 'band': 'near'}
describe 2 o'clock close   -> {'clock': 2, 'band': 'near'}
```

Both work. Say it exactly as you originally wrote it and see whether the answer is what you meant.

---

## Edge cases worth probing

- **Two directions in one breath** — `report left north`. Expect a *"say again"*, not a guess: two
  *where* words is treated as a recognition failure rather than a conjunction. (Measured:
  `token=None`, verb anchored.)
- **A direction with nothing in it.** A *rear* direction gets "no view" honestly. A **forward**
  direction with nothing believed still gets *"clear"* — **and that can be a false claim about a
  direction he has never looked at.** Stage 4 (a per-hour gaze ledger) is what closes it and is
  deliberately unbuilt. If you hear "clear" about somewhere he plainly never looked, that is the
  known gap, not a new defect.
- **Rear clock hours.** `report six o'clock` resolves to **eight o'clock** — pre-existing on both
  the base and this tip, the same silent-wrong-direction shape as the `left`/`east` bug, for the
  hours the forward clock slot does not cover (5, 6, 7). Worth confirming you hear it, because it
  decides whether it is worth filing.
- **A landmark.** `report south of Gemerek` resolves to `sector: south` and answers about the
  south — not the village. Landmark `where` is Stage 5, gated on free speech. (The roadmap entry
  says this degrades to a *bare* report; measured, it actually keeps `south`, which is the better
  of the two degradations.)
- **Band words you might phrase loosely:** `near`/`close`/`close in`, `medium`/`medium distance`/
  `mid`, `far`/`distant`. All measured working. `close` is phonetically near `clock`, which the
  clock slot also consumes — the one collision worth listening for.

---

## One open question for you

The freshness marker currently fires for **air defence only**. The Reviewer and the implementer
both independently raised the same second candidate: a contact believed to be **moving**.

Position is the fastest-decaying attribute in the belief model — a 30-second half-life, against 60 s
for motion, 180 s for area and 600 s for identity. So a two-minute-old "moving" belief is four
half-lives old, and its clock position is the single thing most likely to be wrong — spoken in
present tense, with no marker.

**Deliberately not built**, pending your call: should a stale *moving* contact also be hedged?

---

## Pass criteria

The feature passes if:

- a slotted `report`/`describe` is recognised reliably at the forms above, under either verb;
- `report left` and `report right` work, and never say anything about east;
- the summary answer aims your eyes well enough that you do not immediately need a second question;
- the freshness marker reads as something a crewman would say;
- nothing that worked before got worse — specifically the unprompted callouts, `scan`, `watch` and
  `follow`, which share the same speech path and the same poll loop.

**And one thing to watch that is not a pass criterion**: a `report` query runs inside the poll body
and enriches *every* contact before any filter applies — measured at ~352 ms at 52 contacts even
with a warm cache, ~3.6 s cold. If asking four questions in a minute makes perception or callouts
feel like they stutter, that is `BL-B49` and it is already filed; say so and it gets priority rather
than a diagnosis from scratch.
