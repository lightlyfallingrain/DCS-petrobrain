# Definition of Done: AC-B12 (Export.lua module split, AC-B13 folded in)

**Verdict scoped to tip `590eebb1fb6cff4170c938e7e8e73d4066b15a38`** on
`feature/ac-b12-export-modules` — this worktree was fast-forwarded from this DoD run's own prior
`c7a5c8f0` (a strict ancestor, clean tree) to that exact tip before any check below ran. If the
branch moves after this report, the verdict is stale.

## Worktree addressing

HEAD (`c7a5c8f0`) was a strict ancestor of the stated tip with a clean tree; fast-forwarded via
`git merge --ff-only origin/feature/ac-b12-export-modules`. No snapshot fallback needed.

## Code Quality

**Subproject touched: `aircraft-layer` only**, confirmed by diffing the fork point against
`origin/main` (`git diff --name-only $(git merge-base HEAD origin/main) HEAD`) — every changed
path is under `aircraft-layer/`, `plans/ac-b12-export-modules/`, or `.claude/agent-memory/`.
`body-layer`/`world-model`/`brain-layer`/`audio-adapter` are untouched; their own commands were
not run, per the diff-derived scope this role is required to use rather than a memorized list.

Ran fresh (no `.venv` existed in this worktree; created one, installed `ruff`/`mypy`/`pytest`):

```
luac5.1 -p  — Export.lua + all 8 Petrobrain/*.lua files, run individually: all pass
  (core.lua, telemetry.lua, petrovich.lua, sight.lua, ai_pilot_wheel.lua, effectors.lua,
   ptt_ics.lua, commands.lua)

cd aircraft-layer && .venv/bin/ruff format --check src tests
  80 files already formatted

cd aircraft-layer && .venv/bin/ruff check src tests
  All checks passed!

cd aircraft-layer && .venv/bin/mypy src
  Success: no issues found in 27 source files

cd aircraft-layer && .venv/bin/pytest tests -q
  795 passed in 73.75s

cd aircraft-layer && .venv/bin/pytest tests -v | grep -E " (SKIPPED|FAILED|ERROR)\b"
  (no matches — the 139 Lua-interpreter-backed tests across the 7 affected files, plus the new
   test_commands_lua.py's 3, ran for real, not skipped for lack of an interpreter)

cd aircraft-layer && .venv/bin/pytest tests/test_dcs_export_lua_syntax.py \
  tests/test_dcs_export_lua_local_order.py -v
  305 passed — confirms the widened **/*.lua glob (U2) covers all 8 new module files plus the
  loader, and the cross-module local/global leak check passes for every one of them.

cd aircraft-layer && .venv/bin/pytest tests/test_ai_pilot_wheel_lua.py -k TestOnStop -v
  2 passed — AC-B13's own test, extracting the real on_stop.
```

All figures match `review.md`'s re-review record exactly (795 passed, same per-module local
counts). **No new .venv was needed on top of what already existed** — this worktree had none at
all before this run, so every check above is a from-scratch reproduction, not a cached result.

**No debug output, no TODO/FIXME left by this feature** — checked the diff against the pre-split
file directly (`git diff <fork-point> HEAD -- aircraft-layer/dcs-export aircraft-layer/src | grep
-E '^\+.*(TODO|FIXME|XXX|print\(|console\.log)'`): no matches outside test files.

**No unhandled errors/panics in data paths.** Every `pcall` usage in the diff is a relocation of
an existing guard (confirmed against the original file by Reviewer/Security already; independently
spot-checked here) — the loader's own `pcall(dofile, ...)` around each module load is new code,
but it is the one place this plan's own design explicitly wants a caught, logged, non-fatal
failure (a missing/corrupt module degrades that one feature silently rather than crashing the
whole script — named as a known risk in `plan.md`, re-examined by Security and judged acceptable
given the delete-then-copy deploy procedure and the version check).

## Scope & Correctness

- **Matches the plan.** Part 1 (the module split) is built exactly as the plan's module cut and
  load mechanism describe; AC-B13 (the one approved behaviour exception) lands in
  `ai_pilot_wheel.lua`'s new `on_stop()`, as specified. **Part 2 ("read only what is needed") is
  explicitly not built** — stated as out of scope in `plan.md`'s own Goal and Order sections, and
  `implementation.md`'s "Could Not Do / Left Alone" confirms it was not silently started. No
  unplanned scope: the one departure from the plan's own illustrative snippet (telemetry's send
  order) is a *correction* of the plan's own disclaimed-as-illustrative example, not an addition,
  and is traced in `review.md` and the new `notes/planning-and-process-lessons.md` entry below.
