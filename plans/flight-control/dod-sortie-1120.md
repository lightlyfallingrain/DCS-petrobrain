# Definition of Done: BL-16 sortie-1120 bug-fix batch

**Verdict: PASSED.**

Scoped to `fix/bl16-sortie-1120`, tip `bf66cc80fcb7bb0c00738c9c34166fb77221d01d`, base
`98174b54`. This is the gate for the whole batch — most of it was already merged to `main` ahead
of Reviewer/Performance/Security for flight testing (`bbfd6ede`, `a8b21de0`, `3073f133`,
`c2f0fc00`, `276349fc`, `9bab5b48`), per the user's standing direction that live acceptance does
not gate a merge. **If the branch moves past `bf66cc80`, this verdict is stale** — it is a
statement about that one commit, not the branch.

## Code Quality

Subprojects touched, read from the diff (`git diff --name-only 98174b54..bf66cc80`), not from
memory: `aircraft-layer` and `body-layer`.

**aircraft-layer** (`/Users/sg/Code/DCS-petrobrain/aircraft-layer/.venv`):
- `ruff format --check src tests` — 86 files already formatted.
- `ruff check src tests` — all checks passed.
- `mypy src` (from `aircraft-layer/`) — success, 28 source files.
- `luac5.1 -p` on all five touched Lua files (`Export.lua`, `ai_pilot_wheel.lua`, `commands.lua`,
  `core.lua`, `flight_control.lua`) — all pass.
- `luac5.1 -l -p | grep GETGLOBAL` sweep on the same five files — every global read is genuine
  Lua stdlib/DCS API or an already-intentional cross-module table (`ai_pilot_wheel`,
  `flight_control`, `client`, `debug_log`, `safe_call`, `fmt_*_or_null`, etc.). No stray global
  from this batch's own locals.
- `pytest tests -q -p xdist -n auto` — **1046 passed**.

**body-layer** (`/Users/sg/Code/DCS-petrobrain/body-layer/.venv`, full suite via `PYTHONPATH=src:
../world-model/src`):
- `ruff format --check src tests` — 228 files already formatted.
- `ruff check src tests` — all checks passed.
- `mypy src` (from `body-layer/`) — success, 92 source files.
- **Full suite including `slow`**, in parallel: `pytest tests -q -p xdist -n auto` (no `-m`
  filter) — **3729 passed, 4 xfailed, 0 failed** (151.3s). The 4 xfails are pre-existing, unrelated
  to this batch.

All figures match `plans/flight-control/review-sortie-1120.md`'s own independently-reproduced
numbers exactly — this DoD pass re-ran every check itself rather than trusting the review's
account of it.

**Tested tree sha: `bf66cc80fcb7bb0c00738c9c34166fb77221d01d`.** The merge should skip its own
full run if its tree matches this.

No debug output or TODOs introduced by this batch (confirmed by Reviewer's own full read, re-spot-
checked here against the diff). No unhandled errors/panics in a data path — the reset path and
the `/command/reset` handler both fail loud or degrade to the project's existing accepted posture
(see Security below), never silently swallow.

## Scope & Correctness

`plans/flight-control/plan.md` carries this batch's decisions as prose (Decisions 13, 22–32,
F-P7), not `U<n>` ids — `accepted-items-ledger.sh plans/flight-control` confirms the only `U<n>`
placeholders in the file (`U1`/`U2`/`U3`) are unrelated to this section and unanswered elsewhere
in the plan; nothing to ledger for this batch. Reviewer read every relevant decision by hand
against the implementation and found each one either delivered as decided or correctly left
untouched as out of scope — re-confirmed here by reading `review-sortie-1120.md`'s own
item-by-item account against the diff, not re-deriving it from scratch.

No unplanned scope added. No `CLAUDE.md` invariant violated — in particular, the "no LAN message
ever carries a raw axis value" invariant holds for the new `collective` write (confirmed: the
written value is `law_clamp(state.u_c, -1.0, 1.0)`, derived locally, never a wire-supplied
number), and "neither handover token ever asks confirm" is unaffected by this batch (it touches
goal/break arbitration and the reset path, not the handover tokens).

