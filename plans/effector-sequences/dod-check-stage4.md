# Definition of Done — BL-B90 Stage 4 ("readback by need")

**Scope**: Stage 4 only (option B — two readback classes: synchronous one-shot read per sequence
run, plus a small continuously-polled config-driven set). **Not in scope**: Stage 0 (DoD-passed
separately, `dod-check-stage0.md`), Stages 1-2 (DoD-passed separately, `dod-check-stage1-2.md`),
the switch-reference-values/mission-start batch (DoD-passed separately,
`dod-check-switch-values-mission-start.md`), Stage 3 (the re-flight card itself — not a prior DoD
subject, carried forward and now updated by this pass for Stage 4).

**Verdict scoped to**: tip `59722228` (`feature/effector-sequences-stage4`). This worktree's own
branch (`1d02e5e1`) had diverged from this tip in both directions — neither an ancestor of the
other — so per the dispatch instructions I checked out the named tip detached rather than
fast-forwarding (`git checkout --detach 59722228`). Tree was clean before and after. **If the
branch has moved past `59722228` since this report was written, this verdict is stale** — it is a
statement about that one commit, not about the branch.

## Acceptance boundary — what fixtures structurally cannot reach

Every check below ran against fakes, synthetic fixtures, a real Lua interpreter run outside DCS
(`luajit`), and a Lua syntax check (`luac -p`). **None of it touches a real DCS cockpit, a real
DCS export frame, or a real collector↔Export.lua TCP socket.** Four classes of defect are
structurally invisible to this pass:

1. **Whether `get_argument_value`/`performClickableAction` actually behave as assumed inside a
   real DCS frame** — in particular, whether a `read_args` reply issued in the *same* frame as a
   preceding write reflects the pre-write or post-write value (`plan.md` S4.10 names this
   explicitly as unverified against DCS internals; the design is deliberately insensitive to
   either answer via `assumed_writes`, but "insensitive in theory" and "confirmed insensitive in
   practice" are different claims).
2. **Whether the synchronous one-shot read actually completes inside the stated latency bound**
   on a real Windows box under real DCS frame-time variance — `ARG_READ_TIMEOUT_S = 0.25` and the
   8-outstanding-reads cap are measured against nothing live.
3. **Whether the reconnect/version-mismatch path actually recovers cleanly** when a real collector
   process is stopped and restarted against a real running DCS session (block 7 of the updated
   card) — the continuous feed's `WatchedArgsCache.clear()` on every `export_version` line is
   tested against a synthetic line, not a real reconnect handshake.
4. **Whether a real mission restart from the DCS menu actually re-triggers the version/mission
   boundary cleanly** (block 8) — `_check_for_new_mission`'s detection is tested against a
   synthetic `mission_start` event, not DCS's own `onSimulationStart` plumbing.

The updated re-flight card (blocks 7 and 8 specifically) exists to close exactly these gaps —
this is where this stage's real pass/fail lives, not in the green test suite below.

## Mechanical checks (run independently, this pass)

All commands run in this worktree at tip `59722228`, tools resolved from the main checkout's
`.venv`s (no `.venv` in this worktree) per the task's instruction, cwd inside each subproject.

**aircraft-layer:**
- `ruff format --check src tests` — pass (81 files already formatted)
- `ruff check src tests` — pass
- `cd aircraft-layer && .venv/bin/mypy src` — pass (28 source files)
- `PYTHONPATH=src pytest tests -q` — **608 passed** — matches `review-stage4.md`'s own re-review
  numbers exactly
- `luac -p dcs-export/Export.lua` — pass (parses clean)

**body-layer:**
- `ruff format --check src tests tools` — pass (184 files already formatted)
- `ruff check src tests tools` — pass
- `cd body-layer && .venv/bin/mypy src` — pass (74 source files)
- `.venv/bin/mypy tools` — pass (10 source files)
- `PYTHONPATH=src:../world-model/src pytest tests -q` — **2650 passed, 4 xfailed** — matches
  `review-stage4.md`'s own re-review numbers exactly
- `PYTHONPATH=src:../world-model/src .venv/bin/python -m logger --print-tuning | grep effector_engine` —
  both tunables resolve as documented:
  `EFFECTOR_CONDITION_READBACK_WAIT_S: 5.0 (derived)`, `EFFECTOR_SEQUENCE_STEP_DELAY_S: 1.0 (derived)`

No unhandled errors/panics on a data path: `effector_engine.advance`'s failed-read handling
resolves to `snapshot = {}` (everything unknown) after the timeout rather than raising or stalling
forever; `read_args`'s own validation (both aircraft-layer and body-layer sides) raises a typed
`AircraftLayerError`/is caught by the broker's existing error path, never an uncaught exception.
No debug `print`/leftover TODO/FIXME introduced by this stage — grepped the full
`c231efda..59722228` diff for `print(`/`TODO`/`FIXME`/bare `except:` in `src/`: every `print(` hit
is inside a Lua-snippet string handed to the `luajit` test harness (how those tests capture
output, e.g. `test_watched_args_lua.py`), not a debug leftover; no bare `except:`/silent swallow
introduced.

## Code quality / scope / invariants

- **Implementation matches `plan.md`'s revised Stage 4 spec** ("Stage 4 — readback by need (spec,
  revised 2026-10-24 — option B)", S4.1–S4.11), including the security plan review's required
  change (reply-value validation shared between the one-shot and continuous read paths,
  implemented on both the collector and body-layer sides per `security-stage4.md`). The plan's own
  text was corrected in place where the review found a stale filename reference (S4.5's
  `test_export_lua_constants_parity.py` claim, superseded to point at `TestAdmitRead`) — not
  silently, per the project's "supersede, don't delete" convention.
