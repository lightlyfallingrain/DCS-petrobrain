# BL-16 M3 (terrain floor and look-ahead) — Performance Review

Branch `feature/bl16-lift-vector-law`, fast-forwarded cleanly into this worktree from `a29eff71`
to tip `0347b8c7` (`git merge --ff-only`, clean tree, confirmed strict ancestor before merging).
Diff reviewed: `ca0bcb50578ec9a9022d59b8dff0bc2de81dc75c..0347b8c79b691e465c6d3c2b4bd23e8120af5b02`
— matches `review-m3.md`'s own diffed range (M3's three commits plus two fix passes). This is the
one performance pass for the M3 batch (stages 1–4, built back to back per the plan's own
"Implementation plan" section).

Context (no hard real-time budget in this phase; the relevant project rules are "prefer
precomputation," "prefer batching," "no per-request allocations on hot paths," and "work at the
wrong frequency"). Functional correctness was already reviewed twice (`review-m3.md`,
`APPROVED` after two fix passes) — this pass only looks at runtime cost.

## Hot paths examined

- `law_update` (`flight_control.lua`, gated to `profile.law_hz` ≈ 30 Hz) — the new floor
  derivation (`f_eff`), `law_terrain_w_floor`, the power governor, the speed absorber.
- `run_active_frame` (`flight_control.lua`, every DCS frame, ~140 Hz) — the new terrain
  projection block that builds `measured.terrain`.
- The LOS Hook's `terrain_points` op (`petrobrain-line-of-sight-hook.lua`, `land.getHeight` via
  `net.dostring_in`, Hook's own 1 Hz tick).
- `parse_terrain_relay`/`extract_json_raw_string_field` (Lua, per incoming `flight_lease`, ~1 Hz).
- body-layer's poll loop: `_compose_and_relay_terrain` (`body.py`, called from
  `_apply_flight_requests`, ~1 Hz) and `belief/terrain_ahead.py`'s pure composer/encoder.

## Findings

#### 1. The terrain projection in `run_active_frame` allocates fresh tables every DCS frame (~140 Hz), but only `law_update` (~30 Hz, gated) ever reads the result

- **Location:** `aircraft-layer/dcs-export/Petrobrain/flight_control.lua:3453-3467`
  (`run_active_frame`), consumed only by `law_update` via `measured.terrain`
  (`law_update`'s own `w_floor = law_terrain_w_floor(measured.terrain, ...)`,
  `flight_control.lua:1255-1256`).
- **Shape:** `run_active_frame` runs unconditionally every DCS frame
  (`run_flight_control`, `flight_control.lua:3878`, "Every frame, from `LuaExportBeforeNextFrame`"
  per its own comment). Whenever a fresh, in-age, valid grid exists — the common case for the
  entire sortie once the Hook is up — it allocates a new outer table `terrain = {}` and one new
  `{d, point[3]}` table per grid point (up to `MAX_TERRAIN_POINTS`, 32; the user's own default
  geometry is 16) on **every** call. `law_update` itself only runs when `law_due()` says so
  (`profile.law_hz` ≈ 30 Hz) — confirmed by reading the call graph, not assumed from a name,
  per this role's own standing lesson about `_tick`-shaped functions in this file
  (`project_bl16_p3p4_cbtm_tick_is_5hz_not_perframe`). So roughly 4.5 out of every 5 projections
  this block computes are discarded unread the same frame they're built — "work at the wrong
  frequency" by construction, and the allocation itself is new: the LV-3 review
  (`project_bl16_lv3_hover_blend_bounded_scalar_cost`) found "no new table, string or closure
  allocation anywhere" in this file through LV-3; M3 is the first stage to add a per-frame
  allocation that scales with N (grid size).
- **Measured, not assumed** (`luajit -joff` and vanilla `lua 5.5`, both closer to the un-JITted
  Lua 5.1 interpreter DCS actually embeds than JIT-compiled LuaJIT): at `N = 16` points, the
  allocating shape costs **~0.9–1.5 µs/call**; an equivalent reusing two preallocated parallel
  arrays instead of fresh tables costs **~0.25–0.4 µs/call** — a real ~3–4x difference, but at
  140 Hz the allocating version's total overhead is **~0.13–0.21 ms of CPU per second**, against
  a ~7.14 ms per-frame budget (≈0.02–00.03% of real time), and the garbage generated is on the
  order of ~100 KB/s (17 small tables/frame × 140 Hz × ~45 bytes each) — a volume well within
  what any Lua GC absorbs without a visible pause. Script and raw numbers available on request;
  not checked into the worktree (a throwaway micro-benchmark, not a repo artifact).
- **Risk:** at the measured scale, this is not a credible frame-budget or GC-pause risk today.
  It would become one only if `MAX_TERRAIN_POINTS` grows substantially (currently 32, a protocol
  constant) or if a future stage stacks another per-frame, N-scaling allocation onto the same
  function — at which point the *pattern*, not any single instance, adds up.
