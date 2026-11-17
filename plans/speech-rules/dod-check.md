# DoD Check — BL-17 Stages 0, 1b, 2 (`feature/speech-rules`)

**Verdict scoped to tip `630ab18c`.** This worktree started on an unrelated branch
(`worktree-agent-a11491199ef801642`, BL-16/docs work, `HEAD=6fb23698`) with no `plans/speech-rules/`
tree at all. `git merge-base --is-ancestor HEAD 630ab18c` confirmed `6fb23698` is a strict ancestor
of the dispatch's stated tip, tree was clean, and `git merge --ff-only 630ab18c` fast-forwarded
cleanly (60 files, no conflicts). Everything below was checked against that exact commit. If
`feature/speech-rules` has moved since, this verdict is stale.

**Scope**: Stages 0, 1b, 2 only (the rule engine, the adapter seam, and the one ported rule,
`turn_heading_relative`). **Explicitly not in scope**: Stage 1a / D12 (bearing/heading rename —
paused mid-build by the user, parked on `wip/bl17-stage1a-rename`) and Stages 4–10 (re-planned
with the user after this merge, per `BL-17.md` "Checkpoint after Stage 3"). Stage 3 (the test
flight) is the user's live acceptance and does not gate this DoD, per root `CLAUDE.md`'s
auto-merge rule.

## Code Quality

| Check | body-layer | audio-adapter |
|---|---|---|
| `ruff format --check` | pass (218 files) | pass (36 files) |
| `ruff check` | pass | pass |
| `mypy --strict` (`cd <sub> && .venv/bin/mypy src`) | pass, 89 files | pass, 17 files |
| Full suite, `.claude/scripts/fast-tests.sh --full <sub>` | **3476 passed, 4 xfailed** (152.5s, parallel) | **480 passed, 2 skipped** (5.5s, parallel) |

Both venvs built fresh in this worktree (`/opt/homebrew/bin/python3.14` 3.14.10, none existed —
gitignored), `lupa==2.8` installed into body-layer's. These are my own fresh runs, not a re-read of
Reviewer's numbers — they land within 1–4 tests of Reviewer's and the Implementer's own counts
(3472–3476 across four independent full runs across this feature's history), consistent with the
one flagged `pytest-xdist` parallel-teardown flake (`test_slew_trace_is_written_from_the_real_poll_
loop`, pre-existing, in code this feature never touches) — **it did not reproduce in my run either**
(0 failures). `git status --porcelain` was clean after building both venvs (gitignored, no tracked
files touched).

`/invariant-check`'s mechanical scan (run fresh, not re-read from Reviewer's report): no omniscience
leak, module independence, no `sys.path` smuggling, `BINOCULAR_RANGE_MULTIPLIER` absent, no stray
`print()` in belief/perception core, no bare `except` — all PASS. WARN classes (swallowed
exceptions, `type: ignore`) are pre-existing; the one new `type: ignore[import-untyped]`
(`sandbox.py:38`) is exactly the plan's own sanctioned, confined exception — none of the swallowed-
exception WARN hits are in this feature's own files (checked directly).

**No unhandled errors/panics in data paths**: this is the subject of Security's Required Fix
(`nan`/`inf`/non-numeric reaching an unguarded `int()` at the Lua→Python action boundary) — fixed,
re-reviewed, re-verified by mutation twice (once by Reviewer's first pass, once by the re-review).
I did not re-mutate it a third time; the re-review's own mutation evidence (revert-and-restore,
checks re-run fresh) is independent enough of the original fix to trust.

