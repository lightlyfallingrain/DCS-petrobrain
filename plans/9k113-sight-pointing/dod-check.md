# DoD Check: Stage 6 (v3, ASP-17 sight edge-park) — aircraft-layer

*This is the most recent pass. Earlier passes (v2 Stages 1-4/3b, and the superseded v1 pass) are
kept below for history — do not delete them when adding a future pass; prepend instead.*

Scoped to branch `feature/9k113-sight-edge-park`, tip `f65f0ce00d098698cc0c1b322f8674d50bc00a68`
(verified: this worktree's HEAD was a strict ancestor of that sha on a clean tree before this pass;
fast-forwarded, no cherry-pick needed). **This verdict is scoped to that tip — if the branch moves
after this report, re-run.**

Diff touched by this stage (per `git diff --name-only` against the stage's own base
`9dfc3d2f32b4f012672c95fbda7d02ddcb3a19de`): `aircraft-layer/dcs-export/Export.lua`,
`aircraft-layer/src/schema/sight_servo.py`, `aircraft-layer/tests/test_sight_servo_api.py`,
`aircraft-layer/tests/test_sight_servo_lua.py`, plus docs/plans/notes/agent-memory. **No
body-layer source change** — only `body-layer/CLAUDE.md` (a documentation clause), matching the
plan's own Stage 6 scoping ("Does not touch body-layer"). So the subproject commands below run
full for aircraft-layer only; body-layer gets no code-quality gate because no body-layer code
changed.

## Quality Gates — aircraft-layer

| Check | Status | Notes |
|-------|--------|-------|
| Format (`ruff format --check src tests`) | ✓ PASS | 72 files already formatted |
| Lint (`ruff check src tests`) | ✓ PASS | All checks passed |
| Types (`mypy --strict src`, run from inside `aircraft-layer/`) | ✓ PASS | Success: no issues found in 25 source files |
| Tests (`pytest tests -q`) | ✓ PASS | 607 passed |
| Lua syntax (`luac5.1 -p Export.lua`) | ✓ PASS | parses clean |
| `GETGLOBAL` scan (undeclared-global check, per `aircraft-layer/CLAUDE.md`) | ✓ PASS | every name resolved is a genuine DCS API, Lua stdlib, or a pre-existing deliberate one-shot dump global (`DUMPED_*`) unrelated to this stage's diff — none of Stage 6's own new helpers (`sight_clip_to_field_body_deg`, `sight_mark_is_clipped`) leak as a global read |

## Code Violation Scans — files touched by this stage

| Check | Status | Findings |
|-------|--------|---------|
| No debug output (`print(`, `pdb.set_trace`, `breakpoint()`) | ✓ PASS | 0 occurrences in `sight_servo.py` |
| No TODO/FIXME/HACK/XXX markers | ✓ PASS | 0 occurrences in `sight_servo.py` or `Export.lua` |
| No bare/silent error suppression | ✓ PASS | 0 occurrences in `sight_servo.py` |
| File size (`sight_servo.py`, 162 lines) | ✓ PASS | well under the 400-line split threshold |

## Staging / Tree

`git status --porcelain` — clean (fast-forward merge already landed every file; nothing untracked).

## Security Sign-off