All new files staged: confirmed via `git status --porcelain` at session start (empty — this
session branched directly from the tip commit) and will be re-confirmed before this report's own
commit.

## Testing

Core logic covered by tests for every fix in this batch — Reviewer independently confirmed items
1, 2, 5, 7 have explicit **mutation testing**: the fix was reverted (body-layer Python side, Lua
side, or both), the new test confirmed red for the stated reason, then restored byte-for-byte
(`shasum`-verified). This is a materially higher bar than this role's own checklist requires by
default. No existing test was broken — the full suites above are green, matching base-branch
counts plus this batch's additions.

## Documentation

**Reviewer findings**: `review-sortie-1120.md` — **APPROVED, no required fixes.** Three optional
watch items flagged (0.5-tolerance integer-display assumption, dummy rotor-RPM source as a known
Decision-28 stand-in, overlay staleness as an unchanged pre-existing property) — all already
honestly flagged as unverified assumptions in the code's own comments; none blocks merge.

**Accepted-items ledger**: nothing to check (see Scope & Correctness above — no `U<n>` ids in
this section).

**Non-obvious behaviour**: explained via code structure and comments (Reviewer's own read
confirms no durable comment was removed, only superseded reasoning updated in place) plus two new
`notes/` entries from this DoD pass (see Knowledge Harvest below).

## Security

`plans/flight-control/security-sortie-1120.md` exists and is **APPROVED.** No dependency change.
The new `/command/reset` op was traced end-to-end (shape validation, dispatch, what `reset()`
actually does, who can trigger it, confusability with a stale/bogus reset) — no privilege-
escalation or state-confusion path found. Two low-risk items filed to the backlog rather than left
in prose: `[[AC-B23]]` (new — `/command/reset`'s lack of a sender check, not blocking, consistent
with this project's accepted LAN-only/no-auth posture) and `[[AC-B11]]` (corrected — the new
occurrence of the unbounded-`Content-Length` pattern, count now 12). Neither blocks merge.

## Found and fixed at this DoD pass

The already-merged slip-ball calibration card
(`docs/acceptance/2026-11-20-slip-ball-calibration-card.md`) had two real defects, found by
actually trying to run its one command rather than reading it:

1. **Wrong collector IP.** The card hardcoded `192.168.1.50`. Every other recent live sample in
   this repo (`docs/acceptance/2026-11-16-bl16-batch-a-feedback.md`,
   `docs/acceptance/2026-11-18-apw-status-json-quotes-sortie.md`) uses `OMEN=192.168.0.85` — a
   different subnet entirely. Fixed by replacing the hardcoded address with the project's own
   `<collector-host>` placeholder convention, with a note pointing at the observed OMEN address.
2. **A stray leading `!`** on the readout's `while` loop, with no enclosing `if` to give it a
   purpose — negating a `while true` loop's own exit status does nothing useful here, and `!`
   immediately followed by a word is the exact shape that triggers history expansion in an
   interactive bash/zsh session (enabled by default for interactive shells), which would answer
   with "event not found" rather than running the loop. No precedent for this idiom anywhere else
   in the repo's own docs. Removed.

Both fixes are staged in this DoD pass's commit (same file, no new commit needed on the feature
branch itself since the card was authored on this branch).

**What I verified directly, and what I could not**: the embedded Python one-liner
(`json.load(sys.stdin)` against a synthetic `fc_slip_ball_*` payload) was run and produces the
expected output. The `GET /flight_control/latest` field names (`fc_slip_ball_pilot_raw`,
`fc_slip_ball_operator_raw`, `fc_slip_ball_lo_api`) were checked against
`aircraft-layer/src/schema/flight_control.py`'s `to_api_dict` and the endpoint wiring in
`aircraft-layer/src/api/server.py` — both confirmed to exist and match. **Reaching the actual
Windows box over the LAN is UNVERIFIED from here** — this role has no DCS/Windows access; that is
why the card still needs a live flight.

## Acceptance boundary — what this batch's fixtures structurally cannot reach

