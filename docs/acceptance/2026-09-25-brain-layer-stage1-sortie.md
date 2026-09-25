# Brain layer, Stage 1 sortie

> **SUPERSEDED, 2026-09-25**, by `2026-09-25-crew-behaviour-sortie.md` — fly that instead. Not stale, merely absorbed: it recommended its own short flight, and the user chose to fold the day's cards into one. Its content survives as that card's block 4, caveat intact — with `StubDecider` behind the wire, only the mechanical parts of the exchange are judgeable. Kept for the record.

The first time a free-text utterance that used to produce silence produces a real spoken response,
end to end, over HTTP — with no model involved at all. `StubDecider` (a configurable-delay stand-in)
proves every hard part of the wire — non-blocking handoff, stand-by, staleness revalidation,
newest-wins — without any model risk.

**Merged 2026-09-25 (`fc4e4af`).** DoD — format, lint, type check, tests, Reviewer, Performance,
Security — complete and clean. Everything is on `main`, alongside the four other outstanding
cards.

```sh
git checkout main && git pull
```

body-layer 1220 tests / 4 xfailed, brain-layer 20 tests — verified this session against an isolated
copy of the branch's own source (not read off a docstring).

## Setup — one new process, and it can be skipped

This is the first slice that adds a whole new process to start. `brain-layer/` is a plain HTTP
peer of body-layer — nothing pins it to any particular machine except that body-layer needs to be
able to reach it. In this user's current setup, body-layer, brain-layer and the audio adapter all
run on the same machine (the Mac); only `aircraft-layer` is pinned, because it needs the DCS
installation. If that setup changes, `run-brain.sh` already omits `--host`, so `--host 0.0.0.0` is
one flag away — nothing here assumes same-machine.

Start it before the logger, same terminal habits as the other run scripts:

```sh
./run-scripts/run-brain.sh
```

That runs `python -m brain_layer --stub-delay-s 0` on loopback (port 7796). Leave it running.

Then start the logger as usual, with two new flags:

```sh
./run-scripts/run-crew-text.sh --brain-client http --brain-url http://127.0.0.1:7796
```

**If you forget to start brain-layer, or leave the flags off:** nothing breaks. `--brain-client`
defaults to `debug` (prints escalated payloads to stderr, says nothing) and `NullBrainClient`/an
unreachable `http` target both degrade to silence — a free-text utterance that would have
escalated instead produces no spoken reply, same as every sortie before this one. Worth trying
once on purpose: send an unparseable utterance with brain-layer *not* running and confirm you get
silence, not an error, not a hang.

- Windows: collector, capture with `--ptt dcs`, as before — untouched by this branch.
- Mac: `run-scripts/run-audio-adapter.sh`, then `run-scripts/run-brain.sh`, then
  `run-scripts/run-crew-text.sh --brain-client http --brain-url http://127.0.0.1:7796`.

## Not testable, and why — read this before you fly

**With `StubDecider`, there is no intelligence to evaluate.** Every free-text utterance that
escalates gets the same canned structural answer — `unable, no such command` — regardless of what
you actually said. Do not fly this expecting Petrovich to understand anything new; he doesn't yet.
What this card *can* judge:

- **Does the cockpit keep running normally while the brain "thinks."** The stub can be told to
  delay (it isn't, by default — `--stub-delay-s 0`), but even at zero delay the escalate/poll
  round trip is a real async path. Nothing else — scans, attention, other commands — should ever
  stall waiting on it.
- **Does "stand by" land at a sane moment**, not instantly, not absurdly late, when a reply is
  slow. (The default run has zero stub delay, so this is hard to provoke without editing the run
  command — see block 2.)
- **Does hearing Petrovich answer at all, after previously getting silence, feel right** — the
  qualitative thing no fixture can measure, and the actual point of this slice.

What this card **cannot** judge, and don't try to read more into a "pass" than this: whether any
future *content* of a reply makes sense, whether disambiguation phrasing is good, whether this
generalizes to real model output. None of that exists yet — that's Stage 2.

## 1 — Hearing him answer at all. WORTH MOST

**Do.** With brain-layer running and the flags above, say something Petrovich's fixed grammar
doesn't recognize — a real sentence, not a known command (e.g. "what's that guy doing" pointed at
nothing in particular, or any phrasing outside the known vocabulary).