- **No unplanned scope added.** `EffectorDef.shape`/`absolute_write`, `PolledSet`/
  `load_polled_config`, and the two new API routes are all named in the plan's revised spec
  (S4.2–S4.4a) and the security plan review that preceded implementation — nothing here is a
  silent addition.
- **No invariants violated.** DCS stays authoritative (conditions/self-checks read observed
  readback, never commanded state); the one-shot/continuous readback stays bounded to a curated,
  registry-resolved arg set on both the Lua and Python sides (`parse_arg_list`'s shared bound,
  held equal across Lua/collector/body-layer by `test_export_lua_constants_parity.py`); no new
  dependency (stdlib only, confirmed by the security plan review's own `/extract-plan-deps` run);
  provenance/timestamp fields unaffected; module independence unaffected (aircraft-layer↔body-layer
  stays HTTP/JSON; the one-shot read is a synchronous HTTP call, not a new transport).
- **All new/modified files staged.** `git status --porcelain` at the dispatched tip showed a clean
  tree (confirmed at both the detached-checkout step and again here); the three files this pass
  itself touched (card, roadmap entry, notes) are staged below.

## Testing

- **Core logic is covered by tests, and verified meaningful by mutation, not just by this pass
  trusting the implementer's/reviewer's report.** The Reviewer independently mutated three things
  live against the actual checked-out source across its two passes: `_effective_value`'s `>=`→`>`
  (E4, the same-poll write-then-read race rule), `math.isfinite` dropped from
  `AircraftLayerClient.read_args` (the security required change), and `admit_read`'s per-frame cap
  removed (the Lua-side transport bound) — all three went red for the stated reason and were
  restored clean. The re-review additionally mutated the rewritten `test_logger.py` fake to
  discard `raw_args` unconditionally and confirmed three guidance-unit-lamp tests failed red for
  the stated reason, closing the loop on whether the rewritten call sites are load-bearing. I did
  not re-run these mutations myself this pass (the Reviewer's two independent passes already did,
  against the actual tip this verdict is scoped to) — re-running an already-independently-verified
  mutation a third time would not add information; I instead independently re-ran every mechanical
  check (format/lint/type/test, both subprojects, Lua syntax) rather than trusting the reviewer's
  reported counts, and they match exactly.
- **No existing tests broken.** Both subprojects' full suites are green at the counts the Reviewer
  itself last confirmed, with no regression.

## Documentation

- **Reviewer findings addressed, both required fixes, verified on re-review (`review-stage4.md`
  "Re-review (2026-10-24)"), APPROVED.** Fix 1 (the test-fake "rewrite" was a relocated adapter,
  not the call-site rewrite the plan's text and the user's own "rewrite" answer specified) —
  resolved: the adapter is gone, ~40 call sites drive the arg-keyed shape directly, confirmed by
  the reviewer's own grep and a live mutation. Fix 2 (`body-layer/CLAUDE.md`'s BL-B90 paragraph was
  stale) — resolved: read the current file directly as part of this pass (see the system prompt's
  attached copy) and confirmed it now describes the one-shot/continuous split, `assumed_writes`,
  `absolute_write`, and `polled.toml` in the detail the reviewer asked for.