- **No CLAUDE.md invariants violated.** Checked directly, not taken on Security's word alone:
  `grep -rc AI_WHEEL_RIGHT aircraft-layer/dcs-export/*.lua aircraft-layer/dcs-export/Petrobrain/*.lua`
  → `0` everywhere (the E-P6 invariant). The ASP-17V invariant (Petrovich never touches device 2)
  is untouched — this split relocates code, it does not add a new consumer of any device. The
  single-player-only scope is untouched (nothing here is multiplayer-adjacent).
- **All new files staged.** Confirmed by `git status --porcelain` after this report is committed
  (below) — every new `Petrobrain/*.lua` file, the new test file, and this plan's own documents
  were already committed on the branch fast-forwarded into this worktree; nothing new needs
  staging beyond this DoD's own output files.

## Testing

- Core logic (the module split's load mechanism, the state-relocation, AC-B13's fix) is covered by
  the existing Lua-interpreter-backed suite (139 tests across 7 files, re-pathed not rewritten) plus
  two new suites: `test_commands_lua.py` (3 tests, the dispatch-guard fix, one of them a genuine
  counterfactual reproducing the real pre-fix Lua crash under `luajit`) and
  `test_ai_pilot_wheel_lua.py::TestOnStop` (2 tests, AC-B13's own fix, counterfactual-verified in
  `implementation.md` by removing the release call and confirming the test fails for the stated
  reason, then restored by checksum).
- **Meaningful, not decorative** — Reviewer independently re-ran the pre-fix counterfactual under
  `luajit` and got the exact Lua error (`attempt to index global 'effectors' (a nil value)`)
  confirming the new test's failure mode is real, not an artifact of the test harness.
- **No existing tests broken** — 795 passed, 0 skipped, 0 failed, matching the pre-fix-round
  baseline of 792 plus the 3 new `test_commands_lua.py` tests.

## Documentation

