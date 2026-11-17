# DoD Check: BL-17 Stages 3a, 3b, 3d, 4 (fuzzy matching, category gates, effector-write surface, flight-control port)

**Branch:** `feature/speech-rules-matching`. Dispatch named expected tip `e4c6b707`.

**Verification, before anything else ran:** this worktree's own `HEAD` at dispatch was `fc282270`
(main's number-words-decision merge). `git merge-base --is-ancestor HEAD e4c6b707` confirmed `HEAD`
was a strict ancestor of the named tip (`git merge-base HEAD e4c6b707` == `fc282270` == `HEAD`), and
`git status --porcelain` was clean — so per the dispatch's own instruction, `git merge --ff-only
e4c6b707` ran directly (fast-forward, no conflicts, no snapshot fallback needed). All checks below
ran against the real fast-forwarded tree, not a stale or reconstructed one.

**This verdict is scoped to `e4c6b707` plus the two DoD-pass commits made on top of it in this
worktree** (the `record_corpus.py` testing-aid fix, `564c6ca9`, and this report/roadmap/notes
commit) — see "Tip sha" at the end.

## Code Quality

Full suites run in parallel (`pytest-xdist`), `--full` (slow tests included), fresh `.venv`s built
from `/opt/homebrew/bin/python3.14` (neither subproject had one in this worktree):

| subproject | format | lint | mypy --strict | full test |
|---|---|---|---|---|
| body-layer | pass (223 files) | pass | pass (91 source files, 0 issues) | **3548 passed, 4 xfailed, 0 failed** |
| audio-adapter | pass (36 files) | pass | pass (17 source files, 0 issues) | **526 passed, 2 skipped, 0 failed** |

**The previously-known `test_shipped_effector_config_loads_without_errors` failure (named in the
dispatch as expected to now pass) is gone** — confirmed by grepping the full run's output for both
the test name and any `FAILED`/`FAILURES` marker: zero hits either way. `main`'s removal of the
empty `seat-copilot.md` row (carried in by the `fc282270..e4c6b707` fast-forward) is what fixed it;
no code change in this batch touched that file.

**No unhandled errors or panics in data paths.** `rules/engine.py::run_rule` gained a bare `except
Exception` alongside the existing `(RuleRuntimeError, RuleBudgetExceeded)` catch (Stage 4), logging
the rule id/file/exception type before degrading to D6's `ACTION_FILE_ERROR_LINE` — verified by
Security (`security-stage3-4.md`) as sound, not a silent swallow, and correctly leaving
`BaseException` subclasses to propagate. `rules/gates.py`'s `GATE_REGISTRY` is closed: an unknown
category answers `UNABLE("NO_SUCH_COMMAND")`, never a silent `PASS` — pinned by `test_rule_gates.py`.

**No debug output left in committed code.** The one new `print(...)` introduced in this batch's
diff (`body.py`, `--print-rules`'s own listing loop) is the pre-existing intentional CLI-debug
convention this project already uses for `--print-tuning`/`--print-rules` — not leftover debug
code.

**No leftover debug code or TODO comments introduced by this feature.** `/invariant-check` (run in
full below) found zero `TODO`/`FIXME`/`HACK`/`XXX` anywhere in any subproject's `src/`, and a direct
grep of this batch's own diff (`c97731c0^..e4c6b707`, `body-layer/src` + `audio-adapter/src`) for
`print(`/`TODO`/`FIXME`/`XXX`/`HACK`/`pdb` outside test files found only the one `--print-rules`
line above.

### `/invariant-check`

| Invariant | Status |
|---|---|
| No omniscience — `derived_world_position` outside the Percept boundary | PASS |
| Module independence — no unsanctioned cross-subproject import | PASS |
| No `sys.path` manipulation in `src/` | PASS |
| Retired `BINOCULAR_RANGE_MULTIPLIER` has not returned | PASS |
| No stray `print()` in `perception/`/`belief/` core | PASS |
| No bare `except:` | PASS |
| Swallowed exceptions (`except ...: pass`) | WARN, 4 occurrences — all pre-existing entrypoint shutdown handlers (`collector/__main__.py`, `audio_adapter/__main__.py`, `body.py:5658`, `brain_layer/__main__.py`), none introduced by this batch |
| `# type: ignore` suppressions | WARN, 16 occurrences — pre-existing (`lupa` import-untyped, `__init__` reset patterns, `eyesight_view.py` row typing); none new in `rules/`, `belief/crew_console.py`, or `belief/effector_engine.py` from this batch |
| No TODO/FIXME in committed source | PASS |

Both WARNs are the mechanical check's standing baseline, not something this batch added — checked
by hand against the diff, not assumed from the WARN count alone.

### `command-map-check.py`

```
on the map but no longer in TOKENS: altitude_step, hold_altitude, hvrt_hold, hvrt_step_down,
hvrt_step_up, hvrt_translate_back, hvrt_translate_forward, hvrt_translate_left,
hvrt_translate_right, level_flight, level_off, set_altitude, set_speed, speed_step, turn_heading,
turn_heading_relative
command map STALE -- run /command-map
```

**Fails for the known, named reason, not a regression.** Every listed id is a rule now
(`config/rules/flight.lua`), not a `vocabulary.TOKENS` entry — the command map's own generator
reads `vocabulary.TOKENS`/`PHRASES` and has no concept of a Lua rule pattern yet. Per the dispatch's
own instruction, not redrawn here; the map staying stale while rule-ported commands exist is a
known gap in the map tool itself, to close whenever the map generator is next touched.

## Scope & Correctness

**Implementation matches `plans/speech-rules/plan.md` Revision 2's Stages 3a/3b/3d/4** (D13–D20,
U19–U24). Traced against each review's own verdict rather than re-deriving independently:

| stage | content | review verdict | re-review(s) |
|---|---|---|---|
| 3a | fuzzy literals (D13), number-word grammar (D14), two perf caches | CHANGES REQUIRED → APPROVED WITH MINOR FIXES → one more required fix (whisper-numerals citation) → closed | 2 rounds, both closed |
| 3b | rule categories + dispatch gates, hold-and-fly (D16) | APPROVED WITH MINOR FIXES (2 required fixes: the `settling`-proxy generalization risk, a stale comment) | fixes landed same day, re-reviewed as part of Stage 4's pass |
| 3d | effector-write action surface (D20) | CHANGES REQUIRED → 3 required fixes closed → **1 more required fix** (cross-thread race, Required Fix 4) → closed → **re-review found the fix itself still racy** (poll-thread drain vs. an open dispatch window) → buffer-then-commit → closed | 3 re-review rounds on Required Fix 4 alone |
| 4 | 18 flight-control rules ported (19 planned minus "straight", user-dropped) | APPROVED, no required fixes | — |
| perf+security fixes | `compile_rules` O(n²) memoization gap, `_poll_transcripts` dict-slot drop | both CHANGES REQUIRED → both fixed → re-reviewed APPROVED | 1 round each |

**No unplanned scope added silently**, with one explicit exception, flagged here rather than
folded into the batch quietly: running `plan.md`'s own Stage 3c step 3 command before writing it
into the flight card (see "Acceptance boundary" below) found the command never existed as written.
Fixed `audio-adapter/tools/record_corpus.py` (a light-path testing aid — `--phrases-file`/
`--list-prompts`, committed separately at `564c6ca9`) and corrected `plan.md`'s own text. This is
not Stage 3a/3b/3d/4 scope; it is reported as its own thing, not claimed as part of the batch.

**No invariants from `CLAUDE.md` violated** — see `/invariant-check` above, plus the project-
specific ones checked by hand: module independence (body-layer↔world-model is the only seam; this
batch adds no new cross-subproject import), the no-omniscience boundary (`Percept` untouched by
this batch — rules only read `CrewState`, a belief-state projection, never ground truth), and
"behaviour-affecting constants are tunable" (`RULE_GATE_HOLD_TIMEOUT_S` declared through
`tuning.py` with `lo`/`hi` bounds, confirmed present in `config/defaults.toml`).

**All new files staged with `git add`** — confirmed via `git status --porcelain` (clean) after each
commit in this pass.

## Testing

**Core logic is covered by tests, and the tests are meaningful, not decorative** — verified by
reading the Reviewer's own mutation testing, not just trusting "tests exist":

- Reviewer reverted the perf fix and the security fix in turn and confirmed the regression tests
  go red for the stated reason (`review-perf-security-fixes.md`).
- Reviewer reverted Required Fix 4's rollback to the rejected length-based-truncate shape and
  confirmed only the concurrency test (not the single-dispatch test) tells the difference
  (`review-stage3d.md`'s "Re-review (Fix 4)").
- Reviewer reproduced the poll-thread-drain race with a standalone probe against the real,
  unmodified code before it was fixed, and the buffer-then-commit fix's own new test
  (`test_poll_thread_drain_during_an_open_dispatch_window_gets_nothing_from_it`) reproduces that
  exact probe (`review-stage4.md`).
- Reviewer mutation-tested both grep-fence tests added for the dispatch-token follow-up
  (reintroduced a direct construction via an aliased import; both fences fired for the stated
  reason).

**No existing tests were broken** — both full suites pass clean (table above); the one previously-
failing test is now fixed by `main`'s own change, not by this batch, and nothing else regressed.

## Documentation

**Reviewer findings addressed** — see the Scope & Correctness table; every required fix across
every review round traced to a landed commit and re-reviewed, with the final state APPROVED on
Stage 4's pass (which also covered Stage 3d's last re-review and the perf/security fix re-review).

**Accepted-items ledger.** `.claude/scripts/accepted-items-ledger.sh plans/speech-rules`:

```
ledger plans/speech-rules: U1 ->
    295:   patterns.py`'s own module docstring) rather than an oversight: U1's own "fixed wording is the
ledger plans/speech-rules: accepted U2 is never named in implementation.md -- built, or deferred to a named stage? Say which there.
ledger plans/speech-rules: accepted U3 is never named in implementation.md -- built, or deferred to a named stage? Say which there.
ledger plans/speech-rules: U4 ->
    341:  readback (the rule writes its own, D4/U4); `"turn_heading_relative"` removed from
ledger plans/speech-rules: accepted U5 is never named in implementation.md -- built, or deferred to a named stage? Say which there.
ledger plans/speech-rules: U6 ->
    2082:At the plan's own U6 ~100-rule target this removes essentially all of the regression the
ledger plans/speech-rules: U7 ->
    17:  U7 (user approval).
ledger plans/speech-rules: accepted U8 is never named in implementation.md -- built, or deferred to a named stage? Say which there.
ledger plans/speech-rules: accepted U9 is never named in implementation.md -- built, or deferred to a named stage? Say which there.
ledger plans/speech-rules: U10 -> ... (found, context omitted here -- see Stage 0-2's own dod-check.md)
ledger plans/speech-rules: U11 -> ... (found)
ledger plans/speech-rules: accepted U12 is never named in implementation.md -- ...
ledger plans/speech-rules: accepted U13 is never named in implementation.md -- ...
ledger plans/speech-rules: accepted U14 is never named in implementation.md -- ...
ledger plans/speech-rules: accepted U15 is never named in implementation.md -- ...
ledger plans/speech-rules: accepted U16 is never named in implementation.md -- ...
ledger plans/speech-rules: accepted U17 is never named in implementation.md -- ...
ledger plans/speech-rules: accepted U18 is never named in implementation.md -- ...
```

(Exit code 1 — the script's own "found a gap" signal. Full command and output re-run and read in
full for this report, not excerpted from memory.)

**This is the script matching only the plan's *first* "Decisions Requiring User Input" heading**
(U1–U18) — the prior DoD pass (Stage 0/1b/2, `plans/speech-rules/dod-check.md`) already resolved
every one of U1–U18 by hand and recorded it in that file's own ledger table; nothing here reopens
it. **This batch's own decisions are U19–U24**, under a *renamed* heading ("### Revision 2's own
open decisions (U19–U24)") the script's `awk` never matches at all — a third, independently-
reconfirmed shape of the ledger's known false-negative class (`.claude/agent-memory/dod/
feedback_accepted_items_ledger_misses_indented_answered_line.md`; first found on this exact plan
by Reviewer, `.claude/agent-memory/reviewer/feedback_ledger_misses_a_renamed_decisions_heading.md`).
Checked by hand, each against the shipped code directly:

| id | decision | status |
|---|---|---|
| U19 | `when.speech(id, pattern, category, handler)` — category required, no default | **built** — `rules/loader.py`'s `RawRegistration.category: str = "always"` is a test-only convenience default documented as such; every shipped `config/rules/flight.lua` call passes one explicitly |
| U20 | `RULE_GATE_HOLD_TIMEOUT_S` = 5.0s, lo 1.0/hi 15.0, tunable | **built** — `config/defaults.toml:171-172` (`source: belief/crew_console.py:RULE_GATE_HOLD_TIMEOUT_S`, value `5.0`) |
| U21 | latest held flight command wins, silently | **built** — `crew_console.py`'s `_handle_rule` assignment and `drain_pending_rule_dispatch`, both commented "latest wins, U21" |
| U22 | flight readbacks may cut off a routine callout while flying | **built** — `crew_console.py:3543`'s `CalloutScheduler.note_urgent` reuse, confirmed by Reviewer against the real differential tests (`review-stage4.md` point 5) |
| U23 | narrowed-hint ship threshold (Stage 3c) | **deferred** — Stage 3c itself is out of scope for this batch (see below); nothing to build yet, correctly named as pending in `plan.md` |
| U24 | a rule-originated effector write that keeps failing: no change for now | **deferred, as decided** — no shipped rule in this batch calls `effector.write` (confirmed by Security, `security-stage3-4.md`: "no shipped rule calls this yet"), so there is nothing yet to observe the gap in; revisit when one does |

All six accounted for — four built and verified against code, two correctly deferred to a stage
this batch does not include.

**Any non-obvious behaviour explained** via `config/rules/README.md` (fully rewritten: the
category table, the `when.speech` signature, the failure/reload model), module docstrings
(`rules/engine.py`, `rules/gates.py`, `rules/actions.py`, `rule_patterns.py`'s slot-type registry),
and two `notes/` topic files gained content this pass (see "Notes harvest" below).

## Security

`plans/speech-rules/security-stage3-4.md`: **CHANGES REQUIRED** — one required fix (`body.py`'s
`_poll_transcripts` silently dropping `set_speed`'s dict-valued `speed_target` slot, a real,
empirically-reproduced defect; `implementation.md`'s own account of this being "already fixed" was
itself wrong, caught only by reading the current source). Two items filed, not blocking
(`[[BL-B127]]` — no category/seat coupling on `effector.write`, not exploitable today since no
seat-restricted category or effector exists yet; `[[BL-B128]]` — a narrow, low-probability,
low-impact cross-thread race on `drain_pending_rule_dispatch`, same shape as the effector-write race
but not yet fixed, filed for whoever next touches that path).

Fix landed (`79d75af8`) and re-reviewed: `plans/speech-rules/review-perf-security-fixes.md` —
**APPROVED**, verified by mutation (reverted the fix, confirmed the two new regression tests go red
for the stated reason) and by tracing the end-to-end test's real call chain through to the real
`config/rules/flight.lua`, not a double.

## Acceptance boundary — what this feature's fixtures structurally cannot reach

Every check above ran against fixtures, synthetic probes, and a non-interactive CLI. **None of it
is a live DCS flight.** Specifically out of reach from here:

- Whether the gate's `"unable, not flying"`/hold-and-retry behaviour reads correctly to a pilot
  mid-takeover, in real time, against DCS's own AI-overlay state machine rather than a test
  double of `ParkedFlightState`.
- Whether whisper actually transcribes "turn left thirty" as digits or as the word "thirty" on
  the user's own voice (the whole reason D14's word-grammar fallback exists) — `plan.md`'s own
  "Settle with real whisper output when the re-plan picks this up" is still unmet; Stage 3c (the
  corpus/measurement stage that would settle it) is explicitly not in this batch.
- Whether 18 commands' worth of gate/hold/readback behaviour, now live simultaneously instead of
  one at a time, interacts in some way a fixture never constructs — e.g. two flight commands said
  in quick succession during a real takeover, not a synthetic `PendingRuleDispatch`.

**One item this draft originally listed here turned out to be stale, caught only by actually
running the check rather than trusting `implementation.md`'s own narrative**: five candidate
wording collisions `implementation.md` found mid-stage are *not* still rejected at `PUT /rules`
today — the D9 recalibration (`d3ec510b`) rescued three and the user's later decision to drop
"straight" removed the last pair's own colliding side. Verified directly, raw output:

```
$ python -m body --print-rules --audio-adapter-url http://127.0.0.1:<port>
loaded 18 rule(s) from .../body-layer/config/rules:
  altitude_step [flight_control_altitude]: <direction:climb|descend> <amount_m:quantity>
  hold_altitude [flight_control_altitude]: hold <verb:altitude|alt>
  hvrt_hold [flight_control]: hold
  hvrt_step_down [flight_control]: down
  hvrt_step_up [flight_control]: up
  hvrt_translate_back [flight_control]: back
  hvrt_translate_forward [flight_control]: forward
  hvrt_translate_left [flight_control]: left
  hvrt_translate_right [flight_control]: right
  i_have_controls [always]: i have controls
  level_flight [flight_control_any]: level flight
  level_off [flight_control_heading]: level off
  set_altitude [flight_control]: <verb:alt|altitude> <altitude_m:quantity> [<reference:radar|barometric>]
  set_speed [flight_control]: speed <speed_target:speed_target>
  speed_step [flight_control_speed]: <verb:slow|speed> <direction:down|up>
  turn_heading [flight_control]: <heading_deg:heading>
  turn_heading_relative [flight_control_heading]: turn <direction:left|right> <degrees:angle>
  you_have_controls [always]: you have controls
adapter accepted: ['altitude_step', 'hold_altitude', 'hvrt_hold', 'hvrt_step_down', 'hvrt_step_up',
  'hvrt_translate_back', 'hvrt_translate_forward', 'hvrt_translate_left', 'hvrt_translate_right',
  'i_have_controls', 'level_flight', 'level_off', 'set_altitude', 'set_speed', 'speed_step',
  'turn_heading', 'turn_heading_relative', 'you_have_controls']
```

All 18 accepted, zero rejected, zero missing. See `body-layer/ROADMAP/BL-17.md`'s own corrected
account. Left in this report as a worked example of exactly the failure this role's brief warns
about — the narrative in a plan/implementation log can go stale between when it was written and
when DoD reads it, and the only way to know which is current is to run the thing.

This is the same class of gap the worked example in this role's own brief names: a fixture can
prove the mechanism does what it says, never that it is pointed at the right thing or sounds right
to a human ear. Flight is what resolves the remaining bullets above, not a further fixture pass.

## Executed the unblock condition, not just read it

`body-layer/ROADMAP/BL-17.md`'s Stage 0/1b/2 entry carries `#needs-flight` with "flight to be flown
on `main` after this merge" as its clearing condition. That condition has not yet been cleared —
no sortie report exists for it — so it is **not** re-asserted as resolved here; it stays open,
folded into this pass's own `#needs-flight` entry below (the user's 2026-11-15 testing-debt
direction batches live `#needs-flight` items for one sortie rather than clearing them piecemeal).
The one thing this pass *could* execute directly — `plan.md`'s Stage 3c `record_corpus.py` command
— was executed, found broken, and fixed (see "Scope & Correctness" and the commit `564c6ca9`),
rather than written into the card unverified.

## Tip sha

Checks above ran against `e4c6b707` (the fast-forwarded tip). This report, the roadmap update, and
the notes harvest are committed on top of it in this worktree, along with the separate
`record_corpus.py` testing-aid commit (`564c6ca9`) — the verdict is PASSED for that resulting tree,
not for any later change to the branch.
