# BL-11 tick cost sortie — Stages 1, 2, 3b and 5

**Branch: `feature/bl11-tick-cost`** (not merged as of this card — five review rounds, the security
deep analysis and the performance pass have all passed; DoD mechanical checks pass; this flight is
the only thing outstanding):

```sh
git checkout feature/bl11-tick-cost && git pull
```

If you are flying after it has merged, check out `main` instead — same setup and test items apply.

## Read this first: the whole change is invisible from the cockpit

**This branch makes nothing new happen. It makes the existing tick cheaper.** Nothing is added to
what Petrovich says, sees, or decides. The observable is the *absence of lateness* — and lateness is
nearly impossible to score from the controls, because you have nothing to compare a callout against.

So: **the real verification is the log, not your ears.** Fly a normal sortie, then run the one
reduction in "The actual test" below. Your ears have exactly one job on this flight, and it is the
enrichment risk in "What could genuinely be wrong" — not the timing.

Measured on the bench at this branch tip (440 objects, real `syria-full.sqlite`, 300 polls):

| | before | at this branch |
|---|---|---|
| poll work, median | ~330 ms | **12.6 ms** |
| poll work, p90 / max | — / 1,736 ms | 98.6 / 1,642 ms |
| **realised poll period, median** | **1.33 s** | **1.000 s** |
| `group_salient_ids` | ~300 ms *every* poll | **1.1 ms** |
| enrichment-cache hits within a callout tick | **0 %** | **89.7 %** |
| polls overrunning 1.0 s | — | 2.0 % |

`BL-B30` — "the poll loop runs at roughly 0.7 Hz" — is closed by this branch.

## Setup

Nothing new to deploy. No Hook script, no `Export.lua` change, no wire-format bump. Same processes
as any recent sortie:

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text-debug-view.sh
```

Windows side, collector: `cd run-scripts && ./run-collector.sh`

**Use `run-crew-text-debug-view.sh`, not `run-crew-text.sh`, for this flight.** Only the debug-view
script passes all three log flags; plain `run-crew-text.sh` passes `--speech-log` alone, and the
reduction below needs the belief-truth log. (Verified by reading both scripts on this branch.)

Both scripts were corrected on this branch: their four `~/dcs-*.jsonl` paths are now
`logs/dcs-*.jsonl`, and both `pushd ../body-layer/`, so the files land in `body-layer/logs/`.

## Two things you will notice, and one you must not read as a bug

**1 — The logs have moved, and muscle memory will point at the wrong file.**

They were `~/dcs-detection-trace.jsonl`, `~/dcs-belief-truth.jsonl`, `~/dcs-speech.jsonl`. They are
now under `body-layer/logs/`, with a per-run stamp:

```
body-layer/logs/dcs-detection-trace-20261006-040452.jsonl
body-layer/logs/dcs-belief-truth-20261006-040452.jsonl
body-layer/logs/dcs-speech-20261006-040452.jsonl
```

**The startup stderr line is the authoritative answer, not this card.** Three lines, one per log, at
launch (exact format, read from `logger.py:2215`):

```
detection-trace: writing logs/dcs-detection-trace-20261006-040452.jsonl
belief-truth-log: writing logs/dcs-belief-truth-20261006-040452.jsonl
speech-log: writing logs/dcs-speech-20261006-040452.jsonl
```

All three carry **one shared stamp** per run, so a sortie's three logs always match. Verified by
execution, in an empty directory:

```
$ python -c "import logger; from pathlib import Path; \
    print(logger._per_run_log_paths(detection_trace=Path('logs/dcs-detection-trace.jsonl'), \
    belief_truth_log=Path('logs/dcs-belief-truth.jsonl'), speech_log=Path('logs/dcs-speech.jsonl')))"
