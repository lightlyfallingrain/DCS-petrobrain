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

## Re-review, 2026-11-20

Scope: the review-fix round only, `git log --oneline add3bd16..HEAD` = `b1346a18` (the four
fixes) + `083e363b` (an implementer-memory note, no production change). Read
`implementation.md`'s "Review-fix round" section in full, `plan.md`'s U2/Q1a text, every line the
round's diff touched, and the module-map entries in both `aircraft-layer/CLAUDE.md` and
`body-layer/CLAUDE.md`. Both subprojects' checks run fresh in this re-review's own worktree
(`review2/desired-s3`, cut from `083e363b`), not taken on trust from `implementation.md`'s report.

**Required Fix 1 (U2 clamp) — built correctly, and the two clamps cannot drift.** The clamp lives
exactly where it has to: `build_take_seed`'s unpark branch (`flight_control.lua:1573-1586`)
clamps only the `seed` fed to `law_init_at_take` against `fc_limits.min_ias_kmh`/`max_ias_kmh`/
`floor_agl_m`; `desired` itself (and `fd_ias`/`fd_alt`, its wire mirror) is never touched —
confirmed by reading the diff, not just the comment. **Checked the drift question directly**:
`fc_limits` is not a Lua-local constant table independent of body-layer — it is set wholesale by
`handle_flight_lease_command` from the `limits` dict `belief.flight_control.
flight_control_limits()` builds (`body-layer/src/belief/flight_control.py:517-545`), and that
dict's `min_ias_kmh`/`max_ias_kmh`/`floor_agl_m` keys are exactly `MIN_IAS_KMH`/`MAX_IAS_KMH`/
`FLOOR_AGL_M` — the same three `tuning.real` constants `clamp_speed`/`clamp_altitude` read on the
body side. One declaration, sent over the wire every poll (`POST /command/flight_lease`,
`aircraft-layer/CLAUDE.md`'s own description); Lua's local `fc_limits` table (lines 209-213,
80/280/40) is only the pre-lease fallback and happens to equal the same code defaults. So the two
clamps are structurally the same clamp, not two maintained in parallel — confirmed by reading
`flight_control_limits()`, not inferred from the docstring's claim. (The one narrow case this
does not cover — an unpark in the few-hundred-ms window before the first lease poll ever lands,
with a non-default `tuning.toml` override in effect, could see Lua's hardcoded fallback diverge
from body-layer's constant — is a pre-existing property of the whole lease-sync mechanism from
Stage 1-2, already reviewed and approved; not introduced by this round, not reopening it here.)
Speech: `decide_carried_value_speech` fires only when `new.fd_mode == "m1"` and `new.mode_cause
== "unpark"` with a genuine `mode_n` edge (`flight_authority.py:259-261`), returns one non-urgent
`FlightAuthorityDecision` per differing part, and never writes `new.ias_kmh`/`alt_m` anywhere —
confirmed by reading the function body. Order: `body.py` calls it immediately after `decide_
flight_speech` each poll (lines 5531-5550), before `_apply_flight_requests`/`drain_flight_control`
(the ack-outcome drain) — matches the plan's own speech order (mode-change, then U2's line, then
acks in seq order) exactly. Mutation-tested: flipping the speed-clamp branch's condition to
`False` fails 3 of the 10 `TestDecideCarriedValueSpeech` cases, so the test suite is not vacuous
on this path either.