- **Security plan review** (`security-stage4-plan.md`) — CHANGES REQUIRED → one required change
  (finiteness/type validation on the one-shot read response) → implemented before/during Stage 4,
  confirmed present on both sides by the security deep analysis.
- **Security deep analysis** (`security-stage4.md`) — **APPROVED**, no findings. Confirmed the one
  plan-review required change is implemented on both ends (collector and body-layer), and
  independently re-verified the broker lifecycle, per-frame/per-op bounds, and the dead-route
  removal rather than taking the design's own account on trust.
- **Performance review** (`performance-stage4.md`) — **APPROVED**. Two MONITOR-not-NOW findings
  (the synchronous one-shot read blocking an HTTP worker thread, bounded by the 8-outstanding cap
  and 0.25 s timeout; up to N sequential blocking reads in one `advance()` call if every shipped
  trigger fired simultaneously, which none does) — both already documented in the plan's own risk
  section (S4.10) with the correct order of magnitude, not newly discovered.
- **Non-obvious behaviour explained.** `body-layer/CLAUDE.md`'s BL-B90 paragraph (fixed by review
  fix 2 above) and `triggers.md`'s rendered preamble sentence both now state the one-shot/
  per-wait-row read rule directly. The acceptance card is updated for Stage 4 (this pass, see
  below) rather than left describing the superseded per-frame push.

## Security

- `security-stage4-plan.md` — CHANGES REQUIRED, resolved before implementation, folded into the
  spec.
- `security-stage4.md` — **APPROVED**, no findings.

## This pass's own changes

