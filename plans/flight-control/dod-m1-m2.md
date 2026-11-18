PASSED

# Definition of Done — BL-16 mode 1 Stages M1+M2 (raw-axis flight control)

**Tip this verdict is scoped to:** `f2803bad55a1e07bd0f65e45ae05c7762413d1c9` (branch
`feature/bl16-raw-axes`). If the branch moves after this report, this verdict is stale and
must be re-run. This DoD agent's own worktree started on an unrelated branch
(`worktree-agent-af6acdc39aa0ed9db`, HEAD `59192cfa`, neither an ancestor nor a descendant of
the dispatched tip — separate histories); tree was clean, so per the dispatch's own fallback:
`git branch dod-m12 f2803bad && git checkout dod-m12`. All checks below ran against that
checkout.

## Acceptance boundary — what this pass structurally cannot reach

Everything below is a fixture/suite pass, a toy-plant pass, or a ground-level read. **None of it
is a flight.** The class of defect this cannot catch, named up front per this role's own standing
instruction (the worked example is the F10 vocabulary's sight-vs-naked-eye defect, which no
fixture could have caught):

- **Whether the real cockpit's physical stick, pedals and collective are genuinely ignored
  while mode 1 holds the controls.** M0-D measured no felt twitch against the Mac-side wobble
  amplitude, on the probe branch, not against this merged law's own real per-frame output
  cadence, in the actual cockpit. This is the single most safety-relevant unknown in the whole
  feature and nothing short of a real flight answers it.
- **Whether the control law's placeholder gains produce a flyable response at all**, as opposed
  to a mathematically-correct-against-a-toy-plant one. M0-E (the real step-response measurement)
  was never flown. The toy-plant suite proves the shaper and the wiring; it cannot prove the
  real aircraft's response.
- **The felt experience of every silent mode switch** (park/unpark, Request Aircraft Control
  toggled twice) — the tests prove no field value jumps; they cannot prove nothing is *felt*.
- **The pedal channel's real-world coordination**, since no slip-ball measurement exists at all;
  it runs on feedforward alone and has never been flown.

Flight M-A (below) is designed to close exactly these gaps, and is reported PENDING (live), not
blocking this merge, per this project's standing "never block a merge on live acceptance" rule.

## Code Quality

