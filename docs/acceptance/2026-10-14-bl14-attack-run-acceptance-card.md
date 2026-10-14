# BL-14 acceptance sortie: the attack run (Stages 5-7 together)

**Published card** (in-cockpit-readable, checkboxes persist): https://claude.ai/artifact/MyDhxSLYhD8BJVcu2UFUih

**Branch to check out, in the repo root: `main`, after the merge.** If testing before the merge
lands: `git checkout feature/bl14-attack-run`. The root is yours to park wherever you like; this
is the only channel telling you what to check out.

**DoD passed on fixtures and mutation/reproduction testing** (`plans/attack-run/dod-check.md`).
This card is the first time any of it is exercised live.

## What this sortie is for

Flying `engage` once will not do it. Losing line of sight during the readback delay was found,
mid-implementation, to be a case you hit on the very first run — so this card deliberately covers
tier 1 (clear line of sight), tier 2 (obstructed), and the projection for a moving target together,
not tier 1 alone.

## Setup

**Everything below assumes the same launch command you already use for a normal sortie, with one
addition** — `--speech-log` is new since the last card, recommended so a transcript exists if
anything sounds wrong and needs debugging afterward. Run from `body-layer/`:

```sh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<aircraft-layer-host>:7791 \
  --theatre <TheatreName> --world-model-db <path-to-region.sqlite> \
  --crew-text --speech-audio --audio-adapter-url http://<audio-adapter-host>:<port> \
  --speech-input --speech-log <path>.jsonl
```

**Verified**: `--help` run against this worktree's own `logger.py` confirms every flag above
exists and is spelled this way (`--crew-text`, `--speech-audio`, `--audio-adapter-url`,
`--speech-input`, `--speech-log` all present in the current CLI). **Not verified**: whether this
exact combination launches cleanly against your live aircraft-layer/audio-adapter hosts and a
real DCS session — that needs your machines and is the thing this sortie is for. If the launch
itself fails, that is useful information, not a distraction from the test.

## The three constants this sortie sets

Still unset, by design — a fixture cannot tune a value the spec says must come from flying:

| constant | current value | what "too tight" sounds like | what "too loose" sounds like |
|---|---|---|---|
| lined-up azimuth band | 5.0° | he keeps correcting on a run you'd call lined up | he says "lined up" while visibly still off-nose |
| elevation gate | 10.0° | he calls "higher"/"lower" on a target you're clearly on | he stays silent on two units stacked at different elevations near the same bearing — the gate exists to *discriminate*, not to fine-aim |
| change threshold | 3.0° | chatter on a steady, settled run | silence through a slow drift that should have triggered a correction |

## What to listen for — four things already known, so they read as expected, not as defects

1. **`step` against a large or loosely-grouped formation may feel sluggish.** This is `BL-B49`'s
   already-filed, uncached terrain-query cost through `describe_contact`'s enrichment pipeline —
   `step` is a new caller of an existing cost, not a new defect. If it is audibly slow, that
   confirms the finding; it is not a surprise to report as new.
2. **`engage`'s own readback occupies the channel before the first guidance callout.** This is
   correct behaviour by your own direction (one voice, one utterance at a time) — not a stall.
3. **A bare `"engage"` re-confirm on the already-selected target will re-speak the current
   alignment line, even if nothing about the target or geometry changed.** Pre-existing, outside
   this feature's fixes, and very likely intentional — but worth knowing before you hear it, so a
   repeated callout right after saying "engage" again reads as expected, not as a glitch.
4. **The `", obstructed"` qualifier should appear and disappear as line of sight breaks and
   returns** — including on "lined up" itself (`"lined up, obstructed"` then a bare `"lined up"`
   again on regaining sight). This is the observable that tells you which channel you're hearing;
   it should never go silent when LOS breaks mid-run.

## Test cases

1. **Clean tier-1 run.** Select a target with clear LOS the whole run, `engage`, fly a normal
   roll-in. *Expect*: o'clock words outside ±15° of the nose, "come left/right"/"a bit left/right"
   inside it, "higher"/"a little lower" on the vertical axis, one "lined up" then silence once
   settled. *Record*: does silence actually feel like confirmation, or like Petrovich went quiet
   on you?
2. **Obstructed mid-run.** Select a target, `engage`, then manoeuvre so LOS breaks (terrain,
   banking the target behind the airframe) partway through. *Expect*: guidance continues against
   the remembered position with `", obstructed"` appended to whatever tier-1 would otherwise have
   said — never silence. *Record*: does the obstructed register feel like "I can tell this is
   stale," or does it sound identical to a live look?
3. **Regain sight while lined up.** From test 2, regain LOS while still aligned. *Expect*: a bare
   "lined up" once (no qualifier), then silence. *Record*: is the transition audible/clear?
4. **Moving target, LOS lost.** Select a moving target, `engage`, lose sight. *Expect*: guidance
   projects the target's position rather than freezing it at the last known spot — should not feel
   like guiding toward where the target *was* if it's clearly moved on. *Record*: does the
   projected position feel plausible, or does it visibly lag the target's real motion?
5. **`step` a group.** Select a group member, `step left`/`step right` a few times while circling
   it. *Expect*: the next unit left/right of your *current* line of sight, re-evaluated each press
   — not a fixed list order. *Record*: does it ever feel like it picked the wrong unit, or
   repeated one?
6. **Re-select mid-run.** `engage` target A, then `select target` a different unit B without
   `disengage` first. *Expect*: guidance re-points cleanly to B, no stale correction toward A, no
   double-voiced confusion. *Record*: any hint of guidance still referencing the old target?
7. **End the run.** `disengage`, `drop target`, and the generic cancel path, each from a fresh
   run. *Expect*: guidance stops cleanly in every case, no lingering "fixed look" on the old
   target for subsequent scans. *Record*: does anything feel like it's still watching the old
   target after ending the run?

## Edge cases to probe

- **Crosswind.** Does the lined-up band (5.0°, non-zero on purpose) feel right when crabbed into a
  crosswind, or does Petrovich call you misaligned on a correctly-flown run?
- **Close-in run with little time.** Start a run from close range with terrain to navigate. Is the
  guidance useful in the few seconds available, or does it still feel like it's narrating too
  much/too little?
- **Two units near the same bearing, different elevation.** Does "higher"/"lower" actually help
  you pick the right one, or does the gate feel too wide/narrow to discriminate?

## What a clean flight cannot tell you

Fixtures and mutation tests confirmed the code does what it says against the inputs it was given.
They cannot tell you whether the vocabulary works spoken aloud, at synthesis cadence, under
workload, in the time a real run actually allows — that is what this sortie is for. Nor can they
tell you whether `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` (guidance treated as exact while looking at
the target) feels too twitchy, too forgiving, or correct.

## Bring back

- How did "lined up" actually feel — confident, or ambiguous?
- Did the obstructed qualifier ever feel confusing rather than clarifying?
- Were the three constants (5°/10°/3°) too tight, too loose, or about right?
- Anything that surprised you is worth more than anything on this list.

**This milestone stays `#needs-flight` until this sortie (or one like it) clears it** — record
which flight did, in `body-layer/ROADMAP/BL-14.md`, when it happens.
