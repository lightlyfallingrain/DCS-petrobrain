## Reviewer: BL-B67 Stages 1-2 (run skeleton + single-unit aim)

Branch `feature/bl-b67-atgm-run` @ `5033afc5b1971c4d3f6b7107c8ef39b8c7d56573`, fast-forwarded into
this worktree from `ca69f8ec` (tree was clean, HEAD was a strict ancestor of the tip). Diff under
review: `e523f2b3..5033afc5` on `body-layer` — stage commits `7aee88de`, `3fc1ab59`, plus the
implementer-memory commit `5033afc5` (the merge `178c4348` only brings an unrelated main-side
header-comment fix, confirmed by `--stat`, not re-reviewed).

Inputs read in full: `plans/bl-b67-atgm-run/plan.md`, `explore-notes.md`, `implementation.md`
(all 6 flagged deviations), `security-plan-review.md` (approved, two items explicitly passed to
Reviewer with no verdict). Source diff read in full (965 lines across `atgm_run.py`,
`attack_run.py`, `crew_console.py`, `optic_policy.py`, `percept.py`, `sight_head.py`, `speech.py`,
`body.py`, `naked_eye_source.py`, `source.py`) plus the full `test_body.py` diff (the four
Co-moving-Fields integration tests).

### Checks run

`ruff format --check`, `ruff check`, `mypy --strict` (via `cd body-layer && .venv/bin/mypy src`),
`pytest tests -q` — all pass, matching the implementer's reported numbers (2733 passed, 4 xfailed).

### Mutation verification (not just reading)

- Appended a stray `aim_unit_direction` reference to `crew_console.py` → the `belief/`-wide grep
  fence in `test_attack_run.py::test_belief_never_references_relative_direction_except_sanctioned_readers`
  failed correctly (glob over every `belief/*.py` file, not a hardcoded list). Reverted.
- Reordered `_decide_sighting` so `sight_lock_contact_id` is checked before `sight_steady` (i.e.
  simulated the regression "lock overrides the violent-manoeuvre OBSERV-off") →
  `TestSightLock::test_a_forced_observ_off_still_fires_under_the_lock` failed correctly. Reverted.
- Confirmed `git status --porcelain` clean after both reverts.

These two were the highest-risk invariants named in the dispatch (no-omniscience boundary, gyro
safety vs. tracking lock) and the security review explicitly passed both to Reviewer with no
verdict of its own. Both are real, falsifiable tests, not decorative ones.

### Findings by checklist item

- **Single-unit aim never uses the cluster centroid while locked**: `aim_unit_direction` is
  computed from the cluster member nearest the gaze centre, falls back to the centroid only when
  unset (never silently picks the centroid while the sight-tier gate is satisfied), and a
  single-member cluster trivially reduces to the centroid (tested:
  `test_aim_unit_direction_equals_the_centroid_for_a_single_member_cluster`,
  `test_single_unit_prefers_aim_unit_direction_over_the_centroid`). Confirmed in code, not just
  the test names.
- **Sight lock vs. violent-manoeuvre OBSERV-off**: verified correct by mutation above. The lock is
  reached only after the pre-existing `sight_steady` check in `_decide_sighting`, so
  `_force_observ_off` still wins.