- **Action: MONITOR.** Real and mechanically wasteful (the result is thrown away on most frames
  it's computed), and the fix is cheap and low-risk, but the measured cost does not clear the bar
  for "must fix now" at the Rules above ("do not demand optimization without evidence or credible
  risk at realistic scale"). Worth doing opportunistically the next time this function is touched,
  and worth re-measuring (not re-assuming) if `MAX_TERRAIN_POINTS` or the grid's default geometry
  changes.
- **Mitigation (if taken):** replace the fresh `terrain = {}` / `{d, point[3]}` allocation with
  two preallocated parallel arrays (`fc_terrain_proj_d`, `fc_terrain_proj_t`) plus a count field,
  overwritten in place each frame — the same fixed-capacity-array shape this file already uses for
  the estimator's ring buffers (`est_ring_*`). `law_terrain_w_floor`'s `ipairs(terrain)` would need
  to become a bounded `for i = 1, n do` over the count field rather than relying on the table's own
  length, since a reused array can carry stale entries past the current grid's size.

#### 2. A second, independent `GET /line_of_sight/latest` fetch added per poll, duplicating an existing one when expected-area checks are also open

- **Location:** `body-layer/src/body.py:4361` (`_compose_and_relay_terrain`, called from
  `_apply_flight_requests`, every poll once the command-reset epoch is confirmed — effectively
  every poll in flight) vs. the pre-existing `body.py:1955` (inside the expected-area-check
  resolution path, which returns early at `body.py:1913` — `if not checks: return` — when no
  check is open).
- **Shape:** the two call sites are independent fetches of the exact same collector-cached
  endpoint. They do **not** always both fire — the expected-area one is gated on `checks` being
  non-empty — but whenever an expected-area check happens to be open in the same poll cycle M3's
  terrain relay runs (i.e. most polls in flight), the poll loop now issues **two** separate HTTP
  GETs to `/line_of_sight/latest` for the identical cached snapshot, rather than fetching it once
  and sharing it.
- **Risk:** bounded and low — at most one extra idempotent LAN HTTP GET per poll (~1 Hz), to a
  server that only serves its own in-memory cache (no DCS-side work triggered by an extra GET).
  Not a correctness issue (both reads see the same data) and not scaling with anything. This is
  the "redundant queries" focus area, not a budget risk.
- **Action: LATER.** Not blocking — the absolute cost is one extra cheap LAN round trip,
  conditionally, once a second. Worth folding into a later touch of `_apply_flight_requests` or
  the expected-area path: fetch `GET /line_of_sight/latest` once per poll and pass the snapshot
  into both consumers, rather than teaching either side about the other's cache.

## Not flagged (checked, no concern)

- `law_terrain_w_floor` itself (`flight_control.lua:973-998`): O(N) scalar arithmetic over
  `measured.terrain`, N ≤ 32, no allocation inside the loop, called only at `law_hz` (~30 Hz) —
  the same "bounded scalar cost" shape this role has already accepted for LV-3's hover blend.
- The LOS Hook's `terrain_points` op (`petrobrain-line-of-sight-hook.lua`): `land.getHeight` × up
  to 32, fixed-shape `%d`-template splice (`SET_TERRAIN_TEMPLATE`), coalesced to one setter call
  per frame, evaluated at the Hook's own 1 Hz tick — matches the plan's own accepted cost
  (`~0.5 ms` fixed bridge overhead + `~1–9 µs`/point, from `2026-10-05-elevation-cost-probe-
  results.md`/`2026-09-29-bridge-call-cost-at-scale.md`) and the already-shipped `probe_points`
  op's shape exactly. No behaviour change to call frequency.
- `parse_terrain_relay`/`extract_json_raw_string_field` (Lua, per `flight_lease` ≈ 1 Hz):
  one regex match plus up to 32 small per-point table allocations, at 1 Hz — "16 points at 1 Hz is
  noise" per the plan's own value-against-effort note, and this role's measurement above confirms
  the per-call cost of this *shape* (allocate N small tables) is on the order of 1 µs even for the
  allocating variant; at 1 Hz it is immaterial regardless.
- `_compose_and_relay_terrain`/`belief/terrain_ahead.py` (Python, ~1 Hz): pure, O(N) geometry and
  string-join, N ≤ 32 — negligible at this cadence; `_terrain_sent` is pruned to a fixed 8 entries
  every poll (`_TERRAIN_SENT_KEEP`), so it cannot grow unbounded.
- `push_flight_control_state`'s new status-line fields (`fc_floor_eff_m`, `fc_terrain_n`, etc.):
  scalar reads/derivations at the existing 5 Hz push tick, same shape as every other status field
  already pushed there.

## Verdict

**APPROVED — MONITOR.** No finding rises to a budget-violation risk at measured/realistic scale;
both are real but bounded, and neither blocks this batch. Finding 1 is the one worth remembering —
it is a new allocation *pattern* for this file (scaling with grid size, at frame rate, consumed at
a slower gated rate) — fix it opportunistically next time `run_active_frame`/`measured.terrain` is
touched, and re-measure rather than re-assume if the grid size or call frequency changes.
