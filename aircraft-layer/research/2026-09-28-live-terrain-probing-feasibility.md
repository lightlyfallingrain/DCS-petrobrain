# Live in-mission terrain elevation probing — feasibility and cost

**Date:** 2026-09-28
**DCS version:** 2.9.29.27278 (per prior sessions' `autoupdate.cfg` read; not reprobed this session)
**Theatre:** n/a (scripting-API/architecture question, applies to any theatre)

### Question

Is live in-mission terrain elevation probing (`land.getHeight`, plus `land.getSurfaceType`)
feasible through the aircraft-layer setup that exists *today*, at what per-call/per-tick cost, and
does a return path already exist to persist samples in the world model's fog-of-war-style probe
store? This gates the incremental terrain-densification design the user has chosen in response to
the missed-AAA-detection defect (`plans/missed-aaa-detection/debug.md`, fix option 5).

### Base

`git rev-parse HEAD` → `570dccc` (feature/group-reporting tip in the main checkout; this worktree
was created from it, per the task). Investigated as pure research — no code touched.
`plans/missed-aaa-detection/debug.md` is not on this ancestry (`f518826`, on `main` but not yet a
main-checkout ancestor at this HEAD); read via `git show f518826:...` since the file itself is not
present at HEAD.

### Findings

**1. `docs/concept/PETROBRAIN_RUNTIME.md`'s recorded blocker is stale — confirmed, not merely
suspected.**

- **evidence: reproduced-locally (by reading the shipped, deployed code)** — **source:**
  `aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua`,
  `petrobrain-mission-telemetry-hook.lua`, `aircraft-layer/research/
  2026-09-22-mission-bridge-already-shipping.md`, `2026-09-21-unit-velocity-via-mission-scripting.md`.
- The blocker text (written 2026-09-08) says *"there is currently no live data path from a running
  DCS mission back into the persistent world-model store."* That was true when written, and false
  since 2026-09-13: `petrobrain-f10-commands-hook.lua` has run `net.dostring_in("scripting", ...)`
  in production since then (F10 command vocabulary, user-accepted live), and
  `petrobrain-mission-telemetry-hook.lua` has done the same for `Object.getVelocity()` since
  2026-09-22 (ACCEPTED live 2026-09-23). Both cross Hook state → mission-scripting state → loopback
  UDP → collector → LAN HTTP, in near-real time, at 1 Hz.
- **This sentence should be corrected in the concept doc** (Architect's call, not mine to edit) —
  it is actively misleading every reader who hits it, exactly as the task description suspected.

**2. `land.getHeight`/`land.getSurfaceType` are Mission Scripting API, and the mission-scripting
bridge already in production runs Lua *inside that exact environment*.**

- **evidence: documented** (function signatures/environment) — **source:** Hoggit
  `DCS_func_getHeight`/`DCS_func_getSurfaceType`; confirmed in `world-model/research/
  2026-09-03-m4-elevation-recon.md` Finding 1 and `2026-09-03-m5-roadnet-file-recon.md`'s
  companion note on `getSurfaceType`.
- **evidence: inferred, high-confidence, not yet directly reproduced against this exact call** —
  the `"scripting"` state that `net.dostring_in` targets is the same Mission Scripting environment
  `missionCommands`, `coalition.getGroups`, `Object.getVelocity()`, and `timer.getTime()` are all
  confirmed-live inside (per the F10/velocity hooks). `land.*` is documented as living in the same
  environment with no per-function override on Hoggit. **No prior session has actually called
  `land.getHeight` through `dostring_in` and read back a number** — every prior probe of
  `land.getHeight` (M4/M5) ran as a mission-editor "DO SCRIPT" trigger inside a throwaway mission,
  writing to `net.log`/`io.open` for offline batch collection, not through the Hook bridge. The
  inference is strong (same state, same sandbox, functions in the same documented table) but is
  not the same as having watched it work.
- **What would settle it, cheaply, without a new channel**: a one-line addition to
  `petrobrain-mission-telemetry-hook.lua`'s existing `VELOCITY_CODE` string (or a throwaway sibling
  snippet), e.g. `return tostring(land.getHeight({x=ownship_x, y=ownship_z}))`, run once through the
  already-flying bridge on the next sortie. This does not need a new Hook script, a new port, or a
  new collector endpoint — it reuses machinery already deployed. I did not run this (execution
  against the live install is the user's boundary) — see Unresolved.

**3. Throughput/safety — genuinely unmeasured, and the closest analog says "probably fine at low
N, unknown at scale."**

- **evidence: reproduced-locally (self-measurement design exists) + inferred (extrapolation to
  terrain queries)** — **source:** `aircraft-layer/ROADMAP.md`'s unit-velocity entry,
  `aircraft-layer/research/2026-09-26-performance-review.md` finding 3,
  `.claude/agent-memory/performance-reviewer/project_aircraft_layer_hotspots.md`.
- The velocity hook already does the closest available thing to what elevation probing would need:
  one `dostring_in` call per poll running an **O(N) loop inside the mission-scripting state**
  (not N separate bridge calls), self-measuring `bridge_call_ms`/`unit_count` via `os.clock()` and
  logging both to `dcs.log`. This pattern is directly reusable for a chunk of elevation points: one
  `dostring_in` call per probe batch, looping over the batch's points inside the state, returning a
  packed string.
- **The self-measurement has never actually been read.** As of 2026-09-26 (performance review),
  `bridge_call_ms` has never been captured from a live sortie with a realistic population — the
  only flown sortie (2026-09-22 acceptance) had twelve units, "well below the 50-200 range that
  would stress this." So there is no number for "cost of an O(N) dostring_in call" at any N, for
  *any* payload type, let alone elevation specifically.
- **The existing offline terrain probes (M4/M5) independently establish a chunking discipline that
  transfers directly**: `terrain_probe_full.lua` processes points in batches of 20 per
  `timer.scheduleFunction` tick specifically because "one giant loop holding results in memory"
  was flagged as a defect in review. That discipline is about *not blocking one mission-scripting
  tick for too long*, which is exactly the risk an in-flight probe batch would carry too — so the
  chunking pattern is reusable, but it was tuned for an offline batch write to a file, not for
  cost-per-`dostring_in`-call over the Hook bridge, which is the actually-unknown variable here.
- **My reasoned estimate, not a measurement**: F10's poll (a handful of small string ops) and
  velocity's poll (an O(N) loop, N≈12 in the only flown test) are both comfortable at 1 Hz. A
  100-point elevation batch (one probe-store chunk row at M8's locked 100 m spacing is 2,601
  points, not 100 — see Finding 5) is two orders of magnitude more per-call work than the velocity
  hook's flown case. Whether that is "fine" or "a frame hitch" is not derivable from anything
  measured so far — it needs the same self-measurement pattern applied and actually flown.

**4. Return path exists on the collector's LAN API pattern side, but no endpoint for this exists
yet — and the better seam is direct file transfer, not a new HTTP endpoint.**

- **evidence: reproduced-locally (reading the shipped API surface)** — **source:**
  `aircraft-layer/CLAUDE.md`'s endpoint list, `src/api/`, `src/collector/`.
- Every existing write-adjacent channel (`/text/push`, `/command/petrovich_search`, `/audio/play`,
  `/f10_commands/poll`) is collector-mediated, loopback-UDP-to-a-Hook-script, small fixed
  vocabulary. None of them is the right shape for *pulling probe samples off the Windows box and
  into the Mac's `world-model/data/world-model/<region>-probe.sqlite`* — that store lives on the
  Mac, is written by `probe_store.writer`/`build.pipeline.add_probe_chunk` (Python, world-model's
  own code), and nothing in aircraft-layer's process ever touches SQLite today.
- **This is new plumbing, not a design decision I should make** — Architect's call — but the seam
  is visible: either (a) the collector gains a new endpoint that accumulates elevation samples and
  a periodic Mac-side puller writes them into the probe store via `add_probe_chunk` (matching the
  existing collector→LAN-poll pattern, adds one more `/elevation_probe/latest`-style endpoint), or
  (b) probe samples are written straight to a local file on the Windows box by the Hook script
  itself (mirroring the *offline* M4/M5 pattern) and synced/ingested in a batch — cheaper to build,
  but reintroduces the manual round-trip the whole point of this exercise is to avoid. (a) fits the
  "within the same flight" requirement in the concept doc; (b) does not.
- **`world-model.probe_store`'s write side is ready to receive whichever path is chosen** —
  `open_probe_store`/`add_probe_chunk` (`world-model/src/build/pipeline.py`,
  `world-model/src/probe_store/writer.py`) already accumulate chunk-by-chunk, already have the
  tri-state coverage table (`UNQUERIED`/`QUERIED_VOID`/covered, keyed `(kind, chunk_ix, chunk_iz)` —
  the exact "don't rescan what we already have" mechanism the user described), and measured cheap
  on the write side: **~23 ms for one full 2,601-point `add_probe_chunk` call, ~0.4 ms for a
  `describe_position` read with the probe store attached** (Apple Silicon Mac, local disk, single
  run — `plans/m8-incremental-store/implementation.md`). The Mac-side store is not the bottleneck;
  the DCS-side probe call is the open question (Finding 3).

**5. Resolution/range arithmetic — affordable *if* the per-call cost turns out reasonable, moot
otherwise.**

- **evidence: inferred (arithmetic on locked parameters, no live rate to plug in)**.
- M8's locked probe-store parameters: chunk size 5,000 m, probe spacing 100 m → 2,601 points per
  full chunk (51×51 grid). A 10 km-radius bubble is ~12.6 chunks by area (`π·10000² / 5000²`), i.e.
  up to ~32,700 points if densified uniformly to 100 m everywhere inside the bubble — the user's
  own framing ("fine close, coarser further, not at all beyond the bubble") argues against
  uniform 100 m across the whole 10 km radius; a coarser spacing further out (e.g. 250-500 m)
  would cut that by 6-25x. Either way, **the point count itself is not the constraint** — 32,700
  points is trivially cheap for `add_probe_chunk` (Finding 4's ~23 ms/chunk, so ~5 s total DB
  write time for the whole bubble if it arrived all at once, which it never would). **The
  constraint is entirely how many points per `dostring_in` call, and how many calls per second,
  DCS tolerates without a frame hit — which is Finding 3's open number.** I cannot give sortie-
  coverage-time arithmetic without that rate; a placeholder shape (assuming, unverified, that a
  100-point batch per 1 Hz poll is safe — i.e. the same order of magnitude as the velocity hook's
  flown 12-unit case, times ~8): covering one chunk (2,601 points) would take ~26 polls (~26 s);
  covering the reduced (coarser-outward) bubble described above would be on the order of a few
  minutes of flight, which fits comfortably inside "a sortie." This is a **shape**, not a number to
  design against.

### Reproducible Test

None run this session — this is desk research per the task's explicit boundary ("do not run a
live probe yourself"). Two things exist and are ready to run on the next sortie:

1. **Elevation-through-bridge existence check** — add one `land.getHeight` call to a throwaway
   `dostring_in("scripting", ...)` snippet (reusing `petrobrain-mission-telemetry-hook.lua`'s
   existing plumbing/poll timer as a template) and confirm a real number comes back over the
   bridge. Settles Finding 2's remaining gap.
2. **Cost-at-scale check, already designed and already deployed, just never read**: fly any
   sortie with 50-200 units/statics present and `grep "velocity poll:"` (or the exact log prefix
   `petrobrain-mission-telemetry-hook.lua` uses) in `Saved Games\DCS\Logs\dcs.log` for the
   `bridge_call_ms`/`unit_count` trend. This doesn't answer the elevation-probe cost directly (a
   `getVelocity()` loop and a `getHeight()` loop are different work per iteration), but it is the
   single best proxy that exists today for "how expensive is an O(N) `dostring_in` payload," and
   costs nothing new to capture.

### Possible Approaches

Not picking one — laid out for Architect:

- **A. Batch elevation probing over the existing bridge**, same shape as the velocity hook: one
  `dostring_in("scripting", ...)` call per poll, looping over a chunk (or partial chunk) of
  `(x, z)` points inside the mission-scripting state, packing results into one delimited string
  (same "one scalar across the boundary" constraint the velocity hook already works around),
  self-measuring `bridge_call_ms`/`point_count` exactly as that hook does. New Hook script (own
  lifecycle, mirroring the "third independent Hook script" precedent) or an extension of the
  velocity hook — Architect's call, same reasoning that kept the velocity hook separate from the
  F10 hook applies here.
- **B. New collector endpoint + Mac-side puller** for the return path (Finding 4's option (a)):
  collector accumulates elevation-probe samples in a bounded cache/queue (mirroring
  `F10CommandQueue`'s drain-all pattern), a small Mac-side process (or the eventual Runtime
  process itself) polls it and calls `add_probe_chunk` once enough points for a chunk have
  accumulated, or on a timer.
- **C. Look-ahead ring / throttle policy** (concept doc's own idea) is unaffected by anything found
  here and remains a pure policy question once (A)/(B) exist — decide *after* Finding 3's rate is
  known, not before, since the throttle's safe rate is exactly what's missing.
- **If Finding 3 comes back expensive** (a real frame hit at any usable N): fall back to a lower
  poll rate (e.g. one small batch every 2-5 s instead of every 1 s) before abandoning the live-probe
  idea — the existing bridge headroom (F10 and velocity both run comfortably at 1 Hz with far
  smaller payloads) suggests there is room to trade rate for batch size long before this becomes
  infeasible.

### Unresolved

- **Whether `land.getHeight`/`land.getSurfaceType` actually return correct values through
  `dostring_in("scripting", ...)`** — inferred from the shared-environment argument (Finding 2),
  never directly watched. **Resolves with:** Reproducible Test item 1 above, on the next sortie
  for any reason.
- **Per-call cost of an O(N) `dostring_in` payload at realistic N, for *any* payload shape** — the
  velocity hook's self-measurement has never been read from a real sortie (Finding 3).
  **Resolves with:** Reproducible Test item 2 — fly with 50-200 units present, read `dcs.log`.
  This is the single most load-bearing open number in this whole feasibility question; nothing in
  Finding 5's arithmetic is safe to design against until it exists.
- **Per-call cost specifically for `getHeight`/`getSurfaceType`, as distinct from `getVelocity`** —
  even once Finding 3's proxy exists, terrain queries may cost differently (different underlying
  engine call, e.g. potentially a raycast/heightfield sample rather than a stored per-unit field).
  **Resolves with:** the same self-measurement pattern applied to an actual elevation-probe Hook
  snippet (Reproducible Test item 1, extended to log its own `bridge_call_ms`/`point_count`), flown
  at a batch size worth testing (e.g. 100, 500, 2601 points) before committing to a production
  batch size.
- **Whether a `dostring_in` call of this shape blocks DCS's own frame** (the aircraft-layer
  `CLAUDE.md` invariant: "`Export.lua` runs on DCS's own thread — cost here means cockpit stutter,
  not service latency") **vs. only costing wall-clock time inside the Hook/mission-scripting
  states** — not established anywhere in prior research for *any* `dostring_in` payload, velocity
  included. This matters more for terrain probing than it did for velocity, because the batch
  sizes under consideration (hundreds-thousands of points) are much larger than a typical unit
  count. **Resolves with:** the same live measurement, read against DCS's own frame-time/FPS
  counter simultaneously (the aircraft-layer performance review already recommends this exact
  cross-check for the unrelated `LoGetWorldObjects` 5 Hz question — same technique applies here).
- **Exact wire/endpoint shape for the return path** (Finding 4) — deliberately left as two named
  options rather than resolved, since designing it is Architect's job, not this pass's.
- **No DCS install file is needed to resolve any of the above** — everything outstanding needs a
  live sortie, not a file fetch, so there is nothing to ask the user to pull from the Windows box
  this time.