- **Guns/rockets regression (BL-14, missing `missiles` weapon word)**: `attack_run_weapon` is read
  but only `"missiles"` is gated or starts an ATGM run; any other value (including a bare
  `engage`) runs the unchanged BL-14 path. `test_engage_guns_never_gated_on_guidance_unit` and
  `test_engage_accepts_and_ignores_the_weapon_slot` (updated per Decision 15's supersession) cover
  this directly.
- **Guidance-ladder floor deferral (implementer's deviation 1)**: the plan's "Keeping the look
  through launch" section is written as part of Stage 1's design ("Keeping the look through
  launch... the guidance ladder's floor is `SIGHT_WIDE_OPTIC`"), but Stage 1's own numbered task
  list only names `sight_lock_contact_id` in `optic_policy.decide`, not the
  `attack_run.decide(..., floor=...)` change. The implementer's read — defer it, since no Stage
  1/2 test exercises the ladder's floor and `attack_run.py`'s `guidance_request_for(...,
  floor=UNAIDED_OPTIC, ...)` call is untouched — is a reasonable reading of an ambiguous stage
  boundary, correctly flagged rather than silently dropped, and genuinely has no observable effect
  until Stage 3 wires the InFlight guidance path. **Accepted as deferred, not a defect**, but
  Stage 3 must make an explicit decision here (plan already says so); this is not optional to
  forget.
- **No new tunables, so no tuning.py / `defaults.toml` gap** — confirmed: no behaviour-affecting
  literal was added this stage (`SHTURM_SPEED_MPS` etc. are Stage 3's). `test_tuning_defaults_toml.py`
  passing unchanged corroborates this rather than merely asserting it.
- **Co-moving Fields table**: the four rows Stage 1 claims (fresh construction on `engage
  missiles`; both cleared on `engage` without `missiles`; both cleared on disengage; both cleared
  when `drain_attack_run` returns `None` for drop-target/lost-contact) are each driven through the
  *real* threaded `_run_crew_text_poll_loop`, not a unit-level stand-in — this is exactly the
  "verify by mutation per entry, not per set" standard this project asks for, and it is met. The
  table's "mission (re)start" row and the general invariant row (`atgm_run_state is not None ⇒
  attack_run_state is not None`, asserted generically rather than per-scenario) have no dedicated
  test, but both are structurally guaranteed: `reset_for_new_mission` re-invokes `__init__`
  wholesale (so an un-listed field reverts to its dataclass default with no extra code needed —
  the same mechanism that protects every other field on that class), and every engage-apply branch
  sets or clears the pair together by construction. Low risk; noted as optional, not required.

### Required fixes

1. **`body-layer/CLAUDE.md`'s invariant text, "The ownship-relative channel has exactly two
   consumers, and neither is a position," is now incomplete, not just unchanged.** It still
   describes only `Percept.relative_direction`; `aim_unit_direction` is a second field on the
   *same* structural no-omniscience boundary, fenced to the same two files
   (`percept.py`/`attack_run.py`), and the `test_attack_run.py` fence docstring itself says so in
   almost these words ("the same ownship-relative boundary's second field, not a second
   exception"). This is exactly the invariant class the file's own header warns about ("break
   these and the failure is silent") and exactly the kind of staleness this project has been
   burned by repeatedly (root `CLAUDE.md`'s "a list in this file has now gone stale four times").
   A reader who checks only CLAUDE.md before adding a third reader of `aim_unit_direction` would
   have no reason to know it is under the same fence as `relative_direction`. Fix: extend the
   bullet (or add one sentence) naming `aim_unit_direction` as the sibling field under the same
   two-file fence, citing `[[BL-B67]]`.
2. **`body-layer/docs/STRUCTURE.md` has the matching gap, twice over.** The `src/perception/
   source.py` entry still says only `RelativeDirection`/`relative_direction` are the fenced
   ownship-relative datum (no mention of `aim_unit_direction`), the `src/belief/attack_run.py`
   entry still says `attack_run.py` and `percept.py` are "the only two files under `belief/`
   allowed to mention `relative_direction`/`RelativeDirection`" with no update, and there is **no
   entry at all for the new `src/belief/atgm_run.py` module** — STRUCTURE.md's own header says "the
   per-module detail for `body-layer/`... read the entry for any module before you modify it," which
   presumes every module has one. Fix: a short entry for `atgm_run.py` (Stage 1 scope: `contact_id`
   only, Stage 3 owns the rest — the new file's own docstring already has this text verbatim and
   can be summarized), and a one-line addition to the `source.py`/`attack_run.py` entries naming
   `aim_unit_direction`.

Neither fix touches `src/`; both are small, mechanical doc edits with no code or test risk, and
both can be made directly rather than looping back through Implementer.

### Optional refinements

- A single generic test asserting `atgm_run_state is not None ⇒ attack_run_state is not None`
  across the four Co-moving-Fields scenarios (parametrized over the existing fixtures) would catch
  a future fifth transition path the per-scenario tests don't happen to cover. Not required: the
  invariant currently holds by construction in every branch that touches either field, and Stage 3
  adds several more transition rows anyway, which is a more natural point to add a combined
  check.
- `plans/attack-run/plan.md` Decision 15 and `body-layer/ROADMAP/BL-B74.md`/`plans/
  emitter-visibility/plan.md`'s amend-on-merge notes (plan's "Second-order effect") are still owed
  — implementation.md deviation 4 flags this correctly as out of the Implementer's remit ("does
  not own that plan file"). Worth doing at merge time, not blocking this review.

### Verdict

**APPROVED WITH MINOR FIXES** — both required fixes are documentation-only (CLAUDE.md invariant
text, STRUCTURE.md module entries), cost no code change, and do not need to loop back through
Implementer; they can be applied directly before merge.

### Review Confidence

Full read. All ten touched `src/` files read in full diff, both new tests files' fence/lock/
single-unit sections read, the four real-poll-loop Co-moving-Fields tests read in full, two
targeted mutation tests run against the two highest-risk invariants named in the dispatch
(no-omniscience fence, sight-lock-vs-OBSERV-off), and all four mechanical checks (`ruff format`,
`ruff check`, `mypy --strict`, `pytest`) run and confirmed green. Not spot-checked.

---

## Reviewer: BL-B67 Stage 4 (aircraft-layer payload feed)

Branch `feature/bl-b67-atgm-run`, fast-forwarded into this worktree from `ca69f8ec` to the dispatched
tip `8ca495ad775562c35b691dab6dfd6b83f25861ac` (tree was clean, HEAD was a strict ancestor of the
tip — plain `git merge --ff-only`, no cherry-pick needed). Diff under review: the single commit
`8ca495ad` only (`git show --stat`: 13 files, 1057 insertions / 7 deletions) — Stages 1–3's commits
(`7aee88de` through `901daf9b`) are already reviewed above and not re-read here.

Inputs read in full: `plans/bl-b67-atgm-run/plan.md` (Stage 4's own paragraph, "Affected Modules" —
aircraft-layer section, "Reused, not rebuilt", the risks list), `implementation.md`'s Stage 4
section (all 5 flagged deviations), `security-plan-review.md` (the `/payload/latest` paragraphs —
"extends an already-accepted exposure shape, not a new one", no outstanding item for this stage),
`aircraft-layer/research/2026-10-29-bl-b67-loadout-and-atgm-object-recon.md` Finding 1 (the
documented-but-unconfirmed `LoGetPayloadInfo` shape). Source diff read in full: `Export.lua`'s
`push_payload_state`, `src/schema/payload.py`, `src/collector/cache.py`/`server.py`/`__main__.py`,
`src/api/server.py`, `body-layer/src/aircraft_client.py`. Both new test files
(`test_payload_api.py`, `test_payload_lua.py`) and the `test_aircraft_client.py` additions read in
full.

### Checks run

- `luac5.1 -p Export.lua`: pass. `GETGLOBAL` bytecode scan (the exact command in the dispatch):
  every global read is either this project's own `DUMPED_*`/`io`/`lfs` pattern, a genuine DCS API
  (including the two new ones, `LoGetPayloadInfo`/`LoGetNameByType`), or Lua stdlib — **no
  own-helper name appears** (`push_payload_state`, `json_escape_string`), confirming the no-hoisting
  rule is honoured (function defined below `safe_call`, matching `implementation.md`'s claim).
- aircraft-layer (from the worktree's own `.venv`): `ruff format --check src tests` — 75 files
  already formatted; `ruff check src tests` — all checks passed; `cd aircraft-layer &&
  .venv/bin/mypy src` — 0 errors, 26 files; `pytest tests -q` — **645 passed**, matching
  `implementation.md`'s reported count exactly.
- body-layer: `ruff format --check` / `ruff check` — clean; `mypy src` — 0 errors, 78 files;
  `pytest tests -q` — **2735 passed, 4 xfailed**, matching `implementation.md`'s reported count
  exactly.

### Mutation verification (not just reading)

- Removed the `if signature == payload_last_signature then return end` early-return from
  `push_payload_state` and re-ran `test_payload_lua.py` against the live, patched source (the test
  harness extracts the real function text, so this exercised the actual change, not a copy):
  `test_unchanged_signature_sends_only_once` failed correctly, asserting a non-`None` second line
  where `None` was expected. Reverted (`git status --porcelain` clean afterward). **This is the one
  behaviour-affecting mechanism this stage adds** (the change-gate), and the test that is supposed
  to pin it does.
- Checked the `pairs()` ordering risk this stage's signature construction depends on directly, not
  by inspection only: `for i, st in pairs(payload.Stations or {})` builds the signature string from
  iteration order, and `pairs()` order is unspecified by the Lua language spec in general. Ran a
  5-trial probe (`luajit`, the interpreter installed here) iterating a dense 1–8 array table built
  fresh each trial: order was `1,2,3,4,5,6,7,8` every time — consistent with the Lua 5.1
  reference-implementation behaviour of walking the array part before the hash part, which this
  file's own existing code already relies on in four other `pairs()` loops (`line_of_sight`/
  `watched_args` state, line 1964 is the fifth, not a new pattern). Not a defect; recorded here
  because it is exactly the kind of thing that looks fragile on a read and isn't.

### Findings by checklist item

- **Scope fits the plan exactly.** Stage 4's own paragraph says "this stage is safe before Stage
  0... Q1 can only change the payload schema's field names." The diff touches only
  aircraft-layer's wire/schema/cache/API layer and `aircraft_client.py`'s one new method — no
  `belief/atgm_run.py`, no station/family logic, confirmed by `git show --stat` showing no file
  under `body-layer/src/belief/` in this commit. Matches the plan's own "Stages 1-3... and Stages
  5-8 are untouched" statement in the commit message, and it's true.
- **Provenance fields present and correctly named.** `PayloadSample.dcs_model_time_s` +
  `received_wall_clock_s` — the project's dual-clock convention, same field names as every sibling
  schema (`sight_servo.py`, etc.). Not a mixing-DCS-with-external-GIS feature (this is DCS-only), so
  the confidence/provenance checklist item for *that* case doesn't apply here, but the
  model-time/wall-clock pair the project requires on every live sample is correctly carried.
- **Tolerant parsing matches the stated uncertainty, and is the right amount of tolerant.**
  `schema/payload.py`'s module docstring states plainly that `LoGetPayloadInfo` on the Mi-24P is
  "inferred, not probed" — `name` is passed through unvalidated and an empty `stations` list parses
  cleanly rather than erroring, which is exactly what a Stage-0-pending probe needs: if Q1 comes
  back with different field *values* (store names, counts), nothing here breaks; if Q1 comes back
  with `LoGetPayloadInfo` absent on this airframe (`type(payload) ~= "table"`), `push_payload_state`
  already returns early and sends nothing, which the API already treats as "not an error" (`null`).
  The schema does still *require* `t`/`current_station`/`stations` as keys and type-checks every
  field it does see (`PayloadParseError` on a wrong type) — so "tolerant" means tolerant of *values*
  this project hasn't confirmed yet, not tolerant of a malformed line. That is the correct line to
  draw, and it is the one the plan's "no pipeline code depends on Q1 to build" framing asked for.
- **`EXPECTED_EXPORT_VERSION`/`EXPORT_SCRIPT_VERSION` bumped together, same string, same commit** —
  both `"2026-10-29"`, confirmed by diff; an old deployed `Export.lua` degrades gracefully (never
  sends `"stations"`, `PayloadCache` stays empty, `/payload/latest` answers `null`) rather than
  breaking, matching every prior version-bump's stated behaviour in this file.
- **Wire parser bounds (untrusted DCS strings)**: `PayloadStation.from_dict` rejects a non-string
  `name`, a non-boolean `container`, a non-numeric `count`/`index` — type bounds are present. There
  is **no length bound on `name`** (unlike `schema/firing.py`'s own `OwnWeaponRawEvent` type field,
  truncated to 48 chars Hook-side per the plan's Stage 5 text) — but that bound exists there because
  the firing Hook's line travels over the Hook's own small per-line budget on a 1 Hz drain and feeds
  a bounded in-memory ledger; this feed travels as one JSON object over TCP through `json.loads`
  with no equivalent fixed-size downstream structure, and `name` is `LoGetNameByType`'s own DCS
  store-name return value, not attacker-shaped input. Security's own review already classified
  `/payload/latest`'s exposure (LAN-reachable, read-only, "ammo-station counts... no credential, no
  write capability") as accepted under this project's single-user/LAN-only threat model — a missing
  length cap on an internal DCS string doesn't change that classification. Not a finding.
- **404/empty-before-first-sample behaviour is tested, not just asserted**: both
  `TestPayloadLatestEndpoint::test_null_before_the_first_line_arrives` (a real `TelemetryAPIServer`
  on an OS-assigned port, a real `urllib.request` GET) and the collector-level
  `TestPayloadCache::test_empty_until_a_line_arrives` cover it; confirmed by reading both, not
  inferring the behaviour from the cache's `latest()` docstring alone.
- **Tests are real, not decorative** — verified above by mutation on the one behaviour-affecting
  mechanism (the change-gate), and by reading the Lua test harness: it slices the actual
  `push_payload_state`/`json_escape_string` functions out of the real, currently-deployed
  `Export.lua` and runs them under a real Lua interpreter against a mocked `LoGetPayloadInfo`/
  `LoGetNameByType`/`client`, rather than a hand-duplicated copy that could silently drift from the
  shipped source.
- **No tunables added, correctly** — the change-gate signature does exact-equality comparison
  (station index/name/count, current station), no threshold or epsilon, so there is nothing here
  that qualifies as a behaviour-affecting constant under the `tuning.py` rule. `implementation.md`
  states this explicitly (point 5) and it's correct on inspection — confirmed no new literal in the
  diff resembles a tunable (compared against `tuning.py`'s existing entries, none added).
- **Comment pruning**: the one touched comment block with prior content is `EXPORT_SCRIPT_VERSION`'s
  own header comment — nothing was deleted from it, only appended (the new paragraph is additive,
  the prior bump's own dated paragraph is untouched above it). No `#:`-rendered `defaults.toml` text
  is touched by this stage (no tunables), so that half of the check doesn't apply. No boundary case
  silently dropped from a comment into nothing — the one new deliberate judgment call (see below) is
  explicitly flagged in `implementation.md`, which is the correct place for a new flag, not a
  pre-existing comment that needed pruning.

### The two flagged deviations, judged

1. **`container` excluded from the change-gate signature, but carried on the wire.** This is a
   genuine judgment call (no plan text decides it either way), it is flagged exactly as the plan's
   "flag it rather than inheriting it silently" instruction asks, and the reasoning given (a
   container flag flipping independently of name/count is not a loadout change this feed exists to
   report) is sound — nothing downstream reads `container` yet, and Stage 6's station-selection logic
   keys on `count`, not `container`. **Gap, not a defect**: no test pins this exclusion either way —
   if a future edit accidentally folded `container` into the signature (e.g. "while touching this
   function, tidy the signature to include every field"), nothing would fail, and the loadout feed
   would start resending on every poll where DCS reports no load change but flips a container flag
   that Q1 hasn't even confirmed exists reliably. Low risk today (nothing reads `container`, so a
   silent regression here costs an occasional extra wire send, not a wrong belief), but cheap to
   close — one `test_payload_lua.py` case: a frame that flips only `container` on an otherwise
   unchanged station must not resend. **Optional, not required** — recorded for the Implementer to
   pick up opportunistically, e.g. alongside Stage 5 or 6 when this file is touched again.
2. **`Cannon` read by `LoGetPayloadInfo()` but never sent.** Nothing reads it, there is no behaviour
   to regress, and the absence is stated plainly in both the Lua comment and `implementation.md`
   point 3. No test can meaningfully pin an absence that nothing downstream depends on; not a gap.

### Required fixes

None.

### Optional refinements

- Add one `test_payload_lua.py` case pinning that a `container`-only flip on an otherwise-unchanged
  station does not resend (see deviation 1 above) — cheap, and closes the one case where a future
  "tidy this up" edit could silently change wire behaviour with no test catching it.
- `aircraft-layer/CLAUDE.md`'s "Structure" section (`src/api/`'s endpoint list, `src/collector/`'s
  cache list) is not updated with `/payload/latest`/`PayloadCache` in this diff — consistent with
  how Stage 4 was scoped (the plan's own "Affected Modules" doesn't list this file), and the module
  docstrings this stage *does* update (`api/server.py`'s own endpoint-list docstring,
  `collector/__main__.py`'s wiring docstring) already carry the equivalent detail inline, which is
  where a reader actually looking at this code will see it first. Not required — `CLAUDE.md`'s own
  "Structure" bullets are already a step behind several other endpoints (e.g. `/mission_start/
  latest` gets one line there; several `watched_args`/`sight_servo` details don't), so this isn't a
  regression this stage introduced, just an existing gap it didn't need to close.

### Verdict

**APPROVED**

### Review Confidence

Full read. All 6 modified/new `src/` and `Export.lua` files read in full diff; both new test files
(`test_payload_api.py`, `test_payload_lua.py`) and the `test_aircraft_client.py` addition read in
full; one mutation run against the stage's one behaviour-affecting mechanism (the change-gate),
caught correctly; the `pairs()` ordering question probed directly with a live interpreter rather
than assumed; all four mechanical checks run per subproject and confirmed green with counts matching
`implementation.md` exactly; the Lua `GETGLOBAL` bytecode check re-run and confirmed clean. Not
spot-checked.

---

## Reviewer: BL-B67 Stage 0 (ATGM-run probe sortie) — pre-flight review

Branch `feature/bl-b67-atgm-run`, fast-forwarded into this worktree from `ca69f8ec` to tip
`739f533f` (tree was clean, HEAD was a strict ancestor of the tip — ff, not cherry-pick). Reviewed
**before the user flies it**, per this review's purpose: catch anything that would waste the
sortie or answer the wrong question, not a post-hoc check.

Read in full: `aircraft-layer/dcs-export/Export.probe-weapons.lua`,
`aircraft-layer/dcs-export/petrobrain-damage-events-probe-hook.lua`,
`docs/acceptance/2026-10-29-bl-b67-stage0-probe.md`, `implementation.md`'s Stage 0 section (all 5
flagged deviations), `plan.md`'s Stage 0 item/Q-table/Risks section,
`aircraft-layer/research/2026-10-29-bl-b67-loadout-and-atgm-object-recon.md`,
`body-layer/config/sequences/mi-24p/switch-reference.md`'s Device 6/7 rows, `aircraft-layer/
CLAUDE.md`, `aircraft-layer/WORKFLOW.md`.

### Checks run (not just trusted from `implementation.md`)

- `luac5.1 -p` on both outer files: **pass** (re-run myself, `luac5.1` is available at
  `/opt/homebrew/bin/luac5.1`, Lua 5.1.5 — the correct DCS-embedded version).
- `GETGLOBAL` check on both outer files: **clean**, matches `implementation.md`'s claim exactly —
  only genuine DCS APIs (`GetDevice`, `LoGetModelTime`, `LoGetNameByType`, `LoGetPayloadInfo`,
  `LoGetWorldObjects`, `log`, `net`, `require`) and Lua stdlib.
- `GETGLOBAL` check on all four extracted `dostring_in` literals (`LIFE_CODE`,
  `EVENT_REGISTER_CODE`, `EVENT_POLL_CODE`, `WEAPON_EXIST_POLL_CODE`), extracted myself with a
  throwaway script rather than re-using the implementer's own extraction: **clean** on all four —
  only `coalition`/`ipairs`/`pairs`/`pcall`/`string`/`table`/`timer`/`tostring`/`type`/`world`
  (genuine) and `PB_PROBE_EVENT_NAMES`/`PB_PROBE_EVENT_QUEUE`/`PB_PROBE_HANDLER_REGISTERED`/
  `PB_PROBE_KEPT_WEAPON` (the deliberate cross-`dostring_in` shared-global set, matching the
  file's own documented pattern). No own-helper-referenced-before-its-`local` bug found.
- Device/cmd/arg numbers checked against `switch-reference.md` directly, not assumed from the
  code comment: Device 7 ("I9K113") row 213, `SHSCHO-KNOB-PTR`, cmd **3038**, arg **963**,
  `multiposition_switch`, "0 to 0.8 (9 steps)" — matches the probe's `CMD_KNOB`/`ARG_KNOB` and its
  `n * 0.1` write exactly. Row 270, `OP-AIM-RESET-RAD-PTR`, cmd **3029**, arg **882**,
  `default_button`, "0/1 momentary" — matches `CMD_RAD_RESET`/`ARG_RAD_RESET` and the
  press-then-release sequencing exactly. `DEV_I9K113 = 7` also matches the production
  `Export.lua`'s own constant (grepped: `aircraft-layer/dcs-export/Export.lua:272`). No mismatch.
- Clock correlation across the two log files: the Export probe stamps `LoGetModelTime()`; the Hook
  probe stamps `timer.getTime()` read inside the `"scripting"` state (not the Hook's own
  `DCS.getRealTime()`). These are the same simulation clock by established project convention —
  `petrobrain-mission-telemetry-hook.lua`'s own header note (lines 36-43) documents exactly this
  equivalence and explains why `DCS.getRealTime()` is avoided (wall-clock drift). So the card's
  instruction to correlate `payload`/`COUNT DROP` lines (Export probe) against `OWN_SHOT`/
  `WEAPON_GONE` lines (Hook probe) by timestamp is sound, not an assumption this review had to
  take on faith.
- Each Q in the card's table traced to an actual log line the code emits: Q1 → `payload
  current=... stations=...` (confirmed emitted every poll by `poll_payload`/`format_payload`) +
  `COUNT DROP step=... N->M`; Q2 → `NEW: <name> keys=...` (first-seen key dump, confirmed in the
  per-poll loop); Q3 → `SWEEP write step=N` / `arg963(knob)=...` / `payload current=...` together
  (confirmed: `poll_watched_args` logs on change, `run_knob_script` logs each write); Q5 →
  `RADIATION RESET pressed/released` + `arg882(rad_reset)=...` (confirmed); Q6 → `OWN_SHOT ...`,
  `WEAPON_GONE t=...`, `HIT_ON_KEPT_WEAPON` (confirmed in the Hook's event handler and poll
  functions). No Q is asked for a line the code does not actually produce.
- No pipeline code, no DCS state mutated outside a clickable cockpit control (`performClickableAction`
  on cmd 3038/3029 only — neither is a weapon-release or jettison command per `switch-reference.md`,
  so the scripted sweep/park/reset cannot itself fire a weapon or drop a store).
- Card: names the branch, states air-start/straight-and-level, is numbered, ~10 minutes, and the
  bring-back list (two log files + the user's own clock-at-impact note) is complete against what
  the Results section and Q6's own "gap... only you can give" framing need.

### Required Fix

**The auto-advance switches the knob away from the just-fired station on the same poll the count
drops — which, per the plan's own stated unknown (Q1: "when does the count drop relative to the
shot?"), is very plausibly at or immediately after launch, i.e. while the just-launched missile is
still in flight (a Shturm's ~3.5 km flight at 345 m/s is ~10 s).** This is exactly the action the
plan's own Risks section (`plan.md`, "Knob turned during flight") calls "unknown" whether it
breaks guidance in DCS, and says production's own design "never does it" for that reason
(selection barred in InFlight). The Stage 0 probe's `maybe_advance_station` (triggered by
`LoGetPayloadInfo`'s count-drop, not by the Hook's `WEAPON_GONE`) does exactly this untested thing,
on the very first shot the sortie fires — and the card, the plan's Q-table, and
`implementation.md`'s deviation list (which flags the *station-index* assumption in the same
function, but not this one) are all silent about it.

If switching the SHSCHO knob mid-flight does affect which missile receives guidance commands, the
most likely visible consequence is the first Shturm going unguided or off-target a few seconds
after launch — which would (a) make the "note the clock at the moment you see it hit" instruction
unreliable for missile 1 (a wandering, possibly out-of-view detonation has no clean "visible
impact" moment), and (b) read, to the user watching, as an ordinary missed shot rather than a
probe-script side effect, with nothing in the card telling them which it was. That is squarely the
kind of thing that wastes a flight or produces a misleading answer to the wrong question — here,
conflating "did my shot miss" with "did switching stations break guidance," neither of which the
sortie currently distinguishes.

Two independent ways to close this, either is enough — recommend the first as cheaper and more
conservative, but the choice is the user's:

1. **Delay `maybe_advance_station`'s write** by a fixed interval after the count-drop it detects
   (e.g. close to `ATGM_MAX_FLIGHT_S`'s already-estimated ~17 s real flight time, or simply "wait
   N seconds" using the same `model_time()` gating the SWEEP/PARK/RESET state machine already
   uses) rather than switching on the same poll. A few lines, no new mechanism, keeps the
   auto-advance (so the pilot still never touches the knob) while removing the exact action the
   production plan flags as unverified from happening during this sortie's own first missile
   flight.
2. **Or, if the user would rather fly it as specified** and treat the question itself as
   additional data worth having (does switching stations right after launch visibly disturb the
   missile?) — add one line to the card saying so explicitly, and asking the user to note whether
   the first Shturm's flight looked normal or erratic, so a genuine miss is distinguishable from a
   probe-script side effect in the bring-back.

Either is a small change; the point is that right now neither the card nor the plan's own
deviation list surfaces this to the user before they fly, even though the plan already named the
underlying risk as unknown.

### Optional Refinements

- `SWEEP` skipping knob step 0 as "off" (comment, `Export.probe-weapons.lua` line 141-142) is
  asserted, not confirmed against `switch-reference.md`, which gives the value range ("0 to 0.8,
  9 steps") but not per-step semantics. Low-risk: if step 0 were in fact a loaded station, the
  sweep's own `sweep_best_step` logic would simply never pick it (first checked is step 1), so the
  worst case is defaulting to step 1 with a logged "no loaded station found during sweep" line
  that already exists for the no-stations-at-all case — not a silent failure, just worth noting
  this is an assumption rather than a confirmed fact, in case the sortie's own log contradicts it.
- The single-kept-weapon-slot limitation (deviation 4) and the no-tunables-outside-body-layer
  posture (deviation 5) are correctly flagged and both match project convention
  (root `CLAUDE.md`'s "Behaviour-affecting constants" section on declaring normally outside
  body-layer) — no action needed, noted only for completeness of this pass.

### Verdict

**NEEDS REVISION** — one required fix (the knob-during-flight gap), cheap to close either way
(code delay, or a one-line card addition plus the user's own call on which they'd prefer),
before this sortie is flown. Everything else checked — the mechanics the sortie is built to
measure (device/cmd/arg numbers, the Q-to-logline mapping, the Lua syntax/global checks, the
deploy/restore steps, the card's shape) is correct and ready.

### Review Confidence

Full read of both Lua files and the card. Mechanical checks (`luac5.1 -p`, the `GETGLOBAL`
bytecode scan on all six Lua units — two outer files plus four extracted `dostring_in` literals)
re-run independently rather than trusted from `implementation.md`. Device/cmd/arg numbers checked
directly against `switch-reference.md`, not assumed. No live DCS access from this machine — the
one thing this review cannot do is confirm the knob-during-flight risk empirically; it can only
confirm the risk is real, undocumented to the user, and cheap to close.

---

## Reviewer: BL-B67 Stage 3 (`atgm_run.decide` + in-flight hold + guidance-floor settle)

**Dispatch note on branch state**: the dispatched tip was `44ad42beefdd0031864afffd758cb228131521bc`.
This worktree's own `HEAD` (`30a663b5`, on `worktree-agent-a76778b2f3afacfe5`) is **not** an
ancestor of that tip, and the tip is not an ancestor of `HEAD` either — the two have diverged (this
worktree branched from `main` well after the feature branch split off, and the feature branch's own
history — Stage 0 review/fix, explore rounds 6-8, Stages 3/4 — was never rebased through here). Per
dispatch instruction, no `git merge --ff-only` was attempted. Verified instead against an isolated
snapshot: `git archive 44ad42beefdd0031864afffd758cb228131521bc | tar -x -C <scratch>`, with every
check run from inside that scratch tree's own `body-layer/`. This file is written and committed in
this worktree for the orchestrator to harvest onto the feature branch; the content below is accurate
against the dispatched tip regardless of which branch holds it.

Diff under review: the single commit `44ad42be` (14 files, 1887 insertions / 31 deletions). Stages
0/1/2/4 are already reviewed above (or, for Stage 0's required fix, tracked in `implementation.md`)
and not re-read here except where Stage 3 touches the same files.

Inputs read in full: `plan.md` (the full "Design" section, "Range calls", "Silence while the missile
flies", "Launch and impact detection", the Co-moving Fields table, Decisions N1-N3), `explore-notes.md`
rounds 7-8 (the user's own words — these override `plan.md`'s own decisions section per this review's
dispatch, and in practice the two agree: round 7 decision 1 is "Range calls," decision 2 is "Silence
while the missile flies," round 8 N1/N2 are the backstop and the Danger-drop), `implementation.md`'s
Stage 3 section (all 7 numbered deviations/discoveries), `review.md`'s own Stages 1-2 entry (above —
confirming both its required fixes actually landed: `CLAUDE.md` line 323 and `STRUCTURE.md`'s
`atgm_run.py`/`source.py` entries all now name `aim_unit_direction`, checked directly, not assumed).
Source diff read in full: `atgm_run.py` (now 280 lines, read end to end, not just the added blocks),
`speech.py`, `attack_run.py`, `crew_console.py`, `callouts.py`, `body.py`'s two touched sites,
`STRUCTURE.md`'s rewritten entry, the regenerated `defaults.toml`'s rendered `[belief.atgm_run]`
block (read the rendered file, not the source `#:` comments, per this role's own standing
instruction). All three new/extended test files read in full (`test_atgm_run.py`, the `test_callouts.py`
and `test_attack_run.py` additions).

### Checks run

From the scratch snapshot's `body-layer/`, against the repo-root venv
(`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/`):
- `ruff format --check src tests tools`: 190 files already formatted.
- `ruff check src tests tools`: all checks passed.
- `cd body-layer && .venv/bin/mypy src`: 0 errors, 78 files.
- `pytest tests -q`: **2776 passed, 4 xfailed** — matches `implementation.md`'s reported count
  exactly (2735 → 2776, +41: 36 `test_atgm_run.py` + 3 `test_callouts.py` + 2 `test_attack_run.py`).
  Repeated (full suite, twice) and `--collect-only` three times: collection order was identical
  every run (file-then-definition, as pytest does with no active randomizer) — see the flake note
  below.

### Mutation verification (not just reading)

Five targeted mutations against the stage's highest-risk claims, each reverted and the suite
re-confirmed green afterward:

1. **Range calls, "starts in range says neither."** Changed the silent in-range branch of
   `_maybe_range_call` (`atgm_run.py` line ~374) to speak `render_range_state(in_range=True)`
   instead of `None`. `test_run_starting_in_range_says_neither` failed correctly (asserted `()`,
   got `["In range."]`). **Caught.**
2. **Backstop silence, Decision N1.** Changed `_in_flight_tick`'s `speech = (render_impact(),) if
   inputs.missile_gone else ()` to unconditionally `(render_impact(),)`.
   `test_backstop_leaves_in_flight_silently_after_max_flight_time` failed correctly (expected `()`,
   got `["Impact."]`). **Caught.**
3. **No-ATGM-at-start, "No more missiles."** Changed `_preparing_tick`'s empty-station branch to
   return `()` instead of `(render_no_more_missiles(),)`.
   `test_preparing_with_no_atgm_loaded_says_no_more_missiles` failed correctly. **Caught.**
4. **Decision N2, "Danger `<unit>`" dropped during the flight.** Widened `callouts.py`'s
   `hold_routine` pass-through condition (line ~1253) from `event.kind == CONTACT_FIRING_SEEN and
   event.targets_ownship` to also admit `event.kind == CONTACT_ENGAGEMENT_CHANGED` — i.e. exactly
   the regression round 8's N2 answer (*"focus is on guidance during missile flight. Drop the
   danger callout."*) forbids. **Ran the full `test_callouts.py` suite: 74/74 still passed, zero
   failures.** This is a real gap, not a reading error — see Required Fixes below.
5. **Failed launch, "treat as not launched."** Confirmed by inspection (not by mutation, since
   there is nothing to mutate: `decide` never reads `inputs.failed_launch` at all, per that
   dataclass's own docstring) that no state field, speech, or action depends on it —
   `test_failed_launch_gives_no_speech_no_state_change_and_no_reset` pins exactly this absence.

All five mutations reverted; re-ran `pytest tests -q` after the last one and confirmed
2776 passed, 4 xfailed, matching the pre-mutation baseline.

### Findings by checklist item

- **Range calls per run** (round 7, decision 1): verified correct by mutation (#1 above) and by
  reading `test_run_starting_out_of_range_says_out_then_in_range_once` end to end — out-of-range
  speaks once, stays silent while still out, speaks "In range." once on the crossing, then stays
  silent for the rest of the run including a later missile and a range that re-opens past max.
  Matches round 7 exactly: *"per run, but only if out of range first. If run starts in range, say
  nothing."*
- **In-flight hold + pass-through set** (round 7/8, decisions 2 and N2): `CONTACT_FIRING_SEEN`
  with `targets_ownship` passes, everything else — including `CONTACT_ENGAGEMENT_CHANGED` — is
  held, matching the design table in `plan.md` ("Silence while the missile flies"). The *mechanism*
  is correct (read in full, confirmed against `callouts.py`'s diff); the **test coverage for the
  N2 half specifically is not** (mutation #4). See Required Fixes.
- **Guidance unit not ready → refusal**: unchanged from Stage 1 (not touched this stage); confirmed
  by `git show --stat` showing no change to `crew_console.py`'s refusal gate.
- **Failed launch, "log it, treat as not launched"** (round 7, decision 4): correct by design —
  `decide` structurally cannot act on `failed_launch` because it never reads the field. The actual
  *logging* (round 7's "log it" half) is explicitly Stage 7's job (`body.py`, not built yet) — this
  is consistent with the plan ("the caller... logs the raw event directly to the sight trace/
  belief-truth log, never through `decide`'s return") and is not a gap in this stage.
- **N1 backstop**: silent, resets (`Fire("atgm-impact")`), and (via `_resetting_tick`) selects the
  next loaded station, all confirmed by mutation #2 and by reading `_in_flight_tick`/
  `_resetting_tick` together. The **error log** (round 8's "log an error" half) is, like the
  failed-launch log line, Stage 7's job — `decide` has no logging side channel by design (pure
  function, no I/O), so this cannot be Stage 3's to produce. Correctly deferred, not missing.
- **No-ATGM → "No more missiles."** (round 7, decision 5): verified at both the Preparing
  (run-start) and Tracking/Resetting (mid-run empties-out) entry points, by mutation (#3, Preparing
  only) and by reading `_tracking_drop_check`/`_resetting_tick`'s matching branches, which share the
  station-selection rule (`_resolve_station_selection`) rather than duplicating the "nothing loaded"
  check three times.
- **Count-drop-without-shot grace rule**: `_tracking_drop_check` arms
  `unconfirmed_drop_since_sim` on the first poll the selected station's count reads lower than last
  seen, resolves after `ATGM_UNCONFIRMED_DROP_GRACE_S`, and a `LaunchEvent` arriving before the
  grace elapses is handled by `decide`'s own ordering (the Preparing/Tracking block checks
  `inputs.launch` *before* falling through to `_tracking_drop_check`, so a launch inside the grace
  window always wins and the drop timer is cleared as part of the same transition) — confirmed by
  reading `decide`'s own docstring and `test_count_drop_followed_by_launch_inside_the_grace_window_
  gives_no_selection_before_the_launch`.
- **Guidance-ladder floor settle** (Stage 1/2's flagged deferral, "made, not deferred further"):
  `attack_run.decide` gains `guidance_floor`, threaded at the same `runner.atgm_run_state is not
  None` granularity `vertical` already uses — not narrowed to `home_phase is SIGHTING`, with the
  reasoning given (`BL-B71`'s own "continuous and bidirectional" ladder) checked against that
  module's own docstring directly, not taken on the implementer's word. This is a genuine
  design decision the Stage 1/2 review flagged as owed ("Stage 3 must make an explicit decision
  here") and it has been made, with a reason, not silently resolved either way.
- **Tunables, lo/hi bounds, rendered `defaults.toml`**: all seven entries checked in the rendered
  file (`config/defaults.toml`, `[belief.atgm_run]` block), not the source comment. All seven
  render correctly — first sentence intact, no markdown corruption across the line wraps, no
  truncated warning (none of the seven's *second* sentence is a warning/consequence the first
  sentence doesn't already carry — `ATGM_MAX_FLIGHT_S`'s dropped second sentence is the Ataka
  15 s derivation, informational, not a warning; see Optional Refinements for the one wording nit).
  `lo`/`hi` bounds are plain numeric literals in every case (confirmed by reading, not just trusting
  `generate_defaults.py --write`'s clean exit). **One of the seven, `ATGM_MIN_RANGE_M`, is declared
  and rendered but never read by any code this stage adds** — see Required Fixes; this is the one
  genuine gap in an otherwise clean tuning pass.
- **Cross-key couplings**: confirmed none — `_FAMILY_SPEED_MPS`/`_FAMILY_MAX_RANGE_M` are plain
  dicts keyed by `family_of`'s return value, not asserted against each other or against
  `ATGM_MIN_RANGE_M`/`ATGM_MAX_FLIGHT_S` anywhere in `src/`. No import-time assertion exists linking
  any two of the seven.
- **Scope fits Stage 3 exactly**: no file under `perception/own_weapons.py` (Stage 5),
  `effector_sequences.py`'s enum (Stage 6), or `atgm.toml` (Stage 5/6) is touched — confirmed by
  `git show --stat`. `LaunchEvent`/`FailedLaunch`/`Fire` are declared locally in `atgm_run.py`
  rather than imported from a module that doesn't exist yet, exactly as the module's own docstring
  states and exactly the right call for a pure-function stage that must not block on Stage 0's
  probe answers.
- **The discovered re-point gap** (`body.py`'s engage-apply block always builds a fresh
  `AtgmRunState` on re-point, contradicting the plan's own Co-moving Fields table): see its own
  section below.
- **Comment pruning** (deviation 6): `STRUCTURE.md`'s `atgm_run.py` entry's own forward-reference
  sentence ("the state machine... are Stage 3") was deleted and replaced with what Stage 3 actually
  built, confirmed by reading the diff directly — this is exactly the right prune (a stale
  forward-reference superseded by the thing it pointed at, not a durable/dated line, not a `#:`
  block, not a dropped boundary case).

### The discovered re-point gap — decided: safely deferred to Stage 7, not a required fix now

`body.py`'s engage-apply block (`AtgmRunState(contact_id=atgm_contact_id)`, Stage 1's own
construction site, `body.py:3746`) always constructs a wholesale-fresh `AtgmRunState` on every
`engage ... missiles`, including a re-point while an ATGM run is already active. The plan's own
Co-moving Fields table says the opposite for that exact transition: keep `phase`/in-flight/
`selected_step`, reset only the range latches and `contact_id`.

