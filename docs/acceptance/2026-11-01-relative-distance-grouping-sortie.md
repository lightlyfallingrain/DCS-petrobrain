# BL-B108 — relative-distance grouping — sortie acceptance

**Branch:** `main` (BL-B108 merges automatically on this DoD pass — `git checkout main; git pull`
if your checkout is elsewhere).

## What this tests

Whether two real groups sitting on roughly one bearing, at clearly different distances, now give
**two contacts and two callouts** instead of folding into one — the thing that started this
milestone (`[[BL-B104]]`'s scenario flight folding a far group and a near group six seconds
apart).

## What it cannot test

- **The memory-only cross-optic numbers are not directly observable in a sortie.** The accepted
  honest limit (0-86% fold rate in one specific geometry: far group founded through binoculars,
  then held in memory, near group later reacquired unaided, far-first, at 4.5-5.0 km) is a
  probability measured over an ensemble of simulated noise draws, not a thing a single flight
  can confirm or refute by itself. One flight through that exact geometry tells you one draw from
  that distribution, not the rate. Flying it is still useful — see "Prize" below — but do not read
  one fold or one split as proving or disproving the number.
- **`[[BL-B109]]`'s callout wording** ("second group, beyond") is not built yet — a second group
  on the same bearing still gets an ordinary, independent callout, not one worded relative to the
  first.
- **`[[BL-B105]]`'s group-identity re-check on a remembered far group** is not exercised by this
  milestone's own tests (no multi-member `Group` forms in the E1a scenario) — this sortie cannot
  tell you whether that path is sound either way.

## Setup

From the repo root, on `main`, inside `body-layer/`:

```sh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python -m body \
  --aircraft-layer-url http://<aircraft-layer-host>:7791 \
  --audio-adapter-url http://127.0.0.1:7795 \
  --world-model-dir <dir-of-full-theatre-stores> \
  --eyesight-view \
  --group-trace logs/group-trace.jsonl
```

`--eyesight-view` gives you a live top-down view with ground truth alongside belief, so you can
see directly whether two groups resolved to two markers or one. `--group-trace` records every
`GroupStore.reconcile` outcome, in case anything here needs a closer look afterwards.

**UNVERIFIED as a live command** — it needs a running aircraft-layer collector and a built
world-model store this session does not have; the flags themselves, their names and defaults,
and the environment variables are read directly from `body-layer/src/body.py`'s own
`argparse` definitions and `body-layer/CLAUDE.md`'s run instructions, not guessed. What **was**
run and confirmed on this exact branch, with no DCS needed:

```
$ cd body-layer && PYTHONPATH=src:../world-model/src .venv/bin/python -m body --print-tuning | grep RANGE_DECORRELATION_RANGE_RATIO
  perception.estimation.RANGE_DECORRELATION_RANGE_RATIO: 4.0 (judgement)
```

confirming the shipped build on `main` carries this milestone's calibration change (4.0, not the
pre-amendment 1.5).

## Test cases

1. **Two groups on one bearing, far shows first.** Fly toward two real groups spaced ~1.5 km+
   apart along your line of sight, so the far one comes into detection range first and the near
   one six-plus seconds later. **Expect:** two separate contacts, two callouts — not one group
   re-sized.
2. **Orbit one group.** Hold a steady orbit around a single real group for a couple of minutes.
   **Expect:** it stays one contact throughout — no spurious "new contact" callout, no split into
   two from range noise during the dwell.
3. **Straight-in run.** Approach one group head-on. **Expect:** spoken range still carries today's
   usual error (not suddenly precise just from closing distance), and the group does not split or
   merge with anything else along the same line.
4. **Stationary group, overflown and re-asked after 2+ minutes.** Fly over a group, then ask about
   it again after at least two minutes. **Expect:** it is still recognised as the same group, not
   reported as new.

## Prize

**Does case 1 — the original folding scenario — actually give two callouts in a real flight, not
just in the scenario fixtures?** This is the one thing the whole milestone was built for; every
other case is a regression check.

## Bring back

- For case 1: did you hear two callouts, and roughly how far apart (in time and distance) were
  the two groups when each was first called?
- For any case: did a group split or merge when you did not expect it to, and what were you doing
  at that moment (optic switch, turn, dwell)?
- Anything that surprised you is worth more than anything on this list.