- `docs/acceptance/2026-10-23-bl-b90-sequences-reflight.md` — updated per `plan.md`'s S4.9: branch
  → `feature/effector-sequences-stage4`; Setup now re-copies `Export.lua` and restarts the
  collector (reversed from the Stages 1-2 card, which needed no redeploy), with the version-check
  log line and `watch_args installed` debug line both verified against the actual shipped
  source text (`aircraft-layer/src/collector/server.py:110`,
  `aircraft-layer/dcs-export/Export.lua:182,936`) rather than guessed; deleted the "Stage 4 is not
  built yet" bullet; revised blocks 2 ("read, all match" check, with the `read_args` debug-log
  line), 3 (promptness + the ~1s/~5s-lag-is-a-finding framing), and 5 (the decisive one-shot
  check framing); added blocks 7 (collector restart in flight, plus the "Observ off"/"Observ on"
  one-shot exercise through the restarted collector) and 8 (mission restart from the menu,
  re-running block 1's expectation); added the bisection note pointing at
  `feature/effector-sequences` (not `-stage4`) for isolating Stage 4 from Stages 1-2. Every
  command in the card carries its own directory. `$DCS_SAVED_GAMES_PATH` is used as a placeholder
  for the user's own DCS Saved Games folder (varies stable vs. Open Beta) rather than a guessed
  literal path. Commands that need a live Windows/DCS session are marked UNVERIFIED per the
  card's existing convention; the two commands I could verify from this worktree
  (`--print-tuning`'s output, and the exact log-line text/line numbers) were run/grepped and match
  exactly as written.
- `body-layer/ROADMAP/BL-B90.md` — added the Stage 4 done-entry (built/reviewed/DoD-passed,
  `#needs-flight`, on `feature/effector-sequences-stage4` pending the re-flight then merge) and
  the milestone-completion question: Stage 4's completion closes BL-B90's own stage list (this was
  explicitly the milestone's last stage, R7/R15 REVISED) — once flown and merged, BL-B90 itself is
  done, not just this batch; it sharpens `BL-B67`'s choice of `polled.toml` vs. read-at-need for
  962/the weapons bar, and establishes the one-shot-read seam `BL-B95`'s eventual `effector(name):
  get` would reuse. **Left the top-level checkbox at `[~]`** (in-progress) — this is a `#needs-flight`
  pending item, not a waived or deferred one, and stays `[~]` until a real sortie clears it.
- `notes/fixture-management-and-test-infrastructure.md` — two insights harvested
  (`/notes-harvest effector-sequences`'s automated pass only reaches the first `implementation.md`
  batch's "Notable Discoveries" section, so these two — from the Stage 4 batch further down the
  same file — were added by hand after checking neither duplicates an existing entry): (1)
  `git checkout --` is only a safe mutation-test restore for an already-staged/committed file,
  demonstrated live against `effector_engine.py` while body-layer's own Stage 4 changes were still
  entirely uncommitted; (2) a shared Lua-function-extraction test helper that tracks only
  `function`/`if`/`end` silently mis-slices a function containing a `for`/`while` loop, found live
  via a genuine Lua syntax error when first used to extract a function with a `for` loop, fixed in
  one copy, flagged (not retroactively fixed) in the other two copies that do not yet need it.

## Recurring-fix check (against `.claude/agent-memory/dod/MEMORY.md`)

Checked `review-stage4.md`'s two required fixes against this role's own prior "recurring fix"
pattern memories (`project_recurring_*.md`). Neither matches an existing 2+-occurrence category:

- Fix 1 (the implementer's narrower reading of the user's one-word "rewrite" decision, disclosed
  transparently in `implementation.md` and caught at Reviewer) resembles
  `project_fix_answers_review_wording_not_user_direction.md`'s shape in spirit (a correct-sounding
  narrower target standing in for the broader thing actually meant) but that memory is specifically
  about a **Reviewer's own fix instruction** naming a narrow proxy field that the implementer then
  faithfully implements, defect intact. Here the narrowing happened at **implementation** time,
  against a terse user decision word, and was caught and fixed in the same review round with no
  defect reaching a second round. Not the same mechanism — filed as a one-off here, not merged into
  that memory or promoted to a new recurring-pattern entry.
- Fix 2 (a module's `CLAUDE.md` paragraph going stale when a mechanism changes underneath it) does
  not match any existing recurring-category memory in this directory either. First occurrence
  under this exact shape for BL-B90's own module-map paragraph specifically (the sibling
  `aircraft-layer/CLAUDE.md` paragraph *was* correctly updated in the same diff, so this was not a
  systemic miss across both files — one file was simply missed). Not promoted to a new pattern
  memory on a single occurrence.

No new agent-memory file written this pass for either — both are single occurrences, and this
role's own convention (seen throughout the existing `project_recurring_*.md` files) is to promote
to a tracked pattern only at a 2nd occurrence, filing the first as a note in the DoD report itself
(this section) so a future second occurrence has something to match against.

## Milestone-completion question

Stage 4's completion closes BL-B90's own stage list — Stage 4 was explicitly named as this
milestone's **last** stage (R7, R15 REVISED) from the earliest explore pass. So once this stage is
flown and merged, BL-B90 itself is done, not just this batch — the next roadmap action for this
entry is the user's re-flight, not another implementation stage. It sharpens two downstream
things: `BL-B67`'s choice of `polled.toml` vs. read-at-need for 962/the weapons bar (that entry now
names the mechanism explicitly, so it does not have to rediscover it), and establishes the
one-shot-read seam (`POST /query/read_args`) that `BL-B95`'s eventual scripted `effector(name):get`
would reuse directly before any scripting work begins.

## Verdict

**PASSED** (mechanical/review/security/performance). Acceptance testing is outstanding —
`#needs-flight` — per the Acceptance Boundary section above; the updated card is the artifact that
closes it. No merge yet: the user decides when, after at least this card's flight, per this
milestone's existing posture (unchanged from Stage 3).