| File | Status |
|------|--------|
| `plans/9k113-sight-pointing/security-plan-review.md` (v1/v2) | ✓ PASS (APPROVED — covers the subsystem's original plan) |
| `plans/9k113-sight-pointing/security-review-v3.md` (Stage 6, this pass) | ✓ PASS — APPROVED, "no required fixes. This stage adds no new dependency, no new network-reachable surface, no code path" |

## Scope & Correctness

- Implementation matches the plan: `implementation.md`'s Stage 6 entry confirms the root-cause fix
  (`sight_mark_is_clipped` against the mark's own raw reading, replacing the wrong-magnitude gimbal
  check), the always-closed loop on `field_target`, the feed-forward switch, the merged `homing`
  mode, and open-loop removal — all per plan.
- No unplanned scope added silently: the implementer explicitly flagged the one scope narrowing
  (not wiring `field_target_*`/`mark_clipped` into `sight_trace_writer.py`, per the plan's own
  Stage 6 bullet) rather than silently deviating — recorded in `implementation.md`'s "Notable
  Discoveries" and reflected in the `body-layer/CLAUDE.md` clause.
- No invariants violated: aircraft-layer-only change, cockpit-write channel unchanged, no new
  network surface (security-review-v3.md confirms).
- All new/modified files staged and committed (fast-forward merge brought everything in one
  commit set; verified via `git status --porcelain` above).

## Testing

- Core logic covered: `TestSightClipToFieldBodyDeg` (incl. an 11-sample property test pinning the
  margin-inset bound), `TestSightMarkIsClipped`, `TestRunSightServoFieldPark` (7 end-to-end tests,
  including the red-run-against-pre-fix-code regression check, the continuous-edge-tracking test,
  the feed-forward-rate test with its named mutation, and the stall-while-sliding test).
- Tests are meaningful, not decorative: `review-v3.md` independently confirmed the plan's own named
  mutations actually catch what they're supposed to (reviewer feedback memory on this exact point:
  "actually make that edit against the real source and run the suite").
- No existing tests broken: full 607-test aircraft-layer suite passes.

## Documentation

- Reviewer required fixes: **none** (`review-v3.md`, "Required Fixes: None"). Two Optional
  Refinements were noted — the missing Flight B card (addressed by the test card below) and the
  open-guess status of `ASP17_FIELD_EL_HALF_DEG`/`ASP17_FIELD_MARGIN_DEG` (carried forward, per the
  plan's own ANSWERED decision, to be measured in flight — see the test card).
- Non-obvious behaviour explained: `notes/the-9k113-sight-bl-b64.md` updated; `body-layer/CLAUDE.md`
  clause documents what's true after this stage (fields exist on the API, trace writer doesn't read
  them yet).

## Verdict: **PASS**

All mechanical checks pass. Reviewer, Performance Reviewer, and Security all APPROVED with no
required fixes. Proceeding to acceptance-testing card (live, PENDING) and roadmap/notes harvest.

## Acceptance boundary — what no fixture here can reach

Every test above runs against Lua pure functions and a mocked `GetDevice`/`LoGetSelfData` — none
of it touches a real 9K113 gimbal, a real ASP-17 optical mark, or DCS's own intermittent-obedience
behaviour. Specifically out of reach of this test suite, by construction:

- **Whether the real ASP-17 field is actually ≈4.3° az / the guessed el half-angle** —
  `ASP17_FIELD_EL_HALF_DEG` and `ASP17_FIELD_MARGIN_DEG` are both placeholders the plan ships
  deliberately; only a flight with `--slew-trace`'s sibling per-frame log on can read the real
  555 clip edges.
- **Whether the real sight visually parks at the HUD edge rather than drifting/pegging** — the
  fixture suite proves the Lua *math* clips the setpoint correctly; it cannot show the real
  cockpit cross hair doing it, which is the whole symptom this stage was built to fix.
- **Whether continuous edge-tracking looks smooth to a human eye**, as opposed to numerically
  monotonic in a mocked sequence of setpoints.

This is why the card below is tagged `#needs-flight` rather than treated as closed by this PASS.

---

## v2 (previous pass — Stages 1-4 with 3b)

# Definition of Done: BL-B80 v2, Stages 1-4 (with 3b) — 9K113 sight pointing

**Scope note:** this batch is `plan.md` v2's Stages 1–4, with Stage 3b (seen aim) folded in as the
plan directs ("one performance and one security pass after Stage 4"). **Stage 0 (the calibration
probe) is explicitly outside this batch** — the plan's own words: "Stage 0 is a probe, outside the
batch." It is a prerequisite for Flight B's numbers, not part of this implementation or this DoD
pass. **This DoD does not mark BL-B80 done.** Live acceptance (Flight A, Flight B) has not
happened and cannot happen in this pass.

