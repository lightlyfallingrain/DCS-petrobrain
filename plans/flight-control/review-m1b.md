# Review — BL-16 mode 1, Stage M1, re-review round ("M0-J capture fixes")

Branch `feature/bl16-raw-axes`, target tip `fb9df20f53998ead7d0da2ebaf8e30e19691d9a1`. The
worktree's `HEAD` (`59192cfa`, an unrelated main-line merge) was not an ancestor of the target, so
per the dispatching instructions I checked out `fb9df20f` directly on a local branch
`review-m1b` (tree was clean; no stash needed).

Reviewed against: `plans/flight-control/plan.md` ("Revised 2026-11-18" mode 1 re-cut, Decisions
21–25, U5–U10 — read by hand; the ledger script (`accepted-items-ledger.sh plans/flight-control`)
reports nothing to check because this plan's decisions are not in the `U<n>` + `**Answered` form
it scans for), `plans/flight-control/review-m1.md` (my prior NEEDS REVISION, two Required Fixes),
`plans/flight-control/implementation.md`'s two logged fix rounds, and
`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md` at `probe/bl16-flight-axes`
tip `eef87430` (read via `git show`, as instructed — it is not on this branch).

### Review Summary

Both of my prior Required Fixes are closed correctly:

- **Required Fix 1** (stale `fc_goal_*`/`held_*` leak across release→re-take): `handle_flight_
  control_command`'s `"release"` branch now clears all five `fc_goal_*` fields, matching `on_stop`.
  New test `TestReleaseClearsHeldGoalsAcrossRetake` exercises take → goal → release → re-take and
  checks the wire line at each step. Verified by reverting the fix and re-running the test; it
  fails for the stated reason (confirmed in `implementation.md`'s own counterfactual note, and I
  re-derived the same failure independently for the second fix round below).
- **Required Fix 2** (Decision 13's "at every confidence" test): five new tests in
  `test_voice_commands.py` cover `i_have_controls` acting unconditionally, `you_have_controls`'s
  `CONFIRM_FLOOR` boundary on both sides, and the ambiguous-pair branch resolving on `has_controls`
  at every confidence. These exercise `classify_response` directly (not routed through
  `CrewConsole.handle_command` the way the pre-existing `HANDOVER_TOKENS` tests do), closing the
  coverage gap the first review found.

The second commit (`fb9df20f`) is a separate, main-loop-directed round closing the two capture-
timing bugs flight 9 (`probe/bl16-flight-axes`) measured: the unpark-take capture read a partly
cross-faded pilot set at the park-falling edge instead of the last fully-stowed frame (causing a
measured 4°+ bank excursion), and the voice-take capture read the camera seat instead of the live
(non-zero) arg set (causing a measured ~7° pitch excursion when the camera sat in an idle seat).
Both fixes are well-built, match the findings file's own stated remediation, and are backed by
tests whose failure mode I independently reproduced (see "Mutation check" below). The three
pre-existing Lua tests the Implementer rewrote rather than extended are legitimate — each asserts
real, flag-flip-driven new behaviour rather than a weaker version of the old assertion (see
"Checked, test rewrites" below).

One required fix remains: two new behaviour-affecting constants in this round skip the project's
own standing convention for tuning outside body-layer, which this exact file otherwise follows
immediately above them. Two further items are flagged for the user's/coordinator's attention but
are not required fixes on this diff.

## Required Fixes

### 1. `STOWED_THRESHOLD` and `LIVE_SEAT_ZERO_EPS` skip the file's own tuning-note convention

Root `CLAUDE.md`, "Behaviour-affecting constants are tunable": "Outside body-layer the loader does
not exist — declare the constant normally and note that it would want the mechanism, rather than
improvising a second one." `flight_control.lua` already does this correctly for `FLIGHT_WOBBLE`
(lines ~145–152): *"Behaviour-affecting (a visible twitch would be a real defect) but this
subproject has no `tuning.py`-equivalent loader... would want the X-T26 mechanism if one existed
here."*

`STOWED_THRESHOLD` (0.99) and `LIVE_SEAT_ZERO_EPS` (0.01), added a few lines below `FLIGHT_WOBBLE`
in this same round, have no equivalent note despite being squarely behaviour-affecting by the
project's own test ("what he sees, says, remembers, or how long he waits" — here, what gets
written to the aircraft on a take): `STOWED_THRESHOLD` is literally the knob that, mistuned, is
flight 9's own bug (a lower threshold reproduces the faded-edge capture that rolled the aircraft;
I confirmed this directly — see below). `LIVE_SEAT_ZERO_EPS` decides which seat's axis values get
written on a voice take; a mistuned value could misclassify a lightly-trimmed-but-live seat as
idle.

