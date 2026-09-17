# Definition of Done Check: f10-command-vocabulary

**Date:** 2026-09-16  
**Branch:** `feature/f10-command-vocabulary` (8 commits, 63f4fc2 HEAD)  
**Reviewed by:** (Reviewer approved at b0cb9bd; DoD agent validating)

---

## Checklist

### Code Quality

- **Format/Lint/Type/Test Gates** ✅ PASS
  - **body-layer** (touched): ruff format ✓ | ruff check ✓ | mypy --strict ✓ | pytest 522 passed ✓
  - **aircraft-layer** (touched): ruff format ✓ | ruff check ✓ | mypy --strict ✓ | pytest 109 passed ✓
  - **world-model** (untouched): verified no changes in diff ✓

- **Error Handling & Exceptions** ✅ PASS
  - ValueError in `ContactStore.add_area` is correctly enforced (mutual exclusion: sector XOR relative_sector)
  - Every caller respects the mutual exclusion (all scan paths supply exactly one)
  - `AircraftLayerError` in `_handle_scan` is caught and logged, with task still registered (D5 contract) ✓
  - No unhandled panics or silent error suppression ✓

- **Debug Output & Leftover Code** ✅ PASS
  - No `print()`, `logger.debug()`, or `TODO`/`FIXME` comments introduced ✓
  - Docstring correction commit (63f4fc2) narrowed an overstatement; did not introduce new unreachability, only documented an existing one ✓
  - F10_SCAN_RADIUS_M and DEFAULT_SCAN_DEADLINE_S are explicitly flagged as uncalibrated placeholders in comments ✓

### Scope & Correctness