**Verdict scoped to tip `e009465eba841a1a320ac02740dbbd1133221b96`** on
`feature/9k113-sight-pointing`. HEAD at dispatch (`49fa122b`, on `main`) was a strict ancestor of
this tip; fast-forwarded cleanly in an isolated worktree, tree clean throughout. If the branch
moves past this sha before merge, re-run this check.

## What superseded v1

`plans/9k113-sight-pointing/plan.md` ("Re-plan, 2026-10-22") replaces the entire v1 mechanism this
subproject's previous DoD pass (below, "v1 (superseded)") verified. Probe runs 1–11
(`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`, merged `6d6c99a9`; run 11, merged
`d6ed947f`) overturned v1's three load-bearing premises: the AI axis is **not** a position target
(it is edge-triggered — DCS only obeys a `SetCommand` write whose value *changes* frame to frame,
confirmed 18/18 vs. 3/10 constant), 874/876 echo the demand rather than reading a position, and the
DCS AI overlay is not required at all. None of v1's own unit tests could have caught this —
every one of them exercised the model's own internals against its own, now-wrong assumptions; only
the live probe surfaced the mismatch (see `notes/the-9k113-sight-bl-b64.md`'s closing bullet, added
by this pass). v1's whole position-model mechanism (`ShowMenu`, `ai_believed_on`,
`GYRO_ALIGNMENT_S`, the elevation-conversion functions) is removed in this batch's Stage 1, not
patched. One piece survives unchanged and model-independent: the exponent-float parser fix
(`extract_json_number_field`), kept as-is per the plan's own table.

## Code Quality

Every command below run fresh, in this isolated worktree, cwd inside the subproject, using the
main checkout's venvs (no `.venv` exists per-worktree; binaries are shared, config discovery is
CWD-only per `body-layer/CLAUDE.md`).