**No debug output / no leftover TODO/FIXME**: `grep`'d for `TODO|FIXME|HACK|XXX` across every
touched module — none found; `/invariant-check` confirms the same for the whole tree. Every
`print()` in the touched files (`body.py`'s `--print-rules`/`--print-tuning`-style banners,
`_print_rule_banner`'s stderr output) is deliberate CLI-output or startup-error-banner text matching
an existing precedent (D11 mirrors `--print-tuning`), not debug cruft.

## Scope & Correctness

- **Matches the plan**: every Stage 0/1b/2 line item in `plan.md`'s "Affected modules" and stage
  descriptions is present in the diff; nothing from Stage 1a, 3, or the later-stages table shipped.
  Confirmed by reading `git diff 6fb23698..630ab18c --name-only` (60 files) against the plan's own
  module list — no file outside that list, no module ahead of its stage.
- **No unplanned scope added silently**: `plans/behaviour-trees/explore-notes.md` is the one touched
  file outside `plans/speech-rules/`+body-layer+audio-adapter, and it's an explicitly-cited plan
  *input* (the explore conversation this plan was built against), not new scope.
- **No CLAUDE.md invariants violated**: no omniscience leak (actions never touch `Percept`/ground
  truth, confirmed by reading `flight.increment_heading`'s one read, `parked_flight_state.
  held_heading`, an existing belief-side field); module independence held (`sandbox.py` is the sole
  `lupa` importer, grepped; `rules/` imports `belief.*` one direction only, `crew_console.py`
  imports nothing from `rules.*`, confirmed by reading — the injected `rule_runner` is a plain
  tuple-callable type); tuning mechanism correctly *not* invoked for the three new instruction/
  memory-budget constants (safety bounds, not behaviour, matching root `CLAUDE.md`'s own carve-out).
- **All new files staged**: `git status --porcelain` clean throughout (before and after my own
  checks); the fast-forward merge itself brought in a clean tree.

## Testing

Covered above (code quality table). Meaningful, not decorative — independently spot-verified by
re-running `/invariant-check` fresh and by executing the Stage 3 card's first command for real
(below) rather than trusting any prior report's account of it. No existing test was broken: full
suites pass clean in both subprojects at this tip.

## Documentation

### Reviewer findings addressed

- `review-stage1b-2.md`'s one Required Fix (D8's text no longer matched what shipped — fuzzy
  scoring vs. the actual full-consumption exact-literal matcher) is addressed: `plan.md`'s D8 now
  carries a dated "As built, 2026-11-17 (Stages 1b–2)" addendum recording the actual scope and why,
  exactly as the fix asked (confirmed by reading `plan.md` lines 153–158).
- Security's Required Fix 1 (`security-stage0-2.md`, CHANGES REQUIRED) landed, and Reviewer's
  re-review of that fix (`review-security-fix.md`) found the first pass treated two
  architecturally-different sites uniformly — `_make_action_wrapper`'s degrade-to-reject-branch was
  correct and unchanged; `_digits_readback`'s identical treatment was wrong (no stderr log, a
  misleading "Unable." for what is actually a rule-file bug) and was corrected to raise
  `RuleRuntimeError`, routing through D6's existing logged/"Action file error." path. A second
  re-review round confirmed the correction landed exactly as asked, by mutation (revert-and-restore,
  not just reading the diff), and verdict APPROVED.

### Accepted-items ledger

`.claude/scripts/accepted-items-ledger.sh plans/speech-rules` flags U2–U18 as "never named in
implementation.md" (mechanical: it only greps for the literal `U<n>` string). Checked each by
reading the code/tests, not just trusting Reviewer's own pass of this:

| id | decision | status |
|---|---|---|
| U1 | fixed wording is the fast path | **built** — patterns are fixed Lua phrases by construction (D1); loose speech still falls through to the brain |
| U2 | typed directions, 3 digits, no checksum | **deferred** — Stage 1a (rename), paused on `wip/bl17-stage1a-rename` |
| U3 | bearing relative / heading compass, rename existing code | **deferred** — Stage 1a, paused |
| U4 | each rule writes its own readback | **built** — `config/rules/flight.lua`'s `say(...)` call; test: `test_rules_flight_actions.py` |
| U5 | target choice stays in code, `nil` → no contact | **deferred** — Stage 7, per plan's later-stages table |
| U6 | all commands move, grouped into files | **deferred** — plan's later-stages table (Stages 4–10) |
| U7 | lupa approved | **built** — `body-layer/pyproject.toml` `lupa==2.8`, `research/2026-11-17-lupa-sandbox.md` |
| U8 | sequencing: structure, then 1–2 ports, then flight, then schedule the rest | **built** — this is literally this plan's own Stage 0→1b→2→3→(later) structure |
| U9 | scan/report bearing relative, plain readback | **deferred** — Stage 1a (D12), paused |
| U10 | duplicate rule ids: both disabled, one warning | **built** — `RuleSet._dedupe`; test: `test_rules_engine.py`'s duplicate-id case |
| U11 | rule files reload at mission restart | **built** — `body.py`'s `_check_for_new_mission` wiring (D2); tests in `test_rules_engine.py`/`test_body.py` |
| U12 | first port on AI-overlay flight | **built** — Stage 2 ports `turn_heading_relative` onto `parked_flight_state.held_heading` (AI-overlay state) |
| U13 | every failure logged + one fixed spoken phrase | **built** — `ACTION_FILE_ERROR_LINE`; test: `test_crew_console_rules.py` |
| U14 | marks numbered, append-only | **deferred** — Stage 8 (marks group) |
| U15 | marks relative to known points/map features | **deferred** — Stage 8 |
| U16 | map-feature mark from world model, not sight | **deferred** — Stage 8 |
| U17 | rename reach: everything, but as a later stage | **deferred** — command-surface slice is Stage 1a (paused); full internal rename is Stage 10 |
| U18 | rule files edited in place in the repo checkout | **built** — `config/rules/flight.lua` is committed in `body-layer/config/rules/`; R5 (uncommitted edits block `/merge`) accepted as-is |

No decision this run's actual scope (Stages 0/1b/2) owed is missing or silently dropped. Everything
flagged "never named" either belongs to a later/paused stage the plan already names, or is built
and verifiable by code+test even though `implementation.md`'s prose doesn't cite the literal `U<n>`
token.

### Non-obvious behaviour

Explained via `plan.md`'s D1–D12, `config/rules/README.md` (the pattern-grammar reference for a
future rule author), and `body-layer/research/2026-11-17-lupa-sandbox.md` (every sandboxing gotcha,
probe-backed). `notes/lua-sandboxing-with-lupa.md` (new, this pass) captures the five most
transferable gotchas for future lupa work; `notes/voice-recognition-and-command-matching.md` gained
one bullet on the exact-literal-vs-fuzzy tradeoff.

## Security

`plans/speech-rules/security-stage0-2.md`: CHANGES REQUIRED → fix landed → `review-security-fix.md`:
NEEDS REVISION (one sub-finding) → fix landed → re-review: **APPROVED**. `lupa==2.8` dependency
checked clean (MIT, no GPL conflict; the one relevant CVE affects ≤2.6 and requires
`register_builtins=True`, which this sandbox never sets). Two non-blocking findings filed as
backlog, not required for this PASS: `[[BL-B125]]` (budget constants are ~1000× smaller in real VM
instructions than their names suggest), `[[BL-B126]]` (`PUT /rules` has no body-size/list-length
cap, pre-existing posture inherited by a new endpoint). Both confirmed present in
`body-layer/ROADMAP/BL-B125.md`/`BL-B126.md` and indexed in `body-layer-backlog.md`.

## Process signal: a recurring defect category, now at a fifth occurrence and a new boundary class

Security's Required Fix 1 here (`nan`/`inf` reaching `int()` unguarded) is the same shape as four
prior findings this project's own `dod` memory already tracks
(`.claude/agent-memory/dod/project_recurring_unguarded_nonfinite_float_before_conversion.md`): three
in one day in two body-layer modules (2026-10-13), a fourth on a new wire field at the aircraft-
layer↔body-layer LAN boundary (BL-B104, 2026-10-30). **This is the first occurrence at a non-LAN
boundary** — the Lua→Python action-dispatch boundary `rules/engine.py` builds for BL-17 — which
confirms the category is "any boundary where a value this codebase did not construct itself gets
`int()`/`float()`-converted," not "a wire-parsing habit." It also surfaced a new wrinkle this
category hadn't produced before: the correct remedy differed *by site* even within one fix (one
site's existing "caller checks rejection" contract made degrade-gracefully correct; the other site's
total absence of such a contract made the same remedy wrong, because it hid a rule-author bug behind
an unlogged "Unable."). I updated the DoD memory file with this fifth occurrence and the new
wrinkle — this is process debt, not code debt: the lesson from findings 1–4 did not reach whoever
designed BL-17's validation boundary, meaning it is still being caught at Security/DoD rather than
at Architect/Implementer time. Worth raising as a checklist item at Architect time for any plan
introducing a *new kind* of boundary (not just a new field on an existing one).

## Executed the unblock condition, not just read it

Stage 3's test-flight card (`plan.md`, card step 1) claims: "`--print-rules --audio-adapter-url …`
shows `turn_heading_relative` loaded and accepted, with nothing rejected." I ran this for real
rather than trusting the plan's prose:

```
$ cd body-layer && PYTHONPATH=src:../world-model/src .venv/bin/python -m body --print-rules
loaded 1 rule(s) from .../body-layer/config/rules:
  turn_heading_relative: turn <direction:left|right> <degrees:angle>
```

Then started a real `audio-adapter` process (`python -m audio_adapter --port 17795`, no mocks) and
re-ran against it:

```
$ PYTHONPATH=src:../world-model/src .venv/bin/python -m body --print-rules --audio-adapter-url http://127.0.0.1:17795
loaded 1 rule(s) from .../body-layer/config/rules:
  turn_heading_relative: turn <direction:left|right> <degrees:angle>
adapter accepted: ['turn_heading_relative']
```

Exactly as claimed — loaded, accepted, nothing rejected. Server stopped and the test port's process
confirmed gone afterward. Card steps 2–7 genuinely need a live DCS session with AI-overlay flying
and cannot be run from here — those stay **UNVERIFIED** until flown, not silently assumed.

## Acceptance Testing Plan

**Published card**: https://claude.ai/artifact/UaZdz1eas5M5DEME4bdZu4 (cockpit-readable; source
`docs/acceptance/2026-11-17-bl17-speech-rules-card.html`, sortie notes
`docs/acceptance/2026-11-17-bl17-speech-rules-sortie.md`). The plan below is the same content in
the format this report requires; the card is what to actually fly with.

**This feature's fixtures structurally cannot reach**: whether the ported `turn_heading_relative`
rule actually commands the aircraft correctly in flight (the differential test proves the rule
reproduces the deleted handler's *logic* bit-for-bit, not that `AiPilotWheelGoal`'s wire effect on
a real DCS AI-overlay autopilot feels right to fly behind); whether exact-literal matching holds up
against real STT noise rather than the three transcripts Reviewer hand-checked; whether the single
"Action file error." phrase is actually distinguishable in the cockpit from ordinary radio chatter;
and anything about Stage 1a's paused rename (out of scope, not tested at all here). A fixture pass
on this feature is not a flight pass — the gap is specifically "does it fly right," not "is the
code correct," and no amount of additional unit testing closes that gap.

### Acceptance Testing Plan: BL-17 Stages 0/1b/2 (speech rules, "turn left/right NN")

**Goal:** verify the Lua-rule-ported "turn left/right NN" command behaves identically to the
deleted static handler, in real AI-overlay flight, and that a rule-file edit/error is actually heard
correctly.

**Prerequisites**
- [x] Type-checked and importable: `cd body-layer && .venv/bin/mypy src` (confirmed above, this
  run)
- [ ] `audio-adapter` and `body-layer` both running against each other on the LAN as usual, with a
  live DCS session, AI-overlay (parked, mode 2) flight, player in the operator seat

**Test Cases** (from `plan.md`'s own Stage 3 card)
1. `--print-rules --audio-adapter-url …` before flying — rule loaded and accepted. **Already
   verified above, standalone, without DCS.**
2. "turn left two zero" → "20 left." and the aircraft turns ~20° left; "turn right four five" turns
   the other way.
3. Edit `flight.lua`'s readback text, **restart the mission** (not body-layer) — the new readback is
   heard on the next attempt.
4. Add a second rule under another id with the exact same pattern, restart the mission — one
   "Action file error." is heard, and "turn left two zero" is no longer acted on. Remove it,
   restart — the command works again.
5. Put a syntax error in `flight.lua`, restart the mission — the same single "Action file error."
   line, and the stderr banner names the file and line.

**Edge Cases to Probe**
- "Uh, turn left two zero" (filler word) — should still match (confirmed by Reviewer against the
  real matcher, not re-verified live here).
- "turn left thirty" (number word, not digit-by-digit) — should fall to "say again," the same as
  the deleted legacy handler, not silence and not a wrong turn.
- "the tanks are on the ridge" — must still fall through as ordinary speech, never a command.

**Pass Criteria**
The feature passes if test cases 2–5 all produce the expected result, the pilot cannot tell from the
seat that this command is now a rule rather than static code (barring the deliberately-narrowed
D8 matching tolerance), and no regression is audible in any other existing command.

**Acceptance testing: PENDING (live).** Per root `CLAUDE.md`'s auto-merge workflow, this does not
gate the merge. `#needs-flight` is on `body-layer/ROADMAP/BL-17.md`'s own new entry, naming `main`
as the branch to fly after this merges.