**Expect.** Instead of silence, you should hear "Unable, no such command" — spoken, not just
printed — a few seconds after you speak, not instantly and not stalling the cockpit in between.

**Record.**
- [ ] Did you hear a spoken reply at all, where before this branch you'd have heard nothing
- [ ] Roughly how it felt — natural pause, or an awkward gap
- [ ] Whether anything else (scans, other commands) felt delayed or stuck while waiting for it

## 2 — Stand-by timing, if you can provoke it

**Do.** Optional, and needs editing the run command: restart brain-layer with
`--stub-delay-s 8` (`./run-scripts/run-brain.sh --stub-delay-s 8`, or edit the flag directly),
then send one unparseable utterance.

**Expect.** Per the plan's own worked scenario, "stand by" should fire once at 2 seconds if no
reply has arrived yet, then the real (stub) reply at 8 seconds. This exercises the actual
mechanism that will matter once a real model replies slowly.

**Record.**
- [ ] Did you hear "stand by" partway through the wait
- [ ] Did the final reply still arrive at roughly the expected time, and did anything in the
      cockpit stall while waiting

## 3 — Confirm graceful degradation (quick, do it once)

**Do.** Stop brain-layer (Ctrl-C the process, or just don't start it) and send an unparseable
utterance with `--brain-client http --brain-url ...` still set.

**Expect.** Silence — no crash, no error spoken, no hang. Same as `NullBrainClient`'s posture.

**Record.**
- [ ] Silence, not a crash or a hang, when brain-layer isn't there to answer

## Where this sits among the outstanding sorties

Four other sorties are already open and unflown on `main`: `docs/acceptance/
2026-09-23-eyes-and-voice-sortie.md` (binocular optic, voice command completeness, precise
position belief), `docs/acceptance/2026-09-24-watch-reporting-sortie.md` (unprompted contact
reports, engagement envelopes, `follow`), `docs/acceptance/2026-09-24-damage-and-firing-probes.md`,
and `docs/acceptance/2026-09-25-position-belief-sortie.md` (the range-runaway fix). That's five
sorties of live-acceptance debt including this one.

**This one is worth its own short flight, not a fold-in — but it doesn't need a long one.** The
other four are about whether specific belief/perception behavior is *correct* in the air; this one
is about whether an entirely new process (brain-layer) and an entirely new interaction shape
(escalate → stand by → real spoken reply) work at all outside a fixture. Mixing it into one of the
longer belief-correctness sorties risks the new-process setup (forgetting to start brain-layer, or
the flags) contaminating whichever card it's folded into. Five to ten minutes on the ground or in
a short local hop is enough to clear blocks 1 and 3; block 2 needs one restart with a different
flag. If a single combined flight is preferred instead, fly this one's three blocks first, since
blocks 1 and 3 establish whether the new process is even working before spending time on the
others.

## Stage 2 prerequisites — recorded, not fixed, not exercised by this card

Two things measured during the performance pass are written into `plans/brain-layer/plan.md`'s
Stage 2 section and are **not reachable today**, so nothing in this card can exercise them:
`poll_replies()`'s 5 s timeout on the poll thread (a wedged brain would cost 5015 ms *every* poll,
~83% tick loss at the 1 s default), and `Decider.decide()` having no bounded timeout (one unjoined
daemon thread per `/escalate`). `StubDecider` cannot wedge, so neither is live yet — Stage 2, which
adds a real model, is what arms them.

## Bring back

1. **Block 1 — did you hear him answer at all, and did it feel right.** This is the actual point
   of Stage 1 and the thing worth most in this card.
2. Block 2 — stand-by timing, if you tried it.
3. Block 3 — clean silent degradation with brain-layer stopped.
4. Anything that surprises you is worth more than anything on this list.
