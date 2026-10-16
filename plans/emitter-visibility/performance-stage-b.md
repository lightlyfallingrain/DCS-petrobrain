### Performance Review — Stage B

Reviewed `feature/emitter-events` @ `6e61488` (Stage B of `AC-B8`/`BL-B73`: the production
firing-event channel — Lua Hook, collector `EmitterTracker`, body-layer's `firing_emitters`/
`resolve_emitters`, the LOS sightline-cap mitigation). Stage A's gate-bypass/burning-emitter
findings are in `plans/emitter-visibility/performance.md` and are not repeated here. No real-time
budget applies to this phase (Petrobrain Runtime has not started); the realised poll period is
~1.3-1.4 s (1.0 s default interval + the loop's own post-work sleep, `BL-11`'s own measurement —
not the stale "5 Hz specified / 0.7 Hz actual" framing, which is wrong and already corrected in
agent memory).

Per the dispatch's framing: the event channel's hot path, the Lua-side cost (most expensive place
to spend time in this system), and the LOS sort-key splice.

### Findings

#### The event-channel drain is O(events), not O(active-map) or O(theatre)
- **Location:** `aircraft-layer/src/collector/firing_receiver.py`, `EmitterTracker.ingest()`.
- **Mechanism:** `ingest()` does three things per received batch: (1) one O(1) regression check
  against `_last_dcs_model_time_s`; (2) `for event in batch.events: self._apply(event, now)` — one
  dict write per event, O(events-in-this-batch); (3) a prune pass,
  `[name for name, emitter in self._active.items() if now > emitter.expires_at_sim]`, which is
  O(active-emitters), not O(theatre) or O(events). `_apply` itself is O(1) per event — a dict
  lookup/write or delete, no nested loop over `_active`.
