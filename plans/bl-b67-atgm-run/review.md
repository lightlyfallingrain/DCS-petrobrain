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