**Fix**: add the same two-line note (or a one-line pointer to `FLIGHT_WOBBLE`'s own) to both
constants' comments. Mechanical, no behaviour change.

## Checked, not required fixes

### Settle-window interaction (`fix/apw-seat-swap-settle`, now on `main` as `c54920e7`)

`git merge-tree --write-tree fb9df20f c54920e7` auto-merges `ai_pilot_wheel.lua` cleanly (the new
`stick_park_raw()` getter sits far from the settle-window edit). Two unrelated files conflict —
`body-layer/ROADMAP/BL-16.md` and `body-layer/config/rules/flight.lua` — but I confirmed this
conflict **predates this review round**: `git merge-tree --write-tree ac524294 c54920e7` produces
the identical two-file conflict, and `git diff ac524294 fb9df20f` touches neither file. So it is
pre-existing merge-sequencing noise from the two branches' independent roadmap/rules edits, not
something this round introduced; ordinary conflict resolution at actual merge time, not a code
defect.

On the substantive question — does the settle window interact with the unpark-take capture
tracking — I read both mechanisms and conclude **no interaction, by design**:

- `stick_park_raw()` returns `ai_pilot_takeover.raw_arg852`, which `run_ai_pilot_wheel` sets
  unconditionally every frame (`ai_pilot_takeover.raw_arg852 = stick_park`, before the seat-gate/
  settle logic runs). It is never filtered by the settle window.
- The settle window only holds `ai_pilot_parked_active` (hence `is_parked()`) at its *previous*
  value for up to 0.5 s, and only on the pilot→operator direction (entering the operator seat).
  `flight_control.lua`'s stowed-pilot tracking is gated on `fc_mode == "armed"`, which is itself
  only entered once `is_parked()` genuinely (post-settle) reads true — so tracking only starts
  after the settle has already resolved the park question, using the correct raw signal.
- The settle explicitly does *not* apply to the operator→pilot direction (the unpark direction;
  the new commit's own comment: "the reverse... forces the park arg to `nil` unconditionally...
  which has no transient to absorb"), so the unpark-take's own timing is unaffected either way.

No fix needed; the two mechanisms are correctly decoupled (the settle masks a derived boolean used
for edge-triggering, the capture tracking reads the raw value it actually needs).

### Mutation check on the unpark-take capture-timing fix

Reverted the unpark-take branch's `fc_last_stowed_pilot_capture` read back to a fresh
`capture_from_seat("pilot")` at the edge (removing the tracked-snapshot indirection) and re-ran
`TestUnparkTakeCaptureTiming::test_captures_the_last_fully_stowed_frame_not_the_faded_edge` alone:
it fails for the stated reason (`0.085` vs the expected `0.133`, matching
`implementation.md`'s own reported counterfactual exactly). Restored the file; `git status
--porcelain` clean afterward. This corroborates the Implementer's own counterfactual claim rather
than just trusting the report.

### Test rewrites (three existing Lua tests)

- `test_unpark_take_is_refused_disabled_in_stage_m1` → `test_unpark_take_succeeds_with_the_flag_on
  _by_default`: legitimate. The old test's premise (the flag is off, so the unpark-take path is
  unreachable through this module's public interface) is exactly what this round changes; the new
  test is strictly *more* assertive (checks the actual written pitch value against the pilot set,
  not merely that the flag masks every precondition), not weaker.
- `TestUnparkTakeRefusals`'s two tests (now asserting `"too_slow"`/`"lease"` instead of
  `"disabled"`): legitimate for the same reason — the flag no longer masks the real precondition,
  so asserting the real cause is the correct test, not a looser one. The companion
  `test_refusal_still_available_via_the_flag` pins the kill-switch's continued existence by reading
  the module source directly, since the constant has no exported test seam; a reasonable judgement
  call for a one-line flag that should not need a seat added purely to be testable, as the
  Implementer's own docstring states and I accept.

### `M.player_seat` kept, not removed

Implementer's own flagged judgement call (no longer called in-process; kept exported for
diagnostics, docstring corrected). I agree with keeping it — zero cost, a documented, deliberate
decision rather than a silent dead export, and removing a diagnostic-only read-only getter has no
upside proportionate to the churn.

### Comment pruning

`ai_pilot_wheel.lua`'s `player_seat()` comment: the removed sentence ("`flight_control.lua`'s own
capture-source rule (Decision 25) reads this on a voice take") is exactly the claim this round made
false, and its replacement correctly marks the supersession with a citation to the finding
(`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`, "Flight 9") rather than
silently deleting the fact. No durable (dated/quoted) line was lost; this is the "supersession
marked, not deleted" pattern working correctly.

## Optional Refinements

- **`plans/flight-control/plan.md`'s Decision 24 and Decision 25 sections are now stale on the
  capture-source question and not annotated.** Decision 25 still reads, unqualified: *"on a voice
  take, the player's seat set... from `ai_pilot_wheel.player_seat()`"* — this is exactly the
  behaviour flight 9 found wrong and this round removed; the code and `implementation.md` both
  correctly cite the correction, but the plan's own decision text does not. Decision 24's "the
  capture source for an unpark take is always the pilot set... Whether that, or the sum of the two
  cross-fading sets, gives no jump is M0-J" was left as an open question with a specific set of
  candidate answers (J1 vs J2); the actual answer — a tracked last-fully-stowed snapshot, not a
  direct capture of either set at the edge — is neither of the two candidates named and is also
  unrecorded in the plan. This plan already has a precedent for exactly this kind of annotation
  (Decision 25's own "**Corrected here:**" paragraph for an earlier revision). Not a code defect
  and not blocking — `implementation.md` and the research file both carry the correction
  faithfully — but a future reader of `plan.md` alone would read a decision the shipped code no
  longer implements. Worth a short amendment paragraph under each decision, in the plan's own
  established style, before this stage is called fully closed. (Optional because the record
  exists elsewhere and is internally consistent; not optional in the sense of "doesn't matter.")

## Checks run

- `ruff format --check` / `ruff check` — both subprojects (aircraft-layer, body-layer): pass.
- `mypy src` (run from inside each subproject): both subprojects pass, 0 issues (28 aircraft-layer
  source files, 92 body-layer source files).
- `luac5.1 -p` on `flight_control.lua`/`ai_pilot_wheel.lua`/`commands.lua`/`Export.lua`: pass.
- `.claude/scripts/fast-tests.sh aircraft-layer`: smoke + 48 targeted files, **808 passed**.
- `.claude/scripts/fast-tests.sh body-layer`: smoke + targeted files, **2810 passed, 4 xfailed**
  (pre-existing xfails, unrelated to this round).
- `.claude/scripts/invariant-check` (skill): all mechanical invariants PASS; the two pre-existing
  WARNs (`except: pass`, `# type: ignore`) are unrelated to this diff.
- `git merge-tree --write-tree fb9df20f c54920e7`: two pre-existing conflicts (roadmap/rules docs,
  confirmed to predate this round), `ai_pilot_wheel.lua` auto-merges clean.
- Independent mutation check on the capture-timing fix (see above): confirmed red on revert.
- Did not re-run the full suites (DoD's own job per root `CLAUDE.md` "Verification"); the fast-test
  runs above cover every file this round touches, matching both `implementation.md`'s own reported
  full-suite numbers (939 aircraft-layer, body-layer unchanged this round) in direction.

## Verdict

**APPROVED WITH MINOR FIXES** — one required fix (the two missing tuning-convention notes,
mechanical, no behaviour change), one optional doc-currency item (plan.md's Decision 24/25
annotation), nothing blocking. Both prior Required Fixes are correctly closed and independently
verified; the M0-J capture fixes are sound, well-tested, and I reproduced one of the Implementer's
own counterfactuals rather than taking the report on trust. The pre-existing roadmap/rules merge
conflict against `main` is ordinary conflict resolution at merge time, not a defect in this diff.

## Review Confidence

Full read of `flight_control.lua`'s complete diff against `ac524294` (both commits), the full
`ai_pilot_wheel.lua` diff, both new/changed test files in full, the relevant plan sections
(Decisions 21–25, U5–U10) by hand, the full M0-J findings file (flights 1–9) via `git show`, and
both fix-round entries in `implementation.md`. Independently reproduced one counterfactual rather
than trusting the report. Did not re-read `crew_console.py`/`rules/gates.py`/`rules/actions.py` in
full this round since neither commit touches body-layer production code — only `test_voice_
commands.py` changed on that side, read in full above.