**Verified this is genuinely inert right now, not merely asserted to be**: grepped the entire
snapshot's `src/` for any call to `atgm_run.decide` outside the test suite —
`grep -rn "atgm_run\.decide\|import atgm_run" body-layer/src` returns exactly one hit,
`body.py`'s `from belief.atgm_run import AtgmRunState` (the dataclass only, never `decide`). Stage
3 added the state machine but nothing in `body.py`'s own poll loop calls it yet — that wiring is
explicitly Stage 7's. So the fields the re-point gap would silently drop (`phase`, `in_flight_since_sim`,
`selected_step`, `tracked_family`) are never read by any production code path today; the gap has
zero observable behaviour until Stage 7 wires `decide` into the loop. On that basis: **not a
required fix for Stage 3.**

It is, however, flagged in three places (`STRUCTURE.md`'s `atgm_run.py` entry, `implementation.md`'s
Notable Discoveries #2, and a new agent-memory file,
`.claude/agent-memory/implementer/project_bl_b67_atgm_run_repoint_gap.md`) — all three read and
confirmed accurate. This is the **third** recorded instance of the exact defect shape
`.claude/agent-memory/dod/project_recurring_stale_state_on_transition.md` already tracks across two
other features (`BL-14`, four instances; `BL-B64`, at least two more) — a fresh-construction
re-point that drops a field added after the construction site was written, caught only because this
review went looking for it rather than because any mechanism prevents it. **Treat this as a hard
blocking precondition for Stage 7's own dispatch, not a "nice to remember" note**: whoever wires
`decide` into `body.py`'s poll loop must fix the engage-apply block's re-point branch (`replace()`
instead of fresh construction when an ATGM run is already active) *before* or *as part of* that
same stage, not after — the moment `decide` is wired in without that fix, a re-point mid-flight
silently forgets the missile is in flight and resets to `PREPARING`, which is now live and user-
visible, not latent.