**Subprojects touched** (derived from the diff against `main`'s merge-base, not from memory):
`aircraft-layer`, `body-layer`. (`git diff --name-only 0c206b37..HEAD` — the two subprojects
`git ls-files '*/pyproject.toml'` already lists as the whole project's enumeration.)

| Check | aircraft-layer | body-layer |
|---|---|---|
| `ruff format --check` | pass (85 files) | pass (241 files) |
| `ruff check` | pass | pass |
| `mypy --strict` (`cd <sub> && .venv/bin/mypy src`) | pass, 28 files | pass, 92 files (`PYTHONPATH=../world-model/src`) |
| **Full test suite** (`.claude/scripts/fast-tests.sh --full <sub>`, parallel) | **953 passed** | **3619 passed, 4 xfailed** |
| `luac5.1 -p` on every touched `.lua` file | pass (5 files: `Export.lua`, `ai_pilot_wheel.lua`, `commands.lua`, `flight_control.lua`, `body-layer/config/rules/flight.lua`) | — |

Tested tree's sha: `f2803bad55a1e07bd0f65e45ae05c7762413d1c9`, both subprojects. Venvs did not
exist in this worktree and were created fresh (`python3 -m venv .venv && pip install -e .` plus
`pytest`/`pytest-xdist`/`mypy`/`ruff`; body-layer additionally needed `pip install -e
../world-model` and `pip install lupa` for the world-model seam and the rule sandbox).

- **No unhandled errors/panics in data paths.** Lua: a bad `limits` bound rejects the whole
  message (logged), never crashes; `read_measured` fails soft to 0.0 on a bad `LoGet*` read,
  with the envelope check — now reading `self_data_ok`/`ias_valid`/`bank_valid` captured before
  the fail-soft zeroing — as the actual safety backstop, confirmed by reading both functions,
  not trusted from the implementation note. Python: every action either returns its result table
  or raises `RuleUnable`, caught once at `run_rule`; no bare `except` found in the touched files.
- **No debug output left in committed code.** Grepped the diff for `print(`/stray `console.log`-
  style calls in the touched files: none. The flag-gated `aircraft_layer_flight_debug.flag` →
  `aircraft_layer_flight_trace.log` per-frame trace is the intended, documented debug surface
  (built in from the start per `feedback_dcs_debug_logging_preemptive`), defaults off.
- **No leftover debug code or TODO comments introduced by this feature.** Grepped
  `flight_control.lua`/`flight_control.py`/`crew_console.py`'s new sections for `TODO`/`FIXME`/
  `XXX`: none. Every open item (M0-E gains, the pedal slip-ball gap, the two MONITOR perf items)
  is named in a docstring or this report, not left as a silent TODO.

## Scope & Correctness

- **Implementation matches the plan.** M1 (the seam, handover, bit-exact capture, `armed`/
  unpark-take) and M2 (the control law) both match `plans/flight-control/plan.md`'s "Revised
  2026-11-18 — mode 1 (unparked, raw axes) re-cut" section, read in full for this pass (the
  "Goal (mode 1)" through "Decisions Requiring User Input (mode 1 re-cut)" subsections). The
  handful of judgement calls the plan left ambiguous (the M1/M2 boundary for the ten `axes_*`
  action bodies; `fc_measured_altitude`/`fc_measured_speed` not named in the plan's own wire-shape
  text) are each flagged in `implementation.md`'s own Notable Discoveries, not silently decided.
- **No unplanned scope added silently.** The one deliberate scope addition beyond the plan's
  explicit list — `fc_measured_altitude`/`fc_measured_speed` — is named in `implementation.md` as
  "a small, mechanical, same-shape addition to an already-open wire message," and is exactly the
  kind of addition the plan's own instruction to report additions asks for.
- **No invariants from CLAUDE.md violated.** Checked against `body-layer/CLAUDE.md`'s own
  invariants list directly (not from memory): no LAN message carries a raw axis value (confirmed
  — `flight_control.py` only ever sends bounded goals/limits, read the module); neither handover
  token ever asks "confirm?" (confirmed — `HANDOVER_TOKENS`'s own floor, checked ahead of the
  ordinary comparison); an `axes_*` goal action never writes one of mode 2's `ai_pilot_*` one-shot
  fields (confirmed — Co-moving row 11's leak fix, tested both directions); park/unpark change the
  mode, never who has the controls (confirmed — Decision 24, Co-moving rows 8/8b/9/9a/9b/9c).
- **All new files staged with `git add`.** `git status --porcelain` on this worktree before this
  report's own commit showed only `M body-layer/ROADMAP/BL-16.md` and the new
  `docs/acceptance/2026-11-18-bl16-mode1-flight-ma.md` — both staged below.

## Testing

- **Core logic is covered by tests**, not decoratively. The toy-plant suite
  (`test_flight_control_law.py`, 11 tests) runs the five exported pure law functions directly
  against a real toy plant and asserts the plan's own named properties (bit-exact at take, the
  4.9°/5.1° takeover-mode boundary, convergence with no reversal in `h_ref`, the roll-out/settle
  heading). The Lua-interpreter suite (`test_flight_control_lua.py`) exercises the real module
  against a mocked DCS surface for everything a toy-plant test cannot reach (bound rejection,
  stale-seq, the park/unpark state machine, the pause/freeze row). Confirmed meaningful, not
  decorative, by this pass's own read of the mutation-testing record in `implementation.md`:
  several required fixes were counterfactual-verified by reverting the fix and watching the
  specific named test go red for the stated reason, then restoring and matching `shasum` — a
  discipline this pass did not re-run from scratch (trusted the documented record) but spot-
  checked by reading the diffs these tests exercise directly.
- **No existing tests were broken.** The differential test (`TestSeatNeverGatesMode1`) pins
  today's `CrewState`/`flight_mode()` results with axes inactive. The full suites above (953 /
  3619 passed) are the mechanical confirmation.

