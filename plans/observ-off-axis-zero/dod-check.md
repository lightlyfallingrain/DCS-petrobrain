# DoD Check: observ-off-axis-zero

**Scoped to tip `8a46e30aa8ee47284aad8b616aecd143cd54e608`** (fast-forwarded cleanly from this
worktree's `c08c06d9`, which was a strict ancestor; tree clean throughout). If `fix/observ-off-
axis-zero` moves after this sha, this verdict no longer covers it.

## Code Quality

| Check | Result |
|---|---|
| `ruff format --check aircraft-layer/src aircraft-layer/tests` | PASS — 81 files already formatted |
| `ruff check aircraft-layer/src aircraft-layer/tests` | PASS — all checks passed |
| `cd aircraft-layer && mypy src` | PASS — 28 source files, no issues |
| `PYTHONPATH=aircraft-layer/src pytest aircraft-layer/tests -q` | PASS — 619 passed in 76.3s |
| `luac5.1 -p aircraft-layer/dcs-export/Export.lua` | PASS — syntax OK (real Lua 5.1.5, this worktree has it — unlike Reviewer's, see `.claude/agent-memory/reviewer/reference_luac51_unavailable_in_worktree.md`) |
| Own-helper-leak scan (`luac5.1 -l -p ... \| grep GETGLOBAL`) | PASS — every global read is genuine DCS API/Lua stdlib (`GetDevice`, `LoGet*`, `list_indication`, `io`/`lfs`/`os`/`math`/`pairs`/`pcall`/`string`/`table`/`tonumber`/`tostring`/`type`/`require`, plus the pre-existing `DUMPED_*` dump globals); `sight_observ_transition` is not among them |
| Unhandled errors/panics in data paths | None — the new call site inherits `sight_point_quiet`'s existing `pcall` guard; no new unguarded `SetCommand`/`GetDevice` call |
| Debug output left in committed code | None found (`git diff` scanned for `print(`/`console.log`/debugger; the one `print(` hit is inside a test's generated-Lua-harness string literal, not production output) |
| TODO/FIXME comments introduced | None found |

body-layer is untouched by this diff (only `aircraft-layer/`, `docs/`, `plans/`, and one
`.claude/agent-memory/reviewer/` file) — per the diff-driven subproject rule, body-layer's own
checks are not owed here.

## Scope & Correctness

- This is a bug fix (Debugger → Reviewer → Security → DoD), not an Architect-planned feature, so
  there is no `plan.md` to check implementation against — `plans/observ-off-axis-zero/debug.md`
  is the specification record, and matches `docs/acceptance/2026-10-24-sortie-feedback.md` F1's
  verbatim user direction exactly (one-time zero write on the on→off edge; nothing on any other
  off frame; writes only while OBSERV is on).
- No unplanned scope: one file changed for the fix (`Export.lua`, +56/-3 per `review.md`'s own
  count), one new test file, no wire/schema change (`EXPORT_SCRIPT_VERSION` correctly left
  unbumped).
- No invariants violated: this is aircraft-layer Lua servo logic, outside every body-layer
  invariant (`Percept`/no-omniscience boundary, import direction, etc.) and outside the DCS-
  install-is-read-only invariant (a Hook/Export script deploy, not an install-tree edit).
- All new files staged: confirmed via `git status --porcelain` below — working tree is clean,
  nothing new to stage (everything arrived already committed on the branch).

## Testing

- Core logic covered: `TestSightObservTransition` (pure decision, 4 parametrized cases + a 5-frame
  rapid-toggle sequence) and `TestRunSightServoObservOffWrites` (6 cases, end-to-end against the
  real unmodified `run_sight_servo` via a `GetDevice`/`SetCommand` mock) — both independently
  re-run here, both pass.
- Tests are meaningful, not decorative: `review.md` and `debug.md` both record deliberately
  mutating `sight_observ_transition` to wrong implementations and re-running — 6-9 of 21 tests
  failed each time, confirming the suite depends on the real fix. Not re-run again here (already
  verified twice, by Implementer and Reviewer independently); re-running the real suite (619/619)
  is the check this pass adds.
- No existing tests broken: full suite 619/619, same count `debug.md`/`review.md` report.

## Documentation

- Reviewer findings addressed: `review.md` verdict is APPROVED, Required Fixes: None. Two Optional
  Refinements recorded (failed-OBSERV-read-as-edge posture; a restart test that doesn't actually
  exercise a prior ON state) — both explicitly non-blocking per Reviewer's own judgment, not
  silently dropped. Carried forward below as an open item, not re-litigated.
- Non-obvious behaviour explained: the Lua diff carries inline comments pointing at the sortie-
  feedback entry and explaining the edge-detection rationale; `debug.md` has the full account.
  Added a notes/ entry distinguishing this failure mode (axis latches when writes stop) from the
  already-documented dither finding (axis ignores an unchanging write) — see Knowledge Harvest.

## Security

- No `security-plan-review.md` — correct for a bug fix (no Architect stage, so no plan to
  review). `security.md` (the deep-analysis equivalent for this sequence) exists and is APPROVED,
  no required fixes. Verified by direct read: every finding row has "Action Required: None",
  scoped appropriately to the LAN-only/single-user threat model.

## Open item (carried from Reviewer, not a blocker)

Reviewer's optional refinement — a failed OBSERV arg-read (886) is treated identically to a
genuine off, which after this fix means a transient read glitch immediately following a real ON
state can now trigger one visible snap-to-zero that didn't exist pre-fix (pre-fix, a failed read
caused no axis write at all). Reviewer and Security both judged this non-blocking (no observed
flakiness in `aircraft-layer/research/`, and failing toward a stop is the safer default). Not
re-opened here. Worth a one-line note if this path is touched again.

## Acceptance boundary — what fixtures structurally cannot reach

Every check above proves the Lua logic computes the right `SetCommand` calls against a mock. None
of it can show what the **real DCS 9K113 gimbal** does when it receives a single `(0.0, 0.0)`
command after holding a non-zero value — specifically, whether it snaps to mechanical centre or
merely stops advancing from wherever it was. `debug.md`'s own "UNVERIFIED until flight" section
names this exactly, and it is real: the probe findings this fix leans on
(`aircraft-layer/research/2026-10-21-9k113-slew-readback-probe-findings.md`) describe a centred
*stick* writing 0, which is not necessarily the same physical claim as "writing 0 to the AI
command axis recentres the gimbal." A fixture pass here is not a flight pass — see the flight
check written into `docs/acceptance/2026-10-24-sortie-feedback.md` F1 and the published card:
https://claude.ai/artifact/Cwgypqi7oLswCVoZwLfPrN

## Knowledge Harvest

Ran the notes-harvest extraction by hand (plan dir has no `implementation.md`; `review.md`'s
Required Fixes section is empty, so nothing to extract there). One insight added to
`notes/the-9k113-sight-bl-b64.md` — distinguishing "DCS ignores an unchanging per-frame write"
(already documented, the dither finding) from "an axis holds its last command indefinitely once
writes stop" (this fix's root cause) — not a duplicate of the existing dither bullet, a different
mechanism on the same axis. No other candidate found: the failed-read question is already
tracked as an open Reviewer refinement, not a standalone insight, and the GETGLOBAL-with-luac5.5
caveat is already captured in Reviewer's own agent memory (not duplicated into notes/, which is
for project insights, not tooling workarounds already memory'd).

No recurring-fix pattern: `review.md`'s Required Fixes is empty, so there is nothing to check
against `.claude/agent-memory/dod/` for a repeated category.

## Roadmap / tracking

- `docs/acceptance/2026-10-24-sortie-feedback.md` F1 — updated with DoD status, `#needs-flight`,
  and a three-part flight check (Petrovich-commanded / hand / DCS-AI-commanded OBSERV-off, each
  asking stop-in-place vs. snap-to-centre). Published as a card, not left as a plan-file section:
  https://claude.ai/artifact/Cwgypqi7oLswCVoZwLfPrN
- `body-layer/ROADMAP/BL-B80.md` — addendum added (mirroring the existing `fix/guidance-ready-edge`
  block's style, since this fix patches code that entry's own v2 design built) noting the fix,
  merge, DoD/Reviewer/Security verdicts, and `#needs-flight`, with an explicit note that it does
  not change what Flight A/B (BL-B80's own outstanding flights) should observe.
- No `BL-B` id minted: this follows the `fix/guidance-ready-edge` precedent of folding a small
  defect-fix-to-an-in-progress-milestone's-own-code into that milestone's entry as an addendum,
  not a new backlog item. Root `ROADMAP.md`'s status table is unchanged — body-layer's overall
  phase status is unaffected by this fix.

## Unblock condition executed

No deferred/accepted-debt clearing condition exists on this branch to execute — the only open
items (the failed-read refinement, the Flight A/B live checks) are already correctly tagged
`#needs-flight`/left as Reviewer-accepted non-blockers, not a stated "fix it when X" this pass
needs to run.

## Verdict: PASS

## Git state at this pass

```
$ git rev-parse HEAD
8a46e30aa8ee47284aad8b616aecd143cd54e608
$ git status --porcelain
(clean before this pass's edits — see commit below for what this pass adds)
```
