# BL-B64 acceptance sortie: the 9K113 sight (perception only)

**Branch to check out, in the repo root: `feature/9k113-sight`** (or `main` after the merge —
the user merges this, not the orchestrator). `git checkout feature/9k113-sight`.

**DoD passed on fixtures, mutation testing, and direct reproduction** (`plans/9k113-sight/dod-check.md`).
This card is the first time any of it is exercised live.

## What this sortie is for

Whether sight-grade detection/classification ranges feel right, whether the per-optic position
sigma produces reports you trust, and whether the handover between naked eye, binoculars, and
sight reads as a crew member choosing an instrument — not thrashing. This is **perception only**:
nothing in the cockpit moves, there is no warm-up, and OBSERV is a pure body-layer concept with no
cockpit switch behind it yet.

## The one thing you cannot discover any other way: how to turn OBSERV on

**There is no F10 radio-menu item and no spoken command for "Observ on"/"Observ off" yet** — both
are explicitly next-entry (`BL-B66`) work. The only way to trigger it today is a typed line in the
`--crew-text` console's own stdin, on whichever machine is running body-layer:

```
!voice observ_on 1.0 1.0 1 0 observ on
!voice observ_off 1.0 1.0 1 0 observ off
```

**Verified by actually running it**, not read off the code: this returns `Observ on.` / `Observ
off.`, and the sight becomes selectable/stops being selectable immediately. You will need a
terminal window on body-layer's own console within reach while flying — the same machine/session
you already use to watch its text output.

## Setup

Run from `body-layer/`, same launch you already use for a normal sortie:

```sh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<aircraft-layer-host>:7791 \
  --theatre <TheatreName> --world-model-db <path-to-region.sqlite> \
  --crew-text --f10-commands --speech-input --speech-audio \
  --audio-adapter-url http://<audio-adapter-host>:<port>
```

**Verified**: every flag above exists in this worktree's own `logger.py --help` output, run
directly. **Not verified**: whether this exact combination launches cleanly against your live
aircraft-layer/audio-adapter hosts and a real DCS session — that needs your machines and is part
of what this sortie is for.

**Restart body-layer between missions.** A known, deferred defect (stale belief surviving a
mission restart within the same service run) means contacts from a previous mission can persist
and show up as spurious far-away returns in this one. Kill and restart the `logger.py` process
each time you load a new mission during this sortie, so it does not contaminate what you're
judging.

## The constants this sortie sets

Still unset, by design — a fixture cannot tune a value the spec says must come from flying:

| constant | current value | what "too tight" sounds like | what "too loose" sounds like |
|---|---|---|---|
| wide down-range sigma scale | 0.5 | ranges called with more confidence than the view supports | no improvement over naked-eye range precision at all |
| narrow down-range sigma scale | 0.3 | same, for the x10 mode | same, for the x10 mode |
| sight manoeuvre-tolerance | 30°/s | OBSERV survives manoeuvres that should have kicked it off | OBSERV drops out during perfectly flyable manoeuvring |
| sight max dwell | 30 s | he returns to the sight before you'd expect a break | he stays on the sight for an uncomfortably long stretch before glancing away |

Confirm these render correctly before flying: `PYTHONPATH=src:../world-model/src .venv/bin/python
-m logger --print-tuning` — verified just now, all four appear under `belief.optic_policy`/
`perception.estimation` at the values above.

## What to listen for — known, so it reads as expected rather than as a defect

1. **No autonomous wide↔narrow switching within one look.** You will not see Petrovich go wide to
   find something and then flip to narrow to classify it within the same continuous look, even
   though that is how the manual procedure describes using the real instrument. He goes narrow
   while actively looking, wide while idle — the same simplification binoculars already make.
2. **A ~1 second latency after lowering back to idle before the sight can pick a new target.**
   Small, by design, consistent with other scan-boundary latencies already in this module.
3. **No elevation is ever spoken about the sight itself** — there is no instrument reading for it.
   World reference ("on the ridge") still works normally; it just isn't sight-specific.
4. **Both wide and narrow carry a 20 km reach in the direction the sight is pointed, while
   everything else stays bounded at 10 km.** This is deliberate (direction, §7) and not a leak.

## Test cases

1. **Narrow-mode long-range detection.** `!voice observ_on ...`, point roughly at a distant known
   contact (beyond 10 km if you have one), let the sight pick it up in narrow mode. *Expect*:
   detection/classification earlier than the naked eye would manage at that range, with a position
   report that feels usably precise, not loosely scattered. *Record*: does the first report's
   range/bearing line up with what you can independently judge?
2. **Wide-mode surroundings.** With OBSERV on and idle (no committed look), confirm the sight
   behaves like a wider-reach scan rather than a narrow spotlight. *Record*: does switching
   between an active look (narrow) and idle (wide) feel coherent, or does the FOV change feel
   arbitrary?
3. **The long-dwell / glance-away rhythm.** Stay on the sight for an extended period (well past 30
   s). *Expect*: a brief, scheduled glance away to the naked eye, then back to the sight — the
   inverse of the binocular rhythm. *Record*: does the glance-away feel natural, or does it
   interrupt at an awkward moment?
4. **Manoeuvre kicks OBSERV off.** While OBSERV is on and sighted, fly an aggressive manoeuvre.
   *Expect*: OBSERV drops out (gyro-tolerance constant above). *Record*: does the threshold feel
   right for what a 24P crew would actually fly?
5. **Turning OBSERV off mid-look.** While actively looking through the sight at something,
   `!voice observ_off ...`. *Expect*: the sight stops immediately (within one poll), not after a
   lingering dwell. *Record*: any sense that the sight kept running after the command?
6. **Naked eye / binocular handover.** Cycle naked eye → binoculars → OBSERV on (sight) → OBSERV
   off, a few times across the sortie. *Record*: does this feel like a crew member deliberately
   choosing an instrument, or like thrashing between modes?

## Edge cases to probe

- **A contact just past 10 km, off to one side of the sight's pointed direction.** Should **not**
  be detected — the 20 km reach is a narrow cone in the sight's own direction, not a general range
  increase.
- **A contact at the edge of the sight's field of regard** (±60° azimuth). Should either be
  rejected as a look target or clamped to the edge, never pointed at past the mechanical limit —
  this was the one required security fix on this entry, and it is the thing most worth stress-
  testing live.
- **A group of several units at range.** Expect one shared range estimate across the group, not
  independently scattered per-unit positions.

## What a clean flight cannot tell you

Fixtures and mutation tests confirm the code does what it says against the inputs it was given.
They cannot tell you whether the detection ranges and position sigma feel right at the controls,
whether the phase handover reads as natural, or whether the 20 km cone's cost holds up against
your mission's own unit density (the performance measurement is a projection from one recorded
trace, not a live measurement).

## Bring back

- Did the sight's detection ranges and position precision feel earned, or too generous/too stingy?
- Did the long-dwell rhythm (sight-as-baseline, naked eye as the brief interruption) feel right?
- Did the manoeuvre-tolerance threshold (30°/s) feel right for real flying?
- Was the `!voice observ_on`/`observ_off` typed-command workaround usable at all, or did it get in
  the way enough that it's worth fast-tracking a real input surface?
- Anything that surprised you is worth more than anything on this list.

**This milestone stays `#needs-flight` until this sortie (or one like it) clears it** — record
which flight did, in `body-layer/ROADMAP/BL-B64.md`, when it happens.
