### Performance Review

**Branch:** `feature/dcs-driven-los`, verified tip `bcc96fe7883f6af4e50b3b30a8fbe9a1b3424c22`.
This worktree's own HEAD (`01d84d0e6224...`, branch `worktree-agent-a471d4cb0d3975e97`) is **not**
an ancestor of that tip — confirmed via `git merge-base --is-ancestor`, as the dispatch warned.
All reading, grepping and reasoning below was done against an isolated snapshot:
`git archive feature/dcs-driven-los` extracted to
`/private/tmp/claude-501/-Users-sg-Code-DCS-petrobrain/912e8304-06e6-47eb-b21d-2480a8d16101/scratchpad/dcs-driven-los-snapshot`.
No commands were run against this worktree's own checked-out code (it is the wrong code); no
venv/pytest/mypy was invoked by this pass — Reviewer and Security already ran and recorded the
mechanical checks (252 / 1457+4xf / 550+3skip) against the same tip, and this pass does not
re-derive them. This is a static/reasoning review of cost shape, not a flown or profiled one — no
DCS, no profiler available to this agent. Everything below is labelled **measured** (carried
forward from the plan's own flown probes/logs) or **estimated/reasoned** (this pass's own
arithmetic over the code as written).

### Findings

#### Full-theatre unit enumeration inside `LOS_CODE`, every poll
- **Location:** `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`, `LOS_CODE` lines
  261–292 — iterates `coalition.getGroups(coa)` → `getUnits()` across all three coalition sides,
  computing a range check (`sqrt`) for every live unit in the theatre, before the 10 km bubble and
  look-direction wedge filters are applied.
- **Risk:** this is O(all theatre units) arithmetic once per second (1 Hz `POLL_INTERVAL_S`), not
  bounded to the bubble or wedge. At the plan's own measured worst case (568 units theatre-wide,
  `dcs.log`, 2026-09-29), that is ~568 `sqrt`+`atan2` calls/poll.
- **Action:** MONITOR, not NOW. **Reasoned, not measured**: this is the identical enumeration
  shape `petrobrain-mission-telemetry-hook.lua` already runs live at the same 1 Hz cadence for unit
  velocity (confirmed by grep — same `coalition.side` / `getGroups` / `getUnits` triple loop), and
  that script is shipped and flown without a reported stutter. The per-unit work here (one
  subtraction, one `sqrt`, later one `atan2` for the ~172–195 units that pass the bubble check) is
  pure Lua arithmetic, not an engine call — it carries none of the measured per-sightline cost
  (8.7–15 µs) that motivated the whole cone-scoping design. Nothing in this plan's own cost
  measurements (Finding 21, the elevation-cost probe, Stage 0/§8) separately prices this
  enumeration, because it was never the expensive part — `world.searchObjects`/`land.isVisible`
  are. No mitigation proposed; flag for the first flown log in case the theatre-unit count ever
  grows enough to matter, which nothing on this branch indicates.

#### Worst-case single bridge call if the wedge filter misbehaves
- **Location:** `LOS_CODE` line 322, `if sightlinesComputed >= 128 then break end` (the inner,
  hardcoded guard) vs. the outer `local MAX_SIGHTLINES_PER_CALL = 128` (line 177) — two independent
  literals, already flagged by both Implementer and Reviewer as having no mechanical guard tying
  them together.
