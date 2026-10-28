# Acceptance card — theatre read from DCS at mission start

Published card: https://claude.ai/artifact/81mVEm4waPeXuoWNan6gVK

**Branch to fly: `main`** — this merges right after DoD, so check out `main` after the merge lands.
`git checkout main` from the repo root.

**Setup:** `body-layer/.venv` present, an aircraft-layer collector reachable, and a world-model
`DIR` holding at least one `<theatre.lower()>-full.sqlite` for the theatre(s) you fly (e.g.
`syria-full.sqlite`). No `--mission-understanding` file needed for this test — that is the point.

## What changed

Previously, starting body-layer without `--theatre`/`--world-model-db` required a
`--mission-understanding` JSON artifact to derive the theatre. Now `--world-model-dir` alone is
enough: the theatre is read from DCS's own mission-start event (the aircraft-layer collector's
latest one at startup, then on every mission (re)start), and the matching
`<theatre.lower()>-full.sqlite` is loaded automatically.

## 1. Start body-layer with `--world-model-dir` alone, DCS not yet running

From `cd body-layer`:

```sh
PYTHONPATH=src:../world-model/src .venv/bin/python -m body \
  --aircraft-layer-url http://<aircraft-layer-host>:7791 \
  --audio-adapter-url http://127.0.0.1:7795 \
  --world-model-dir <path-to-dir-of-full-theatre-stores>
```

**Do:** start this before DCS has loaded a mission.
**Expect:** a startup line on stderr — `theatre: not given -- waiting for DCS to report it at
mission start` — and no crash. Any voice command or REPL line at this point should get the
refusal response, not a traceback.
**Record:** did it sit quietly waiting, or did it crash/hang?

## 2. Load a mission in DCS

**Do:** load and start any mission on a theatre whose store exists in `DIR`.
**Expect:** within one poll interval, Petrovich should start perceiving (naked-eye/HelperAI
reports should become possible) and a voice command like "status" or "report" should get a real
answer instead of the refusal line.
**Record:** which theatre did you fly, and how long from mission start to the refusal line
clearing (roughly)?

## 3. Restart the mission (same theatre)

**Do:** restart the mission in-sim (not a body-layer restart).
**Expect:** belief/mission-memory reset (as before, BL-15 Stage 1 — already live-accepted), and
the same theatre's store stays loaded without any refusal interruption.
**Record:** any unexpected refusal line or pause at the restart?

## 4. If you can fly two different theatres back-to-back

**Do:** end the first mission, load a mission on a **different** theatre whose store also exists
in `DIR`, without restarting body-layer.
**Expect:** the store switches live — Petrovich should perceive correctly against the new
theatre's terrain (no obviously wrong line-of-sight/range behaviour), with no body-layer restart.
**Record:** did the switch happen cleanly, and did anything said or perceived seem to lag behind
or reference the old theatre?

## Not testable from this card

Stage 2 (Mission Interpreter briefing) is unaffected and still deferred — nothing here depends on
`--mission-understanding`, which remains optional (mission-phase input only).

## Bring back

- Test 1: did it wait quietly without `--mission-understanding`, or error/crash?
- Test 2: theatre flown, and rough time from mission start to first real answer.
- Test 3: any refusal/pause on a same-theatre restart?
- Test 4 (if flown): did a live theatre switch work cleanly?
- Anything that surprised you is worth more than anything on this list.