| Check | Subproject | Result |
|---|---|---|
| `ruff format --check .` | aircraft-layer | PASS (1 pre-existing unrelated file flagged — `research/2026-10-06-unit-id-join-reduce.py`, last touched `bc680887`, confirmed outside this branch's diff) |
| `ruff check .` | aircraft-layer | PASS (same file, `EXE001` shebang-not-executable) |
| `mypy src` (`--strict`) | aircraft-layer | PASS — 27 source files, no issues |
| `pytest -q` | aircraft-layer | PASS — 533 passed |
| `luac5.1 -p Export.lua` | aircraft-layer | PASS — syntax OK |
| `luac5.1 -p Export.probe-9k113-calibration.lua` | aircraft-layer | PASS — syntax OK |
| `GETGLOBAL` scan (`luac5.1 -l -p Export.lua`) | aircraft-layer | PASS — every unresolved global is a genuine DCS/stdlib name (`GetDevice`, `LoGet*`, `math`, `string`, `pcall`, `io`, `lfs`, …); no own-helper referenced before its `local` |
| `ruff format --check .` | body-layer | PASS (1 pre-existing unrelated file flagged — `research/2026-10-05-security-audit.md`, a markdown research note, confirmed outside this branch's diff) |
| `ruff check .` | body-layer | PASS — all checks passed |
| `mypy src` (`--strict`) | body-layer | PASS — 71 source files, no issues |
| `pytest -q` | body-layer | **1 failed under randomized order**, 2442 passed, 4 xfailed; re-run with `-p no:randomly`: 2443 passed, 4 xfailed, 0 failed |

**The one test failure, investigated, not waved through.** `tests/test_logger.py::
test_connection_reporter_announces_the_first_connection` failed once under `pytest-randomly`'s
reordering (a `caplog` assertion collided with log records from an unrelated test that happened to
run first in that order) and passed cleanly in isolation and under a fixed/default order. Confirmed
**pre-existing**: `git log -1` on that test's own lines shows it was added by `a5def59e`
("Say \"disconnected\" once, not a traceback every second"), and `git diff 1c433fc6..e009465e --
body-layer/tests/test_logger.py` shows no change to that test in this batch's diff. Not a blocker
for this batch; worth a `caplog`-isolation fix on its own, tracked in the roadmap entry rather than
fixed here (out of this batch's scope).

Both pre-existing lint findings are confirmed outside this branch's diff the same way (`git log -1`
on each path, `git diff 1c433fc6..e009465e --name-only | grep <path>` returns nothing).

- No unhandled errors/panics in data paths — confirmed via Reviewer's full read, Security's deep
  analysis, and Performance's review; no open findings in any of the three.
- No debug output left in committed code — none found (Reviewer's re-review confirms the fix diff
  specifically; no new debug output anywhere else in the batch).
- No leftover debug code or TODO comments introduced by this feature — none found.

## Scope & Correctness

- Implementation matches `plans/9k113-sight-pointing/plan.md` v2 — confirmed by Reviewer's full
  read (every changed source file), the re-review of the three required fixes (defaults.toml
  first-sentence extraction, the widened F4 differential no-leak test, the `run_once` wiring tests
  for Stages 3/3b — all verified present and correct **by mutation**, not by reading the diff:
  Reviewer reverted the logger.py gating fix, reran the targeted test, confirmed it failed exactly
  as predicted, restored it, confirmed it passed clean again), and Security's deep analysis
  (dependency status, code findings, housekeeping — all clean).
- No unplanned scope added silently — Reviewer's re-review confirms the fix diff touches exactly
  the four files the three required fixes named (`Export.lua`, `logger.py`, `test_logger.py`,
  `implementation.md`), nothing else.
- No invariants from `CLAUDE.md` violated — `body-layer/CLAUDE.md`'s invariant edit (the
  ownship-relative channel's second sanctioned consumer, `seen_world_direction` → `sight_head.py`)
  matches the plan's text verbatim; grep-fenced by `test_attack_run.py`/`test_sight_head.py`; no
  omniscience leak (belief position/memory/tools proven unaffected by the seen aim, Security's
  F4 differential test); module independence unaffected (no new cross-subproject import).
- All new files staged — confirmed (`git status --porcelain` clean after the fast-forward; see
  below).

## Testing

- Core logic covered: `SightHead`'s world-hold through a turn, per-axis rate limits, gimbal
  clamping and stop-dragging, caged→free transition; `seen_world_direction`/`select_sight_goal`'s
  full selection table (seen/held/belief, including the binocular-look-does-not-steer case and the
  masking-drop-to-held-then-belief case); the F2/F3 fences; the `sight_servo` pure-math Lua
  functions tested against Python reference vectors under `luajit`; a `run_once`-level wiring test
  for Stage 3 and Stage 3b each, each paired with a mutation the test is shown to catch (closing
  the recurring leaf-tested/wiring-untested defect class this subproject has hit three times
  before).
- Tests are meaningful, not decorative: Reviewer re-derived the `Export.lua` `ai_off_since`-era
  fix frame-by-frame independently (not present in v2 — that detector is removed entirely in this
  batch, confirmed by grep) and, for this batch's own fixes, verified the logger.py gating fix by
  mutation rather than trusting the diff's intent. The F4 differential test's own red-run history
  (three distinct mutations, each caught, one first-draft mutation that stayed green because it
  set the wrong field — documented in `implementation.md` as the mutation's own mistake, not the
  test's) is the strongest evidence here: this is a test that has actually been shown to fail on
  a real defect shape, not just pass on the intended code.
- No existing tests broken — full suite green both subprojects (above), modulo the one
  pre-existing order-dependent flake, confirmed unrelated to this batch.

## Documentation

- Reviewer findings addressed: all three required fixes from the v2 review's first pass
  (NEEDS REVISION) verified present and correct in the re-review (APPROVED) — one by independent
  mutation, two by reading the fix against the plan's exact wording and the review's own suggested
  mutations.
- Non-obvious behaviour explained: `body-layer/CLAUDE.md`'s invariant section documents the second
  sanctioned consumer of `Percept.relative_direction`; `sight_head.py`'s own module docstring states
  the aim-source selection rule; `notes/the-9k113-sight-bl-b64.md` now carries two new lessons from
  this batch (the change-driven-axis finding and the position-model-overturned-by-probe finding —
  see Notes Harvest below, checked against the file's existing content first, not duplicated).

## Security

- `plans/9k113-sight-pointing/security-plan-review.md` — APPROVED.
- `plans/9k113-sight-pointing/security-review.md` — APPROVED ("Security Deep Analysis:
  9k113-sight-pointing (BL-B80, v2, Stages 1-4/3b)", the current top-level section — dependency
  status clean, code findings clean, housekeeping noted but non-blocking).
- `plans/9k113-sight-pointing/performance-review.md` — APPROVED — MONITOR (two items: redundant
  per-frame `GetDevice` lookups, an established pre-existing pattern not worsened by this batch;
  the synchronous `write_sight_target` HTTP write in the poll loop, matching the already-accepted
  `write_cockpit_switch` posture — neither is a blocker).

## Roadmap

`body-layer/ROADMAP/BL-B80.md` updated: the v1 "Status, 2026-10-22 — Stages 1-3" section replaced
with a "Status, 2026-10-22 — v2 Stages 1-4 (with 3b)" section naming what was built, this DoD
pass's fresh check results, the two outstanding flights (A and B) and exactly what each must
verify, and the plan-stated pre-merge condition on Flight A's cold-start check (below). Checkbox
state stays `[~]` / `#status/in-progress` (not `[x]`/done, not merged) — unchanged, correctly, from
the v1 pass's own reasoning about when `#needs-flight` applies.

**Execute-the-unblock-condition check, per this role's own standing instruction.** The plan names
one concrete clearing condition for Flight A — "960 on a cold start is unconfirmed... Flight A's
cold start is therefore before any merge" — but this is a live-DCS check with no command this DoD
pass can run; there is nothing to execute mechanically here, only to flag loudly, which the
roadmap update and the next section both do. This is different from the usual case this rule
guards (a command someone claimed would clear debt, left unrun) — here the condition is
irreducibly a live flight, correctly labelled as such rather than worked around.

## Acceptance boundary — what Flights A and B structurally cannot be skipped for

Everything above is mechanical and fixture/unit-test-reachable. Nothing in this batch's own test
suite can reach `Export.lua` live or a real DCS 9K113 servo. Specifically, this DoD pass cannot and
does not verify:

- Whether arg 960 (the believed guidance-unit READY lamp) actually lights on a cold start, and
  when — **the plan itself treats this as a pre-merge condition**: if it never lights, Petrovich
  refuses OBSERV for the whole sortie. This is the one item in this batch that is not an ordinary
  deferred-acceptance item; it is a stated correctness risk on the whole feature.
- Whether the real DCS 9K113 axis actually obeys the dithered setpoint and holds a world direction
  through a turn at the error magnitudes the plan predicts (well under run 10's 0.06–0.10°).
- Whether 555's elevation clip edges allow a closed loop at all (unknown, never closed-loop-tested
  before this batch — Flight A's own stated purpose).
- Whether the seen-aim mark visibly sits on the real vehicle hull in a live flight, and whether
  belief's position estimate is genuinely unaffected by a held look outside the fixture (F4 proves
  the mechanism; it cannot prove the live behaviour).
- Whether a real hard manoeuvre's DCS-triggered automatic OBSERV-off is followed correctly.

These are exactly Flight A's and Flight B's acceptance lists. Flight A's card (published):
https://claude.ai/artifact/YAfTTDn8XbeinrPjUAyovf (source
`docs/acceptance/2026-10-22-bl-b80-v2-flight-a.md`). Flight B's card has not been written — it
depends on Flight A's calibration numbers (Stage 0 feeds Stage 4's servo constants) and is this
entry's own next deliverable, not this DoD pass's.

## Milestone-completion question

**Does this batch change what the next milestone should be, or invalidate a downstream
assumption?** Not yet, conditionally. `[[BL-B67]]` (the ATGM run) is built out of this pointing
loop and cannot be planned without a trustworthy channel and calibration numbers — unchanged by
this batch, since Flight A/B have not flown either model. What *could* change it: if Flight A finds
555 cannot be closed-loop at all, or Flight B finds the dither-held world-frame error exceeds the
ATGM budget, that correction must land in this entry (per the plan's own "Second-order effect"
section) before `BL-B67` is planned. The larger second-order effect already happened and is
recorded above: the *entire v1 plan and its DoD pass* were overturned by a live probe after
passing every mechanical and review gate — the structural lesson (unit tests on a control-loop
model cannot substitute for a live probe before building on that model) is now in
`notes/the-9k113-sight-bl-b64.md`.

## Acceptance Testing Plan

**Goal:** confirm the real 9K113 axis's calibration (scale, boresight, clip edges, world-frame
loop error) via Flight A, then — once Stage 4's servo constants are set from those numbers —
confirm the simulated sight holds a world direction through the real DCS slave, the seen-aim mark
sits on the real vehicle without leaking into belief, and `home_phase` follows DCS's own observed
state, via Flight B.

**Branch to fly:** `feature/9k113-sight-pointing` (not merged — check it out explicitly; the repo
root is not parked here).

**Flight A — ready now.** Card: https://claude.ai/artifact/YAfTTDn8XbeinrPjUAyovf. Two parts: the
calibration sweep sequence (Stage 0 probe script) and the cold-start READY-lamp timing check
(production `Export.lua` or the probe — either logs the lamp).

**Prerequisites**
- [x] `mypy --strict` clean on both touched subprojects (ran above, this report).
- [ ] `Export.probe-9k113-calibration.lua` deployed to the Windows box (UNVERIFIED — needs
  Windows).
- [ ] `Saved Games\DCS\Scripts\Export.lua` backed up before the probe is copied over it
  (UNVERIFIED — needs Windows, stated on the card).

**Flight B — not yet ready.** Depends on Flight A's numbers (scale, boresight, clip edges feed
`SERVO_WOBBLE`/the Kp constant Stage 4 was built with placeholders for). Card to be written once
Flight A's results are known.