**Reviewer findings addressed.** The one Required Fix (commands.lua's dispatch table coupling
every op's fate to three modules' load success, contradicting the plan's own per-module isolation
goal) was fixed and re-reviewed APPROVED. Two Optional Refinements (the version-bump question,
resolved by the main-loop's own decision to bump; the "Comments pruned" log-accuracy note) are
both closed, confirmed in the re-review.

**Accepted-items ledger.** Ran `.claude/scripts/accepted-items-ledger.sh plans/ac-b12-export-modules`:

```
ledger plans/ac-b12-export-modules: decisions U1 U2 not yet answered (no **Answered line) --
nothing accepted to check.
```

**This is a false negative, by hand-correction** — a third variant of the already-known
`^\*\*Answered`-anchoring gap (`.claude/agent-memory/dod/
feedback_accepted_items_ledger_misses_indented_answered_line.md` documents the indented-line
case; this plan's "Decisions Requiring User Input — answered 2026-11-16" section uses a different
format again: a heading stating the answer date, a verbatim user quote block, then `- **U1 →
...`/`- **U2 → ...` resolution bullets, with no `**Answered` string anywhere). Checked both by
eye:

- **U1** (deployment-staleness check: version string alone, no per-module stamp) — answered, and
  built: `WORKFLOW.md`'s deploy step describes copying the loader and the whole `Scripts\
  Petrobrain\` folder together; no per-module version constant exists anywhere in the 8 module
  files (confirmed by grep); `EXPORT_SCRIPT_VERSION`/`EXPECTED_EXPORT_VERSION` are the only version
  strings in the diff.
- **U2** (subfolder, not flat) — answered, and built: all 8 modules live under
  `aircraft-layer/dcs-export/Petrobrain/`; `test_dcs_export_lua_syntax.py`/
  `test_dcs_export_lua_local_order.py`'s globs were widened to `**/*.lua`, confirmed passing above
  (305 passed, including every `Petrobrain/*.lua` file by name).

Both decisions answered and built — nothing accepted and left unmentioned.

**Security.** `plans/ac-b12-export-modules/security.md` exists, verdict **APPROVED**. Its one
Risk Communication item (bare-global helper names now live in the Export Lua environment for the
session's life) was presented to the user with options (A)/(B)/(C)/(D); **the main loop decided
option (A) — no change, nothing filed**, on the stated grounds that it is low/low and
self-inflicted only (requires the user's own future action — chaining a second Export-side add-on
into the same Lua state — to become reachable at all). This is a closed, permanent acceptance, not
a deferral with an unblock condition, so there is no command to execute against it (unlike the
`feature/doc-conventions-audio-adapter` case this role's own memory warns about, where a deferral's
stated unblock command had never been run) — option (A) has no clearing condition by design.

**Non-obvious behaviour explained.** `implementation.md`'s "Decisions Made" covers the
cross-module global/local channel design and why it takes the shape it does (the test harness's
own extraction regex, not an arbitrary style choice) — harvested into `notes/` below rather than
left only in a plan file.

## Mechanical proof the deploy-staleness check actually works

Not asked for by the mechanical checklist, but this is the one piece of the live acceptance that
*can* be run off-Windows: started the real collector (`python -m collector`, alternate ports in
this worktree) and sent it the exact wire line `Export.lua` sends on connect.

```
$ python3 -c "import socket, json; s = socket.create_connection(('127.0.0.1', 17790)); \
  s.sendall((json.dumps({'export_version': '2026-11-16b'}) + '\n').encode())"
INFO Export.lua wire-format version 2026-11-16b (matches)

$ python3 -c "... json.dumps({'export_version': '2026-11-16'}) ..."   # the pre-bump string
WARNING Export.lua VERSION MISMATCH: deployed copy reports 2026-11-16, this collector expects
2026-11-16b. ...

$ python3 -c "import urllib.request; print(urllib.request.urlopen(
  'http://127.0.0.1:17791/telemetry/latest', timeout=3).read())"
b'null'
```

Both sides of U1's "version string is the whole check" actually fire against the real,
just-merged collector code, not just read as plausible.

## Acceptance boundary — what this DoD cannot reach

**Mechanical/fixture checks cannot tell "the split works" from "the split works on this dev
machine with no DCS process on the other end of the socket."** Specifically, nothing above
touches:

- Whether the real `dofile` chain actually loads in DCS's embedded Lua 5.1 interpreter (this
  worktree's `luac5.1` only parses — it never executes the chain the way `Export.lua`'s own
  `load_module` does at mission start).
- Whether a real multi-file Windows deploy (copy `Export.lua` **and** the `Petrobrain\` folder)
  actually lands every file where `MOD_DIR` (`lfs.writedir() .. "Scripts\\Petrobrain\\"`) expects
  it — this is the plan's own named live risk, and no amount of unit testing retires it.
- Whether `dcs.log` stays clean across a real session — the pcall-guard design means a deploy
  mistake degrades a feed *silently*; only a real log read catches that, not a passing test suite.
- **The prize: AC-B13's live cross-check.** The Lua unit test proves `on_stop()` releases a press
  and clears the takeover fields when called directly with a mocked `GetDevice`. It does not prove
  DCS's real `LuaExportStop` callback actually fires `on_stop()` at the right moment during a real
  mid-correction-hold mission restart — that is a different claim, and it is this plan's whole
  reason for existing as a security finding rather than a closed non-issue.

This is the same class of gap this role's own brief names for the F10 vocabulary and the
`callout-observability` fix: code doing exactly what it says, against inputs no fixture can
produce. Card published, naming all four of the above explicitly as live-only checks:
https://claude.ai/artifact/5Q1za4baC6VNYaRoScNuyc
(`docs/acceptance/2026-11-16-ac-b12-export-modules-sortie.md`).

## Recurring-fix pattern check

`python3 .claude/scripts/memory-search.py -r reviewer failure isolation gap one module` returns
only this feature's own reviewer memory
(`project_ac_b12_export_lua_module_split_review.md`) — the dispatch-table/eager-table-construction
failure-isolation gap is a **first occurrence** in this project's recorded memory, not a recurring
category. No pattern memory update warranted; not a process-debt signal to raise at an earlier
role this time.

## Overall Verdict: PASSED

Reviewer APPROVED (round 2). Performance Reviewer APPROVED — MONITOR. Security APPROVED. All
mechanical checks pass. Both accepted decisions (U1/U2) answered and built. No scope drift. Tests
meaningful and green. Acceptance is **PENDING (live)** per the process below — DoD passing is the
merge trigger; live behaviour is tagged `#needs-flight` on `aircraft-layer/ROADMAP/AC-B12.md` and
`AC-B13.md`, not held against the merge.
