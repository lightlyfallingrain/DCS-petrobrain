---
name: body-layer-poll-loop-diagnosis
description: BL-B30 diagnosed 2026-10-05 — the "5 Hz spec" never existed (default is 1.0 s), the loop sleeps AFTER the work, and group_salient_ids is ~300 ms/poll of pure recomputation.
metadata:
  type: project
---

Whole-subproject performance pass on body-layer, `main` @ `19143fa`. Full report:
`body-layer/research/2026-10-05-performance-review.md`.

## The premise correction, which matters more than any single number

`BL-B30` (and the sortie note it came from) says the poll loop is "specified at 5 Hz, observed at
0.7 Hz, seven times slower". **There is no 5 Hz configuration anywhere in body-layer.**
`logger._DEFAULT_POLL_INTERVAL_S = 1.0` since 2026-09-08, `RUN.md` never passes
`--poll-interval-s`, and `ROADMAP.md`/`audio-adapter/ROADMAP.md` both already call 1.0 s "the
project's own default". The 5 Hz claim lives only in stale **docstrings** (`logger.py`,
`belief/brain_client.py` ×2, `perception/motion.py`).

**Why:** a performance target read off a docstring rather than the config turned a 1.4× miss into
a reported 7× miss, and produced a false corollary — that every decay/dwell constant was
mis-calibrated. They were tuned in flight at 1 Hz, which is what the code always did.

**How to apply:** on this project, read the default off the constant and the documented run
command, never off a docstring or a backlog entry quoting one. `CLAUDE.md`'s own
"verify state, not the account of it" applied to a performance budget.

## The mechanism, and the measured breakdown

`logger.py` ends both poll bodies with `stop_event.wait(poll_interval_s)` — a **fixed sleep after
the work**, so the realised period is `work + interval`, never `interval`. Measured work at sortie
scale (440 objects / 142 contacts / real `syria-full.sqlite`): **median ~330 ms, peaks 1,736 ms**
→ period 1.33 s, against the sortie's measured 1.43 s.

| term | measured | note |
|---|---|---|
| `group_salience.group_salient_ids` | **~300-318 ms EVERY poll**, 160 k `profile_for` calls | 58 % of a 300-poll cProfile; scales with *candidate* count, not contacts |
| `CalloutScheduler.tick` → `describe_position` | up to **47 calls / 1,579 ms** in one tick | `BL-B26`'s 3× gather; median callout tick 13 calls |
| `check_visibility` whole gate chain (LOS incl.) | 2.4-21 ms/poll for all 440 | **ruled out** — was `BL-B30`'s leading suspect |
| `ContactStore.tick` / `_cluster_contacts` | 6.4 / 5.8 ms @ 142 contacts | `BL-B23` holding |
| trace writer | 4.4 ms/poll, 440 rows, 290 KB/poll | volume is the finding, not CPU |
| 5 aircraft-layer GETs | 3.4 ms loopback floor | but **2.0 s timeout each** = 10 s worst case |

## `group_salient_ids`: the fix is recomputation removal, measured 8.1× — **but the shipped fix is 5.1×**

> **Updated 2026-10-06, `feature/bl11-tick-cost` @ `8fa2ad6`.** The 8.1× below is this prototype's,
> not the shipped code's. What shipped measures **5.1×**, and the gap is one more per-candidate
> quantity left inside the pair loop — see [[group-salience-hoist-residual]] before quoting either
> number. The table below is still the correct *baseline* measurement (its per-pair unit cost
> reproduces to within 3 %).


`_cohesive` recomputes two `profile_for` lookups and two `range_m` calls **per pair** of an O(n²)
loop, all four depending on one candidate only. Hoist them into the `_resolvable` pass that already
walks the list; add `@lru_cache` to `profile_for` (pure fn of a str, 0.93 → 0.04 µs/call).

| n | 55 | 128 | 250 | **440** | 800 |
|---|---|---|---|---|---|
| current | 3.4 | 17.8 | 69.7 | **215.1** | 722.0 ms |
| hoisted | 0.5 | 2.3 | 8.8 | **26.8** | 92.6 ms |

Output `frozenset` asserted bit-identical at every n. Still O(n²) after — spatial pruning is an
Architect question, and the plan deliberately runs this over the whole 10 km bubble *before* the
gaze gate, so it cannot be scoped to the cone without changing semantics.

See [[project_dcs_driven_los_cone_scoping]] for the related gaze-cone scoping that *was* legitimate.

## `WorldEnrichmentCache` misses by construction for the contacts that matter

Keyed on `contact_id` + **exact structural equality of `Contact.last_position`**. A re-observed
contact has a freshly-updated believed position every poll, so it misses every poll — and those are
exactly the contacts that get spoken about. Measured: 92 % hit rate overall, but
`distinct_positions == describe_calls == cache_misses` in **every** callout-bearing tick. A 1 m
nudge costs the full 42 ms. Fix is to quantise the key (50-100 m), which the function's own output
coarseness already tolerates. **Shipped 2026-10-06 (Stage 3b) — but it fixes only the across-poll
axis, not the N-members one; see [[enrichment-cache-axes]].**

`describe_position` on `syria-full.sqlite` is **median 51.6 ms cold-distinct, 41.4 ms warm-repeat**
— it does not get cheaper on repeat, so it is CPU-bound Python, not cold I/O. Any "add a world-model
query per X" proposal should be costed at ~40-50 ms, not at the ~0.1 ms a single SQL `execute`
suggests. `BL-B26`'s own estimate used ~0.3 ms/member and was therefore two orders out.

## `audio-adapter`'s `POST /speak` synthesizes TTS synchronously before responding

`server.py`'s `_handle_speak` calls `engine.synthesize(text)` in the request path, and body-layer's
`CrewConsole._print` → `push_speech` (5 s timeout) runs inside `drain_events`, inside the poll body.
**Every spoken callout blocks the poll loop on speech synthesis.** Unmeasured here (no TTS engine in
the sandbox) but architecturally against the project's own "never block the main thread" rule, and
it stalls the polls immediately after Petrovich notices something.

## Harness technique worth reusing

`from x import y` binds a separate reference, so **patch the name at the *importing* module**
(`naked_eye_source.group_salient_ids`), not the defining one. Patching the defining module measures
nothing and reports zeros — which looks exactly like "this is cheap". A fake in-process
`AircraftLayerClient` duck type plus the real `logger._build_sources` and real
`syria-full.sqlite` gets the whole hot path under `cProfile` with no DCS and no LAN.