**Pass Criteria:** Flight A's measures (above) land within the ranges the plan predicts, with no
surprise strong enough to force a Stage 0/1-4 rework; the 960 cold-start timing confirms the
READY-lamp hypothesis (or, if it does not, that is reported as a blocking finding, not worked
around). Flight B, once flown: all its blocks (world-frame hold through a turn, mark settling on
the servo, seen-aim mark-on-vehicle with belief unaffected, hard-manoeuvre auto-off) produce the
expected result and no regression appears in `BL-B66`'s existing switch-power-up behaviour.

**Live acceptance is not an ordinary merge gate here, but one specific item within it is.** Per
`CLAUDE.md`'s standing direction, Flight B's full acceptance can sit outstanding while other work
starts — nothing here blocks that. **Flight A's cold-start half is different: the plan itself
states it must happen before this merges**, because a 960-never-lights result would mean the whole
feature is unusable from OBSERV onward. Recommend flying Flight A (both parts) before this branch
is merged to `main`; Flight B can follow after merge, tagged `#needs-flight` on this entry once
merged.

---

## v1 (superseded)

# Definition of Done: BL-B80 Stages 1-3 (9K113 sight pointing)

**Scope note:** this batch is Stages 1-3 of `plans/9k113-sight-pointing/plan-v1-position-model.md`
(then `plan.md`, since renamed — the whole v1 mechanism this report verifies was removed in v2's
Stage 1, per the table above). Stage 4 (the live sortie) is explicitly not part of this DoD pass —
it is the acceptance step this report hands off. **This DoD does not mark BL-B80 done.**
**Superseded in full 2026-10-22 — see the current report above.**

