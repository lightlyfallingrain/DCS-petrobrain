# BL-8 acceptance sortie: mission memory, Sortie A

**Published card** (in-cockpit-readable, checkboxes persist): https://claude.ai/artifact/6vHvDfB5UrafTw4j1WNHzz

**Branch to check out, in the repo root: `feature/bl8-mission-memory`.** This has not merged yet —
`git checkout feature/bl8-mission-memory`. The root is yours to park wherever you like; this is the
only channel telling you what to check out.

**DoD-passed on fixtures and mutation-tested test suites, conditional on this sortie**
(`plans/bl8-mission-memory/dod-check.md`). This card is the first time any of it runs against a
live DCS session.

## What this sortie is for

BL-8 is Petrovich's post-flight notepad: an append-only JSONL file written from settled belief
after every poll — groups he identified, air defence he spotted, pilot-ordered marks, and moments
he was fired on. **It is write-only in flight.** Nothing in this batch reads the file back during
a sortie, and nothing is spoken from memory yet — so there is nothing to listen for in the air
beyond setting a mark by voice. The test is a **post-flight file read**: does the notepad, read
afterwards, look like something worth having kept?

Two subprojects changed for this batch: `body-layer` (the memory store itself) and
`audio-adapter` (the voice phrases that let you set a mark by speaking — added in a second pass
after the first DoD check found the mark command had no voice path at all). **Both need to be
restarted on whichever machine runs them** so they pick up this branch's code — per
`aircraft-layer/WORKFLOW.md`'s cross-machine pattern, DCS/aircraft-layer itself (Windows box) is
unaffected and does not need restarting for this feature.

## Setup

From `body-layer/`, on the machine that runs it:

```sh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<aircraft-layer-host>:7791 \
  --theatre <TheatreName> --world-model-db <path-to-region.sqlite> \
  --crew-text --speech-audio --speech-input --audio-adapter-url http://<audio-adapter-host>:<port> \
  --mission-memory logs/mission-memory.jsonl
```

**Verified**: `--help` run against this worktree's own `logger.py` confirms every flag above
exists and is spelled this way, including `--mission-memory`. **Not verified**: whether this exact
combination launches cleanly against your live aircraft-layer/audio-adapter hosts and a real DCS
session — that needs your machines.

**Where the file actually lands**: `--mission-memory logs/mission-memory.jsonl` does not write to
that exact path. Each run stamps its own start time into the filename (`BL-11` Stage 5's
convention, so two sorties in one evening don't overwrite each other) — the real file is
`logs/mission-memory-<YYYYMMDD-HHMMSS>.jsonl`, created alongside whatever directory you point at.
Use the newest one.

On `audio-adapter`'s machine, make sure it is running with `--whisper-model` so your voice is
actually transcribed (`GET /transcripts/poll` otherwise always drains empty):

```sh
cd audio-adapter
PYTHONPATH=src .venv/bin/python -m audio_adapter --whisper-model <path-to-model>
```

**Verified**: `--help` run against this worktree's own `audio_adapter/__main__.py` confirms
`--whisper-model` exists and is spelled this way.

**The five phrases that now work — run through the real matcher on this branch
(`audio_adapter.command_matcher.match_transcript`), not guessed, paste of the actual probe:**

| said | token |
|---|---|
| `mark here` | `mark_here` |
| `mark this position` | `mark_here` |
| `remember this location` | `mark_here` |
| `mark target` | `mark_target` |
| `remember target` | `mark_target` |

(`mark the target` and `remember the target` also resolve to `mark_target` — the matcher is
tolerant of an inserted "the".)

## What to fly

One flight, covering all four of the things BL-8 records:

1. **Ground units** you can identify at range (`group` entries — written once a contact's
   classification first reaches a nameable confidence, then again only on a material change).
2. **Air defence** — anything with a SAM/AAA classification (`air_defence` entries — written on
   every sighting, no thinning, since each one matters).
3. **A mark set by voice** — pick a moment and say one of the five phrases above, once for
   `mark here` and once for `mark target` if you have a target selected. **Record**: did Petrovich
   acknowledge it, and did it feel natural to say mid-flight?
4. **Something shooting at you** — ground fire or a SAM launch (`fired_on` entries).

## What to read afterwards

Open the newest `logs/mission-memory-*.jsonl` and read it like a kneeboard page, not a debug dump.

- **Entry count**: expect **tens**, not thousands. If it's in the hundreds or more, the admission
  thresholds below are too loose and need tightening before this is useful.
- **A group's strike chain**: if you fired on something you'd already identified, does the file
  read as one sensible history for that target (identified → fired on → maybe struck again), or as
  disconnected rows that don't obviously belong together?
- **Anything obviously missing**: a unit you clearly saw and identified that never got an entry.
- **Anything obviously noise**: the same unit re-entered over and over for no real reason (it
  hadn't moved, hadn't changed class, hadn't been re-engaged).

**This sortie's whole purpose is calibrating four numbers that are currently guesses:**
`RESIGHT_MOVE_M` (how far a group has to move before it's re-recorded), `RESIGHT_MIN_INTERVAL_S`
(minimum time between re-records), `GROUP_ENTRY_CONFIDENCE_FLOOR` (how sure Petrovich has to be
before a group is worth naming at all), `FIRED_ON_FOLD_WINDOW_S` (how long a burst of fire counts
as "one" being-fired-on event rather than several). **A re-tune and a re-fly is the expected
outcome of this sortie, not a sign something is broken.**

**Performance watch**: if what you read suggests `RESIGHT_MIN_INTERVAL_S` should come down a lot,
say so — the store's lookup for "when did we last see this" does a reverse scan whose cost was
only measured at the current (longer) interval, and a much shorter one wants re-measuring before
it's set that way permanently (`plans/bl8-mission-memory/performance-review.md`).

**Reference for what good looks like**: this kneeboard mock —
https://claude.ai/artifact/Swg1RDkBbkt4qZihnUrP75 — is the "what good looks like" target for
reading the file back. It is a mock, not something this batch builds or renders; use it only to
judge whether your real file reads the same way.

## Deliberately not in this flight

- **Attack-run entries (Stage 4)** — the schema exists but nothing triggers a write yet; deferred
  until weapon-selector export and a damage signal land elsewhere.
- **The "safe from" callout re-enabling itself (Stage 6)** — a separate speech decision with its
  own acceptance sortie, gated on this one going well first.
- **Anything being read back or spoken from memory in flight** — by design, not an oversight.

## Bring back

- Does the file read like a kneeboard page, or like noise?
- Was the entry count in the tens? If not, roughly how many, and for how long a flight?
- Did a strike chain make sense as one history?
- Did `mark here` / `mark target` feel natural to say mid-flight, and did Petrovich acknowledge it?
- Anything that surprised you is worth more than anything on this list.