## Documentation

- **Reviewer findings addressed.** `review-m1.md` (NEEDS REVISION → both required fixes landed,
  confirmed in `implementation.md`'s "Review-fix round, 2026-11-18" with a counterfactual).
  `review-m2.md` (three findings, all fixed with counterfactuals, confirmed in "M2 review-fix
  round"). `review-cr-m1-m2.md` (APPROVED WITH MINOR FIXES — one required fix, the `ARM_LEASE_S`
  rendered-comment gap) — **verified directly by this pass**, reading the rendered
  `body-layer/config/defaults.toml` myself (see excerpt below): the warning now reads in full in
  the first sentence, not truncated.

  ```
  # U10's lease: Lua takes at an unpark only if body-layer has re-sent `arm` within this many
  # seconds -- about three missed ~1 Hz polls, closing the park-then-unpark escape route a
  # same-frame unpark take would otherwise remove from a dead Petrobrain (Decision 2 stands for
  # an *active* mode 1; this is what keeps the *armed* escape open).
  # status: judgement | range: 0.5 .. 10.0
  ```

- **Every accepted plan decision accounted for.** `.claude/scripts/accepted-items-ledger.sh
  plans/flight-control` reported only on the plan's *first* "Decisions Requiring User Input"
  section (mode 2's U1–U4, "not yet answered") — the script's awk only ever reads the first
  matching heading in a file that, after this plan's several re-cuts, now has five such headings.
  This is a real gap in the tool, recorded as its own DoD memory
  (`feedback_accepted_items_ledger_only_checks_first_decisions_section.md`). So U5–U10 (the
  mode-1-re-cut's own section, line ~3290) were checked **by hand** against
  `implementation.md`, named below by their Decision number where `implementation.md` names it
  that way rather than the bare `U<n>` token:

  | U<n> | Answer | Built where |
  |---|---|---|
  | U5 | silent transition both ways; player command only gives the controls back | Decision 24 — `implementation.md` lines ~1443 (bit-exact take), Co-moving rows 8/9 fully tested; `body.py`'s `OVERLAY`/`unpark_take` handling |
  | U6 | yes — no optics while flying, both modes, built in M1 | `body.py`'s `run_once(flying=...)` optic clamp + `write_sight_target` call-site skip, `test_run_once_flying_clamps_the_optic_to_naked_eye` |
  | U7 | accepted — M0 first, M1+M2 do not merge until M0-B/C/D answered | **Verified at this pass directly against the probe findings** (below), not just trusted from the plan's own "Met 2026-11-18" claim |
  | U8 | as recommended — act from `CONFIRM_FLOOR`, never "confirm?" | Decision 13 / `HANDOVER_TOKENS`, `test_voice_commands.py`'s five new tests (review-m1.md Required Fix 2) |
  | U9 | "Unable, AI overlay." in the overlay; nothing remembered | `flight.release_controls()`'s `OVERLAY` branch, Co-moving row 9c, `TestHandoverActions` |
  | U10 | approved as recommended — `ARM_LEASE_S` = 3 s, re-sent every poll | `body._apply_flight_control`'s lease re-send; ceiling now 10 s at all three layers (security Finding B fix) |

  **U7's gate, checked against the source, not the plan's claim about itself:**
  `aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`, Flight 7: *"M0-D (the
  go/no-go) passes for cyclic and collective."* Flight 3/4: M0-B (pedals, sign −1) passes.
  Flight 7 (re-flown after Flight 5's wrong-command finding): M0-C (collective, real id 2087)
  passes. The pedal half of M0-D was accepted by user direction rather than flown ("Assume
  pedals hold as well, if the arg is correct, it'll behave as the other axis.") — this is the
  plan's own documented acceptance, not an unverified gap. Flight 9: M0-J (park/unpark while
  writing) passed with a capture-timing fix, and `UNPARK_TAKE_ENABLED` is `true`.

- **Non-obvious behaviour explained** via `body-layer/CLAUDE.md`'s own module-map entry for
  `flight_control.py` (already present, read and confirmed accurate against the code) and this
  feature's own `notes/` additions (below).

## Security

No standalone `security-review.md` exists for this feature — this project's own convention for
a feature built in explicit stages is a per-batch security file
(`security-m1-m2.md`, matching `security-batch-a.md`/`security-p2.md`/`security-takeover.md`
for this same feature's earlier stages). `security-m1-m2.md`: **APPROVED**, two findings
surfaced for the user's decision rather than blocked. Both were **fixed**, not merely
acknowledged, in the subsequent change-request round (`review-cr-m1-m2.md`: APPROVED WITH MINOR
FIXES, confirmed above). The one residual the change-request round could not close (the max-seq
jam) is carried below as a backlog candidate, not silently dropped.

## Perf

`perf-m1-m2.md`: **APPROVED — MONITOR**. The one NOW finding (the `check_envelope`/
`read_measured` double-read) was fixed in the change-request round, confirmed by this pass's own
read of `flight_control.lua`'s `run_active_frame` (calls `read_measured()` once, passes the
result into `check_envelope`). Two MONITOR items remain open by design (not required fixes),
carried below as backlog candidates.

## Trial merge against `main`

`main` tip at this pass: `3f6b1a624725a262bdcfd7fd7e20c208f8e61d47`.
`git merge-tree --write-tree f2803bad main` — **two conflicts, both resolved below for the main
loop's `/merge` to apply directly.**

### Conflict 1 — `body-layer/ROADMAP/BL-16.md`

Pure insertion-point collision, not a content conflict: this branch appends its own "Mode 1
(unparked, raw axes)" section at the same point `main`'s `fix/apw-status-json-quotes` (merged
2026-11-18, after this branch forked) inserted its own paragraph about the `ai_pilot_wheel.lua`
JSON-quoting bug fix. **Resolution: concatenate — keep `main`'s `fix/apw-status-json-quotes`
paragraph first, then this branch's "Mode 1 (unparked, raw axes)" section (now further extended
by this DoD pass's own "Mode 1, Stages M1+M2 — DoD pass" addition) immediately after it.**
Nothing in either addition contradicts the other — worth noting that `main`'s fix is for exactly
the bug this branch's own `implementation.md` (M1's Notable Discoveries) flagged as "shipped,
not fixed here, out of scope" in `ai_pilot_wheel.lua`'s `push_ai_pilot_wheel_state`; `main`
closed it independently and first.

### Conflict 2 — `body-layer/config/rules/flight.lua`

A real content conflict: `main` carries the user's own 13:53 (2026-11-18) wording edits to
BL-17's shipped rules, made on `main` after this branch forked, which **must not be reverted**.
This branch adds new behaviour (the optional-degrees `turn_continuous` pattern, the real
`flight_handover` category bodies) at the same lines `main`'s rewording touched.

**`main`'s changes to keep, verbatim:**
- `level_off`'s spoken pattern: `"stop turn"` (was `"level off"`).
- Every HVRT bare-word pattern reworded: `"move left"`/`"move right"`/`"move forward"`/
  `"move back"`/`"move up"`/`"move down"` (bare `"left"`/`"right"`/`"forward"`/`"back"`/`"up"`/
  `"down"` on `main` before the reword); `"hold"` is unchanged.
- `turn_heading`'s pattern gains a verb slot: `"<verb:turn|fly> heading <heading_deg:heading>"`
  (was bare `"<heading_deg:heading>"`).
- Every `when.speech(...)` call's own multi-line argument formatting (one argument per line) —
  this branch's copy still has the old single-line-where-it-fits style; keep `main`'s.

**This branch's changes to layer on top, not instead of the above:**
- The module header comment: merge both docstring updates (this branch's mode-1/`_by_mode`
  explanation, placed so it reads naturally after whatever `main`'s own header text says —
  `main`'s diff did not touch the header, so this branch's full replacement text applies
  cleanly).
- `turn_heading_relative`'s pattern becomes `"turn <direction:left|right>
  [<degrees:angle>]"` (optional degrees) — applied to `main`'s own multi-line formatting of this
  rule, not this branch's single-line copy. The new no-degrees branch body (calls
  `flight.turn_continuous(sign)`, says "Left."/"Right.") is inserted before the existing
  degree-handling body, unchanged in substance from this branch's diff.