**Verdict scoped to tip `8b2967008f7654f41be52d2779cc430c5605c32d`** on
`feature/9k113-sight-pointing`. HEAD at dispatch (`9284cd34`) was a strict ancestor of this tip;
fast-forwarded cleanly, tree clean throughout. If the branch moves past this sha before merge,
re-run.

## Code Quality

| Check | Subproject | Result |
|---|---|---|
| `ruff format --check` | aircraft-layer | PASS (1 pre-existing unrelated file flagged — `research/2026-10-06-unit-id-join-reduce.py`, last touched `bc680887`, not in this branch's diff) |
| `ruff check` | aircraft-layer | PASS (same pre-existing file, `EXE001` shebang-not-executable) |
| `mypy --strict src` | aircraft-layer | PASS — 26 source files, no issues |
| `pytest` | aircraft-layer | PASS — 469 passed |
| `ruff format --check` | body-layer | PASS (1 pre-existing unrelated file flagged — `research/2026-10-05-security-audit.md`, a markdown research note, not in this branch's diff) |
| `ruff check` | body-layer | PASS — all checks passed |
| `mypy --strict src` | body-layer | PASS — 70 source files, no issues |
| `pytest` | body-layer | PASS — 2418 passed, 4 xfailed |
| `luac5.1 -p Export.lua` | aircraft-layer | PASS — syntax OK |

All commands run fresh in this worktree, not copied from a prior report. The two flagged files
are both outside this branch's own diff (confirmed via `git log` on each path showing only a
pre-existing commit) and are not blockers.

- No unhandled errors/panics in data paths — confirmed via Reviewer's full read plus Security's
  deep analysis; no open findings.
- No debug output left in committed code — none found.
- No leftover debug code or TODO comments introduced by this feature — none found.

## Scope & Correctness

- Implementation matches `plans/9k113-sight-pointing/plan.md`, including the 2026-10-22
  coordinator amendments — confirmed by Reviewer's full read and independently spot-checked here
  (Co-moving Fields table, elevation formula derivation, `EXPORT_SCRIPT_VERSION`/
  `EXPECTED_EXPORT_VERSION` pairing at `2026-10-22b`).
- No unplanned scope added silently — Reviewer's review confirms this; the one post-review fix
  (the exponent-float bug) is an in-scope bug fix on code this batch introduced, not scope
  expansion, and went through the standard bug-fix role sequence (Debugger implicit in the fix,
  Reviewer, Security) per `AGENTS.md`.
- No invariants from CLAUDE.md violated — no-omniscience boundary, module independence, and the
  fixed cockpit-write vocabulary precedent are all explicitly checked in `security-plan-review.md`
  and `security-review.md`.
- All new files staged — confirmed, see below.

## Testing

- Core logic covered: `sight_effector.py`'s new conversion functions, `in_gyro_alignment`,
  `advance_sight_aim`'s readback-preference branch, `sight_target` wire validation (both API and
  Export.lua sides), the exponent-float fix's live-Lua-interpreter round trip.
