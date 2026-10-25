# Definition of Done — BL-B89 Stage 1 (9K113 sector scan)

Scope: Stage 1 only (`feature/9k113-scan-procedure`). Stage 2 (pointing) is designed, not built,
and is explicitly out of scope for this check.

**Verdict is scoped to tip `7611888cbbf5808828d59b0d742e5aede1c225d8`** — this worktree was a
clean ancestor of that sha (fast-forwarded, no divergence) at the time of this check. If the
branch has moved since, re-run.

## Mechanical checks (body-layer/, main checkout's venv — this worktree carries none)

- `ruff format --check src tests`: **pass** (173 files already formatted)
- `ruff check src tests`: **pass** (all checks passed)
- `mypy src` (cwd `body-layer/`): **pass** (74 source files, strict)
- `mypy tools` (cwd `body-layer/`): **pass** (10 source files, strict)
- `pytest tests -q`: **pass** — 2587 passed, 4 xfailed (identical count to Reviewer's own run,
  consistent with no code drift since review)
- `config/defaults.toml` vs `tools/generate_defaults.py --write`: **no diff** — regenerated into a
  scratch copy, diffed against the committed file, byte-identical
- `git status --porcelain`: **clean**, both before and after the regeneration round-trip

## Scope & correctness

- Implementation matches `plan.md` Stage 1: three-leg cycle (`wide_near`/`wide_far`/
  `narrow_far_sweep`), `choose_sighting_look`'s class-before-presence priority bucket,
  `SIGHT_SECTOR_WEDGE_DEG`/`SIGHT_AHEAD_LEGS` sector tables, mandatory per-lap naked-eye pause as
  a second trigger alongside `SIGHT_MAX_DWELL_S` — all verified by reading the code directly
  (`gaze.py:171-189`, `optic_policy.py`'s `SightSearchLeg`/`_idle_sight_search`/
  `_SEARCH_LEG_ORDER`), not only the implementation/review accounts of it.
- Spot-checked against the user's own verbatim words in `explore-notes.md`:
  - Sector spans: `left` (-30,30)→[-60,0], `right` (30,30)→[0,60], `full` (0,60)→[-60,60] — matches
    *"left scan -60 to 0 deg. right scan 0 to +60 deg."*
  - `SIGHT_AHEAD_LEGS`: (-10,20)→[-30,10], (10,20)→[-10,30] — matches *"alternating sequence -30
    to +10 deg and -10 to +30 deg"* exactly.
  - `SIGHT_SEARCH_NEAR_M = 1500.0` in the rendered `config/defaults.toml` — matches *"more like
    1.5 km - 4 km"*.
  - Naked-eye pause is wired as a mandatory per-lap trigger (`_idle_sight_search` routing to
    `_start_glance_away` on lap completion, independent of `SIGHT_MAX_DWELL_S`) — matches *"naked
    eye sweep -> ... a pause to 9K113 sweeping ... needed so that no surprise attack creeps up"*.
  - Stage 2 (pointing) correctly left designed-not-built, matching *"sector first, pointing as
    second stage"*.
- No unplanned scope added: `BL-B86`'s decline is correctly reflected (residue only — a nose-up
  test within 50-800 m AGL), `BL-B98` is filed as a found-not-introduced defect with its own ID,
  not silently folded into this stage's own claims.
- No invariants violated: no new omniscience path, no mechanism/calibration conflation (the
  derived→plain tunable change for `SIGHT_SEARCH_WIDE_FAR_M` is flagged and justified in the
  plan as a forced, explained exception), tuning additions follow the `X-T26` convention with
  `lo`/`hi` AST literals and rendered `#:` comments checked against the actual file, not the
  source comment.
- All new files staged: confirmed via `git status --porcelain` (clean) and the fast-forward diff
  listing (`plan.md`, `review.md`, `security-plan.md`, `security.md`, `implementation.md`,
  `performance-review.md`, `BL-B98.md`, plus the `.claude/agent-memory/reviewer/` memory file —
  all land as part of the merged commit history, nothing untracked).

## Testing

- Core logic covered: `TestChooseSightingLook`, `TestSightSearchLegs`, `TestSightSectorWedge`,
  altitude/attitude edge cases (nose-up at 100/300/800 m AGL, the 1-2 km band) — all read directly,
  not taken on the implementer's or reviewer's word (Reviewer's own re-review drove two of the
  edge-case tests directly; I re-ran the whole suite and got an identical pass/xfail count).
