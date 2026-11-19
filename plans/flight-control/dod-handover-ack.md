## Definition of Done: fix/handover-ack-seq

Checked at tip `666b4d98f59eb90d96fbe89fc2f48fad2de9b56c`, base local `main` @ `bba8d03b`. **This
verdict is scoped to that exact sha** — if the branch moves, re-run.

Reviewer: APPROVED WITH MINOR FIXES (`plans/flight-control/review-handover-ack.md`, re-review,
mutation-tested twice). The one documentation-only required fix from the re-review landed as
`ed2e2323` before this tip. Security: APPROVED, deep analysis (`plans/flight-control/
security-handover-ack.md`), no findings requiring action.

### Acceptance boundary — what these fixtures structurally cannot reach

Every test here runs against a real Lua interpreter and the real schema/parse path, which is
stronger than most of this project's fixture coverage. But no fixture can exercise: the actual
DCS wire path end to end (Export.lua → TCP → collector → LAN HTTP → body-layer, all five hops at
once, with real timing); whether the ack-timeout/release safety net behaves correctly under a
*genuinely* late or lost UDP datagram on the real network (the interleaving test re-review added
exercises the code path, not a real dropped packet); or whether a human pilot's actual cadence of
"take"/"turn"/"give back" lands inside or outside the 2 s ack window in practice. A fixture pass
here is not a flight pass — see the live card below.

### Code Quality

- **aircraft-layer** (`ruff format --check src tests`: 86 files; `ruff check src tests`: clean;
  `mypy src` from `aircraft-layer/`, strict: 28 files clean; full `pytest tests -q -p xdist -n
  auto`: **997 passed**, no skips (`luajit` available); `luac5.1 -p` on `core.lua`/
  `flight_control.lua`/`ai_pilot_wheel.lua`: all clean; GETGLOBAL sweep confirms `fmt_int_or_null`
  reads as a bare global in both consuming modules, same pattern as `fmt_num_or_null`, no
  collision). All re-run fresh in this pass, not taken from the review report.
- **body-layer** (`ruff format --check src tests`: 227 files; `ruff check src tests`: clean;
  `mypy src` from `body-layer/`, strict: 92 files clean; **full suite including `slow`**,
  `pytest tests -q -p xdist -n auto` (no `-m` filter — this is the one place the slow set runs):
  **3696 passed, 4 xfailed, 0 failed** in 151 s. The 4 xfailed are the same pre-existing/unrelated
  ones every prior pass in this plan reports. The count is higher than the review's `-m "not slow"`
  figure (3669) because this run includes the slow set; no failures anywhere).
- No debug output or TODO/FIXME introduced (`git diff bba8d03b..666b4d98` over `src`/`dcs-export`
  greps clean for print/console.log/debug-print/todo/fixme).
- No unhandled error paths found in the diff; both fixes were reviewed and security-cleared for
  exactly this (see Security's table — every new/changed branch in the state machine only ever
  moves belief toward releasing control, never toward granting an unintended take).

### Scope & Correctness

- Matches `plans/flight-control/debug.md`'s own two fix descriptions exactly; no scope beyond the
  two diagnosed defects (mode 1 Lua payload unchanged except the two formatter swaps; mode 2
  Python/`ai_pilot_wheel.py` genuinely untouched, confirmed by diff stat).
- No invariants violated: Security's table confirms no new dependency, no new dynamic-exec/
  shell-out/filesystem surface, no widened LAN-facing vocabulary, nothing crossing the
  code-owns-truth line (every fix narrows an existing gap, nothing invents new authority).
- All files staged — `git status --porcelain` was already clean at the branch tip before this
  pass started (everything through the security commit was already committed).
- **Accepted-items ledger**: `.claude/scripts/accepted-items-ledger.sh plans/flight-control` →
  *"decisions U1 U2 U3 not yet answered (no `**Answered` line) — nothing accepted to check."*
  This branch does not touch `plan.md` and introduces no new `U<n>`; the ledger's U1–U3 gap is
  pre-existing in the plan's own markup (the body text answers them in prose — "U1 answered
  2026-11-18" — without the exact `**Answered` marker the script looks for) and is unrelated to
  this bug-fix branch's scope. Not a gap this pass needs to close; flagged for whoever next
  touches `plans/flight-control/plan.md`'s decisions section, so the marker gets fixed rather than
  re-discovered.
- **No unblock-condition commands to execute.** Nothing in `debug.md`/the review/security reports
  defers work behind a stated command — the only deferred item is live acceptance itself
  (`#needs-flight`), which by its nature needs DCS/Windows and cannot be run from here.

### Testing

- Both fixes are backed by tests verified to fail on pre-fix code **by mutation, not by reading**
  — confirmed independently by the Debugger (who wrote them), the Reviewer (first pass and
  re-review, each reverting the touched files to the prior commit and re-running), and this pass
  did not need to repeat that mutation a fourth time since the prior two rounds already exercised
  it against two different intermediate commits.