- Tests are meaningful: Reviewer independently re-ran the implementer's edge cases against a live
  Lua interpreter rather than trusting the implementer's account; one gap (missing `run_once`-level
  integration test for the gyro-alignment optic cap) was flagged and left as a documented residual,
  not silently dropped.
- No existing tests broken — full suite green both subprojects (above).

## Documentation

- Reviewer findings addressed: all five required fixes from `review.md`'s first pass verified
  present and correct by Reviewer's own fix-diff re-review; the exponent-float fix's own required
  fixes (bound documentation, precision-ceiling note) are optional refinements, not blocking.
- Non-obvious behaviour explained: `sight_effector.py`/`Export.lua` docstrings state which
  functions are command-domain vs. readback-domain (post-fix); `notes/the-9k113-sight-bl-b64.md`
  now carries both the domain-distinction lesson and the shared-field/optic-gating lesson from this
  batch (see Notes Harvest below).

## Security

- `plans/9k113-sight-pointing/security-plan-review.md` — APPROVED.
- `plans/9k113-sight-pointing/security-review.md` — APPROVED (Stages 1-3, as originally written)
  and APPROVED (exponent-float fix, the post-review addendum) — both verdicts present, no open
  findings.
- `plans/9k113-sight-pointing/performance-review.md` — APPROVED — MONITOR (one item to watch
  under real load, not a blocker).

## Tuning

`GYRO_ALIGNMENT_S` declared via `tuning.real` in `sight_effector.py` (lo=5.0, hi=20.0,
status="measured") and rendered correctly in `body-layer/config/defaults.toml` with its full
`#:`-sourced comment, status, and range — confirmed by reading the rendered file, not the
generator's source comment.

