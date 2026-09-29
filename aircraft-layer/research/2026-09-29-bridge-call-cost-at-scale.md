# `bridge_call_ms` at realistic unit counts — the number that was never read

**Date:** 2026-09-29
**Machine:** the Windows box (DCS installed). Source: `Saved Games/DCS/Logs/dcs.log`.
**Theatre:** n/a (the cost is a bridge property, not a terrain one).

### Question

What does one `net.dostring_in("scripting", ...)` call actually cost, at a unit count that stresses
it? This was named the single most load-bearing open number in
`2026-09-28-live-terrain-probing-feasibility.md` — nothing in that note's arithmetic was safe to
design against without it, and it gates whether live in-mission terrain probing is affordable at all
(`plans/missed-aaa-detection/debug.md`, fix option 5).

The measurement mechanism has existed since 2026-09-22 and had **never been read**. The only sortie
anyone had looked at carried twelve units.

### Base

`git rev-parse HEAD` → `7b4d2b2` (`main`). No code was changed to produce this; the numbers were
already on disk. `petrobrain-mission-telemetry-hook.lua` logs `unit_count` and `bridge_call_ms` to
`dcs.log` on every poll, by design (its Stage 0 part 2 self-measurement).

### Findings

**1. A sortie with 568 units was already sitting in the log, unread — 4.7x the top of the range the
handoff asked for.**

- **evidence: reproduced-locally** — **source:** `Saved Games/DCS/Logs/dcs.log`, 1,713 samples,
  `2026-09-28 17:54:22` → `18:36:53`, two regimes in one session.
- The log holds two populations: 1,194 polls at **565–568 units** (17:54–18:17) and 519 polls at
  **56 units** (18:18–18:36). The handoff asked for 50–200; both bracket it.

**2. The bridge is cheap, and it is cheap at scale.**

- **evidence: reproduced-locally** — **source:** as above, 1 Hz polling (`POLL_INTERVAL_S = 1.0`).

  | units | n | mean | p50 | p90 | p95 | p99 | max | ≥5 ms | ≥10 ms |
  |---|---|---|---|---|---|---|---|---|---|
  | 56 | 519 | 0.67 ms | 1 | 1 | 2 | 3 | 18 | 0.6% | 0.39% |
  | 565–568 | 1,194 | 1.99 ms | 2 | 3 | 3 | 8 | 20 | 3.9% | 0.75% |

- **The scaling is the important part, not the absolute number.** A 10x increase in units (56 → 568)
  raised the mean by 1.32 ms. That decomposes into roughly **0.5 ms fixed bridge overhead and
  ~2.6 µs per unit** — so the per-item work is trivial and what you mostly pay for is making the
  call at all. A design that does more work *inside* one `dostring_in` call is therefore far cheaper
  than one that makes more calls, which is exactly the shape the velocity hook already uses and the
  shape a terrain-probe batch would want.
- At 1 Hz, p99 = 8 ms is **0.8% of the interval**. There is no budget pressure here.

**3. The tail is real but rare, and it does not scale with unit count.**

- **evidence: reproduced-locally** — **source:** as above.
- Maxima are 18 ms (56 units) and 20 ms (568 units) — essentially the same, an order of magnitude
  above each population's own p99. A tail that is indifferent to the payload size is not the payload:
  it is almost certainly scheduler/GC/frame contention. Worth knowing because **a 20 ms outlier is a
  dropped frame at 60 fps if it lands on DCS's own thread**, and whether it does is still unestablished
  (Unresolved, below).

**4. Every number here is quantised to 1 ms, which sets a floor on what this measurement can say.**

- **evidence: reproduced-locally (every logged value is a whole millisecond) + documented (Windows CRT)**
  — **source:** `petrobrain-mission-telemetry-hook.lua` line 166 uses `os.clock()`; on Windows
  `CLOCKS_PER_SEC` is 1000.
- So "p50 = 2 ms" means the median sample *rounded* to 2 ms, and the 56-unit mean of 0.67 ms is an
  average over a 0/1 ms mixture, not a sub-millisecond reading. The derived fixed-overhead and
  per-unit figures in Finding 2 are therefore **estimates from two population means**, not direct
  timings, and are good to roughly a factor of two — fine for an order-of-magnitude go/no-go, not
  for tuning a batch size.
- **Any probe that wants a sharper number must repeat the call and divide**, which is why the
  elevation probe written this session does exactly that.

### What this decides

**Live probing is affordable.** That was the fork the whole terrain question hung on, and it is now
resolved in the probe route's favour: a bridge call costs ~2 ms at 568 units, per-item cost is
~2.6 µs, and there is ~99% of a 1 Hz interval spare. The concern that motivated the file route —
that live probing might be too expensive at any useful sample density — is not supported.

**It does not yet decide the batch size**, because a `getHeight` iteration is different work from a
`getVelocity` iteration (plausibly a heightfield sample or raycast, not a stored per-unit field).
That is what `petrobrain-elevation-cost-probe-hook.lua` measures.

### Reproducible Test

```sh
grep -o "unit_count=[0-9]* bridge_call_ms=[0-9.]*" \
  "$DCS_SAVED_GAMES_PATH/Logs/dcs.log"
```

Already run; 1,713 samples. `.claude/skills/dcs-log-recon` covers this extraction shape generally.

### Unresolved

- **Per-call cost specifically for `land.getHeight`, at batch sizes worth shipping.** Resolves with:
  `aircraft-layer/dcs-export/petrobrain-elevation-cost-probe-hook.lua`, **deployed to
  `Saved Games/DCS/Scripts/Hooks/` on 2026-09-29** and firing 10 s into the next Syria mission. It
  times batches of 1/100/500/2601 points, 20 repeats each, against a zero-work null call so bridge
  overhead can be subtracted.
- **Whether a `dostring_in` call blocks DCS's own frame**, as opposed to only costing wall-clock time
  inside the Hook/mission-scripting states. Unestablished for *any* payload, velocity included —
  and Finding 3's 20 ms outliers are what make it matter. **Resolves with:** the same probe flown
  while watching DCS's frame-time counter, the cross-check the 2026-09-26 performance review already
  recommends for the unrelated `LoGetWorldObjects` question.
- **Whether 568 units is representative of the missions Petrovich will actually fly.** It is one
  session. It is comfortably above what the handoff asked for, so it is enough to settle the go/no-go,
  but it is not a distribution over mission types.
