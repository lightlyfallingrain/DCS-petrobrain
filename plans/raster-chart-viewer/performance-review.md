### Performance Review

Batch reviewed: `raster-chart-viewer/` (RC-1 / MI-B4), Stages 1-6 plus the reviewer-requested
thread-safety fix commit, `cf5d8f7f..a80611ed` on `feature/raster-chart-viewer`. Worktree
fast-forwarded to the named tip `a80611ed4598c50df6a971e1be88d508b90fd23b` (HEAD was
`f72ae5b3`, a strict ancestor; fast-forward merge, clean tree before and after).

**Context this review is judged against** (per the task brief, not the project's Petrobrain-Runtime
real-time budget, which does not apply here): a single-user LAN tool on the Windows DCS machine,
one browser, pan/zoom, possibly while DCS is running. "No hard real-time budget" — so findings
below are about *felt responsiveness and long-session degradation*, not a missed deadline.

**Method**: measured directly against the real, installed, read-only DCS copy
(`/mnt/f/Games/DCS World`, WSL bridge) using the actual `discovery`/`cache`/`warmup` modules, plus
isolated local-disk micro-benchmarks to separate WSL-bridge latency from real CPU/algorithmic cost.
Every number below has a stated can-fail probe (byte-identity checks, collision-free fixture
assertions, or a deliberately-bad variant shown to produce a different reading) — none is accepted
from reasoning alone. Cache dir under `/tmp`, deleted after each run; nothing written to the DCS
install; venv created at `raster-chart-viewer/.venv`.

**Headline finding**: `discovery.read_tile_bytes`'s "open a fresh `ZipFile` per read" design —
correct and necessary *across* threads/requests (confirmed sound by Reviewer) — is also applied
*within* a single request's or warm-up pass's own entry loop, where it has no safety benefit and
costs real time: reopening the same zip (4 of 5 terrains have exactly one) once per entry instead
of once per batch measures a **4.1x** slowdown on exactly the paths this feature is most worried
about (middle zoom, small-mip-cold, the "genuinely slow" full-tier overview). This is the one item
rated NOW; the cache-sweep batching item is the other.

### Findings

#### 1. Per-entry `zipfile.ZipFile` reopen inside a single request's own read loop
- **Location:** `discovery.read_tile_bytes` (opens fresh every call) as used from
  `cache.read_and_populate_small_mips`'s and `warmup.WarmupScheduler._warm_up`'s per-entry loops.
  Every multi-entry `compose_view_tile` call and the whole warm-up pass pay this once per entry,
  even when consecutive entries share the same zip (guaranteed for 4 of 5 terrains; true within
  one Caucasus sheet-zip for `k <= 3` requests, which exactly covers one 8x8 sheet).