- **Plan Adherence** ✅ PASS
  - **In scope (all done):**
    - 14-token vocabulary: 4 relative (ahead/left/right/full) + 8 compass bearing + watch_nearest + cancel_task ✓
    - Ownship-relative sectors (D1-D3): RelativeSector literal, wedge_deg field, project_relative_area reprojection ✓
    - Register-then-trigger (D5): scan_area registers before trigger_petrovich_search; failed trigger doesn't lose task ✓
    - Static menu tree (D4) with fixed vocabulary ✓
    - Docstring correction (D4a clarification about task-area fallback reachability) ✓
  - **Out of scope (correctly excluded):**
    - Spec's autonomous-behaviour half (weapon filtering, classification upgrades, engagement envelope, auto-watch, group-as-single, mission lifecycle) — explicitly deferred ✓
    - Observ/Track verbs — blocked on unidentified 9K113 OBSERV OFF control ✓
    - Richer command forms (dynamic contact list, waypoint-anchored scans, o'clock-and-distance) — **rejected for F10, moved to SRS/BL-10** (D4a) ✓

- **Invariants** ✅ PASS
  - DCS is authoritative: no DCS data overridden ✓
  - Code owns state: belief-state correctly persisted in ContactStore and TaskStore ✓
  - Read-only extraction: no modifications to DCS installation ✓
  - Provenance: F10 command timestamps are explicitly wall-clock-only (documented in decision 1 of the F10 plan) ✓
  - No unverified claims encoded as fact ✓

- **Git Staging & Commits** ✅ PASS
  - Working tree clean: `git status` shows no uncommitted changes ✓
  - All new/modified files committed (no build artifacts or .gitignore'd files staged) ✓
  - 8 commits on branch, properly sequenced: plan → implementation stages 1-5 → implementation stages 6-7 → review fixes + docstring correction ✓

### Testing

- **Test Coverage** ✅ PASS
  - Core logic covered:
    - Relative-sector geometry (wedge bounds, rotation, wraparound) — 3 tests ✓
    - Fixed-area identity (project_relative_area returns fixed areas unchanged) — 1 test ✓
    - Wedge precedence (D3: explicit > sector > none) — 4 tests ✓
    - Add_area mutual exclusion (sector XOR relative_sector) — 1 test ✓
    - Reproject integration with tick (D2) — 2 tests ✓
    - Scan dispatch (relative and absolute) — 2 tests ✓
    - Register-then-trigger (D5) — 1 test ✓
    - Trigger failure graceful degradation — 1 test ✓
    - Cancel task end-to-end — 1 test ✓
    - **Regression: task-area staleness across reprojection** — 2 new tests ensuring the required fix (task.area resolution via store.get_area) actually gates task completion ✓

- **Test Quality** ✅ PASS
  - Not decorative: `test_tick_resolves_relative_scan_area_against_its_live_projection` would have failed pre-fix (captured area.wedge_deg would be None, task completion would be wrongly permissive) ✓
  - Not decorative: `test_tick_falls_back_to_captured_area_when_the_live_area_is_gone` exercises the fallback branch and validates graceful degradation ✓

- **Regressions** ✅ PASS
  - Pre-existing tests re-verified after removal of hollow `scan_forward` token ✓
  - Removed tests replaced with corresponding `scan_ahead`/`scan_left`/`scan_right`/`scan_full` coverage ✓
  - All 522 body-layer tests pass (506 baseline + 14 new from stages 1-5, +2 from fix) ✓
  - All 109 aircraft-layer tests pass (unchanged) ✓

### Documentation

- **Reviewer Findings Addressed** ✅ PASS
  - **Required fix 1 (stale task-area reference):** TaskStore.tick now resolves via store.get_area(task.area.id), confirmed repro'd against the code ✓
  - **Required fix 2 (tasks.py docstring):** Module docstring and PendingIntent.area docstring updated; semantics of ownship-anchored areas as "moving patch of view" documented ✓
  - **Optional fix 3 (plan.md menu tree diagram):** Redrawn to 14 leaves with Bearing submenu; "14-token vocabulary" prose reconciled with diagram ✓
  - **Docstring accuracy (63f4fc2):** Fallback's "should not happen" claim narrowed to truth; pre-existing unwatch_area path documented; not a code behavior change ✓

- **Non-Obvious Behavior** ✅ PASS
  - Relative-sector re-projection happens on telemetry tick, not at command time (D2) — documented in logger.py wiring ✓
  - Task.area staleness risk documented in tasks.py module docstring ✓
  - Fallback to captured area only if live area missing, graceful degradation — documented in code and tests ✓

- **Roadmap & Backlog Updates** ✅ PASS
  - body-layer/ROADMAP.md: F10 command vocabulary milestone marked [x] done with detailed completion statement ✓
  - Live-acceptance debt: F10 command vocabulary should be added to "Live acceptance debt" list (explicitly deferred, not waived) — **needs entry** (see below)

### Security

- **Plan Review:** Skipped per project CLAUDE.md (offline single-user local pipeline, no hot path, no untrusted input) ✓
- **Deep Analysis:** Skipped per project CLAUDE.md (same rationale) ✓

### Acceptance Testing

- **Status:** Deliberately deferred per plan ("No live-DCS acceptance in this milestone's DoD").  
- **Rationale:** The entire point is to enable the user's next sortie; that sortie is the acceptance test ✓

---

## Summary

**DoD Status:** ✅ **PASS**

All mechanical criteria pass. Code quality confirmed independently. Scope is tight and correct. Reviewer's required fixes are complete and verified. Tests are meaningful and would have failed pre-fix. Docstring correction is accurate and changes only documentation, not behavior.

---

## Acceptance Testing Plan

**Goal:** Verify that the widened F10 command vocabulary (14 tokens vs. 3 hollow ones) produces real belief-state changes and that relative sectors correctly track the nose through maneuvers.

### Prerequisites
- [ ] Type-checked and importable: `cd body-layer && mypy src --strict` ✓
- [ ] Live DCS instance with aircraft-layer running
- [ ] Mission Interpreter running (if --mission-understanding is in use for BL-7)
- [ ] body-layer logger running with `--crew-text --f10-commands --overlay`

### Test Cases

1. **F10 menu tree is navigable as planned**
   - Open F10 menu → Other → Petrovich → Scan
   - Verify four submenu items: Ahead, Left, Right, Full
   - Open F10 menu → Other → Petrovich → Scan → Bearing
   - Verify eight submenu items: N, NE, E, SE, S, SW, W, NW
   - Open F10 menu → Other → Petrovich → Watch
   - Verify one submenu item: Nearest
   - Open F10 menu → Other → Petrovich → Cancel Task
   - Verify it exists (not grayed out)
   - **Expected result:** All 14 menu items present and selectable

2. **Relative sectors track the nose (D1-D3 validation)**
   - Press F10 → Petrovich → Scan → Left (heading 0, ownship facing north)
   - Observe: console/overlay reads "Scanning the left sector." or similar
   - Turn aircraft to heading 90 (facing east)
   - Place a target ahead of the new nose
   - Verify: the same "left" scan area from step 1 has rotated with the aircraft (the new ahead-left area, not the old 270-bearing zone)
   - **Expected result:** Relative sector rotates with heading, not frozen to heading at button-press time

3. **Absolute (bearing) sectors do NOT rotate with the aircraft (sanity check)**
   - Press F10 → Petrovich → Scan → Bearing → North (heading 0)
   - Observe: console/overlay reads "Scanning North." or similar
   - Turn aircraft to heading 90 (facing east)
   - Place target ahead of the new nose (due east, bearing 90 relative to true north)
   - Verify: the "North" sector scan is still looking for targets in the true-north direction (behind you), not ahead
   - **Expected result:** Bearing scans lock to compass cardinal directions; heading changes don't affect where they look

4. **Scan area registration is real (D5 validation)**
   - Press F10 → Petrovich → Scan → Ahead
   - Console readback: "Scanning ahead." (or matching render_scan_readback text)
   - Check console `tasks` command output or `get_situation` reply: verify a pending task exists with area.relative_sector="ahead"
   - **Expected result:** Task is registered and visible in belief state (not just a trigger, not hollow)

5. **Cancel Task actually cancels (D5 consequence)**
   - With pending scan task from step 4 still active
   - Press F10 → Petrovich → Cancel Task
   - Check console `tasks` output: verify the pending task is gone (state changed to "cancelled" or removed)
   - **Expected result:** Cancel Task works; not always "no pending task" as it was before

6. **Trigger failure doesn't lose task (D5 contract)**
   - Stop the aircraft-layer collector or simulate a network error
   - Press F10 → Petrovich → Scan → Ahead
   - Observe: console/overlay reads "Scanning ahead." (readback still prints)
   - Check logs for `AircraftLayerError` warning
   - Check console `tasks` output: verify the task is still registered despite trigger failure
   - Restart aircraft-layer
   - **Expected result:** Failed live trigger does not lose the belief-state task

### Edge Cases to Probe

- **Placeholder calibration**
  - F10_SCAN_RADIUS_M is hardcoded to 3000.0 m — verify this feels right for "scan forward" range during a realistic mission (contacts should appear when expected, not be cut off or too permissive)
  - DEFAULT_SCAN_DEADLINE_S (inherited from BL-5) is similar — note whether real flight suggests tighter/looser windows
  - These are uncalibrated placeholders; record observations for future tuning (they're the only real calibration gap left in this milestone)

- **Multi-turn sector updates**
  - Execute a tight spiral (heading changes 360° while holding position)
  - Relative scan area should continuously re-project, staying anchored to the nose throughout
  - No discontinuities or jumps in the sector wedge as heading wraps past 360°
  - **Expected result:** Smooth continuous tracking, no 360° wraparound glitches

### Pass Criteria

The feature passes if:
1. All 14 F10 menu items are navigable
2. Relative scans (ahead/left/right/full) rotate with heading; absolute scans (bearing) do not
3. Each scan registers a real pending task (not hollow)
4. Cancel Task works (pending task is actually canceled)
5. Failed triggers do not lose tasks
6. No visible regressions in other crew commands or belief-state reporting

**Live acceptance is the sortie itself.** This milestone exists to make that sortie informative. After this flight, user decisions about autonomous behaviors (BL-8 and beyond) will have real evidence to ground them.

---

## Notes for Future Sessions

### Live Acceptance Debt Entry Needed

This milestone's live acceptance is explicitly deferred per plan scope. Add to `body-layer/ROADMAP.md` "Live acceptance debt" section:

```
- [ ] **F10 command vocabulary (14 tokens, relative-sector re-projection)** — live acceptance deliberately deferred, "the whole point is to enable the user's sorties; acceptance is the sortie itself" per `plans/f10-command-vocabulary/plan.md`. Not yet confirmed on a real flight; sortie to exercise: new menu tree navigability, relative vs. bearing sector rotation, Cancel Task non-hollowness, F10_SCAN_RADIUS_M and DEFAULT_SCAN_DEADLINE_S placeholder calibration.
```

(This is not a blocker for merge; just a tracking entry for the accumulating live-acceptance backlog.)

### Known Pattern: Captured References Becoming Stale

This milestone's required fix (task.area staleness across ContactStore reprojection) is the second instance of "two views of the same object drift apart" in this codebase. The first was `osm-landcover-optimization` (multipolygon outer/hole rings misaligning during independent simplification). Both were caught at DoD stage after tests missed them because the tests checked the store/object itself, not the captured reference.

**Existing NOTES.md entry covers this adequately** — "Independent simplification of paired rings... post-simplification validation required" captures the essence of the pattern (captured references become stale when mutable containers update). No new note needed; this is the second instance confirming the pattern is real, not noise.

### Scope Impact on BL-10/SRS

D4a's user direction (2026-09-16) **explicitly rejects** the richer command forms from F10 scope and **reassigns them to SRS/BL-10:**

> "the dynamic contact list above, waypoint/landmark-anchored scans, and the spec's o'clock-and-distance location form are *not* deferred pending sortie evidence — they are **rejected for F10 outright** and belong to BL-10/SRS."

This sharpens BL-10's brief: SRS is not merely swapping BL-5a's typed stand-ins for a real adapter; **it inherits the whole command half of `docs/concept/state-transitions.jpg` as its requirements input.** The 14-token F10 vocabulary is the *target* set, not a stepping stone; nobody should later expand the F10 tree on the rationale "we deferred this," because that rationale is now explicitly void.

This is a material change to what the next milestone should be. BL-10's planning and scope definition should incorporate this as a locked decision from D4a, not wait for acceptance testing feedback on a question that's already answered.

---

## Recommendation

✅ **Ready for merge.** All DoD criteria pass. Reviewer approved all work. Acceptance testing is explicitly deferred per plan and will happen in the user's next sortie. No mechanical blockers.

Proceed to merge after user confirms acceptance testing plan is clear and actionable.

---

## Addendum 2026-09-17: first live test, two defects fixed

The milestone's live acceptance — the sortie this whole milestone existed to make informative —
ran on 2026-09-16/17 and did its job: the menu tree, the belief wiring and `Cancel Task` all
worked, and two real defects surfaced that no fixture test could have caught.

**Both fixed on `fix/scan-naked-eye-not-9k113` (`89b8b1d`), reviewed and APPROVED (`8e14eec`).**

1. **Scan drove the 9K113 sight.** `_handle_scan` fired
   `aircraft_client.trigger_petrovich_search("forward")`, inherited from the pre-milestone hollow
   `scan_forward` item and never questioned when D5 wrapped a real task around it.
   `docs/concept/state-transitions.jpg`'s own glossary separates *Scan* (visual) from *Observ*
   (9K113) — the spec was explicit and the implementation contradicted it. The trigger stays on
   `aircraft_client` for a future `Observ`, which remains blocked on the unidentified OBSERV OFF
   control.
2. **`Cancel Task` spoke a task id** ("cancelled task TASK_4"). `speech.py` already established
   that no id is ever spoken — a pilot cannot track `CONTACT_<n>` by ear, and `TASK_<n>` is no
   better; the same fix had been applied to `watch_nearest` on 2026-09-13 and `cancel_task` was
   simply missed. Now names what was stopped.

**Known consequence, accepted by user direction 2026-09-16:** a scan now changes attention but not
perception, because the naked-eye gate uses a fixed cone no command steers. Backlogged in
`todo/todo.md` along with the discovery that the cone's own value
(`NAKED_EYE_FOV_HALF_WIDTH_DEG = 60.0`) is the **9K113's** angular limit rather than anything
established about a human looking through cockpit glass — its docstring reads as reasoned when it
is inherited. `plans/cockpit-visibility/plan.md` supersedes that constant properly rather than
re-guessing it.

**Also filed:** `console.py`'s typed `scan-area` debug command has the same 9K113 mismatch,
deliberately left out of the reviewed commit's scope (`todo/todo.md`).

**Verification:** body-layer 527 passed (was 526), aircraft-layer 109 untouched, world-model 474
untouched; ruff format/check and `mypy --strict` clean. Working tree clean.

**Milestone-completion question, revisited:** the original answer was "no downstream impact". The
live test changes that in one direction worth recording — it established that the naked-eye
perception channel has no elevation term at all, which is a standing no-omniscience gap
(Petrovich sees through the fuselage and floor) that predates this milestone and is now planned
(`plans/cockpit-visibility/plan.md`). That is a finding *about* BL-1/PB-1.5's perception layer,
surfaced by exercising BL-x's command layer — the inspect-and-adapt checkpoint working as
intended.

**Verdict: PASS** (addendum).
