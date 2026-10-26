# DoD Check: Stage 6 (v3, ASP-17 sight edge-park) — aircraft-layer

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
