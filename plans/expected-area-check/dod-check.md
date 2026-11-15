# Definition of Done: expected-area-check (BL-B110, Stages 0a/0/1)

**Scope of this verdict.** Checked against tip `a7600769a7f21ce6af278e63ba6c64a15fa34487` of
`feature/expected-area-check`, fast-forwarded into this DoD worktree from `c588a88d` (which was
already an ancestor). If the branch moves further before merge, this verdict is stale and must be
re-run. Stages 0a, 0 and 1 only; Stage 2 onward (and the full BL-B110 mechanism, which forks into
`BL-B111`) is out of scope for this merge by explicit orchestrator instruction and the plan's own
fifth-pass scope trim.

## Code Quality

Subprojects touched (from `git diff --name-only main...HEAD`): **body-layer only.** (Also touched:
`.claude/agent-memory/**` and `plans/expected-area-check/**`, neither a subproject.)

- `ruff format --check src tests` (body-layer): **PASS** — 193 files already formatted.
  (A pre-existing, untouched `.md` code-block formatting complaint in
  `body-layer/research/2026-10-05-security-audit.md` was found when running `ruff format --check .`
  over the whole subproject — confirmed via `git log` that this file predates the branch and is not
  in its diff. Not a finding against this feature.)
- `ruff check .` (body-layer): **PASS** — all checks passed.
- `cd body-layer && .venv/bin/mypy src`: **PASS** — 0 errors, 79 source files.
- `pytest body-layer/tests -q`: **PASS** — 3044 passed, 4 xfailed, matching the implementer's and
  Reviewer's own reported numbers exactly. Re-run independently by this role (233 s), not taken on
  trust.
- No unhandled errors/panics in data paths, no debug output, no stray TODOs introduced by this
  feature — confirmed by Reviewer (`review.md`, APPROVED, no required fixes) and by this role's
  own read of `implementation.md`'s "Files Changed"/"Deviations" sections; nothing contradicts it.

## Scope & Correctness

- Implementation matches `plans/expected-area-check/plan.md`'s fifth architect pass: Stages 0a, 0
  and 1 only. Stage 2 is explicitly and correctly not built (`implementation.md`, `review.md`,
  `BL-B110.md` all agree).
- **One genuine STOP finding, reported rather than engineered around**: Stage 0's measured
  long-gap (120/600 s), stationary, binocular-then-unaided same-group false-trigger rate (7–27%)
  exceeds the plan's own ~10% gate. This does not block Stages 0a/1 (neither builds the real
  trigger), and is recorded in three places (`plan.md`, the test module's own docstring,
  `BL-B110.md`) for whoever builds Stage 2. Not a defect of this merge — a measurement this merge
  exists to produce.
- No unplanned scope added silently. Two local/reversible deviations from the plan's literal text
  (keeping `scan_cycle_period_s`'s name instead of a ~130-site rename; the interrupt-while-
  `GLASSING` row not advancing the sector) are disclosed in `implementation.md` and accepted by
  Reviewer without a required fix.
- No CLAUDE.md invariants violated — Security's deep analysis (`security-review.md`, APPROVED)
  traced the one new cross-key tuning extension (3 keys/1 invariant → 5 keys/2 invariants) and
  confirmed it closes a known hazard class rather than opening one; no new attack surface.
- All new files staged: confirmed via the fast-forward merge bringing in a clean tree
  (`git status --porcelain` empty immediately after `git merge --ff-only`).

## Testing

- Core logic covered: `test_position_belief.py` (+4), `test_expected_area_trigger.py` (new, 11),
  `test_gaze.py` (+14), `test_optic_policy.py` (+8 across 3 classes), `test_estimation.py` (+37),
  `test_tuning.py` (+2), `test_body.py` (+1 scenario gate). Tests are meaningful, not decorative —
  Reviewer read the diffs of all Decision-3 rewrites and confirmed each still tests the same claim
  with traced, intended number changes, not loosened assertions.