Every fix in this batch was caught by a human flying and noticing something wrong — none of it
was found by a fixture or a unit test first. The toy-plant/mutation tests verify that the *law*
this batch wrote does what its own spec says; they cannot verify that the spec is the right thing
to fly, because that depends on how imprecise real DCS flight actually is, how ED's own AI
responds to a mid-break goal in practice, and what a human pilot's hands actually do under load —
none of which a toy-plant model represents. Concretely: the mutation tests prove the latest-wins
goal/break arbitration (block 4) fires on the *exact* sequencing the test drives; they cannot show
whether a real break's own timing window ever makes "during" and "after" genuinely
indistinguishable in the cockpit. The pedal-sign and collective-interaction fixes (blocks 6–7) are
explicitly built on **unmeasured guesses** pending the slip-ball flight — no test anywhere in
either suite can validate a sign nobody has measured yet. And the crash-causing unpark-mid-turn
bug (block 8) was found by a human crashing an aircraft; the fix's correctness as a *feel*, not
just as a value transfer, is exactly the kind of thing no fixture can judge.

## Acceptance testing

**PENDING (live).** DCS/a live sortie is required and this role has no access to perform it.

Published card: **https://claude.ai/artifact/YFcGHRP9wzF1NKakYgidYF**
(`docs/acceptance/2026-11-20-bl16-sortie-fixes-card.md`) — ten blocks, one per fix, with a
pre-flight redeploy/version-mismatch gate first and block 8 (the crash-causing unpark-mid-turn fix)
marked as the prize. Points to the separate slip-ball calibration card
(`docs/acceptance/2026-11-20-slip-ball-calibration-card.md`, fixed in this pass as described
above) and names the mission-wide running command number as still-open `[[BL-16]]` work, not in
this batch.

`#needs-flight` recorded on `body-layer/ROADMAP/BL-16.md`'s own new entry for this batch. Per this
role's own rule, I ran the one thing that could be run without DCS from this pass's own findings —
there is no stated "run X to clear this" unblock condition anywhere in this batch's debug/review/
security docs beyond the live flight itself, so there is nothing further to execute here.

## Milestone-completion note

Does this batch's completion change what the next milestone should be, or invalidate a
downstream assumption? No change to M3/M4's ordering. It does narrow the existing unflown-
correctness caveat on the two prior `#needs-flight` batches (mode-2 P3+P4, mode-1 break/rotor)
one step further: both still need this batch's fixes (specifically block 8's unpark-mid-turn seed
and block 4's latest-wins goal fix) confirmed together on one flight before their own logic can be
called verified, since several of their own test scenarios run straight into the bugs this batch
fixes.

## Knowledge harvest

Ran `/notes-harvest flight-control`'s own extraction script by hand (the committed skill script's
`awk` patterns only pick up the *first* matching section per file across this plan's entire
multi-month history, not just this batch's 2026-11-20 sections, so the raw output was noisy). Read
`implementation.md`'s 2026-11-20 "Notable Discoveries" sections directly instead. Two
non-duplicate, non-obvious insights added:

- `notes/feedback-control-law-design.md` — a rate term and a position-overlay term look
  interchangeable until actually run forward (the turn-coordination integrator-saturation catch).
- `notes/debugging-and-root-cause-diagnosis.md` — a duck-typed test fake missing one method on an
  unconditionally-called path silently kills a background thread rather than failing a test
  outright; look for climbing CPU time, not an idle hang.

Checked `review-sortie-1120.md`'s required fixes against prior recurring-fix patterns
(`memory-search.py`) — **moot this batch**: Reviewer, Performance Reviewer, and Security all
APPROVED with zero required fixes, so there is nothing to compare against a pattern. No
recurring-fix process signal to report.

## Files touched by this DoD pass

- `docs/acceptance/2026-11-20-slip-ball-calibration-card.md` (IP + stray `!` fix)
- `docs/acceptance/2026-11-20-bl16-sortie-fixes-card.md` (new, source for the published card)
- `docs/acceptance/2026-11-20-bl16-sortie-fixes-card.html` (new, published artifact source)
- `body-layer/ROADMAP/BL-16.md` (new entry for this batch, `#needs-flight`)
- `notes/feedback-control-law-design.md`, `notes/debugging-and-root-cause-diagnosis.md`
- `plans/flight-control/dod-sortie-1120.md` (this report)