- Core logic covered: the take-ack seq fix (`test_body_flight_control.py`), the ack-timeout
  system-release field and its same-poll-clobber fix (`test_flight_control.py`,
  `test_body_flight_control.py`), the `release_controls` widening (`test_flight_control.py`), and
  the Lua int/float wire fix run through the real schema parser from a real Lua-produced string
  (`test_core_lua.py`, `test_flight_control_lua.py`, `test_ai_pilot_wheel_lua.py`).
- No existing tests broken — full suites both subprojects, 0 failures, matches every prior pass's
  counts plus the slow set.

### Documentation

- Reviewer's required fix (same-poll clobber) and its own follow-up documentation-only required
  fix (the "single most-recent-command slot" comment correcting to the real UDP-reordering risk)
  are both addressed and re-verified (re-review's own mutation test, plus `ed2e2323`'s diff read
  directly in this pass — the docstring now names the actual mechanism, `commands.lua`'s drain-all
  loop, not a slot that doesn't exist).
- Non-obvious behaviour: harvested to `notes/lua-export-module-architecture.md` (the blanket
  `%.5f` formatter silently dropping `int`-strict wire lines) and `notes/debugging-and-root-cause-
  diagnosis.md` (a test that builds two counters equal "by hand" verifies the comparison, not that
  production keeps them in sync).

### Security

`plans/flight-control/security-handover-ack.md` — **APPROVED**. No dependency change, no new
dynamic-exec/shell-out/filesystem surface, no widened vocabulary. The one LAN-facing input this
diff's logic depends on (`lua_mode`) can, if garbled, only push belief toward releasing control —
the fail-safe direction already standard in this module.

### Recurring-fix pattern (process signal)

The second bug here is the **sixth** occurrence of this project's own recurring category — a
numeric value crossing a boundary this codebase did not fully construct, with no finiteness/type
validation at the crossing (`.claude/agent-memory/dod/
project_recurring_unguarded_nonfinite_float_before_conversion.md`, updated this pass). Findings
1–5 were all on the **parse** side (a value arriving); this is the first on the **encode** side (a
value leaving) — `core.lua`'s blanket `%.5f` formatter had no per-field awareness of which schema
fields on the Python side are declared strictly `int`. The effect was worse than any prior
instance in this category: not a crash, not a corrupted value, but every `flight_control`
telemetry line dropped silently for a full day, surfacing as two *different*-looking bugs (a
take-ack mismatch, a recovery gap) before anyone traced it back to the wire format. This is now
clearly process debt, not isolated-bug debt: the same lesson has been learned five times before at
Security/Debugger/DoD and still didn't reach the code that introduced this instance a day after
finding 5 landed. **Recommendation, restated from the updated memory**: a mechanical check (every
`fmt_*` call site in the Lua export modules cross-referenced against the schema field it feeds,
run whenever either side changes) would catch this before a sortie does, and is cheap enough to
be worth adding at Architect/Implementer time rather than relying on Security/DoD to catch it a
seventh time.

### Milestone completion note

**This does change something about the last two merges, though not their ordering.** The mode-2
P3+P4 batch (`fefe8cea`, 2026-11-19) and the mode-1 break/rotor batch (`a9b8a7c1`, 2026-11-19) both
merged *after* the telemetry-dropping bug (`307d6a81`, 2026-11-18) was already live, and both are
still `#needs-flight`. Any attempt to fly either of those cards before this fix would have hit
"unable, not flying" from this same root cause, independent of whether either batch's own logic is
correct — so **their own correctness is still genuinely unverified by flight**, not merely
"pending." This doesn't invalidate anything about their design or move the next milestone (M3/M4
terrain floor/SAU are unaffected), but the next sortie should treat all three `#needs-flight`
entries (this fix's own card, P3+P4, and the mode-1 break batch) as one batch — the test card
written this pass says so explicitly and asks the user to try a command or two from the other two
cards on the same flight.

### Verdict

**PASSED**, tip `666b4d98f59eb90d96fbe89fc2f48fad2de9b56c`.

### Acceptance testing

**PENDING (live)** — needs DCS on Windows. Card published:
https://claude.ai/artifact/Y3SxBz7Bn8LJDZSyiByLzb — source at
`docs/acceptance/2026-11-20-bl16-handover-ack-sortie.md`. **Branch to fly: `main`, after merge.**
Redeploy required: the whole `aircraft-layer/dcs-export/Petrobrain/` folder (three files actually
changed: `core.lua`, `flight_control.lua`, `ai_pilot_wheel.lua`). Tagged `#needs-flight` on
`body-layer/ROADMAP/BL-16.md`'s new entry for this fix, below.

Per workflow (user direction 2026-10-26): DoD PASSED is the merge trigger; this does not wait on
the live flight.