- **Sustained-fire scaling (the feature's own target scenario, an AAA battery):** the quantity that
  scales with "many units firing at once" is `len(self._active)`, which is bounded above by the
  number of distinct units DCS currently reports as firing — realistically single-to-low-double
  digits in any scene this project's own measured candidate counts support (`~10 units/poll reach
  the LOS gate` per `[[project_dcs_driven_los_cone_scoping]]`, and the whole bubble-filtered
  candidate pool tops out in the hundreds per `BL-11`'s own numbers). There is no mechanism here by
  which a sustained burst grows the per-poll cost superlinearly — each additional firing unit adds
  one dict entry and one prune check, not a cross-product with anything else.
- **What is genuinely unmeasured, and correctly flagged as such by the implementer:** whether
  `S_EVENT_SHOOTING_START` retrigs mid-burst (Risks & Unknowns, the open DCS question). If it does
  retrigger per round rather than once per trigger-pull, `batch.events` could carry many entries per
  poll per gun during sustained AAA fire — but even then, `_apply`'s per-event cost is O(1) and the
  dict write for the same `event.initiator` just overwrites the same key repeatedly (`ActiveEmitter`
  is looked up and updated, not appended to a list), so a retriggering burst costs more *events
  processed*, linearly, not a new cost *shape*. Not a performance risk even in the retrigger case —
  the thing the open question would change is correctness (watchdog floor), not asymptotic cost,
  and that correctness question is already tracked by the Reviewer/implementer, not this role's to
  re-litigate.
- **Action:** none needed — clean negative, confirmed by reading `ingest`/`_apply`/`snapshot`, not
  assumed from the implementation summary.

#### `snapshot()` and the body-layer join: O(active) and O(theatre), once per poll each
- **Location:** `EmitterTracker.snapshot()` (one dict comprehension over `self._active`);
  `body-layer/src/perception/emitters.py`'s `firing_emitters`/`resolve_emitters`, called once per
  poll from `naked_eye_source.poll()`.
- **Confirmed:** `snapshot()` is O(active-emitters) — the same small set `ingest` already bounds.
  `firing_emitters` is O(raw_objects) (one `Counter` pass + one result-build pass over the
  theatre-wide object list, same scope `burning_emitters` already pays, confirmed clean in Stage A's
  review) with an O(1) `firing_active.get(name)` lookup per object. `resolve_emitters` runs both
  `burning_emitters` and `firing_emitters` and merges with `dict.update` — twice the pass count
  Stage A had (4 full passes over `raw_objects` instead of 2), but still linear, still once per
  poll, still over the same already-fetched, already-theatre-scoped list every other join in this
  module walks. No per-candidate cost at the call site beyond the pre-existing `dict.get`
  (`emitter_by_object_id.get(candidate.object_id)`, O(1), confirmed at
  `naked_eye_source.py:739`/`840`).
- **Action:** none needed — clean negative. Doubling a cheap O(N) pass that was already "none
  needed" in Stage A's review stays "none needed" in Stage B; it is not a new cost class, just one
  more instance of the existing one.

#### `get_firing_latest()`: one more synchronous HTTP call in the poll body, same posture as the existing ones
- **Location:** `body-layer/src/aircraft_client.py`'s `get_firing_latest()`;
  `naked_eye_source.poll()`'s call site, independently-degradable via `AircraftLayerError` → `None`.
- **Risk:** this is a fourth synchronous LAN round-trip in the poll body (telemetry, world objects,
  unit velocity/LOS, and now firing), on top of the five-GET loopback-floor figure `[[project_body_
  layer_poll_loop_diagnosis]]` already measured (3.4 ms loopback floor, but up to 2.0 s per-request
  timeout worst case — an existing, already-tracked risk, not a new one). This call follows the
  exact same shape (`get_line_of_sight_latest`'s sibling, per the implementer's own account) and the
  exact same timeout/degrade contract as the LOS/velocity calls already in that chain — it adds one
  more instance of a risk this project already knows about, not a new risk shape.
- **Action:** MONITOR, folded into the existing tracked risk rather than a new line item — the
  fix (if one is ever needed) is a shared concern across all five GETs, not specific to this one.

#### Lua-side: the event handler itself, and the LOS sort-key splice
- **Location:** `aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua`'s `onEvent` handler
  (runs inside `world.addEventHandler`'s dispatch, i.e. on every world event DCS raises, not just
  the five kinds this feature wants); `petrobrain-line-of-sight-hook.lua`'s sort-key splice.
- **`onEvent`'s per-event cost is O(1) and the filter is cheap.** Every engine event in the mission
  reaches this handler (unit spawn, every hit, every kind the probe's own sortie saw a dozen of:
  `BDA`, `HUMAN_FAILURE`, `SIMULATION_FREEZE`, ...) — `eventNames[event.id]` is one table lookup to
  resolve the name, `ALLOWED_KINDS[kind]` is one more table lookup to early-return on anything not
  in the five-kind allowlist. Both O(1). For the five kinds that do pass, the handler does a bounded
  number of `pcall`-guarded field reads (`safeName`, `targetsOwnship`, `initiatorPosition` — each
  itself O(1), one or two engine calls) and one string-concatenation append to
  `PB_FIRING_EVENT_QUEUE`. **This runs on DCS's own thread, inside the `"scripting"` state, for
  every event the simulation raises** — the one place in this project where cost means cockpit
  stutter. There is no profiler for DCS-side per-event Lua cost in this project
  (`[[project_dcs_driven_los_cone_scoping]]`'s standing gap, which recurs here identically), so this
  is reasoned by shape, not measured: an O(1) hash lookup per engine event, for events this project
  has already observed firing at a rate low enough for the probe's own sortie log to read cleanly,
  is the same cost class as `S_EVENT_SHOT`'s existing damage-events probe handler already ran live
  with no reported stutter. Not a credible new risk at this project's current scale; worth the same
  "read it from a flown log, don't guess" treatment the telemetry hook's `bridge_call_ms` already
  gets, if DCS ever ships a per-callback cost counter.
- **`EVENT_POLL_CODE`'s drain is O(events-in-queue), bounded by the same small count `ingest` is
  bounded by** — a copy loop plus `table.concat`, once per second, not per event.
- **The LOS sort-key splice is the dispatch's named concern, and it is cheap, read once per call —
  confirmed by reading the diff, not assumed.** `local firingUnits = PB_ACTIVE_FIRING_UNITS or {}`
  is a single table reference taken **once**, outside the comparator, immediately before
  `table.sort` — not re-read or re-resolved per candidate or per comparison. The comparator itself
  (`firingUnits[a.name] ~= nil`, `firingUnits[b.name] ~= nil`) adds two hash-table lookups per
  comparison where there was previously one float comparison (`a.rangeM < b.rangeM`). `table.sort`
  is still O(n log n) comparisons on the same candidate list Stage A/pre-existing code already
  sorts every poll (bounded by `MAX_SIGHTLINES_PER_CALL = 128` candidates, since this runs on the
  already-wedge-filtered list the splice's own comment and the existing cap bound) — the splice
  changes the comparator's constant factor (two extra O(1) hash lookups per comparison) and nothing
  about the algorithm's shape or bound. At n ≤ 128, this is noise next to the two actual raycasts
  (`world.searchObjects`/`land.isVisible`) the same Hook performs per candidate, which is the
  dominant cost in that file by a wide margin (`[[project_dcs_driven_los_cone_scoping]]`'s own
  25 µs/sightline peak figure, versus a sort comparator operating on numbers/table lookups).
- **Action:** none needed for the splice itself — clean negative, confirmed by reading the code.
  MONITOR (not new) for the general "no per-event/per-frame Lua profiler exists" gap, which this
  feature inherits rather than introduces.

#### What the bypass admits downstream, for a firing unit specifically
- **Location:** `visibility.check_visibility`'s gate 3/5 bypass (unchanged from Stage A — Stage B
  adds no new gate logic, per the plan's own "nothing in `visibility.py` changes in Stage B" and
  confirmed by `git diff main..feature/emitter-events -- body-layer/src/perception/visibility.py`
  showing no Stage-B-attributed hunk).
- **Risk:** identical shape to Stage A's already-reviewed finding (more candidates reaching
  gate 4+, one more clustering/association pass per admitted candidate, no new per-candidate
  mechanism) — a firing unit is just one more kind of candidate that can trigger the same bypass a
  burning unit already could. The 128-sightline-cap exposure this unlocks for firing units
  specifically (an exposure Stage A did not have, since Stage A's bypass only matters for distant
  burning units and the plan correctly scoped the cap mitigation to Stage B) is the one thing Stage
  A could not assess and Stage B now closes: a firing unit at any range is spliced ahead of the
  nearest-first truncation (previous finding), so it reaches gate 4 with a real verdict rather than
  the fail-closed `None` a truncated-out candidate would get.
- **Action:** none needed beyond Stage A's existing MONITOR (real burning/firing-candidate counts
  in a live engagement, via the detection trace's `emitter_kind` column) — this is the same
  measurement obligation, now also covering the `FIRING` kind, not a second obligation.

### Verdict

APPROVED — MONITOR

No required or recommended fixes. Stage B's event-channel hot path (collector `ingest`/`snapshot`,
body-layer's `firing_emitters`/`resolve_emitters`) is O(events) and O(active-emitters)/O(theatre)
respectively, both bounded by quantities this project has already measured as small at realistic
scale, with no mechanism by which sustained multi-unit fire produces a cross-product or
superlinear cost. The Lua-side sort-key splice this dispatch specifically asked about is read once
per call, outside the comparator, adding a constant-factor cost to an already-bounded
(≤128-candidate) sort that is dwarfed by the same Hook's own raycast cost. The two MONITOR items
(the fourth synchronous LAN GET, folded into an existing tracked risk; and the standing absence of
a DCS-side per-event/per-frame Lua profiler, inherited not introduced) are measurement obligations
this project already owes, not defects in this diff.