### Required fixes

1. **`ATGM_MIN_RANGE_M` is declared through `tuning.py` (bounds 0–2000, rendered into
   `defaults.toml` as "the shared minimum range below which the range calls say nothing at all")
   but is never read by `decide` or any helper it calls** — confirmed by
   `grep -rn "ATGM_MIN_RANGE_M" body-layer/src body-layer/tests`: it appears only in its own
   declaration and in two *test* call sites that use it to compute a belief range, never as a
   condition inside `atgm_run.py`. In the overwhelming majority of reachable cases this is harmless
   by construction — the one-way `range_calls_done` latch means a run that was ever "in range"
   never speaks again regardless of how close the target gets, so "inside 400 m says nothing" (the
   plan's own wording) holds *as a side effect* of the max-bound-only latch, not because the
   minimum is enforced. But it is not equivalent in one edge case I confirmed directly: a run that
   is beyond max range (`range_out_called=True`, `in_range_call_pending=True`) and whose belief
   range jumps, in a single poll, from beyond max straight to *below* `ATGM_MIN_RANGE_M`, speaks
   "In range." — which is correct per the max-bound rule but contradicts the plan's literal "Inside
   400 m says nothing" if that sentence is read as "no range-call speech once inside the floor, no
   matter how it got there." (Reproduced with a one-off probe test against the real `decide`
   function: a `TRACKING` state with `range_out_called=True, in_range_call_pending=True` fed
   `belief_range_m=200.0` — below the 400 m floor — speaks `["In range."]`.) Given the ~4,600 m gap
   between `SHTURM_MAX_RANGE_M` (5,000) and the floor (400), this single-poll jump is not reachable
   at any realistic closing speed for this airframe/target pairing — but the constant is shipped as
   if it were load-bearing, a user tuning it in `defaults.toml` would reasonably expect changing it
   to change something, and nothing documents that it currently doesn't. Compare `own_feed_fresh`
   (`AtgmInputs`), which is *also* accepted-but-unused this stage and got an explicit
   Notable-Discoveries writeup explaining exactly why; `ATGM_MIN_RANGE_M` got none. **Fix: either**
   wire an explicit floor check into `_maybe_range_call` (so the edge case above cannot speak), **or**
   add the equivalent "accepted but intentionally unused this stage, because X" note — to the
   module docstring/`ATGM_MIN_RANGE_M`'s own comment and to `implementation.md` — that `own_feed_
   fresh` already has. Either closes it; leaving it silently unwired as shipped does not.
2. **Decision N2 ("Danger `<unit>`" dropped during the flight) has no test pinning it**, confirmed
   by mutation #4 above: widening `callouts.py`'s pass-through condition to also admit
   `CONTACT_ENGAGEMENT_CHANGED` leaves all 74 tests in `test_callouts.py` green. This is the one
   line in this stage with the most explicit, twice-confirmed user correction (round 8: *"skip"*,
   then *"focus is on guidance during missile flight. Drop the danger callout."*), and it is
   exactly the "verify by mutation per entry, not per set" failure shape this project's own
   retrospective names — a set-level property (the pass-through tuple has exactly one member) can
   look checked by the existing tests (which confirm `CONTACT_FIRING_SEEN`/`targets_ownship` passes
   and an *unrelated* `CONTACT_DETECTED` is held) without any test asserting the specific member
   that was explicitly, deliberately excluded. **Fix: one test**, the same shape as
   `test_hold_routine_still_lets_taking_fire_through`, asserting a live `CONTACT_ENGAGEMENT_CHANGED`
   candidate is held (not spoken) while `hold_routine=True`.

Both fixes are small (a documentation sentence or a short guard clause; one new test) and do not
require re-opening the state machine's design. Neither touches Stage 0/1/2/4's already-reviewed
code.

### Optional refinements

- `ATGM_MAX_FLIGHT_S`'s source comment calls Ataka "the slower family" to justify deriving 25 s
  from its figures — Ataka is actually the *faster* missile (400 m/s vs. Shturm's 345 m/s); what
  makes it the right one to derive from is that it has the *longer* flight time to max range
  (6,000/400 = 15 s vs. Shturm's 5,000/345 ≈ 14.5 s), because its range grew proportionally more
  than its speed. The arithmetic itself is correct and consistent with the code's own constants
  (confirmed: 6,000/400 = 15, matching the comment) — this is a wording nit in the comment ("the
  slower family" → something like "the family with the longer flight time"), not a numeric error,
  and the dropped-from-`defaults.toml` second sentence that carries it is informational rather than
  a consequence/warning, so it doesn't meet this project's bar for a required fix either way.
- Could not independently reproduce the order-dependent flake `implementation.md` reports in
  `test_mission_start_reset.py::test_check_for_new_mission_keeps_the_traceback_for_a_non_
  connection_failure`. The repo-root venv's `pytest_randomly` package is present on disk but has no
  importable dist-info (`pip show pytest-randomly` reports "not found"; `pytest --help` shows no
  `--randomly-seed` option), so no randomizer is actually active in the environment these checks
  ran in — `pytest --collect-only`, run three times, produced byte-identical test order every time.
  Ran the full suite twice on the pre-Stage-3 base (`232eaa9b`) and twice on the Stage 3 tip, in
  this environment: 100% pass, zero flakes, in all four runs. This neither confirms nor refutes the
  implementer's report (a flake that depends on an active randomizer in a *different* environment
  can't be exercised here either way), but since the named test's own file is untouched by this
  stage's diff (confirmed: not in the 14-file change list) and the implementer separately verified
  it passes in isolation and under a fixed order, there is no basis to treat it as a Stage 3
  regression. No action needed; noted for completeness since the dispatch asked for it.

### Verdict

**APPROVED WITH MINOR FIXES** — both required fixes are small and mechanical (a tuning-doc/guard
clause for `ATGM_MIN_RANGE_M`, one new test for the N2 pass-through exclusion); neither reopens the
state machine's design, and neither needs to loop back through a fresh Implementer dispatch from
scratch. The re-point gap is judged safely deferred to Stage 7 (verified inert: `decide` is called
from nowhere in production code this stage), on the explicit condition that Stage 7's own dispatch
treats fixing it as a precondition of wiring the poll loop in, not an afterthought — this is the
third recorded instance of the same defect shape across this project's features, and the first two
were each caught later and at higher cost than this one.

### Review Confidence

Full read. All seven touched `src/` files read end to end (not just the diff hunks, for
`atgm_run.py`, given how much of the stage's correctness lives in how the phases compose rather than
in any single function); the rendered `defaults.toml` block read directly rather than the source
`#:` comments; five targeted mutations run against the stage's highest-risk claims (range-call
latch, backstop silence, no-ATGM callout, the N2 pass-through exclusion, failed-launch no-op), one
of which (N2) found a real test gap; the discovered re-point gap verified inert by grep against the
whole snapshot's `src/`, not taken on the implementer's word; all four mechanical checks
(`ruff format`, `ruff check`, `mypy --strict`, `pytest`) run from the isolated snapshot and matching
`implementation.md`'s reported counts exactly. The test-order flake could not be reproduced in this
environment (noted above) — that one item is not independently confirmed either way. Not
spot-checked otherwise.