- **Risk:** worked through as asked. If the cone filter (bubble + wedge, lines 269/276) were
  disabled or broken so that every candidate reaches the sightline loop, the **inner literal is
  what actually bounds the call**, truncating at 128 sightlines regardless of what the outer
  constant says. At the plan's own peak-cost figure (25 µs/unit, buildings+terrain, Finding 21 +
  the 2026-10-05 note), 128 sightlines is **~3.2 ms** — well under the 24–26 ms single-call cost
  that produced the user's reported stutter, and under one 60 fps frame (16.7 ms). So the specific
  failure mode asked about ("only the inner literal holds") is bounded and safe by the plan's own
  arithmetic, which this pass re-derived rather than took on trust (128 × 25 µs = 3,200 µs = 3.2
  ms, consistent with the plan's §10 table).
- **Action:** MONITOR for the duplication itself (already an Optional Refinement in `review.md`,
  not required), **not a cost finding** — the worst case the duplication could produce (drift to a
  larger inner literal with no outer guard noticing) is still a single bounded constant, not
  unbounded growth. A mechanical test mirroring the `%d`-count guard (grep both literals, assert
  equal) would close the drift risk cheaply; not blocking.

#### Cone scoping correctness — what the Hook queries if the directive never arrives
- **Location:** `LOS_CODE` lines 230–231 (`PB_LOOK_HOUR or 0`, `PB_LOOK_FOV_DEG or 45`) and the Lua
  file's `HOUR_DEFAULT`/`FOV_DEFAULT_DEG` constants (lines 193–194).
- **Risk:** traced rather than trusted, per the dispatch's instruction. If no look-direction
  command has ever arrived this mission-scripting-state lifetime (fresh mission start, lost UDP
  packet, collector not yet sending), the Lua-side `or` defaults resolve to **hour 0, 45° half-angle
  (90° full)** — never to "everything in the bubject" and never to `nil`/unset. This is the second
  revision's own "ships" default (§10), reused correctly at the point that matters. Worst case under
  this path, at the measured peak rate: ~43 units estimated (§10's own uniform-azimuth estimate,
  labelled estimated there and here) ≈ **~1.1 ms estimated** — still far under budget. The directive
  arriving stale (lagging wedge) only costs *coverage* (a unit Petrovich is looking at gets no
  verdict that poll, falls back to `None` → today's offline path), never a wider/more expensive
  query — confirmed by reading the tri-state join (`naked_eye_source._resolve_los_by_unit_name`)
  and gate 4 (`visibility.py` lines ~784–791), not assumed from the plan's prose.
- **Action:** APPROVED, no action. This is the one place the design explicitly reasoned about and
  the code matches the reasoning.

#### Per-frame work added inside DCS (look-direction socket poll)
- **Location:** `petrobrainLineOfSight.onSimulationFrame` (lines 504–521) — calls
  `pcall(pollLookDirection)` every frame (60 Hz), which does a non-blocking `receivefrom()` loop
  (bounded at `MAX_LOOK_DIRECTION_DATAGRAMS_PER_FRAME = 20`) before the existing 1 Hz gate.
- **Risk:** new per-frame work on the DCS thread, same category the dispatch flagged (SPU-8's three
  `get_argument_value` reads/frame on the same file family). **Estimated, not measured**: in steady
  state (no pending datagram — the common case, since look-direction only pushes on change) this is
  one non-blocking socket syscall returning immediately with no data, the same shape
  `Export.lua`'s own `try_open_command_socket` already runs live every frame. No profiler is
  available to this agent to put a number on it; nobody has measured any Lua Hook script's per-frame
  overhead in this project to date (confirmed: the `Optic-policy`/`Cockpit-mask` measurements in
  memory are body-layer Python, not DCS-side Lua).
- **Action:** MONITOR. Reasoned to be cheap by analogy to a shipped precedent (`try_open_command_
  sender`'s pattern), consistent with this agent's own memory note on the SPU-8 case (same
  reasoning, same disposition). **What would actually confirm it**: nothing short of a live sortie
  with frame-time logging — name this on the acceptance card already present in `implementation.md`
  rather than treat it as a gap this review can close. It is not currently on that card; recommend
  adding "note any felt frame irregularity, independent of the 1 Hz LOS poll" to Stage 4.

#### Body-layer join and `annotate_los` — checked against the BL-B23/BL-B26 shape, not reproduced
- **Location:** `naked_eye_source._resolve_los_by_unit_name` (lines 1066–1130ish) and
  `DetectionTraceCollector.annotate_los` (`detection_trace.py` lines 253–279), called once per
  bubble candidate in the per-candidate gate loop (`naked_eye_source.py` line 581), **for every
  candidate regardless of gate outcome** — exactly the shape named in the dispatch as the pattern
  that has bitten this project twice.
- **Risk assessed, not found:** `_resolve_los_by_unit_name` builds one `Counter` and does one
  dict-keyed pass over `objects` (the bubble-filtered set, ~172–195 per the plan's own Stage 0
  measurement) — **O(n), not O(n²)**, run once per poll (5 Hz, the naked-eye channel's own
  cadence), not per-pair and not per-tick-times-contacts the way `_cluster_contacts` or the
  pre-fix `ContactStore` were. `annotate_los` itself is a six-field assignment onto an existing
  dataclass instance already indexed by `object_id` in `_last_by_object_id` — O(1), no allocation,
  no re-scan. **This is not the BL-B23/BL-B26 shape** (work scaling with total-ever-seen or with
  pair count); it scales with the live bubble population per poll, which is what gate 4 already
  iterates over for every other field (`velocity`, `confidence`, motion). Calling it unconditionally
  (not gated on `ADMITTED`) costs nothing extra per call — it's the same dict write either way — so
  the Implementer's choice to annotate every outcome for attributability is free, not a tradeoff.
- **Action:** APPROVED, no action.

#### Engagement term (`ContactStore.tick`, belief) — net cost reduction, not a new risk
- **Location:** `belief/contacts.py`, the engagement term's seventh block (~lines 1340–1390).
- **Finding:** this plan **deletes** a live per-tick call into world-model (`_threat_has_los`,
  which ran a three-point uncertainty sweep against a believed position) and replaces it with a
  plain attribute read (`contact.live_los_clear`) already carried on the `Contact` from perception.
  That is strictly cheaper than what it replaces — fewer calls, no cross-module query, no sweep.
  The watch-count-is-uncapped condition noted in this role's own memory
  (`project_watch_reporting_scale_notes.md` / `project_divides_between_and_group_tick_multiplicity.md`)
  is pre-existing (an `AttentionArea` can still pull an arbitrary number of contacts into watch-
  equivalent attention, and this tick still runs per watched contact) — **not introduced or
  worsened by this plan**, which only changed what each per-contact check costs, not how many
  contacts it runs for.
- **Action:** APPROVED, no action. Noting for the record since it is adjacent to a known watch-list
  scale item, in case that item is picked up later: this plan does not need to be revisited when it
  is.

#### Things scaling with sortie length rather than the picture — checked, none found
- Looked specifically for this, per the dispatch's third ask. `Contact.live_los_clear` is an
  overwrite (not a fold, not an accumulating structure) — same as `last_class_raw`. The
  `DetectionTrace` fields are per-poll dataclass fields, written through the existing
  `_last_by_object_id` dict that already exists for `annotate_motion`; `detection_trace_writer.py`
  needs no change precisely because nothing new accumulates there (confirmed by Reviewer's grep,
  re-confirmed here by reading `annotate_los`'s body: it mutates in place, appends nothing). No new
  caches or lists keyed by anything that only grows. The pre-existing `ContactStore` pruning gap
  (`project_contact_store_never_pruned.md`) is untouched by this plan — it was never a consumer or
  producer of LOS data.
- **Action:** APPROVED, no action.

### What is measured vs. estimated, summarized

| figure | status | source |
|---|---|---|
| ~10 units/poll reach the LOS gate (median) | **measured** | plan §8, flown sortie log |
| 172/179/195 units/poll in the 10 km bubble (p50/p90/max) | **measured** | plan §8/Stage 0 |
| 8.7–15 µs/sightline (buildings/terrain, peak) | **measured** | Finding 21 + 2026-10-05 note |
| 128-sightline guard ≈ 3.2 ms worst case | **derived from measured figures** (this pass) | 128 × 25 µs |
| ~43 units / ~1.1 ms under the no-directive-yet default (45°) | **estimated** (plan's own, uniform-azimuth, explicitly distrusted by §8/§10) | plan §10 |
| per-frame look-direction socket-poll cost | **not measured, no profiler available** | reasoned by analogy only |
| 18–20 ms payload-indifferent `dostring_in` tail | **measured, separately, in prior work** | bridge-cost note Finding 3 — not this feature's cost, not reproduced by it |

### Verdict

**APPROVED — MONITOR**

No required performance fix. The design's own cone-scoping measurement work (Stage 0, §8–§10) is
sound and this pass's independent re-derivation of the worst-case bounded call (128 × 25 µs ≈
3.2 ms) confirms the headline safety property holds even under the failure modes named in the
dispatch (cone filter disabled, directive never arrives). Two items are MONITOR rather than NOW:
the duplicated `128` literal (already an Optional Refinement in `review.md` — a drift risk, not a
cost risk, since the inner literal bounds the call either way) and the per-frame look-direction
socket poll (reasoned cheap by precedent, never measured — no DCS/profiler available to this
agent). Recommend Stage 4's acceptance card add "note any felt frame irregularity, independent of
the 1 Hz LOS poll" so the one claim this review could not measure gets a flown answer rather than
staying permanently reasoned-only.
