### Implementation Summary

Implements X-B29 (DCS-driven batched line of sight) Stages 1-3 together: the cone-scoped Hook
script (buildings + terrain, both fields published), the look-direction command channel, the
collector/API/client plumbing, the body-layer join, gate 4's live-first/offline-fallback wiring,
belief carrying the observed value (engagement term rewritten, `_threat_has_los` deleted), and the
detection-trace annotation. Stage 4 (the acceptance sortie) is **not done** — it needs a live DCS
flight, which this agent cannot run; see "What could not be verified without DCS" and the
acceptance card below.

**Both required Security fixes are implemented, plus the recommended one:**
1. The Hook-side FOV/hour clamp (`_safeClampInt` in `petrobrain-line-of-sight-hook.lua`) explicitly
   tests `type(value) ~= "number"`, NaN self-inequality (`value ~= value`), and `math.huge`/
   `-math.huge` before any ordinary min/max comparison, and the whole decode-clamp-format-
   `dostring_in` sequence is wrapped in `pcall` (`_applyLookDirection`) so a failure leaves the
   previous globals untouched.
2. The inbound look-direction listener drains up to `MAX_LOOK_DIRECTION_DATAGRAMS_PER_FRAME`
   queued datagrams per frame but applies only the **last** one, via exactly one `dostring_in`
   setter call per frame (`pollLookDirection` → `_applyLookDirection`).
3. `aircraft-layer/tests/test_line_of_sight_hook_lua.py` statically asserts `SET_LOOK_TEMPLATE`
   carries no format specifier other than `%d`.

**Mid-task course correction (user direction, 2026-10-05):** the 12 m terrain tolerance
(`world-model/src/query/line_of_sight.py`'s `_TERRAIN_TOLERANCE_M`) is now explicitly documented as
test-path-only — it must never be applied on the live path. No code change was needed to enforce
this: gate 4 already never calls `line_of_sight_clear` when a live verdict exists
(`candidate.live_los_clear is not None`), so the boundary was already correct by construction. The
constant's own definition site and `plans/dcs-driven-los/plan.md`'s "What happens to the 12 m
tolerance and the probe grid" section were both updated with the correction (the plan section keeps
its original text, with a forward pointer, per instruction not to silently rewrite it).

### Files Changed

**aircraft-layer (new):**
- `src/schema/line_of_sight.py` — `LineOfSightVerdict`/`LineOfSightSnapshot`, wire parsing.
- `src/collector/line_of_sight_receiver.py` — mirrors `UnitVelocityReceiver`, port 7796.
- `dcs-export/petrobrain-line-of-sight-hook.lua` — the Hook script: cone-scoped
  `SEGMENT`/`isVisible` sightlines, the inbound look-direction listener, the NaN/Inf-guarded clamp,
  the validated `%d`/`%d` splice.

**aircraft-layer (modified):**
- `src/schema/__init__.py` — re-exports the new schema.
- `src/collector/cache.py` — `LineOfSightCache`.
- `src/collector/command_sender.py` — `LookDirectionSender` (own port 7797 — a *different* inbound
  listener from Export.lua's, since `land.*`/`world.*` are only reachable from the mission-scripting
  state, which Export.lua does not run in).