- **Measured:** reading 100 real Afghanistan entries from `rasterCharts.zip` (same WSL path as
  production for this measurement) costs 1.84s via the current fresh-open-per-entry path vs 0.45s
  reusing one `ZipFile` for the whole batch — **4.10x**, 13.9ms/entry saved (probe: both paths
  return byte-identical >1MB reads, ruling out a stubbed/short-circuited comparison). Isolated on a
  local (non-bridged) disk, `ZipFile()` open cost scales with entry count at ~2.5µs/entry in pure
  Python central-directory parsing (3072-entry zip: 7.7ms vs a 1-entry zip's 0.016ms) — this is
  **CPU-bound, not WSL-bridge-bound**, so the saving carries to the native Windows I/O the service
  actually runs under, even though the absolute WSL numbers above do not.
- **End-to-end effect, real zoom bands against the live Afghanistan 32m tier (3072 entries,
  largest grid)**, cold cache, WSL bridge:
  | band | entries opened | measured | zip-reopen overhead's rough share |
  |---|---|---|---|
  | k=0 (full-res) | 1 | 38.7ms | ~35% (one-time, barely felt) |
  | k=2 (middle zoom) | 16 | 276.5ms | ~80% of total |
  | k=3 (small-mip, cold) | 48-64 | 0.88-1.45s | ~60-80% of total |
  | k=6 (full zoomed-out overview, cold) | 3072 | **71.5s** | ~59% (≈42s of the 71.5s) |
- The plan's and implementer's own anchor figure ("research note's own measured ~16ms/entry warm")
  is undercut by this: that figure almost certainly came from a loop reading all entries off one
  already-open `ZipFile` (the natural way to write a quick probe script), i.e. it already assumed
  the batching this production code doesn't do. The code comment on `read_tile_bytes` claiming
  reopening "costs...negligible [overhead] next to the ~1.4MB inflate itself" is measurably wrong
  for any multi-entry request — it is only roughly true for the single-entry k=0 case.
- **Risk:** the two paths users actually notice — panning at a middle zoom, and the first
  fully-zoomed-out view of a tier (OpenSeadragon's default initial view) — are exactly the ones
  this costs the most on, and the first-view cost is the one Stage 6's warm-up exists specifically
  to hide (see Finding 3).
- **Action: NOW.**
- **Mitigation:** request-scoped reuse only — group the `TileLocation`s a single
  `compose_view_tile` call or one `WarmupScheduler._warm_up` pass needs by `zip_path`, open each
  such zip once, and read every entry from that batch through the same handle before closing it.
  This is scoped to one call on one thread; it does **not** reintroduce a `ZipFile` shared across
  threads/requests (the hazard Reviewer already confirmed is correctly avoided) and needs no new
  locking. Localized to `discovery.py` (add a batch-read helper) and its two call sites in
  `cache.py`/`warmup.py`.

#### 2. `TileCache._enforce_cap_locked`'s full-directory rescan on every write at steady state
- **Location:** `cache.py` `_enforce_cap_locked`, called from `_write` while already holding
  `self._lock` whenever a write pushes `_total_bytes` over `CACHE_MAX_BYTES`.
- **Measured:** with a realistic one-terrain small-mip file count (Afghanistan 32m: 3072 entries x
  8 small mips, levels 3-10 = 24,576 files — exact per-entry formula, not estimated; probe:
  asserted all 24,576 generated paths are distinct before timing), pinning the cap exactly at the
  current total and then writing one more byte triggers a full `rglob("*")` + `.stat()` of every
  file + sort, held under the global lock: **mean 278.9ms, 20 reps, stable** (probe: eviction
  genuinely happens each time — file count returns to exactly 24,576 after each cycle, not
  drifting, confirming the sweep is real work each time, not a skipped no-op).
- **Risk:** this is the recurring cost once the cache is actually at its cap, not a one-off. The
  cap (1GB) and the design (small mips persist across restarts, warm-up populates them eagerly for
  every tier ever touched, composed tiles accumulate with ordinary panning) make reaching steady
  state a matter of *when*, not *if*, for a tool meant to be reused across sessions over weeks: all
  5 terrains' small-mip sets alone sum to roughly 12,500 entries x ~32KB (the plan's own "~100MB
  for Afghanistan's 3072" ratio) ≈ 400MB, leaving well under 1GB of composed-tile headroom to fill
  with ordinary use. Once there, **every subsequent write — any terrain, any tile, the warm-up
  thread included — pays a sub-second full-directory-rescan-and-sort while holding the lock that
  every other concurrent cache operation waits behind.** At the full multi-terrain file count this
  scales toward (100k-150k files is plausible if several terrains are fully warmed), extrapolating
  from the measured ~2.5x count increase costing a proportionally larger scan, this is a multi-
  hundred-ms-to-low-seconds stall per tile fetch, felt directly as the map "hanging" while panning
  — the opposite of "works until you stop looking" the Reviewer already flagged for the pre-fix
  race.
- **Action: NOW** (cheap, localized, matches this role's "poor batching" criterion directly — the
  task brief named this exact mechanism to check).
- **Mitigation:** evict a batch per sweep rather than exactly one file — e.g. sweep down to some
  margin below the cap (90% of `CACHE_MAX_BYTES`, say) instead of stopping the instant the total
  drops at or under it. This amortizes the O(file-count) `rglob`+`stat`+`sort` cost across the many
  writes that follow, instead of paying it on every single one at steady state. No lock or
  correctness change needed — purely the stopping condition inside the existing loop.

#### 3. Warm-up thread races the very request it exists to help
- **Location:** `server.py`'s `_handle_tile`/`_handle_tier_info` call `warmup.touch(...)` *before*
  `compose_view_tile`; `warmup.WarmupScheduler._warm_up` and the foreground request both call the
  same `read_and_populate_small_mips` over the same entries with no coordination between them
  beyond the (idempotent) `has_small_mip` check.
- **Measured:** a 200-entry subset of the real Afghanistan zip, inflated by one thread alone, took
  5.06s. The same 200 entries, with a second thread started via `WarmupScheduler.touch()` at the
  same instant (reproducing `server.py`'s actual call order against a cold cache), took 7.51s wall
  clock for both threads to finish — **1.48x**, not the ~1.0x true deduplication would show.
  Probe: the two threads' start is synchronized with a `threading.Barrier` so the race is
  guaranteed to actually overlap, not just hoped for.
- **Risk:** this specifically defeats Stage 6's own stated purpose for the one request it matters
  most for — OpenSeadragon's default initial view of a newly-opened tier *is* the fully-zoomed-out
  overview, i.e. the same request that triggers `warmup.touch()` for the first time. The plan's own
  risk note ("pays the cost once itself, same as today") undersells this: it is not "the same as
  today", it is ~1.5x worse than today because of the redundant concurrent work, on exactly the
  first impression a newly-opened terrain gives.
- **Action: MONITOR**, not NOW — unlike Findings 1-2, this is **one-time per (terrain, tier) per
  installation's cache lifetime**, not a recurring cost: once warm-up finishes once (ever, since
  small mips persist across restarts), every later restart's `has_all_small_mips` skip check makes
  both the foreground request and any later warm-up touch cheap. It also partially shrinks on its
  own once Finding 1's batching fix lands (both threads' own per-entry work gets faster, narrowing
  the overlap window), without needing a separate change.
- **Mitigation if revisited:** move the `warmup.touch(...)` call to *after* the handler has already
  obtained its own tile/tier-info response, not before. This costs nothing when the first request
  is small (full-res/middle zoom) — warm-up simply starts slightly later and still indexes the rest
  of the tier — and when the first request already is the full-tier overview, the subsequently-
  started warm-up thread finds almost everything already cached and exits almost immediately
  instead of racing the request that just did the work.

#### 4. `TileCache` lock scope and small-mip decode
- **Location:** `cache.py`, `get_small_mip` decodes the cached PNG (`Image.open(...).convert
  ("RGBA")`) while holding `self._lock`.
- **Measured:** 200 reps of decoding the largest small mip (128x128, `SMALL_MIP_MIN`) under the
  lock: mean 232.7µs, max 329.5µs (probe: decoded image's pixel size checked against what was
  written, confirming a real decode happened).
- **Risk:** negligible at this size — sub-millisecond, far below the zip-open/cache-sweep costs
  above. The lock is process-wide (not per-key), so in principle every concurrent cache operation
  queues behind each other one's decode, but at ~230µs per hold this would need a very high request
  rate to matter, which a single-browser LAN tool does not produce.
- **Action: MONITOR** (informational — no change needed now; worth re-checking only if
  `SMALL_MIP_MIN` is ever lowered to admit a much larger "small" mip).

#### 5. Memory per request
- **Location:** `cache.compose_view_tile`'s per-entry decode-then-paste loop.
- **Measured:** `tracemalloc` peak during a real 256-slot (k=4) composition against Afghanistan's
  32m tier: 8.72MB peak, 2.07MB resident after. Probe: a deliberately-leaky 50-entry variant that
  keeps every decoded image alive in a list was run for comparison and showed the measurement
  technique does detect accumulation when it is actually present (6.92MB for just 50 small mips vs
  8.72MB total for the real 256-entry request) — the real code's flat, small peak is a genuine
  absence of per-entry accumulation, not an insensitive probe.
- **Risk:** none found. The sequential decode-paste-discard loop (no list of sub-images ever built)
  keeps memory bounded regardless of how many entries one composed tile covers, including the
  3072-entry full-tier overview.
- **Action: MONITOR** (no action; recorded so a future refactor that batches decodes into a list
  — e.g. to implement Finding 1's zip-reuse fix — doesn't accidentally reintroduce O(entries)
  memory while fixing the CPU/IO cost).

### Verdict

CHANGES REQUIRED

Two NOW items (Findings 1-2), both measured (not hypothetical), both cheap and localized (no
architecture change — a batching fix inside `discovery.py`'s read path and a stopping-condition
change inside `cache.py`'s eviction sweep), and both squarely inside this role's brief ("prefer
batching," "cache-cap sweep cost," the exact two items the task asked to measure). Finding 3 is a
real, measured, one-time inefficiency that does not block on its own — reasonable to fix opportunistically
alongside Finding 1, not worth a separate pass. Findings 4-5 are clean: confirmed no action needed,
not just assumed.

Per `AGENTS.md`, "A change request from Security or Performance Reviewer re-enters the loop": these
two NOW items are implementation work and should go **Implementer → Reviewer (review of the fix) →
Definition of Done**, not straight to DoD and not applied ad hoc by the main loop.