**Required Fix 2 (voice-take-during-`taking` test) — the test genuinely exercises the stated
window.** `TestVoiceTakeSetDuringTakingSurvivesTheSeed` drives `set_desired` with a `seq` strictly
after `take_seq` while `fc_mode == "taking"`, before the resolving `run_flight_control` call — the
exact gap the review named. Note for the record: the underlying `build_take_seed` voice-take logic
this test covers is **unchanged** by this round (`git diff add3bd16 HEAD -- flight_control.lua`
touches only the unpark branch) — this is a coverage addition for pre-existing, already-correct
code, not a regression fix, exactly as the review itself characterized it ("the logic reads
correct by inspection... currently has zero automated coverage"). Confirmed the test is not
vacuous by mutation: commenting out the seed's heading assignment flips the assertion
(`fc_in_band_heading` goes from `"false"` to `"true"`, test fails as expected) — this is a
stronger check than "passes against `add3bd16`'s production code," which it also does, harmlessly,
since that code never changed.

**Required Fix 3 (align-read-scheduling test) — same shape, same conclusion.**
`TestAlignReadScheduling` drives `ai_pilot_cbtm.action = "align"` through a real `update_ai_pilot_
wheel_overlay` call and asserts nothing is written before `ALIGN_READ_DELAY_S`, then the aligned
heading is written once it elapses. `ai_pilot_wheel.lua` has **zero diff** between `add3bd16` and
`HEAD` — this, too, is coverage added for already-live, already-correct code, not a fix. Mutation-
tested by commenting out the deferred `write_internal` call: the test fails
(`writes_after_deadline` goes from `"1"` to `"0"`) — not vacuous.

**Required Fix 4 (`body-layer/CLAUDE.md`) — accurate.** The `flight_control.py` module-map entry
now correctly says `decide_flight_control` is deleted and names what replaced it (`belief.
flight_authority`'s `decide_flight_speech`/ack-matching); `FlightControlState` is correctly called
diagnostics-only. Re-read against the current code and found nothing else stale in the entry.

**New required fix: `body-layer/docs/STRUCTURE.md` still names the deleted function as
current, in the same way Required Fix 4 was about.** Two hits
(`STRUCTURE.md:971` — "it lives in `belief.flight_control.decide_flight_control`" — and
`STRUCTURE.md:1205` — "`decide_flight_control` (the one 'when' apart from those two...)").
`body-layer/CLAUDE.md` itself says this file is "expected to [be read] for any module before
modifying it" — a next agent who reads this entry before touching `flight_control.py` is told the
same wrong thing Required Fix 4 existed to stop `body-layer/CLAUDE.md` from telling it. The
implementer flagged this and left it out-of-scope (the plan's own "Affected modules/files" named
`body-layer/CLAUDE.md` specifically, not `STRUCTURE.md`), which is a reasonable scope read for the
round itself, but per this role's "cheap doc fixes can be listed as required": this is two
sentences in a module-detail doc with the identical failure mode as a fix already done two
paragraphs above it in the same file family. Requiring it now is cheaper than leaving it for
someone to rediscover.

**Not required — `flight_control.lua:1990`'s one stray comment** ("`decide_flight_control`'s own
unpark branch never compares it against anything"), inside the unpark precondition-refusal branch,
untouched by this round and by the Stage 3 round before it. This is a single inline comment deep
in a branch nobody reads as a map (unlike `STRUCTURE.md`/`CLAUDE.md`, which are read deliberately
before touching a module) — low value, low risk, correctly left alone per the "stay local to the
block you are editing" comment-pruning rule. Flagging as optional only.

**Checks, run fresh in this re-review's own worktree:**
- aircraft-layer: `ruff format --check`/`ruff check` clean except one pre-existing, untouched
  finding in `research/2026-10-06-unit-id-join-reduce.py` (confirmed via `git diff add3bd16 HEAD
  --stat -- aircraft-layer/research/` — empty, not touched by this round); `mypy src` clean (29
  files); `luac5.1 -p` passes on `Export.lua`, `flight_control.lua`, `flight_desired.lua`,
  `ai_pilot_wheel.lua`; `pytest tests -q`: **1109 passed**.
- body-layer: `ruff format --check` clean except two pre-existing, untouched findings in
  `research/*.md` (same confirmation, `git diff --stat` empty for that directory); `ruff check`
  clean; `mypy src` clean (93 files); `pytest tests -q -p xdist -n auto -m "not slow"`: **3728
  passed, 4 xfailed**; `pytest tests -q -m slow`: **27 passed**.

## Verdict (re-review)

**APPROVED WITH MINOR FIXES.** All four of the original required fixes are built and verified by
direct inspection and mutation testing, not taken on the implementer's word — U2's clamp is
structurally tied to a single constant declaration (cannot drift), the two new test gaps are
closed with tests proven non-vacuous, and the stale doc named in Required Fix 4 is now accurate.
One new, small required fix: prune `body-layer/docs/STRUCTURE.md`'s two remaining `decide_flight_
control`-as-current mentions (same defect class as the fix just done in `body-layer/CLAUDE.md`,
same two-sentence cost). The stray Lua comment at `flight_control.lua:1990` is optional only.
Nothing here blocks Stage 3 from flying — recommend the doc fix lands before or alongside Stage 4
rather than gating this round further.

## Re-review Confidence

Full read of `implementation.md`'s review-fix section, `plan.md`'s U2/Q1a text, and the complete
diff `add3bd16..HEAD` (both Lua files, both Python files, the card, both `CLAUDE.md` files). Both
subprojects' full check suites (format/lint/mypy/pytest including `slow`/Lua syntax) run fresh in
this re-review's own worktree. Went past reading the diff for the two new test-coverage fixes and
the U2 announcement: ran each test file, then mutated the mechanism under test (the speed-clamp
branch, the voice-take seed assignment, the deferred-write call) and re-ran to confirm each
relevant test actually goes red — not inferred from the implementer's own stash-based claim. Not
independently re-run: live-cockpit acceptance (no DCS session reachable here) — unchanged from the
original review, still the user's own step.