- `src/api/server.py` — `GET /line_of_sight/latest`, `POST /command/look_direction` (range-validates
  `hour: 0..11`, `fov_half_deg: 5..180`, the collector-side layer of the plan's three-deep defense).
- `src/collector/__main__.py` — wires the receiver/cache/sender in, new CLI flags.

**body-layer (modified):**
- `src/aircraft_client.py` — `get_line_of_sight_latest`/`post_look_direction`.
- `src/perception/association.py` — `WorldObjectCandidate.live_los_clear: bool | None`.
- `src/perception/visibility.py` — gate 4 reads `candidate.live_los_clear` first, falls back to
  `line_of_sight_clear` only when `None`.
- `src/perception/naked_eye_source.py` — `_resolve_los_by_unit_name` (mirrors
  `_resolve_velocity_by_object_id`), `LOS_MAX_AGE_S = 3.0`, threads `live_los_clear` through
  candidate construction and the cluster fold (`apparent_motion`'s own "identical keeps,
  disagreement degrades" rule), calls `annotate_los` for *every* candidate in the per-candidate gate
  loop (not just admitted ones — unlike `annotate_motion`, so a `TERRAIN_LOS`-outcome row still
  carries `building_clear`/`terrain_clear`).
- `src/perception/detection_trace.py` — `DetectionTrace` gains `building_clear`/`terrain_clear`/
  `live_los_clear`/`los_skew_s`/`hour_used`/`fov_half_deg_used`; new `annotate_los`.
- `src/perception/source.py` — `Observation.live_los_clear: bool | None`.
- `src/belief/percept.py` — `Percept.live_los_clear`, carried through in `percept_of`.
- `src/belief/contacts.py` — `Contact.live_los_clear` (overwrite, not fold, in `record()`/
  `from_percept()`); the engagement term's seventh block rewritten to read it (fail-open when
  `None` or stale relative to `OBSERVED_WINDOW_S`); `_threat_has_los`, `tick`'s `los_clear`
  parameter, and `LOS_UNCERTAINTY_SAMPLES` **deleted**.
- `src/logger.py` — the `los_clear` closure deleted; `store.tick()` no longer takes a third
  argument; `run_once` pushes the look-direction command (`hour` derived from the same `gaze_at`
  result the naked-eye source is handed, `fov_half_deg=90` per plan §17 decision 2) only on change.

**world-model (modified):**
- `src/query/line_of_sight.py` — `_TERRAIN_TOLERANCE_M`'s comment now states the test-path-only
  boundary explicitly (mid-task correction, see above). No behavioural change.

**Plan correction (not new implementation, but a required edit per mid-task direction):**
- `plans/dcs-driven-los/plan.md` — "What happens to the 12 m tolerance and the probe grid" section
  corrected with a forward pointer, original text preserved beneath it.

### Tests Added

**aircraft-layer** (42 new, all passing):
- `test_line_of_sight_schema.py` — wire parsing: well-formed, empty entries, duplicate unit-name
  (last-wins), malformed payloads (6 parametrized cases), `to_dict` shape.
- `test_line_of_sight_cache.py` — latest-of-one semantics.
- `test_line_of_sight_receiver.py` — real loopback UDP socket, malformed-datagram dropping.
- `test_look_direction_sender.py` — well-formed datagram, lazy socket open, `CommandSendError` on a
  failed send (injected, mirroring `test_command_sender.py`'s own pattern for why a real closed-port
  send can't be relied on to raise synchronously).
- `test_line_of_sight_api.py` — both new endpoints: empty cache, pushed snapshot, valid/invalid
  `hour`/`fov_half_deg` (parametrized), missing sender → 503, send failure → 500.
- `test_line_of_sight_hook_lua.py` — static text checks against the `.lua` file (no DCS, no Lua
  execution — this project's Hook scripts have no automated behavioural test at all, per
  `aircraft-layer/CLAUDE.md`'s own Testing section): exactly two `%d` and no other specifier in
  `SET_LOOK_TEMPLATE`, the NaN/Infinity guards are present, the apply path is `pcall`-wrapped, and
  the receive loop coalesces to one setter call per frame.

**body-layer** (17 new, all passing):
- `test_resolve_los_by_unit_name.py` — the join function directly: no snapshot, well-formed join,
  `live_los_clear = building AND terrain`, absent-from-wedge, stale skew, non-unique `unit_name`,
  malformed verdict shape.
- `test_visibility.py` (+3) — `live_los_clear=True/False` short-circuits gate 4 without consulting
  the offline primitive (asserted via a spy that fails if called); `None` falls back unchanged.
- `test_percept.py` (+1) — `live_los_clear` carried through unchanged (`True`/`False`/`None`).
- `test_contacts.py` (+3, 4 renamed/rewritten) — `live_los_clear` is overwritten not folded;
  fail-open with no verdict at all; fail-open once a verdict goes stale relative to
  `OBSERVED_WINDOW_S`. The four pre-existing `los_clear`-callable tests were rewritten (not merely
  patched) to set `Contact.live_los_clear`/`last_seen_sim` directly instead of passing a fake
  callable, since the parameter no longer exists — this is required by the plan's own deletion, not
  an unrelated test change.
- `test_detection_trace.py` (+2) — `annotate_los` fills in all six fields on the most recently
  recorded entry (regardless of gate outcome, unlike `annotate_admission`); no-op on an unknown
  `object_id`.
- `test_logger.py` (+1) — `run_once` pushes `(hour, fov_half_deg)` once, not again on an unchanged
  gaze; `FakeAircraftClient`/`FakeConsoleAircraftClient` both gained `get_line_of_sight_latest`/
  `post_look_direction` stubs (and five other test files' `FakeAircraftClient` doubles gained
  `get_line_of_sight_latest` returning `None`, to keep every existing `NakedEyePerceptionSource`
  test compiling against the new required call).

**world-model** (+2): reciprocity and "raising the observer never turns clear into blocked"
(monotonicity) — §3a's own cheap property tests of the offline primitive on its own terms, no
cross-implementation contract test.

### Checks

**aircraft-layer/** — ruff format --check: pass · ruff check: pass · mypy --strict: pass (21 source
files) · pytest: **252 passed** (baseline 210 + 42 new)

**body-layer/** — ruff format --check: pass · ruff check: pass · mypy --strict: pass (53 source
files) · pytest: **1457 passed, 4 xfailed** (baseline 1440/4 + 17 new)

**world-model/** — ruff format --check: pass · ruff check: pass · mypy --strict: pass (72 source
files) · pytest: **550 passed, 3 skipped** (unchanged skip count, +2 new tests)

Lua syntax (`luac5.1 -p`): pass on the outer Hook script and on the extracted `LOS_CODE` snippet
(parsed separately, since it's a string literal the outer check doesn't reach into).

### Notable Discoveries

- **The worktree landed on a commit whose `plans/dcs-driven-los/plan.md` predates the §7-§17
  revisions and the security review** (confirmed: `git rev-parse HEAD` = `be12734`, not an ancestor
  of `feature/dcs-driven-los`'s tip `f6a8692`). Per the task's instruction, all reading/implementation
  was done from an isolated `git archive` snapshot of the feature branch, with the actual file edits
  made directly in the worktree checkout (not the snapshot) once I confirmed the worktree's own
  copies of every file I needed to touch were byte-identical to the feature-branch tip's versions —
  i.e., `main` had not diverged for any file this plan touches. **`plans/dcs-driven-los/
  security-plan-review.md` exists on the feature branch but not in this worktree/on `main`** — it
  was read from the snapshot only; nothing was written back to it, since the two required fixes it
  names are implemented in code, not in that document.
- **The Security review's "exactly one `%d`" phrasing had to be relaxed to "exactly two"**, because
  one coalesced `dostring_in` call (required fix 2) sets *two* values (`hour`, `fov_half_deg`), not
  one. The safety argument is identical per substitution point and does not depend on there being
  only one — documented explicitly in the Lua file's header and the corresponding test's docstring,
  so a future reader doesn't mistake the count for a regression.
- **Heading/bearing extraction inside `LOS_CODE` (`Unit:getPosition()`'s forward vector via
  `atan2`) is standard DCS Mission Scripting Engine convention but was NOT independently verified
  against a live DCS session** — no DCS is available in this environment. Flagged in the Lua file's
  own header; Stage 4's sortie is what confirms it. If it is wrong, the symptom would be a wedge
  that silently doesn't track where Petrovich is actually looking — a coverage loss per the plan's
  own safety property (SS9c), not a wrong detection.
- **`tonumber("nan")`/`tonumber("inf")` behaviour on DCS's bundled Lua/CRT was not verified** (same
  reason — no DCS). `_safeClampInt` is written to be correct under either outcome (explicit NaN/Inf
  checks catch a real NaN/Inf; the `type(x) ~= "number"` check catches `tonumber` returning `nil`
  instead), per the Security review's own instruction, but this should be confirmed directly on the
  Windows box before relying on it.
- **The `SEGMENT`/`isVisible` point shapes (Vec3 `{x=, y=altitude, z=}` for the sightline test,
  Vec2 `{x=, y=z-component}` for `land.getHeight`) follow the exact convention this project's own
  prior probe scripts (`petrobrain-segment-los-probe-hook.lua`, `petrobrain-elevation-cost-probe-
  hook.lua`) already used live — not a new, unverified assumption, just reused.
- **`MAX_SIGHTLINES_PER_CALL` is hardcoded as a literal `128` inside the `LOS_CODE` string**, not
  read from the outer Lua `local MAX_SIGHTLINES_PER_CALL = 128` — the two are independent constants
  that happen to share a value, because `LOS_CODE` must be a fixed string literal per the project's
  own `dostring_in` rule and cannot interpolate an outer Lua variable. If this constant is ever
  tuned, both copies need updating; there is no mechanical guard against them drifting apart
  (unlike the `%d`-count test for the look-direction splice). Worth a follow-up test similar to
  `test_line_of_sight_hook_lua.py`'s if this number is revisited.
- **The acceptance-debt consequence the user flagged**: the previously-merged `fix/los-elevation-
  tolerance` work still carries an unflown live-acceptance sortie to confirm the 12 m tolerance fixed
  the missed-AAA case without masking genuinely-ridge-hidden units. Under this feature's design that
  question has mostly dissolved for the *live* path (which no longer uses the tolerance at all once
  a DCS-driven verdict exists), but it still applies to the tolerance's one remaining real use —
  gate 4's fallback branch (feed absent / outside the queried wedge / stale) and fixtures. Not acted
  on here per the user's own note that they will handle the roadmap bookkeeping.
- **Stage 4 (the acceptance sortie) is not attempted** — it needs a live DCS flight. See the
  acceptance card below for what it must confirm.

### Acceptance card (needs a live DCS flight — not run by this agent)

Branch: `feature/dcs-driven-los` (once this worktree's commit is harvested onto it).

1. Deploy `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` to
   `Saved Games\DCS\Scripts\Hooks\` (same `autoexec.cfg` opt-in as the other `dostring_in` Hook
   scripts — see `aircraft-layer/WORKFLOW.md`).
2. Confirm `dcs.log` shows `PetrobrainLineOfSight` lines on mission start and every poll
   (`LOS poll: bridge_call_ms=... result_head=...`), and that `look direction set: hour=... 
   fov_half_deg=...` lines appear and change as the aircraft scans.
3. Fly past a building with a known AAA/vehicle behind it — it should now read as occluded where it
   previously read as clear (new capability, Stage 1).
4. Fly the missed-AAA geometry from `plans/missed-aaa-detection/debug.md` — confirm the live path
   now answers correctly without relying on the 12 m tolerance (check `dcs-detection-trace.jsonl`'s
   `building_clear`/`terrain_clear`/`live_los_clear` fields for that object_id).
5. Pause-state check (per `aircraft-layer/CLAUDE.md`'s testing note) — this Hook-script family has a
   history of export-rate bugs invisible to in-flight-only testing.
6. Watch a contact engage/disengage and confirm the engagement term's danger/safe calls track the
   live building/terrain verdicts, with the "safe from" utterance still deferred (unrelated to this
   plan, already shipped).
7. Read `units_in_bubble`/`units_in_wedge`/`sightlines_computed`/`bridge_call_ms` from a flown log
   before trusting any of §10's wedge-population estimates — they are all unmeasured uniform-azimuth
   extrapolations except the one figure (~10/poll) the plan's own Stage 0 actually measured.
