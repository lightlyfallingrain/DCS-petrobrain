# BL-16 desired state — Stage 3 (+3b) review

Reviewed `feature/bl16-desired-state-s34` tip `5aca44ae` against base `65cbd76a` (Stage 1-2,
already APPROVED). Full read of `plan.md`, `explore-notes.md`, `implementation.md` (Stage 3 and
3b sections and all "Deviations" lists), `alignment.md`, `review-s12.md`, and the Stage 3 test
card. Decisions section of the plan read by hand (U1-U6) — no `U<n>` ids in this plan's own
numbering match the ledger script's ID space cleanly beyond `U1-U4`, so the plan's own "Decisions
Requiring User Input" / "Open Decisions" sections were traced by hand against `implementation.md`
rather than purely via `accepted-items-ledger.sh`.

Both subprojects' checks run fresh in this review's own worktree (not relied on from
`implementation.md`'s report):
- aircraft-layer: `ruff format --check`/`ruff check` pass; `mypy src` clean (29 files); `luac5.1
  -p` passes on every touched Lua file; the GETGLOBAL sweep on every touched file is clean
  (stdlib/DCS APIs plus the legitimate cross-module globals only); `pytest tests -q`: **1101
  passed**.
- body-layer: `ruff format --check`/`ruff check` pass; `mypy src` clean (93 files); `pytest tests
  -q -p xdist -n auto -m "not slow"`: **3718 passed, 4 xfailed**; `pytest tests -q -m slow`: **27
  passed**.
- Symbol-existence check against base `65cbd76a` confirms the new tests are not vacuous:
  `flight_desired.lua`'s `handle_flight_command`/`M2_ONLY_KINDS`, and
  `flight_authority.py`'s `PendingFlightReadback`/`resolve_pending_flight_readbacks`, do not exist
  at the base tip, while `decide_flight_control` (deleted this stage) does — the new tests would
  fail (import/attribute error) against base, not merely show a different value.

## Required Fixes

1. **U2 ("a carried value the new mode cannot fly exactly is announced once, not urgent") is not
   built for the m2→m1 carry, and the gap is not disclosed anywhere in `implementation.md`'s own
   "Deviations and judgment calls" lists.** The plan states twice that this is Stage 3 work: section
   3 ("First needed in Stage 3 (carry starts there for m2→m1)") and the Stage 3 bullet list itself
   ("U2's carried-value line on unpark"). Checked directly: `belief.flight_control.clamp_speed`/
   `clamp_altitude` are called only from the `axes_*` action bodies (`crew_console.py:5609-5671`,
   a *new* mode-1 command written by body-layer) — never at the m2→m1 edge, and nothing in
   `flight_control.lua`'s `build_take_seed` (the unpark-carry branch, verbatim) or `apply_desired_
   changes_to_law` clamps `ias_kmh`/`alt_m` either; `fc_limits.min_ias_kmh`/`max_ias_kmh`/
   `floor_agl_m` are read only by `check_envelope` (the self-release trigger), not as a goal clamp.
   So today, "speed 0" commanded in mode 2 then an unpark literally hands mode 1's law a 0 km/h
   target with no clamp and no announcement — the observable effect is either the law trying (and
   presumably failing) to hold 0 km/h, or `check_envelope`'s "too slow" branch forcing an
   unexpected `"You have controls!"` a few seconds later, neither of which is what U2 asked for.
   The plan's own Stage 3 card text lists `"Speed 0" in m2 then unpark (U2's one line, "Speed 8
   0.")` as a thing to check — the **actual** Stage 3 card
   (`docs/acceptance/2026-11-20-bl16-desired-state-s3-card.md`) omits this scenario entirely, so
   the gap would not even have surfaced in flight testing. Needs: a clamp (reusing `clamp_speed`/
   `clamp_altitude`, or their Lua twins) applied at the m2→m1 edge handler (or at `build_take_seed`
   itself), the once-non-urgent line, and a card step. This is player-facing correctness per root
   `CLAUDE.md`'s current "Reviewer is yours alone" gate, not a cosmetic miss.

2. **`build_take_seed`'s voice-take branch (a `desired` part stamped strictly after the take's own
   `seq` survives the seed, `flight_control.lua:1569-1589`) is untested.** This is a plan-named
   Stage 3 test (`plan.md`'s own test list: "A set during `taking` survives the seed") and
   `implementation.md` describes it as if covered ("the 'a set during taking survives the seed'
   test"), but no test in `test_flight_control_lua.py` or `test_flight_desired_lua.py` drives a
   `set` with a higher seq while `fc_mode == "taking"` (every existing `request_take` driver either
   transitions to active in the same call or sends its `set_desired` only after the take has
   already resolved). The logic reads correct by inspection, but "you have controls, heading 090"
   in one breath is exactly the scenario this branch exists for, and it currently has zero
   automated coverage of the law actually adopting the later value instead of the measured one.

3. **`ai_pilot_wheel.lua`'s new align-read scheduling (`ALIGN_READ_DELAY_S`, `ai_wheel_align_
   read_at_t`, `run_ai_pilot_wheel_with_align_read`) is untested and live today**, not dormant
   until Stage 4: it fires off the *existing* CBTM "align" press (today's mode-2 align action,
   independent of the new wire `kind=="align"`, which stays refused `wrong_mode` this stage), so a
   player saying "align" today already exercises this new write path into `desired.heading_deg`.
   No test in `test_ai_pilot_wheel_lua.py` (or elsewhere) drives `ai_pilot_cbtm.action == "align"`
   through to the delayed `write_internal` call. A silent failure here (e.g. `held_targets`
   returning a stale/nil heading inside the window) would show up only as a wrong carried heading
   after a park, with nothing in the test suite to catch a regression.

4. **`body-layer/CLAUDE.md`'s module map for `flight_control.py` is now stale and describes a
   deleted mechanism as current.** It still reads "`decide_flight_control` is the one 'when' apart
   from those two [take/release] actions" — that function is deleted outright this stage
   (confirmed: only comments reference it in `flight_control.py`/`crew_console.py`/`body.py`; no
   production code). `git diff 65cbd76a..5aca44ae -- body-layer/CLAUDE.md` is empty — this file was
   not touched at all, despite the plan's own "Affected modules/files" list explicitly naming it:
   *"body-layer/CLAUDE.md — the invariants ... and the flight_control.py/ai_pilot_wheel.py
   module-map entries."* This file is always-loaded context for every future agent working in this
   subproject; as written it actively misdirects anyone who reads it before touching
   `flight_control.py`. (`aircraft-layer/CLAUDE.md` was correctly updated this stage — this finding
   is body-layer only.)

## Known, accepted follow-ups (not required fixes — recorded per user/coordinator direction)

- **Late-accepted ack after body-layer's own take/readback timeout is not specially handled**
  (`implementation.md`'s own flagged gap, Stage 3 deviation 3 and Stage 3b deviation 1 — "a clock
  anomaly"). **User decision, this review:** *"if Lua accepts a take after body-layer has already
  timed out and said 'unable', body-layer doesn't notice." -> fix later, not now.* Not a required
  fix for this review.
- **Mode-2 breaks (CBTM) and HVRT are not dual-written onto the numbered `flight` channel this
  stage**, despite the plan's own Stage 3 bullet text saying "Mode-2 breaks write their break
  heading." Self-disclosed as Deviation 4 (Stage 3) and extended to HVRT in Stage 3b's own
  deviation list, with the Implementer's reasoning given (half-building a second temporary wiring
  path ahead of Stage 4's full mode-2 rebuild judged worse than waiting). The actual Stage 3 card
  does not claim this works (step 9 only exercises mode 1's own break carry), so nothing was
  oversold to the tester. Flagging here so it is not lost, but given the explicit self-disclosure,
  the narrow blast radius (mode-2-break-then-unpark only), and the already-approved order change
  delaying Stage 4, I am not blocking on it. Worth a line in `BL-16`'s own roadmap/backlog so it
  does not need rediscovering when Stage 4 starts.

## Verified against the checklist

- Numbered `flight` channel: epoch/seq/`until`/acks correct (`handle_flight_command`); refusal
  reasons closed-vocabulary (`epoch`/`bounds`/`stale`/`not_flying`/`wrong_mode`/`precondition`
  wired through); a stale request is refused `stale`, confirmed by inspection and
  `TestSetRequest.test_stale_until_is_refused`; one mission-wide counter
  (`ConsolePerceptionRunner.command_seq`, preserved across mission restart, in
  `test_mission_start_reset.py`'s `_RUNNER_PRESERVE`); reset/epoch handshake re-verified
  (`reset(epoch)` sets `fd_epoch`/`fd_last_seq=0`, `on_stop` deliberately leaves them); the old
  `flight_control` op/`POST /command/flight_control` path is fully gone (`commands.lua` has no
  `handlers.flight_control`; `test_the_old_flight_control_path_is_gone` pins a 404).
- Mode 1 applies desired by stamp (`apply_desired_changes_to_law`); unpark carries `desired`
  verbatim including a standing break (`build_take_seed`'s unpark branch,
  `TestUnparkTakeSeedsFromMode2SetTargets`, `TestUnparkCarriesAStandingBreak`) — this is tonight's
  crash case and it is fixed and tested; a voice take uses measured defaults except parts stamped
  after the take (code path exists; see Required Fix 2 for its test gap).
- Wait-for-Lua readbacks: strict seq order (`resolve_pending_flight_readbacks`'s FIFO-by-front),
  both suppression rules tested (`TestResolvePendingFlightReadbacks`), nothing spoken twice for
  mode-2 dual-writes (one shared queue, one `fd_acks` ring), the dropped-unsent case speaks "Unable,
  not ready." rather than leaking (`_apply_flight_requests`'s overlay-flip branch). HVRT/CBTM
  deliberately still immediate, and pinned as such
  (`test_align_s_readback_is_not_deferred`/`test_the_readback_is_not_deferred`). No path found
  where a command is acted on with no speech, other than the two disclosed/accepted gaps above.
- Heading reference: `HEADING_REF="true"`, measured live, not a placeholder; `fd_hdg_mag_deg` now
  converts `LoGetMagneticYaw`'s radians via `wrap360_deg`/`math.deg`, with a defensive second wrap
  at body-layer's own boundary (`_as_optional_degrees_0_360`).
- `FlightControlState` is a genuine diagnostics-only mirror; no production code anywhere still
  reads `phase`/`take_seq`/`held_*`/`lua_last_cmd_seq`/`fc_goal_*` for their old meaning (grep-
  confirmed; every hit left is a comment).
- Per-aircraft profile constraint: no new mode-1 law constant was added as a scattered module
  literal this stage (`git diff` shows zero new `local <CAPS> = ...` additions in
  `flight_control.lua`); `HEADING_REF` is the plan's own explicitly-exempted case (a reference
  choice, not a behaviour tunable). `ai_pilot_wheel.lua`'s new `ALIGN_READ_DELAY_S` is mode-2-only
  (Mi-24-specific already), so the mode-1-generic constraint does not apply to it.
- Tuning: `FLIGHT_REQUEST_ACCEPT_WINDOW_S` new (judgement, 1.5, lo 0.5/hi 10.0);
  `HANDOVER_ACK_TIMEOUT_S` raised 2.0→3.0; the cross-key coupling is enforced by a pinned test
  (`test_handover_ack_timeout_exceeds_accept_window_with_margin`) and the rendered
  `config/defaults.toml` entries each carry the coupling in their single rendered sentence (read
  the rendered file, not the source comment, per the reviewer's own standing instruction) —
  checked directly, both correct.
- Card: flyable, names `feature/bl16-desired-state-s34`, no deploy steps beyond the usual
  redeploy/restart, collector via `$DCS_COLLECTOR_IP` (`source run-scripts/petrobrain.env`). The
  card is honest about what Stage 3 does and does not cover (mode 2 "unchanged this stage" is
  stated up front) — except that it omits the U2 scenario it was supposed to carry (Required Fix
  1).

## Verdict

**NEEDS REVISION** — four required fixes above (one behavioural gap against an explicit,
twice-stated Stage 3 plan commitment with no disclosure; two test-coverage gaps on load-bearing,
plan-named behaviour; one stale always-loaded doc). None of them touch the mechanism this stage
exists to fix (the mid-ramp/mid-break unpark crash case), which is built and tested correctly, and
none require unwinding anything already flown — Required Fixes 2-4 are additive (a test, a test,
a doc edit); Required Fix 1 needs a small, localized clamp-and-announce addition at one edge
handler. Recommend routing back to Implementer for these four, then a focused re-review rather
than a full re-read.

## Review Confidence

Full read of the plan, explore-notes, implementation.md (both stages), alignment.md, review-s12.md
and the test card; full diff read for the Lua and Python production files named in "Affected
modules/files"; both subprojects' complete check suites (format/lint/mypy/full pytest including
`slow`/Lua syntax/GETGLOBAL) run fresh in this review's own worktree, not taken on faith from
`implementation.md`'s own report. Not independently re-run: the live-cockpit behaviour the test
card asks the user to fly (no DCS session reachable from this environment, per this role's own
constraints) — that remains the user's own acceptance step, not re-verified here.
