### Performance Review

Reviewed `feature/emitter-visibility` @ `1053265e9bec7411fc1a423d8142b9d64546c17c` (Stage A of
`BL-B72`/`AC-B7`: the shared gate bypass, the burning-unit emitter, its transport). No real-time
budget applies to this phase (Petrobrain Runtime has not started); the relevant bound is the poll
loop's own baseline (1.1 ms median / 12.6 ms worst, `BL-11`) and the DCS main-thread bridge cost.

Per the dispatch's framing, the gate predicate itself is not where the cost could be — the question
is what the bypass admits downstream, and what it costs on DCS's own thread.

### Findings

#### Extra candidates reaching gate 4+ via the bypass
- **Location:** `visibility.check_visibility` (body-layer/src/perception/visibility.py, emitter
  bypass at gates 3/5), called from `naked_eye_source.poll`.
- **Risk:** a candidate that previously failed cheaply at gate 3 (geometric range/size check,
  O(1), no DB) now proceeds to gate 4 (terrain LOS) and gate 5 (skipped when bypassed) and, if
  admitted, into clustering/association/belief.
- **Why this is not costly here:** gate 4, post-`X-B29`/`BL-11` Stage 4, consults only
  `candidate.live_los_clear` — a field already resolved by the DCS-side Hook and joined onto the
  candidate upstream (`naked_eye_source.py`'s `_resolve_los_by_unit_name`). There is no raycast, no
  DB touch, no extra work at gate 4 itself regardless of how a candidate arrived there. Gate 5
  (forest, the one DB-touching test in the chain) is **skipped**, not added to, by the bypass. So
  each extra admitted candidate costs one more pass through clustering/association at whatever that
  already costs per candidate — no new per-candidate mechanism, just more instances of the existing
  one.
- **Bound on how many extra candidates:** the plan's own estimate ("single-digit in any real
  scene") is reasoned, not measured, which per this project's own "measure n before scaling"
  lesson is the figure most likely to be wrong. There is no hard cap preventing many units burning
  simultaneously after a saturating strike — but it is bounded above by the bubble-filtered
  candidate count (`filter_player_bubble`, applied before any gate runs), which is itself bounded
  by scene population. A worst case is "every candidate in the bubble is burning," which degrades
  to "every candidate reaches gate 4/5-skip, exactly as if gate 3 had admitted them all" — not a
  distinct failure mode, just the existing per-candidate cost paid by more candidates.
- **Action:** MONITOR. Worth a sortie-log look (the detection trace's `emitter_kind` column, which
  this feature added for exactly this purpose) once this ships, to see real burning-candidate
  counts in an engagement — but there is no credible mechanism here for a budget violation at this
  project's current scale (single-player, LAN, no hard real-time bound yet).

#### The emitter lookup itself
- **Location:** `perception.emitters.burning_emitters`, called once per poll in
  `naked_eye_source.poll` (line 569), consumed per-candidate via `emitter_by_object_id.get(...)`
  (line 679).
- **Confirmed:** the dict is built exactly once per poll, not per candidate — one `Counter` pass
  and one dict-build pass, both O(N) over `raw_objects` (theatre-wide world objects, same scope the
  existing velocity join already iterates). The per-candidate cost at the call site is a single
  `dict.get`, no allocation. This matches the existing `_resolve_velocity_by_object_id`/
  `_resolve_los_by_unit_name` pattern exactly — no new cost class introduced, just one more O(N)
  pass of the same shape already paid every poll.
- **Action:** none needed — clean negative, confirmed by reading the call site, not assumed from
  the implementer's account.

#### Lua-side cost: two extra `pcall`s per unit per poll
- **Location:** `aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua`'s `VELOCITY_CODE`
  string, `lifeFields(obj)` — two guarded `pcall`s (`getLife()`, `getLife0()`) added to the existing
  in-state per-unit loop, for both live units and now static objects too (statics previously got a
  fixed `":0:0:0"` velocity string with no `pcall` at all — this is new work for the static branch,
  not just doubled work for the unit branch).
- **Risk:** this runs on DCS's own thread inside the `"scripting"` state, which is the one place in
  this project where cost means cockpit stutter, not service latency (`AC-B7`'s own framing). Two
  more `pcall`s per object, per second, roughly doubles the unit-branch per-object cost of this loop
  and adds a non-zero cost to the static branch where there was none before.
- **What stands between this and a credible finding:** the plan and `AC-B7` both name this
  explicitly as "the one number worth measuring," with the self-measuring `bridge_call_ms` field
  already on the wire specifically so this is a log read, not a probe. **That log read has not
  happened yet** — this branch has not had a live sortie, and `AC-B7` is still `#status/open`. So
  this is not a defect, but it is also not yet verified; it is exactly the kind of number this
  project's own precedent (`AC-B4`) says must be measured, not reasoned about, before declaring it
  fine.
- **Action:** MONITOR, with a concrete trigger rather than a vague deferral: **read
  `bridge_call_ms` from the telemetry hook's log on the first live sortie after this merges**
  (DoD's/the user's step, not this role's — matches how the Reviewer correctly left the
  sightline-cap and fire-fraction-bracket claims to DoD rather than re-deriving them). If
  `bridge_call_ms` shows a step change disproportionate to unit count growth, that is a real
  finding for a follow-up debugger/performance pass — not grounds to hold this merge today, since
  the mechanism (one more guarded call per object, same loop, same thread) carries no structural
  reason to expect anything worse than roughly double the existing measured cost, and no
  measurement of the existing cost's absolute magnitude has been flagged as tight to any budget
  (none exists yet for this phase).

#### Transport and schema changes
- **Location:** `schema/unit_velocity.py`'s `_parse_entry` (now tries a 6-field shape before
  falling back to 4), `collector/unit_velocity_receiver.py`, `src/api/server.py`.
- **Risk:** none credible — the receiver and server are payload-agnostic (confirmed: no changes
  needed to either, per implementation.md and verified by reading the diff), and the parser's extra
  `rsplit` attempt is one more string op per sample per poll, the same cost class as the parse it
  already does.
- **Action:** none needed — clean negative.

#### Poll-body blocking / main-thread work
- **Location:** `naked_eye_source.poll`, `_build_observation`, `belief/contacts.py`'s
  `ContactStore.tick` emitter-related additions.
- **Risk:** `BL-B49` already tracks synchronous-stall risk on the poll body; this feature adds no
  I/O, no new synchronous network call, no new DB touch anywhere in body-layer. Every new piece
  (`burning_emitters`, the `emitter_kind` mapping, the mixed-cluster-provenance check, the
  `CONTACT_BURNING_SEEN` emission in `tick`) is pure in-memory computation over already-fetched data.
- **Action:** none needed — clean negative, stated explicitly per the dispatch's request for a
  negative finding where one genuinely holds.

#### 128-sightline-cap exposure
- Already assessed by the prior Reviewer pass and confirmed correct: Stage A's bypass touches gates
  3/5 only; gate 4 is unchanged and still fail-closed on `live_los_clear is None`, so a candidate
  truncated out of the Hook's 128-sightline wedge query is rejected exactly as any far candidate
  already is today, bypass or not. Confirmed in passing by reading `check_visibility`'s gate-4
  docstring and the call site — not re-measured, per the scoping instruction. No new finding here.

### Verdict

APPROVED — MONITOR

No required or recommended fixes. The two MONITOR items (burning-candidate count in a real
engagement, and the Lua-side `bridge_call_ms` delta) are both measurement obligations this project
has already named as owed before further tuning, not defects in this diff — and both are correctly
DoD's/the user's to close with a live sortie, not something this review can or should block on.
