### Goal

Give body-layer a `PendingIntent` command lifecycle (`scan_area` / `get_task_status` /
`cancel_task`) that triggers a real Petrovich search, biases outcome-checking toward a named
area via the existing `AttentionArea` machinery, and reports task outcome from belief state —
plus a matching aircraft-layer effector, since the live investigation (2026-09-11) fully solved
the mechanism this plan was previously blocked on.

### Why this plan was rewritten, in one paragraph

The prior version of this plan was built on two premises a day of live DCS probing
(`aircraft-layer/research/2026-09-11-SUMMARY-petrovich-control.md` and its two detail notes)
proved false: that Petrovich has no scan command, and that no outcome signal exists. Both are
wrong — he has several search verbs and his state/contact list are directly readable. But the
investigation also closed the two routes that would have let us *aim* him at a chosen bearing
(`SRCH 9K113 LOS` is broken; `DesignateAttackPoint` doesn't aim him either — see the RU manual
cross-check confirming the real 9K113 has no search/designation concept at all, only manual
optical acquisition) and explicitly rejected a third (puppeting the player's view) on design
grounds. So the achievable design is narrower than "point him and scan" but wider than the old
plan's fallback: we can trigger a real, un-aimed Petrovich search and verify its outcome for
real, instead of inferring everything from belief-state timeout. This revision reflects that,
supersedes all three prior addenda in the git history, and stands alone.

### What's now established (ground truth for this plan)

- **Effector, sight**: `GetDevice(7):SetCommand(3061, azimuth_deg / 60.0)` points the 9K113
  optics — positional, linear, single write, settles < 0.25 s. Read back via
  `GetDevice(0):get_argument_value(874) * 136.36`. Confirmed not to drive detection on its own
  (five flights) — a solved primitive with no proven use inside this milestone (see Decision 2).
- **Effector, wheel**: `GetDevice(30):performClickableAction(cmd, 1/0)` drives Petrovich's AI
  Wheel (a *different* verb than the sight's `SetCommand`). The centre button (3015) starts a
  search: short press = `SRCH BRST` (boresight), long press (> 0.5 s hold) = `SRCH FWD` (forward
  sweep). Both are real, triggerable, **not aimable** — Petrovich decides where to look.
- **No directed scan exists.** `SRCH PILOT LOS` follows the human's head (TrackIR), disqualified
  as a programmatic primitive by design, not just by difficulty. `SRCH 9K113 LOS` appears
  non-functional — with one still-open, deliberately deferred re-test: whether the ПУВЛ
  weapon-selector must be in УРС (missile) mode for it to work, per the real manual's §5.3.8 step
  2.2 (`2026-09-11-quickstart-ru-9k113-manual.md`). `DesignateAttackPoint` (3020) does not aim
  him — tested directly, stops a search instead. Aiming the sight ourselves does not cause
  detection either — verified across five flights, with and without a concurrent search running.
- **Outcome is directly observable.** `list_indication(10)` gives Petrovich's own state
  (`OBSERV. OFF` -> `WAITING` -> `SEARCHING` -> `TRACKING`) when the wheel's search page is
  open. `list_indication(6)` gives his classified contact list (5-row sliding window, real unit
  types), already the channel `perception/hybrid_source.py` ingests today.
- **Two hard constraints for any design touching this surface:**
  1. **Observation and engagement are different acts.** `SELECT TGT` commits Petrovich to
     tracking (and, weapons free, firing). Nothing this milestone builds may select or mark a
     target as a side effect of reading state.
  2. **Enumerating the contact list is not read-only.** `NEXT TGT` moves his selection and hands
     the sight back to him if he had it; toggling `OBSERV.` costs ~10 s of gyro alignment, and
     Petrovich turns it off himself under hard manoeuvring — it is state to observe, not state we
     own.

### What this plan does NOT attempt

A directed scan (`look_at(bearing)` causing Petrovich to search *there*) is not achievable with
what's confirmed today. `scan_area` in this plan means **"ask Petrovich to search, and tell me
if he finds something relevant to this area"** — a trigger + a scoped outcome check, not an aim
command. If the deferred ПУВЛ-switch re-test later confirms `SRCH 9K113 LOS` works, `scan_area`
gains a genuine aim step without changing its name, signature, or callers (see Decision 1) — that
is intentionally future work, not blocking this plan.

### Affected Modules / Files

**body-layer (unchanged in shape from the original plan — see "What stayed the same" below):**

- `body-layer/src/belief/tasks.py` *(new)* — `PendingIntent` (`task_id`, `kind` currently only
  `"scan_area"`, `area: AttentionArea`, `deadline_sim`, `status: Literal["pending", "succeeded",
  "failed", "cancelled"]`, `created_sim`, `reason`, `result_contact_ids: list[str]`), `TaskStore`
  (store-minted ids, mirroring `ContactStore`'s own id minting) and `tick(now_sim)`: for each
  `pending` task, check `ContactStore` for a contact inside `task.area` whose most recent
  observation arrived after `task.created_sim`; mark `succeeded` (recording the contact id(s)) or,
  past `deadline_sim` with nothing found, `failed` (timeout — see Risks for what this can and
  cannot mean now). No DCS I/O in this module.
- `body-layer/src/belief/tools.py` — `scan_area(store, tasks, center, radius_m, reason,
  deadline_s=DEFAULT_SCAN_DEADLINE_S, sector=None)` (registers a `watch`-level `AttentionArea` via
  `store.add_area`, then a `PendingIntent` over the same area — reuses BL-4's area machinery,
  same pattern as `watch_area`), `get_task_status(tasks, task_id)`, `cancel_task(tasks, task_id)`
  (marks `cancelled`; see Decision 3 on whether it also removes the area). **Stays pure/DCS-I/O
  free**, per body-layer's hard testability requirement — the live trigger is wired one layer up
  (see below), the same place BL-2.5 wired the overlay push rather than inside `tools.py`.
- `body-layer/src/belief/console.py` — `scan-area <bearing> <range_m> <radius_m> <reason>
  [sector]`, `task-status <id>`, `cancel-task <id>`. `scan-area`'s handler is where the live
  trigger lives: after calling `tools.scan_area` (always), if `Console.aircraft_client` is set
  (new optional field, mirroring the existing `enrichment` field's None-means-unchanged pattern),
  it also calls `aircraft_client.trigger_petrovich_search("forward")` in a `try`/`except
  AircraftLayerError` (mirroring BL-2.5's per-push guard in `logger.py`) — a failed trigger
  degrades to "the belief-state task was still registered, no live command fired," never raises
  through to the caller. `task-status <id>`'s handler may additionally fetch
  `aircraft_client.get_petrovich_wheel_latest()` (if configured) to print Petrovich's live
  state as a diagnostic line — display-only, never stored on `PendingIntent`, never changes
  `get_task_status`'s return contract.
- `body-layer/src/belief/tool_api.py` — three new `ToolSpec` entries. `scan_area`'s description
  must state plainly that it triggers a real search but cannot aim it, so the eventual brain layer
  never over-claims "I directed Petrovich to look there."
- `body-layer/src/logger.py` — wire `TaskStore.tick()` into the same poll-loop hook point
  `ContactStore.tick()` already runs from; wire a real `AircraftLayerClient` into
  `Console.aircraft_client` (or `CrewConsole`'s equivalent) in `main()`'s `--console`/`--crew-text`
  branches, same wiring pattern as `--overlay`'s client.
- `body-layer/src/aircraft_client.py` — two new methods: `trigger_petrovich_search(mode:
  Literal["forward", "boresight"]) -> None` (`POST /command/petrovich_search`, raises
  `AircraftLayerError` on failure, mirrors `push_text_line`) and
  `get_petrovich_wheel_latest() -> PetrovichWheelSample | None` (`GET /petrovich_wheel/latest`,
  mirrors `get_petrovich_indication_latest`).
- `body-layer/tests/test_tasks.py` *(new)* — fixture/replay-style: task succeeds when a matching
  contact appears post-creation, times out when none does, cancel stops future checks (and, per
  Decision 3's resolution, removes or keeps the area), idempotence under repeated
  `tick(same now_sim)`.
- `body-layer/tests/test_tools.py` / `test_console.py` — extend for `scan_area`/`get_task_status`/
  `cancel_task`, exercising the `aircraft_client=None` (pure/virtual) path as the default case and
  a recording-double `aircraft_client` for the trigger-call path, mirroring how `test_text_push_api
  .py`'s recording double works on the aircraft-layer side.

**aircraft-layer (new work this revision unblocks — the effector is solved, not gated on a probe
anymore):**

- `aircraft-layer/dcs-export/Export.lua` — two additions on the existing loopback channels:
  1. A new UDP command listener (parallel to the existing text-overlay UDP sender's channel, but
     inbound) that accepts a small JSON command and dispatches it: `{"op": "petrovich_search",
     "mode": "forward"|"boresight"}` drives the wheel sequence (`GetDevice(30):
     performClickableAction(3001, 1); (3001, 0)` to ensure the menu is open if not already, then
     `performClickableAction(3015, 1)` held for > 0.5 s for `"forward"` or released immediately for
     `"boresight"`, then `(3015, 0)`). The hold requires tracking a pending-release deadline across
     frames in `LuaExportAfterNextFrame`, the same per-frame-state pattern the existing 5 Hz export
     throttle already uses (`last_export_t`) — not a new architectural idea, just a second timer.
  2. Push `list_indication(10)` alongside the existing `list_indication(HELPERAI_DEVICE_ID)` (=6)
     push, on the same cadence, as a new sample type.
- `aircraft-layer/src/schema/petrovich_wheel.py` *(new)* — `PetrovichWheelSample`, reusing
  `petrovich_indication.py`'s existing `parse_indication_text` recursive-descent parser against
  the indicator-10 dump (same recursive tree shape, different top-level fields) rather than
  writing a second parser.
- `aircraft-layer/src/collector/cache.py` — `PetrovichWheelCache`, mirroring
  `PetrovichIndicationCache`.
- `aircraft-layer/src/collector/command_sender.py` *(new)* — the command-issuing mirror of
  `text_sender.py`'s `TextOverlaySender`: fire-and-forget UDP JSON sender to `Export.lua`'s new
  listener. Same "never raises on a missing listener" posture is **not** appropriate here —
  unlike `/text/push`'s opaque display string, a dropped command silently not reaching Petrovich
  is a real behavioral gap the caller needs to know about, so `send_command` should raise on a
  clearly-failed send the way `push_text_line` does, not swallow it like `TextOverlaySender.
  send_line`. Flagged explicitly since it's an intentional asymmetry from the existing sender.
- `aircraft-layer/src/api/server.py` — `POST /command/petrovich_search` (validates `mode`,
  forwards to `command_sender.py`, mirrors `/text/push`'s shape: `200 {"ok": true}` means
  "attempted the call" only) and `GET /petrovich_wheel/latest`.
- `aircraft-layer/tests/` — `test_command_sender.py` (mirrors `test_text_sender.py`),
  `test_petrovich_search_api.py` (mirrors `test_text_push_api.py`), schema/cache unit tests for
  `petrovich_wheel.py`. The live Export.lua-side press-hold sequencing has no automated test, per
  this subproject's existing posture on live-DCS-only correctness — validated manually against a
  running mission, cross-checked against `list_indication(10)`'s own state transition.

### What stayed the same from the original plan, and why

The body-layer half's core shape — `PendingIntent`/`TaskStore`, success verified by checking
`ContactStore` for a matching post-task contact, timeout on deadline — is **unchanged**, not
because nothing was learned but because what was learned confirms it was already the right
design. `HybridPerceptionSource` already gates on `list_indication(6)` (the same contacts channel
this investigation used), so a real Petrovich search triggered by this milestone's effector
produces real detections that already flow into `ContactStore` through the existing perception
pipeline — `tick()`'s job (did something relevant appear in the task's area after it was created)
is exactly as correct now as it was under the old "virtual scan" framing, just backed by a real
trigger instead of no trigger at all. The investigator's own conclusion agrees: "the belief-state
success check is still required either way."

### Implementation Plan

1. **`PendingIntent` + `TaskStore` + `tick()`** (`tasks.py`), pure, tested against synthetic
   `ContactStore` fixtures — same as `test_contacts.py`/`test_attention.py`. Unchanged from the
   original plan's design.
2. **`scan_area`/`get_task_status`/`cancel_task` in `tools.py` + `tool_api.py`**, composing
   `TaskStore` with the existing `AttentionArea`/`ContactStore` surface, no DCS I/O.
3. **`Console`/`CrewConsole` wiring**: optional `aircraft_client` field, `scan-area`'s handler
   calling `tools.scan_area` then (if configured) the live trigger; `task-status`'s handler
   optionally appending the live wheel-state diagnostic. `logger.py`'s `TaskStore.tick()` wiring
   alongside `ContactStore.tick()`.
4. **Console/replay tests for the body-layer half**, `aircraft_client=None` as the default,
   tested path — this milestone's DoD does not require a live DCS session to pass, consistent
   with every prior BL-x milestone.
5. **aircraft-layer effector**: `command_sender.py`, the `Export.lua` wheel-press + long-hold
   sequencing, the new indicator-10 push/schema/cache, the two new endpoints, their tests. This is
   new write-path code into a live DCS process — build and unit-test it, but live-validate against
   a running mission before calling this stage done (the user runs the live check, per this
   project's execution-boundary rule).
6. **End-to-end live acceptance**: with a real `AircraftLayerClient` wired into `Console`, issue
   `scan-area` against a mission with contacts present, confirm `SRCH FWD` actually fires
   (visible in `list_indication(10)`'s state transition and, ideally, the cockpit), and confirm
   `get_task_status` eventually reports `succeeded` from a real detection. This is the milestone's
   real acceptance test, not the console/replay tests in Stage 4 alone.

### Risks & Unknowns

- **Outcome verification is still ambiguous, for a different reason than before.** A `failed`
  (timeout) task now cannot distinguish "nothing was there," "something was there but Petrovich's
  own uncommanded sweep never looked that way," and "the search never actually started" (a
  trigger failure or a wheel-page mismatch). This is a *harder* epistemic gap than the old plan's,
  which only had to explain "nothing was there" vs. "nothing was ever attempted" against an
  inferred signal — now there's a real signal but still no aim, so a real search can genuinely
  miss a real target through no fault of the pipeline. `get_task_status`'s description must state
  this plainly (`"failed" means "nothing confirmed by the deadline," never "confirmed empty," and
  a real search still may not have looked toward the requested area`), per the no-omniscience
  invariant.
- **The wheel is stateful and page-aware, and the investigation logged real probe failures from
  assuming otherwise** (pressing a direction by position instead of by verified label, holding a
  stale page context, `NEXT TGT`'s label never changing so a generic "did it work" check silently
  no-ops). `command_sender.py`'s Export.lua-side sequence must open the menu and verify the search
  page's centre slot reads a `SRCH` option before pressing, not press blindly by position — this
  is a concrete lesson from the research, not a hypothetical risk.
- **The long-press timing lives in `Export.lua`, a component with no automated test.** A wrong
  hold duration silently fires `SRCH BRST` (short) instead of `SRCH FWD` (long) or vice versa —
  cosmetically harmless (both are real, triggerable searches) but means the `mode` parameter
  doesn't do what it says. Must be live-verified against `list_indication(10)`'s own reported
  search kind, not assumed from timing alone.
- **`DEFAULT_SCAN_DEADLINE_S` is still a placeholder** needing live-sortie calibration, same as
  before.
- **`scan_area` reuses `watch_area`'s bearing/range-only resolution** — no `find_place`
  integration, same scope cut as BL-5a made and BL-5's `find_place` (already merged) has not yet
  been wired into whichever grammar calls this tool.
- **`command_sender.py`'s raise-on-failure posture is new surface area** — it's the first
  aircraft-layer write path where a silent failure is unacceptable (unlike `/text/push`'s opaque
  display string), so its error handling needs real live-failure testing (DCS not running, wrong
  mission state), not just the happy path.
- **The still-open ПУВЛ-switch lead is explicitly out of this plan's scope.** If a future re-test
  confirms `SRCH 9K113 LOS` works in УРС mode, `scan_area` can gain a genuine aim-then-search step
  without an API break — additive, matching the "strictly additive effector" framing the original
  plan used for its own Stage 6. Recorded here as an enhancement path, not a blocker.

### Decisions Requiring User Input

1. **Naming: keep `scan_area`, or rename now that no aim exists?** I'm keeping `scan_area` for
   this revision — `center`/`radius_m` still meaningfully scope *which* of Petrovich's own
   findings count as satisfying the request ("focus on that area" is a legitimate ask even without
   a search-the-bearing mechanism, and matches how the real crew's operator actually works per the
   manual — visually scanning, not being aimed), and keeping the name avoids reopening the
   `body-layer/ROADMAP.md` tool-freeze wording three times in one day. The tool's description will
   carry a prominent "does not aim Petrovich" caveat. This is a low-cost, reversible lexical choice
   — flagging so the call is visible, not asking you to re-derive it from scratch.
2. **Is `look_at`/sight-pointing in scope for this milestone?** My recommendation: **no** — it's
   a solved, cheap primitive (a single `SetCommand` write) but confirmed *not* to influence
   detection on its own, and nothing in `scan_area`/`get_task_status`/`cancel_task` needs it. I'd
   leave it out of both the body-layer tool surface and the Stage 6 endpoint set, and record it as
   solved-but-unused for a future "where is Petrovich looking" narration tool or a future directed
   scan if the ПУВЛ-switch lead pans out. This narrows Stage 6's scope noticeably (no
   `/command/point_sight` endpoint, no `look_at` tool). Flagging because it's a real scope
   boundary you may want drawn differently — it's cheap to add later either way.
3. **Does `cancel_task` also remove the `AttentionArea` it registered?** Resolved 2026-09-11 (user
   decision): **yes, `cancel_task` removes the area.** Cancelling a scan stops watching that area
   entirely, not just its own success/timeout bookkeeping.

### Second-Order Effects

**Unblocks:** this is still BL-6's tool-set freeze point per `body-layer/ROADMAP.md` — once
`scan_area`/`get_task_status`/`cancel_task` land, `docs/concept/PETROBRAIN_RUNTIME.md` §3.3's tool
list is complete and a brain-layer prototype (PB-6) can build against a stable, and now
*honestly-scoped*, surface. **Narrows:** every future "have Petrovich actually do X" idea inherits
the same un-aimable-trigger ceiling this plan designs around, until/unless the ПУВЛ-switch lead
resolves it — worth remembering before BL-8's memory layer decides how much confidence to persist
about task outcomes, and before any future mission-interpreter work assumes Petrovich can be
directed rather than merely asked. **Complicates none identified** beyond what's already flagged
— the design stays additive with respect to a future real aim mechanism.

### Invariant Check

- **Code owns facts, models interpret:** `get_task_status`'s `"failed"`/`"succeeded"` never
  overstate certainty — see Risks. `scan_area`'s description never claims Petrovich was aimed.
- **DCS authoritative, read-only install:** unaffected — Stage 5/6's new write path calls only
  already-existing, already-deployed `Export.lua` functionality (`GetDevice`,
  `performClickableAction`), the same posture as every other aircraft-layer write. No DCS install
  file is modified.
- **Provenance/uncertainty/timestamps:** `PendingIntent` carries `created_sim`/`deadline_sim`;
  `succeeded` links back to the satisfying contact id(s), so the causal chain is inspectable.
- **Module independence:** no new cross-subproject import. `Console.aircraft_client` reuses the
  existing HTTP-boundary pattern `--overlay` already established — aircraft-layer stays reachable
  only over HTTP from body-layer, same as every other seam.

### Note on this project's role sequence for this plan

`CLAUDE.md`'s "Agents" section currently exempts Security and Performance Reviewer for this
project phase ("this phase is an offline single-user local pipeline with no hot path and no
untrusted-input surface yet... only run either when the user explicitly asks"). `body-layer/
ROADMAP.md`'s existing BL-6 entry says this milestone is "gated on the aircraft layer's command
channel, which needs its own Security plan review" — that line predates the later project-wide
exemption decision and is now stale; per `CLAUDE.md`'s current, more specific instruction, this
plan does not route through Security unless the user asks for it. Flagging the stale ROADMAP
wording here rather than silently overriding it — worth a one-line ROADMAP fix when this milestone
closes.