- No existing tests broken: full suite green (3044/3044 + 4 xfailed, matching across implementer,
  Reviewer and this role's independent run).
- Two full-pipeline fixture tests (`test_mock_flight_chain.py`,
  `test_bl_b104_scenario_mock_flights.py`) broke during implementation from a wiring-defect fix not
  named in the plan's own test-impact list, and were fixed and investigated (not guessed) —
  recorded in `implementation.md`'s "Notable Discoveries" and harvested to
  `notes/fixture-management-and-test-infrastructure.md` (this role, see below).

## Documentation

- Reviewer findings addressed: `review.md` verdict APPROVED, **no required fixes**. Three optional
  refinements noted (comment duplication, a wording nit, confirming the roadmap already carries
  the STOP finding) — none blocking, none requiring action here.
- Non-obvious behaviour explained: `body-layer/docs/STRUCTURE.md` and `body-layer/CLAUDE.md`
  updated (the extended cross-key coupling invariant, I2); `plan.md`/`implementation.md` carry the
  measured numbers and reasoning.
- `defaults.toml` rendered entries checked directly for the three new/changed tunables
  (`EXACT_LOCATION_MIN_GAIN_M`, `GLASS_STALL_COOLDOWN_S`, `GLASS_BUDGET_PER_CYCLE_S`) — each
  carries its full `#:` comment (not truncated to the first sentence), `status`, and `lo`/`hi`
  bounds, per this project's "Behaviour-affecting constants are tunable" convention.

## Security

- `security-review.md` (deep analysis, before DoD): **APPROVED**, no required fixes. No dependency
  change; no new attack surface in this threat model (single-user, LAN-only); the one new
  cross-key tuning extension traced and confirmed safe.
- **`security-plan-review.md` does not exist, and that is correct, not a gap.** Root `CLAUDE.md`,
  "Agents": *"Security's plan review left the sequences at the same time"* (user direction,
  2026-10-30) — the plan-review step between Architect and Implementer was dropped from the role
  sequence project-wide; only the deep analysis before DoD remains mandatory, and that one exists
  and is approved.
- `performance-review.md`: **APPROVED — MONITOR.** No NOW-severity finding; three MONITOR items
  (precomputable sector partition, inherited O(n²) in `choose_look`, pre-existing disposition
  carried forward) — none require a change before merge.

## Milestone Completion

**Does this change what the next milestone should be, or invalidate a downstream assumption?**
Yes, in two ways, both already reflected in the roadmap:

1. **Stage 0's measured 70% far-unaided→near-binocular residual fold (unresolved by either trigger
   variant) raises `[[BL-B111]]`'s priority.** BL-B111 (the point line-of-sight query, the "same"
   verdict) is the only path that removes this residual — Stage 0's own measurement confirms the
   trigger-tuning approach cannot reach it, which `plan.md` already states (Risks: "only a tighter
   trigger or anchors reach it") and this merge now confirms empirically at a larger measured
   scale. BL-B111 was already queued; nothing to add beyond what its own entry says.
2. **The long-gap stationary false-trigger STOP finding points at `[[BL-B112]]` (motion-aware
   certainty) as a candidate way to close part of the gap for Stage 2**, since a correctly-modelled
   "entrenched, unlikely to have moved" contact would shrink exactly the hypothesis-covariance gap
   that makes the 120/600 s cell fail the gate today. This is a hypothesis to consider when BL-B112
   or BL-B111/Stage 2 is next architected, not a scope change to either entry now — noted here per
   "Milestone Completion"'s one-line requirement rather than added to either roadmap entry
   speculatively.

## Acceptance Testing

**Not performable from this subagent — live DCS behaviour.** Per root `CLAUDE.md`'s 2026-10-26
direction, this does not gate the merge. Status: **PENDING (live)**.

**Acceptance boundary, stated honestly:** this feature's fixtures are synthetic sweep harnesses and
scenario tests over committed code — they can measure a fold rate, a false-trigger rate, a worst
revisit time, and a sector-partition boundary exactly. They structurally cannot verify: whether the
sector sweep *feels* right to fly against, whether a flank pickup at the ~28–40 s aliasing bound
reads as "normal and a little quiet" or as "Petrovich missed it" to a human in the seat, or whether
the stall-cooldown's 180 s ever feels wrong in practice at real mission tempo. No fixture here
drives the cockpit; a sortie does.

**Test card published**: https://claude.ai/artifact/GHLrELVKDaBDs1FDosbxfd (source:
`plans/expected-area-check/test-card.md`). Every command in it was run and its real output
recorded (mypy, full pytest) — nothing in the card is a guess.

**Roadmap tag**: `body-layer/ROADMAP/BL-B110.md` carries `#needs-flight` alongside its existing
`#status/open` (the entry stays open — Stage 2 is not built, so BL-B110's own goal is not complete
regardless of the flight result). Clears on a sortie naming which sortie cleared it, per root
`CLAUDE.md`'s "Distinguish deferred from waived."

## Verdict

**PASSED.**

Mechanical checks all green, Reviewer/Security/Performance all APPROVED with no required fixes,
scope matches the plan's own fifth-pass trim, the one genuine STOP finding is reported (not
engineered around) and already propagated to the roadmap in three places. Per root `CLAUDE.md`'s
auto-merge rule, this PASSED report is the merge trigger — the main loop runs `/merge` on
`feature/expected-area-check` next. Live acceptance is `#needs-flight`, not a merge gate.
