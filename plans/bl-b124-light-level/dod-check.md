### DoD Check — BL-B124 (light level)

**Scope.** `feature/bl-b124-light-level`, range `main..7cfbccca462b813c47978e4b6d2083bd7f4e4aad`.
Verdict is scoped to this exact tip sha — `HEAD` was a strict ancestor of it (fast-forwarded
cleanly into this worktree, tree clean before and after; confirmed via `git merge-base
--is-ancestor`). If the branch moves again before merge, this verdict is stale.

### Code Quality

- **Subprojects touched (from the diff, not memory):** `aircraft-layer`, `body-layer` (plus
  `aircraft-layer/dcs-export/*.lua`, not its own subproject but gated on `luac5.1 -p`).
  `mission-interpreter` is correctly untouched — the 2026-11-25 plan amendment superseded the
  original `.miz`/MI-3/MI-6 thread before implementation began, confirmed by `git diff --stat`
  against `main`.
- **Full suites run in this pass** (parallel, `pytest -n auto`, `slow` included — not `fast-tests.sh`'s
  own `-m "not slow"` scope):
  - `body-layer`: `ruff format --check src tests` clean (232 files); `ruff check src tests` clean;
    `cd body-layer && .venv/bin/mypy --strict src` — success, 94 source files; full suite —
    **3808 passed, 4 xfailed, 0 failed, 152.79 s**. (The "background brain reply poll failed
    (retrying)" lines in stderr are `BrainLayerClient`'s own retry-path test, not a failure —
    exit 0, matches the debugger's own account exactly.)
  - `aircraft-layer`: `ruff format --check src tests` clean (86 files); `ruff check src tests`
    clean; `cd aircraft-layer && .venv/bin/mypy --strict src` — success, 28 source files; full
    suite — **1070 passed, 12.96 s**.
  - `luac5.1 -p aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua` — clean (the one
    `.lua` file this branch touches).
  - `.venv`s used: none exist inside this worktree (as expected for an isolated worktree), so
    every command above ran against the main checkout's own `body-layer/.venv` and
    `aircraft-layer/.venv`, invoked with their absolute paths. No symlinked `.venv` was created or
    committed.
  - These figures match `implementation.md`'s and `debug-mock-flights.md`'s own reported numbers
    exactly (3808/4/0, 152.79s vs. their 3808/4/0, 151.44s — the ~1s difference is run-to-run
    noise, not a discrepancy) — **tested tree sha `7cfbccca462b813c47978e4b6d2083bd7f4e4aad`**, so
    a merge whose tree matches this sha can skip its own full run per this report's own header
    convention.
- **No unhandled errors/panics in data paths.** `_resolve_sun_elevation_deg`'s own `try/except
  AircraftLayerError` degrades to the existing forced-dark/grace/error-logged path, not a crash;
  the two `except ValueError` sites added in Stage 1-3/BL-B137 route to the same fail-loud posture.
  No new bare `except`.
- **No debug output left in committed code.** No stray `print()` outside the two sanctioned
  surfaces; `/invariant-check` confirms (see below).
- **No leftover debug code or TODO comments introduced by this feature.** `git diff main..7cfbccca
  -- '*.py' | grep -E '^\+.*TODO|FIXME|XXX'` — none. `/invariant-check`'s TODO/FIXME row is a
  pre-existing WARN with zero occurrences, confirming the project-wide convention (backlog IDs,
  not inline markers) held here too.

**`/invariant-check` (re-run in this pass, not taken from a prior report):**

| Invariant | Status |
|---|---|
| No omniscience — `derived_world_position` outside the Percept boundary | PASS |
| Module independence | PASS |
| No `sys.path` manipulation | PASS |
| `BINOCULAR_RANGE_MULTIPLIER` has not returned | PASS |
| No stray `print()` in `perception/`/`belief/` core | PASS |
| No bare `except:` | PASS |
| Swallowed exceptions (`except: pass`) | WARN, 6 occurrences — all pre-existing (`__main__.py`/`services.py`/`ui.py` entrypoints, `body.py:6630`'s REPL `KeyboardInterrupt`), none introduced by this diff (checked each against `git diff main..7cfbccca`) |
| `# type: ignore` suppressions | WARN, 16 occurrences — all pre-existing, none introduced by this diff |
| No TODO/FIXME in committed source | PASS |

### Scope & Correctness

- **Implementation matches the plan**, including its 2026-11-25 amendment (date/wall-clock from
  the firing Hook's own poll, not `.miz`/MI-3/MI-6; hybrid channel untouched). Stages 1–5 built;
  Stage 6 (`EmitterKind.EXPLOSION`, U1) correctly deferred to `[[BL-B136]]` before implementation
  began, not silently dropped.
- **No unplanned scope added silently.** The one debugger-authored commit on this branch
  (`7cfbccca`, mock-server fix) is test-infrastructure only, triggered by a real regression Stage
  4 introduced in the mock's own coverage — not a feature-scope addition, and `git show --stat`
  confirms it touches only `body-layer/tests/support/mock_aircraft_layer.py`.
- **No invariants from CLAUDE.md violated** — confirmed above by `/invariant-check` and by this
  pass's own read of the "No LAN message... carries a raw flight-axis value" and no-omniscience
  invariants against this diff (neither is touched; Security's own pass already confirmed this and
  this review re-confirms it independently).
- **All new files staged with `git add`** — confirmed via `git status --porcelain` at the end of
  this pass (see "Final state" below); nothing untracked remains.
- **Reviewed the un-reviewed debug commit as instructed.** `7cfbccca` (mock aircraft-layer serving
  a daytime `GET /firing/latest`) had not had its own Reviewer pass. Read as a reviewer would:
  - **Does the synthesised `mission_clock` keep BL-B104 scenarios in daylight as before, without
    masking a real defect?** Yes. The synthesised default (`abs_time_s = 12h + t_sim`, mid-year
    date) advances with the frame's own `dcs_model_time_s` rather than freezing, so it cannot be
    mistaken for a dead/repeated feed by `_resolve_sun_elevation_deg`'s own staleness check
    regardless of how long the test's wall-clock run takes — confirmed by reading the diff
    directly (`_firing_response`'s `abs_time_s` computation), not just the debugger's own account.
    `active: None` preserves the pre-existing "no firing feed" outcome for emitter resolution
    exactly as before — only the light-level consumer's view of this one endpoint changes. This
    does not mask a real defect: it restores the exact behaviour every existing scenario was
    written and tuned against, which Stage 4's own regression had silently inverted.
  - **Does an explicit `"firing"` frame override still work?** Mechanically yes (`frame.get
    ("firing")` returns the explicit value when present, bypassing the synthesised default
    entirely — read directly in the diff) but **no shipped test currently exercises this override
    path** (`grep '"firing"' body-layer/tests/` finds no scenario setting that key). Not a defect
    — nothing in this batch needs it yet, since every existing scenario wants the daylight
    default — but noted for whoever next writes a night-time or degraded-feed scenario test: the
    escape hatch exists and is documented in the module docstring, just unexercised today.
  - Full suite re-run independently in this pass (above) confirms 0 regressions from this commit.

### Testing

- **Core logic is covered by tests.** `light_level.py`'s astronomy and curve are pure-function
  unit-tested; the gate-3/`tier_ranges()` desync correctness trap (Stage 3's own Required Fix) and
  the per-optic resolution fix (Stage 4's departure from the plan's single-tuple design) are both
  mutation-verified by Reviewer, independently of the implementer's own account, per that review's
  "Review Confidence" sections.
- **Tests are meaningful, not decorative** — confirmed by the reviews' own mutation testing
  (guard reverted, test fails for the stated reason, restored) rather than taken on inspection; this
  pass did not re-run every mutation but spot-checked one (see Security section below) and found
  the account accurate.
- **No existing tests were broken** — full-suite pass counts above account for every test in both
  subprojects, zero unexplained deltas from `main`.

### Documentation

- **Reviewer findings addressed.** `review-stages-1-3.md` (APPROVED WITH MINOR FIXES → fix round
  APPROVED), `review-stages-4-5.md` (APPROVED WITH MINOR FIXES → fix round APPROVED),
  `review-bl-b137.md` (APPROVED WITH MINOR FIXES on the security fix itself; its one Required Fix
  was the mock-server regression, closed by the debug commit this report reviewed above). All
  required fixes traced to a landing commit; none left unaddressed.
- **Accepted-items ledger**: `.claude/scripts/accepted-items-ledger.sh plans/bl-b124-light-level`
  prints no `U<n>` lines (this plan answers its two decisions inline in the 2026-11-25 amendment
  section, not in the script's expected ledger format — confirmed by re-running the script myself
  in this pass, same empty result the Stages-1-3 reviewer already reported). Read both by hand:
  - **U1 (explosions)** — deferred, built as `[[BL-B136]]` (present in this diff, outline carried
    over verbatim from the plan's Stage 6 text).
  - **U2 (mission wall clock/date precision)** — answered and built: Stage 1 (amended) reads both
    from the firing Hook's existing 1 Hz poll; the user's own "one probe is enough" recommendation
    is carried as the open live-check item on the test card (clock check, Block 2) rather than
    insisted on as a second data point — matches the plan's own "Recommend" text.
  - **Weather** (BL-B124's own title bundles "light level and weather," but the user scoped this
    feature to light level only — explore-notes, *"Let's take the light level only, leave weather
    for later"*) is **deferred** and now has its own ID, `[[BL-B138]]`, minted in this pass rather
    than left as a title-level loose end on a now-"done" entry — this is the same class of gap the
    DoD role's own standing instruction (BR-2's U4) warns against, caught here before it could
    recur a second time on this feature.
- **Non-obvious behaviour explained**: `light_level.py`'s own module docstring, `BL-B137`'s roadmap
  entry, and two new `notes/` entries from this pass (below) cover the NaN-to-90° clamp mechanism
  and the mock-endpoint-gap class of defect.

### Security

`plans/bl-b124-light-level/security.md` — **APPROVED**. One finding (NaN/Infinity →
silent full-daylight), filed as `[[BL-B137]]`, fixed same day, re-reviewed APPROVED. Spot-checked
one of the review's own mutation claims in this pass rather than re-running all of them: read
`MissionClockSample.from_wire`'s current `math.isfinite` guard directly against
`aircraft-layer/src/schema/firing.py`'s committed source — present exactly as the fix round
describes, success condition now requires both the `isinstance` check and `math.isfinite`. Not
independently re-mutated in this pass (the Stages-4-5/BL-B137 reviews already did this
multiple times); no reason found to doubt their account.

### Performance

`plans/bl-b124-light-level/performance.md` — **APPROVED, MONITOR** across every hotspot named
(the per-poll astronomy call, `light_factor` resolved per-optic at six `tier_ranges()` call sites,
the second `GET /firing/latest` round-trip, the Hook-side poll addition, the `LAUNCH_FLASH` fold).
All measured directly by that pass with real numbers against real budgets; nothing in this DoD
pass's own full-suite timing (152.79 s for 3808 body-layer tests, in line with pre-existing
full-suite durations) contradicts that.

### Recurring-fix pattern (process signal)

Two recurring categories surfaced in this feature's own required fixes:

- **The "dangerous direction" tuning-comment warning dropped from the rendered `defaults.toml`**
  (Stages-1-3 review's Required Fix 1) is already tracked at Reviewer as a recurring category —
  `.claude/agent-memory/reviewer/feedback_dangerous_direction_sentence_recurs_despite_checklist.md`
  names it "recurs despite checklist" and this is (by that file's own count) at least the third
  instance. Already a Reviewer-owned pattern memory; noting here only because this feature is
  another data point for it, not because it needs a new DoD-level memory.

The NaN/Infinity-at-wire-boundary category this feature's own `[[BL-B137]]` instance belongs to
is now **seven occurrences across five sessions**
(`.claude/agent-memory/dod/project_recurring_unguarded_nonfinite_float_before_conversion.md`,
updated in this pass with this instance). This one is notable as the first occurrence where the
unguarded conversion itself (`float()`, not `int()`) never raises at all — the failure surfaces
only several functions downstream, as a silently wrong, in-range, plausible-looking answer. Per
the memory's own standing note, this has now been caught at Debugger, Security and DoD across
five boundary classes and both directions of crossing, which is working as a gate but
demonstrably not as prevention. **Flagging as a process signal for the user**: a project-wide rule
("any numeric value crossing any boundary, in either direction, must be finiteness-guarded and
type-matched to its schema, checked by grepping the other side's own validator") would be cheaper
raised at Architect/Implementer time for any new wire-touching work than caught a seventh (now
eighth, counting this write-up) time by hand.

### Live acceptance

**PENDING (live).** Test card published:
https://claude.ai/artifact/DGSZDA3TmaUDaKt1xRwSji (source:
`docs/acceptance/2026-11-25-bl-b124-light-level-card.md`). Branch to fly once merged: `main`.
`#needs-flight` tag placed on `body-layer/ROADMAP/BL-B124.md`'s own entry. Four blocks: the dawn
pass (the prize — turns the two first-cut tunable end-points into measurements), a clock check
with a deliberate pause (probes the Stages-4-5 review's own flagged, unfixed wall-clock-vs-sim-time
gap), the night light-source row, and the pilot-seat cockpit mask measurement (user's own
2026-11-18 reminder).

**Unblock condition executed, not just stated.** `BL-B138` (weather, newly split in this pass) and
`BL-B136` (explosions, split before implementation) both name "its own backlog item" as their
unblock, with no further command to run — both now exist as real entry files, confirmed by `ls
body-layer/ROADMAP/BL-B13{6,8}.md` in this pass, not merely referenced.

### Final state (this worktree, tip `7cfbccca`)

- `git status --porcelain` — clean before this pass's own additions; after staging this report,
  the two roadmap edits, the new `BL-B138.md`, the two `notes/` edits, and the memory update, see
  commit below.
- Tested tree sha: `7cfbccca462b813c47978e4b6d2083bd7f4e4aad`.

### Verdict

**DoD: PASSED** (scoped to tip `7cfbccca462b813c47978e4b6d2083bd7f4e4aad`). Acceptance testing:
**PENDING (live)** — card published, `#needs-flight` set, proceeding to merge per the
2026-10-26 "DoD PASSED is the merge trigger" direction. The main loop runs `/merge` next.