## Acceptance boundary — what Stage 4 structurally cannot be skipped for

Everything above is mechanical and fixture/unit-test-reachable. **Nothing in this batch's own test
suite can reach `Export.lua` live** (this subproject's standing limitation) or verify a physical
quantity against DCS's real mechanical stops. Specifically, this DoD pass cannot and does not
verify:

- Whether the derived (not measured) elevation calibration actually matches the real +20°/−15°
  mechanical limits.
- Whether the gyro-alignment window is cockpit-invisible in practice (no stray `ShowMenu`, no
  premature sight reports).
- Whether the AI-off detector ever fires when DCS's own AI Petrovich is genuinely on and tracking,
  in real ordinary flight rather than a reasoned-about trace.
- Whether `home_phase` actually follows a real DCS-triggered automatic OBSERV-off, not just the
  commanded one.
- Whether the overlay actually reopens after a real manual close.

These five are exactly Stage 4's acceptance list — see the card below.

## Roadmap

`body-layer/ROADMAP/BL-B80.md` updated: title and opening line corrected from "player axis" to
"AI axis" (the body text already carried the 2026-10-21 SUPERSEDED correction; only the heading
and summary line were stale), checkbox state to `[~]` / `#status/in-progress` (not `[x]`/done —
Stage 4 has not flown and this batch is not yet merged), and a new "Status, 2026-10-22" section
naming what Stages 1-3 built, what Stage 4 must still verify, and the `BL-B67` dependency.
**Deliberately not tagged `#needs-flight`**: per `docs/TAGS.md`, that tag is for a shipped, merged
change awaiting its sortie. This entry has not merged, so `#status/in-progress` is the correct
tag — `#needs-flight` would be added only if this merges before Stage 4 flies.

## Milestone-completion question

**Does this batch change what the next milestone should be, or invalidate a downstream
assumption?** Not yet — Stages 1-3 are exactly what `BL-B67` (the ATGM run) was already known to
depend on, and nothing here changes that dependency's shape. What *could* change it: if Stage 4
finds the derived elevation formula wrong at either mechanical stop, that correction must land in
this entry before `BL-B67` is planned (the plan's own "Second-order effect" section already says
so). So the next milestone is unchanged for now, but is conditionally gated on Stage 4's elevation
check specifically, not on the whole sortie.

## Acceptance Testing Plan

**Goal:** confirm the real 9K113 sight follows Petrovich's modelled aim on the AI axis, hits its
real mechanical stops at the derived elevation calibration, stays cockpit-invisible during the
gyro-alignment window, and that `home_phase`/the AI overlay correctly follow DCS's own observed
state rather than only the spoken command.

Full card, with every command either run for real (output pasted) or marked UNVERIFIED:
`docs/acceptance/2026-10-22-bl-b80-sight-pointing-sortie.md`. Published artifact:
https://claude.ai/artifact/NBTX4TmY2oxEJ1hXz8MY6Y

**Branch to fly:** `feature/9k113-sight-pointing` (not merged — check it out explicitly, the repo
root is not parked here).

**Prerequisites**
- [x] `mypy --strict` clean on both touched subprojects (ran above, this report).
- [ ] Export.lua `2026-10-22b` deployed to the Windows box (UNVERIFIED — needs Windows).
- [ ] Collector restarted, no version-mismatch warning (UNVERIFIED — needs Windows + DCS).

**Test Cases** — see the card's five flight blocks (gyro-alignment window + smooth motion, the
two mechanical stops, Observ-off + auto-off following, reopen-after-manual-close, ordinary-flight
false-fire watch).

**Pass Criteria:** all five blocks produce the expected result and no regression appears in
BL-B66's existing switch-power-up/weapons-arming behaviour (unchanged by this batch, worth a quick
sanity check during the same flight since the power-up sequence is a prerequisite for every block
here).

**Live acceptance is not a merge gate.** Per CLAUDE.md's standing direction, this batch can sit
merged-pending or unmerged while the user's Windows/DCS access permits a flight; nothing here
blocks starting other work in the meantime.
