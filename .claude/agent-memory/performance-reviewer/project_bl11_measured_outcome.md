---
name: bl11-measured-outcome
description: BL-11 closed BL-B30 — poll period 1.33 s to 1.000 s, work 330 ms to 12.6 ms; the residual 2% tail is describe_position's unit cost, not body-layer's.
metadata:
  type: project
---

Measured at `feature/bl11-tick-cost` tip `8fa2ad6` (2026-10-06), full-poll harness, 440 objects /
10 km bubble / 1 s steps / 300 polls, real `syria-full.sqlite`, fake in-process aircraft client
(so every CPU figure is a floor).

| | note, pre-branch | post |
|---|---|---|
| poll work median / p90 / max | ~330 / — / 1,736 ms | **12.6 / 98.6 / 1,642 ms** |
| realised period median | 1.33 s | **1.000 s** (mean 1.008, max 1.642) |
| polls overrunning 1.0 s | — | 2.0 % (3.0 % at 800 objects) |
| `group_salient_ids` | ~300 ms **every poll** | 1.1 ms median, 5.5 max |
| enrichment-cache hit rate within a callout tick | 0 % | 89.7 % |

`_wait_for_next_tick` realises **exactly `max(interval, work)`** to within 0.1 ms, verified side by
side against the pre-Stage-1 `wait(interval)` shape. Overrun re-bases on the clock once and then
sleeps normally — no queued debt, no spin.

**Real in-bubble candidate count: median 232 at 440 objects** (min 32, max 434). The note's "single
most valuable number, one `len()` away" — and it was 2× below what every finding-1 figure assumed.
The player bubble sheds most of the field as the ownship tracks away from the clump centroid. 800
objects → candidates median 570, `group_salient_ids` median 8.1 ms.

**The whole residual tail is one thing: `describe_position` at ~57-85 ms/call** (CPU-bound, same
cost warm or cold — see [[enrichment-cache-axes]]). ~13 misses × 85 ms is the entire 1.6 s worst
poll. **Not addressable by more body-layer caching**; it is a `query.describe` question.

**Still unmeasured and still the credible explanation for the sortie's 4.98 s p90:** the five
sequential 2.0 s aircraft-layer timeouts and the synchronous TTS `push_speech` (note findings 7 and
8). BL-11 fixed the median; the tail is untouched, and the note's suggested timeout reduction was
not taken.

**Stage 5, against the real 3.55 GB artifact** (`/Users/sg/dcs-detection-trace.jsonl`, sampled from
byte offset 2,448,471,603): **real rows average 622 B, not the note's claimed 2.2 KB/row** — the
note divided by an assumed row count, and its premise that real rows have the `None` fields
populated is wrong (mean 12.7 omittable nulls of 25 keys). None-omission saves **50.3 %** on real
rows, so that sortie would have been ~1.76 GB. **64.7 % of real rows are `player_bubble`**;
dropping them behind a flag (never in Stage 5's scope) would reach ~0.6 GB.

Related: [[project_body_layer_poll_loop_diagnosis]], [[group-salience-hoist-residual]],
[[benchmarks-must-be-able-to-fail]].