resolved: logs/dcs-detection-trace-20261006-040452.jsonl
resolved: logs/dcs-belief-truth-20261006-040452.jsonl
resolved: logs/dcs-speech-20261006-040452.jsonl
```

**2 — `--detection-trace` / `--belief-truth-log` / `--speech-log` now create their parent
directory.** Previously, pointing any of them at a directory that did not exist was a startup
`FileNotFoundError` that killed the crew before it started. Now the directory is created; if it
*cannot* be created, that one log degrades to off with a stderr line naming the flag, and the other
two and the crew carry on. In the verified run above, `logs/` did not exist beforehand and was
created.

**3 — DO NOT read this as a bug: your old logs will never grow again, and each run starts an empty
file.** `~/dcs-detection-trace.jsonl` (3.55 GB) and its two siblings are frozen at the 2026-10-05
sortie. Nothing appends to them any more. A fresh run produces a brand-new, initially-empty file
under `body-layer/logs/`. **An empty-looking log right after launch is the feature, not a logging
failure** — it is the whole point of Stage 5 (no more byte-offset archaeology to find where a sortie
began). The flip side is real and yours to manage: **~1.8 GB per sortie, with no retention policy
and nothing pruning it.** That is a by-hand decision.

## The actual test

Fly a normal sortie — whatever mission gives you a decent number of ground units at mixed ranges.
Length matters more than content; ten minutes is plenty.

Then, from `body-layer/`:

```sh
python3 -c "
import json,statistics,glob
f=sorted(glob.glob('logs/dcs-belief-truth-*.jsonl'))[-1]
t=sorted({json.loads(l)['t_sim'] for l in open(f) if l.strip()})
d=[b-a for a,b in zip(t,t[1:]) if 0<b-a<30]
print(f,'polls=%d'%len(t),'median=%.3fs'%statistics.median(d),'p90=%.3fs'%sorted(d)[int(.9*len(d))],'max=%.3fs'%max(d))
"
```

**VERIFIED** — run against the real 2026-10-05 log (the pre-branch baseline), which is what makes
this a before/after rather than a bare number:

```
$ python3 -c "..."   # same reduction, pointed at ~/dcs-belief-truth.jsonl
/Users/sg/dcs-belief-truth.jsonl polls=1340 median=1.424s p90=4.766s max=27.886s
```

**What to expect this flight: `median` should read close to `1.000s`.** That is the single number
this whole branch exists to move, and 1.424 → ~1.000 is the pass.

Two honest caveats on the instrument:
- It reads the *sim-time* gap between polls that produced at least one matched contact row, so
  `polls=` is a subset of all polls and a long contact-free stretch shows as one big gap (hence the
  `<30` filter, and the 27.9 s `max` above).
- **`p90` and `max` are not this branch's to fix** and should not be read as a failure — see below.

## What could genuinely be wrong, and it is not performance

**Stage 3b now shares one enrichment result between all positions inside a 50 m grid cell.** Before,
the cache key was exact float equality on a contact's believed position, so a 1 m nudge cost a full
recompute — which is why it hit 0 % of the time for exactly the contacts being spoken about. Now the
key is the containing 50 m cell.

**The consequence: a spoken line about a nearby terrain feature can be computed from a position up
to the cell diagonal away — ~70.7 m horizontally** (~86.6 m in 3D).

**This is the one thing to listen for.** Does any spoken line ever sound *wrong about a nearby
feature*? Specifically:

- "near a road" / "on the road" for something that is plainly not;
- "beyond the ridge" / "this side of the ridge" with the wrong side named;
- any terrain or landmark qualifier attached to a contact it should not be.

70 m is small enough that most qualifiers survive it and large enough to flip one that sits right on
a boundary — a contact beside a road, or straddling a ridge line. **Record the contact and roughly
where it was**, not just that it sounded off; the discriminator needs the position.

There is a second, unquantified axis the performance pass flagged and declined to guess at: a cache
hit also freezes the cached `world_position`, whose *observer* vantage comes from the most recent
contributing percept. Under the old exact key, a hit implied no new percept had been fused; under a
50 m cell it no longer does. Nobody has measured how much staleness that adds. If something sounds
wrong about a nearby feature, this is the other candidate.

## What is still open, so none of it surprises you

- **2.0 % of polls still overrun 1.0 s**, and every one of them is a single `describe_position`
  spike — 57–85 ms per call, and **the same cost cold or warm** (measured at four different access
  shapes: distinct positions, the same position twenty times, positions 1 m apart, positions inside
  one 50 m cell — all ~57–58 ms). No internal memo, no I/O warming. So this residual is
  `query.describe`'s unit cost and belongs to **world-model**, not to more body-layer caching.
- **The sortie's 4.98 s p90 is still unexplained by this branch.** Nothing in the CPU measurements
  reaches it. The two standing candidates are both outside body-layer: `BL-B33` (five sequential
  aircraft-layer GETs, each with a 2.0 s timeout, no connection reuse) and `BL-B32` (audio-adapter's
  `POST /speak` synthesizing TTS synchronously inside the poll body — **the one live violation of
  this project's own never-block-the-main-thread rule**). **The median is fixed; the tail is not.**
  If your reduction comes back with a ~1.0 s median and a still-ugly p90, that is the expected
  result, not a regression.
- **`BL-B40`** holds a located-but-declined further 1.6× on the salience hoist. Declined with
  arithmetic: it would save ~0.4 ms of a 12.6 ms poll. Recorded so it is not re-discovered as a
  surprise.
- **`BL-B39`** is the marker that a self-disabled log is indistinguishable from one that simply
  stopped — the new writers report a failure once and then go quiet by design.
- **Stage 3a was deliberately not built**, and the performance pass quantified why: 189
  `describe_position` calls against 187 distinct 50 m cells. Two redundant calls, 1.1 %. There is
  almost nothing left for it to collect.

## A trap worth knowing before you or anyone re-runs the old diagnostic

`distinct_positions == describe_calls == cache_misses` is the exact signature the original research
note used to **diagnose** the cache defect. **It still holds, in 37 of 37 callout-bearing ticks.**

It no longer means what it meant. Before, it held *with zero hits* — the cache did nothing. Now it
means each remaining miss is a genuinely new 50 m cell that genuinely needs a new call.

**Anyone re-running that diagnostic will see the same equality and conclude Stage 3b failed.** The
discriminator is **the hit count beside it** (0 % before, 89.7 % now), never the equality alone.

## A product call you have not made — Q7 now has a number

64.7 % of real detection-trace rows are `player_bubble` (gaze 31.9 %, range-or-size 3.4 %). Dropping
them behind a flag would take that 3.55 GB sortie from ~1.76 GB to **~0.6 GB**, for the cost of one
flag.

The trade is that you lose the record of *what was in the bubble and rejected* — which is exactly
what you would want if a contact ever goes unreported and you need to know whether it was ever seen
at all. **Not a performance question and not mine to decide.** Flagging it because the number now
exists.

## Pass criteria

| | |
|---|---|
| **Passes if** | the reduction's `median` reads close to `1.000s` (baseline 1.424 s), and no spoken line sounds wrong about a nearby terrain feature. |
| **Does not fail on** | a still-high `p90`/`max` — that is `BL-B32`/`BL-B33`, outside this branch. |
| **Report back** | the reduction's one line of output, and any contact a terrain/road/ridge qualifier sounded wrong about, with roughly where it was. |

## Verification status of this card

Every command above was executed on this branch except the flight itself:

- the poll-period reduction — **run**, against the real 2026-10-05 log and against a stamped copy
  through the exact `glob` form printed above;
- the per-run path resolution and parent-directory creation — **run**, in an empty directory;
- the three CLI flags and `--poll-interval-s` — **confirmed present** in `python -m logger --help`;
- both run-scripts — **read** on this branch, not executed (they need the DCS collector).

**UNVERIFIED, and only resolvable in flight:** the startup stderr lines appearing in a real launch
(the path resolution behind them is verified, the launch is not); the realised poll period with a
real LAN and a real TTS engine in the path; and the within-tick cache hit rate under manoeuvring
targets — the bench's objects are static, so **89.7 % is an upper bound**, and the magnitude needs
this sortie even though the direction is certain.