- Tests are meaningful: the lap-completion-vs-`SIGHT_MAX_DWELL_S` distinction is asserted via
  `phase_started_sim` timing, not just "a glance-away happened" — proves the *new* trigger fired,
  not the pre-existing one.
- No existing tests broken: 2587 passed, 4 xfailed, matching both the implementer's post-fix run
  and the Reviewer's own counts across two review passes.

## Documentation

- Reviewer findings addressed: both Required Fixes (the `_enter_binocular_search`/`_back_to_home`
  docstring correction, and `BL-B89.md`'s superseded-not-deleted decision line) were applied and
  re-reviewed, re-review verdict APPROVED.
- Non-obvious behaviour explained: `BL-B98` documents the dead-ahead-resume finding with root
  cause and citation to the settled F4/F5 acceptance criterion it falls short of; the plan's own
  "Notable Discoveries" in `implementation.md` records both altitude-edge measurements precisely
  rather than as a vague "mostly works."

## Security

- `plans/9k113-scan-procedure/security-plan.md`: **APPROVED**
- `plans/9k113-scan-procedure/security.md` (deep analysis): **APPROVED** — no code-execution,
  filesystem, network, or secrets surface touched; the one tunable cross-key coupling flagged is
  the same already-accepted shape as `belief.decay`'s own residual coupling, not externally
  reachable (local-user-edited `config/tuning.toml` only), and degrades to a non-stalling search
  at worst, not a crash or hang.

## Performance

- `plans/9k113-scan-procedure/performance-review.md`: **APPROVED — MONITOR**. `choose_sighting_look`
  measured cheaper than the `choose_look` path it replaces at every tested split except a
  pathological 90/10 skew (still ~1% of the 1 Hz poll budget there); the per-poll sweep generation
  and `_sight_commanded_sector` additions are O(1)/unchanged-order. No action required before
  merge.

## Acceptance testing

**Not run — needs a live DCS flight**, per the task scope ("do not merge, do not mark the roadmap
done"). Wrote `docs/acceptance/2026-10-25-bl-b89-sector-scan-flight.md` (do/expect/record blocks
covering sector commands and widths, the near band and per-lap naked-eye pause, the two
degraded-coverage altitude/attitude combinations, and `BL-B98`'s dead-ahead resume as an
observation, not a pass/fail). The main loop publishes the artifact card from that file — not done
here, per the task's explicit instruction.

**Acceptance boundary, stated up front rather than left implicit:** every test in this stage drives
the state machine with synthetic inputs. That proves the mechanism geometrically matches the spec
and never stalls. It cannot show whether the ahead-window alternation is noticeable without being
distracting, whether the per-lap pause reads as a natural beat or a stutter (especially where it
can now closely follow the pre-existing dwell-clock pause), or whether the two degraded-coverage
combinations look purposeful or broken from the cockpit. The flight card above is built to answer
exactly those three questions, not to re-verify the geometry a unit test already settled.

## Milestone-completion question

**Does this change what Stage 2 should be, or invalidate a downstream assumption?**

Yes, one concrete way: Stage 2's plan text (plan.md, "Co-moving Fields") already flagged that a
"pointed, not searching" state needs its own pass at the state machine, not a bolt-on field.
`BL-B98` (discovered by this stage, not introduced by it) sharpens that: Stage 2's design assumed
the sight "stays at last position" on return from a glance-away interruption — the exact claim
`BL-B98` shows is false for the existing glance-away mechanism. Whoever builds Stage 2 needs to
decide, before designing the pointed-state's own resume behaviour, whether `BL-B98` gets fixed
first (so pointing inherits a correct base) or whether pointing's own resume is deliberately
independent of the searching-state's resume path. Recorded here so Stage 2's own plan does not
silently inherit the same false assumption its own text already names as unresolved.

## Overall verdict: PASS

All mechanical, scope, testing, documentation, security and performance criteria pass. Acceptance
testing is the one outstanding item, correctly deferred to a flight rather than gating this DoD
pass — per root `CLAUDE.md`'s "Live verification happens in bursts, and must not gate the work."
Do not merge and do not mark `BL-B89` done until the flight card above has a recorded result.
