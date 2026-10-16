# BL-B71 acceptance sortie: the least-capable-optic guidance ladder

**Published card** (in-cockpit-readable, checkboxes persist): https://claude.ai/artifact/AM35VzYb3Xu1KBQjW5SeQt

**Branch to check out, in the repo root: `feature/bl-b71-optic-ladder`.** This has not merged yet
— `git checkout feature/bl-b71-optic-ladder`. The root is yours to park wherever you like; this is
the only channel telling you what to check out.

**DoD passed on fixtures and mutation testing** (`plans/attack-run-sortie-fixes/dod-check-bl-b71.md`).
This card is the first time any of it is exercised live.

## What this sortie is for

During a guided attack run, Petrovich should use the *least* capable optic that can still resolve
the target — naked eye first, then binoculars, then (only with "Observ on" already commanded) the
9K113 sight — escalating as range opens and stepping back down one rung at a time as it closes.
This sortie checks whether that cadence *feels* right, not just whether the code is correct — a
fixture cannot tell you whether an escalation feels responsive or a de-escalation feels jumpy.

**The common case this sortie will actually exercise is naked-eye <-> binoculars.** The sight rung
needs OBSERV already commanded on; without it, the ceiling is binoculars and that is expected, not
a missing feature.

## Setup

Same launch command as the last attack-run sortie, run from `body-layer/`:

```sh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<aircraft-layer-host>:7791 \
  --theatre <TheatreName> --world-model-db <path-to-region.sqlite> \
  --crew-text --speech-audio --audio-adapter-url http://<audio-adapter-host>:<port> \
  --speech-input --speech-log <path>.jsonl
```

**Verified**: `--help` run against this worktree's own `logger.py` confirms every flag above exists
and is spelled this way. **Not verified**: whether this exact combination launches cleanly against
your live aircraft-layer/audio-adapter hosts and a real DCS session — that needs your machines.

**Commands below were run through the real command matcher on this branch** (`audio-adapter`'s
`command_matcher.match_transcript`), not guessed — paste of the actual run:

| said (no wake word — a "Petrovich, ..." prefix routes to free speech instead) | token |
|---|---|
| `target, unit, twelve o'clock.` | `engage` |
| `follow unit, twelve o'clock.` | `follow` |
| `engage` | `engage` |
| `observ on` | `observ_on` |
| `observ off` | `observ_off` |
| `disengage` | `disengage` |
| `drop target` | `drop_target` |

## Test cases

1. **Naked-eye to binoculars, closing then opening.** Select a target at a range where the naked
   eye alone can't resolve it yet (well beyond its presence threshold but within binoculars'),
   `follow` then `engage`. *Expect*: binoculars raised once (costs the ~1 s hands-busy interval —
   you should notice one short gap, not a pause before every callout), guidance continues normally
   while closing. As range closes past the naked eye's own threshold with margin, binoculars
   should be lowered back to naked eye within about 10 s (not instantly on crossing — there's a
   deliberate hysteresis band and a minimum re-grant interval). *Record*: does the switch feel
   timed right, or does it feel like it lags/thrashes?
2. **A fly-past (range reversing).** Run test 1 but fly past the target rather than closing all the
   way, so range starts opening again partway through. *Expect*: no rapid optic thrashing — the run
   is built to not re-evaluate while the target is behind the cockpit mask, and to hold a grant for
   at least ~10 s once made. *Record*: any audible "flicker" between optics on the pass?
3. **The hard gate — OBSERV off.** While the run holds binoculars, do *not* say "Observ on" at any
   point. *Expect*: the sight rung is never reached, no matter how far the target opens — ceiling
   stays at binoculars. *Record*: confirm you never hear or see sight-rung behaviour without having
   said "Observ on" yourself.
4. **The full ladder, with OBSERV already on.** Say `observ on` *before* `engage`, then run a target
   far enough out to need the sight. *Expect*: the ladder can now escalate all the way to the 9K113
   sight rungs as range opens, and step back down through binoculars to naked eye as it closes.
   *Record*: does reaching for the sight mid-run feel natural, or does it feel like Petrovich is
   reaching for an instrument you didn't expect?
5. **A live-tracked target at binocular range doesn't get "last I saw…".** With binoculars raised
   and the target clearly resolvable through them (not through the naked eye), confirm Petrovich
   speaks the ordinary alignment line ("Lined up...", "Come left...", etc.) rather than a
   remembered-sighting "last I saw..." callout. *Expect*: no "last I saw" phrasing while the target
   is actively visible through whichever optic is currently raised. *Record*: if you hear "last I
   saw" while you can clearly see the target yourself through binoculars, that is the specific
   defect two review rounds on this branch were built to close — say so immediately, it's the single
   most important thing this card is checking.
6. **End the run.** `disengage` and `drop target`, each from a fresh run with a grant standing.
   *Expect*: guidance and any standing optic grant stop within a second or two of the command.
   *Record*: does anything feel like it's still reaching for an optic right after you ended the run?

## What is known and accepted, not a defect to report

- **A tuning footgun, not reachable at the shipped defaults**: if `GUIDANCE_OPTIC_MIN_INTERVAL_S`
  and `HANDS_BUSY_DURATION_S` were both retuned to their extremes, a grant could recharge the
  hands-busy window before the previous charge finishes (Petrovich going quiet mid-run). Not
  reachable with the shipped defaults — only relevant if you've hand-edited `tuning.toml`.
- **A one-extra-poll lag on ending a run.** `disengage`/`drop target` can leave the guidance
  request looking at the just-dropped target for about one extra poll (well under a second) before
  clearing. Bounded and harmless; if test 6 feels instantaneous, that's expected — this is smaller
  than you'd notice.

## What a clean flight cannot tell you

Fixtures and mutation tests (2090 passing, three independently-rerun counterfactuals) confirmed
the code does what it says against the inputs it was given — including the hard gate holding under
a hand-built diverged state. They cannot tell you whether the ladder's *cadence* reads right at
your own closing rates, or whether reaching for the sight mid-run (test 4) feels like something
Petrovich should be doing on his own initiative versus something that should need a more explicit
ask. That is what this sortie is for.

## Bring back

- Did the naked-eye/binocular switch feel timed right, too early, or too late?
- Did test 5 ever produce "last I saw" while the target was clearly visible? (This is the one
  finding that would matter most.)
- If you tested the full ladder (test 4), did reaching for the sight mid-run feel natural?
- Anything that surprised you is worth more than anything on this list.

**This milestone stays `#needs-flight` until this sortie (or one like it) clears it** — record
which flight did, in `body-layer/ROADMAP/BL-B71.md`, when it happens.