- `you_have_controls`/`i_have_controls` move from category `"always"` with empty bodies to
  category `"flight_handover"` with the real bodies (`flight.take_controls(...)` /
  `flight.release_controls()`) — this branch's new category and bodies are applied over `main`'s
  own multi-line formatting of the two `when.speech(...)` calls, not over this branch's own
  single-line copy of them.

No other rule in the file changed on either side — every other `when.speech` call's pattern,
category and body are untouched by both diffs (only `main`'s line-wrapping differs, which this
resolution keeps).

## Backlog candidates surfaced (IDs not minted — main loop mints per root `CLAUDE.md`)

1. **Perf MONITOR — `law_update`'s per-frame full-state `pairs()` copy.** Allocates one ~25-key
   table every active frame via generic iteration; cheap fix when touched (explicit field-by-
   field return, matching `law_init_at_take`'s own style) but not worth a standalone change
   today — no measured symptom, judged against this file's own established per-frame-allocation
   baseline.
2. **Perf MONITOR — `update_live_seat_tracking`'s uncached `GetDevice(0)` pattern.** Re-opens
   the project's own standing "per-frame `GetDevice(0)` read count keeps growing" threshold (now
   18+ per-frame calls across the file); recommended fix when next touched is one cached
   `local device0 = GetDevice(0)` per frame, threaded into every `push_*`/`read_axis` call.
3. **Security residual — the max-seq jam.** Once `fc_last_cmd_seq` reaches its representable
   ceiling (`2**31-1`), the restart-reconciliation fix actively walks `wire_seq` to the same
   ceiling and the channel then jams for the rest of the DCS session — an explicit logged error
   now, not a silent drop, but not reopened as fixable without the separately-reasoned-against
   option (a) (bound how far a single message may advance the counter). Low probability
   (single-user LAN); the physical park gesture remains an independent escape hatch regardless.
4. **The three-way `arm_lease_s` ceiling duplication** (`Export.lua`'s `FC_LIMIT_BOUNDS`,
   `aircraft-layer/src/api/server.py`'s `_FLIGHT_CONTROL_LIMITS_BOUNDS`, body-layer `tuning.py`'s
   `hi` bound) — all three now at 10.0, cross-referenced in comments, but nothing mechanically
   ties them together the way `test_export_lua_constants_parity.py` does for a different
   constant pair. A future change to any one of the three needs a human (or a future
   `invariant-check`-style grep) to keep the other two in step.

## Execute the unblock condition of accepted debt

Per this role's own standing instruction, checked rather than assumed: the one piece of
accepted debt this pass carries forward is Flight M-A itself (`#needs-flight`), whose unblock
condition is "fly it" — not a command this DoD pass can execute from the Mac. Every *other*
named condition in this batch (U7's merge gate, `UNPARK_TAKE_ENABLED`) was already run and
confirmed above, against the probe findings file directly, not trusted from the plan's own
self-report.

## Acceptance testing

**PENDING (live).** Flight M-A (`plans/flight-control/plan.md`, "Flight M-A") is the acceptance
flight, written up as `docs/acceptance/2026-11-18-bl16-mode1-flight-ma.md` and published as a
test card: https://claude.ai/artifact/C4TTm4bK2eJLpGqsZ54Qp5. Tagged `#needs-flight` on
`body-layer/ROADMAP/BL-16.md`'s own M1+M2 entry. Per this project's 2026-10-26 user direction,
this does not gate the merge.

## Notes harvest

Four insights added, none duplicating an existing topic file (checked by the harvest script's
own grep and by hand):

- `notes/lua-export-module-architecture.md` — the same-frame transition-write trap (`run_
  active_frame`'s own bug, caught by the Implementer's own test before review).
- `notes/feedback-control-law-design.md` (new topic, added to `notes-index.md`) — the stopping-
  distance-divisor bug (velocity ceiling vs. deceleration cap), and the fixed-gain-cannot-zero-
  overshoot-against-a-velocity-dependent-target result.
- `notes/wire-protocol-validation.md` (new topic, added to `notes-index.md`) — the bounds-dict-
  as-silent-whitelist trap (`_FLIGHT_CONTROL_LIMITS_BOUNDS`), and the monotonic-reconciliation-
  can-still-jam-at-its-own-ceiling lesson.

## Recurring-fix pattern surfaced (process signal)

`review-cr-m1-m2.md`'s one required fix — `ARM_LEASE_S`'s explanatory second sentence not
surviving `generate_defaults.py`'s first-sentence render — matches a category this project's own
Reviewer memory already names as its **fourth confirmed instance**
(`feedback_arm_lease_s_second_sentence_recurrence.md`), on top of several earlier, differently-
shaped bugs in the same splitter function. Recorded as its own DoD-level process memory
(`project_recurring_tuning_comment_second_sentence_dropped.md`): this is now well past the
threshold where "read the rendered file by hand, every time" should be trusted as the standing
mitigation. Recommending to the user: either the generator gets a self-consistency check
(does the rendered comment equal the *first sentence of the full source paragraph*, for every
key — a mechanical staleness test, not a human read) or the writing convention changes so the
explanation is required to fit in one sentence by construction. This is process debt, and a
candidate for a check earlier in the role sequence (Architect/Implementer) rather than repeatedly
catching it at Reviewer/DoD.

Also recorded: `accepted-items-ledger.sh` only reads the first "Decisions Requiring User Input"
heading in a plan file, silently missing every later section once a plan has been re-cut more
than once (`feedback_accepted_items_ledger_only_checks_first_decisions_section.md`) — a tooling
gap, not a process-discipline gap, worth a mechanical fix if this plan or another re-cut plan
needs its ledger run again.

## Milestone Completion

Per root `CLAUDE.md`'s "Milestone Completion": M1+M2 passing does not change M3's or M4's own
assumptions (M3 still needs M0-A's AGL smoothing τ, untouched here; M4 still needs M0-H, flown
separately) or invalidate anything downstream relies on. What it does change: M3/M4 can now be
designed and flown against a real, merged control law instead of a toy plant, so their own first
flights are no longer purely speculative about what they level off against.

## Summary

- **DoD: PASSED**, scoped to tip `f2803bad55a1e07bd0f65e45ae05c7762413d1c9`.
- **Acceptance testing: PENDING (live)** — Flight M-A, card published, `#needs-flight` tagged.
  Does not gate this merge per standing direction.
- **Trial merge against `main`: two conflicts, both resolved above** for the main loop's
  `/merge` to apply — `body-layer/ROADMAP/BL-16.md` (concatenate) and
  `body-layer/config/rules/flight.lua` (keep `main`'s 13:53 wording/formatting edits, layer this
  branch's new behaviour on top of them, not instead of them).
- **notes/**: four insights added across three topic files (one existing, two new).
- **Recurring-fix pattern surfaced**: the `defaults.toml` generator's first-sentence-only render,
  now a fourth-plus confirmed instance — flagged as process debt worth a mechanical fix rather
  than another Reviewer catch.
- **Backlog candidates surfaced** (4, IDs left for the main loop to mint): two perf MONITOR
  items, the max-seq jam residual, and the three-way `arm_lease_s` ceiling duplication.
