### Definition of Done — `fix/group-undermerging` @ `6d6ea3f`

Run 2026-10-01. Worktree landed on `main` (`1dff0f4`) at dispatch; `git rev-parse HEAD` caught the
mismatch immediately per AGENTS.md rule 4, and the branch was checked out directly in this
worktree (free — nothing else had it checked out) rather than building an isolated snapshot.
Verified at `6d6ea3f` thereafter.

### Code Quality

- **Scope of the diff** (`git diff --name-only 63916e1..6d6ea3f`, `63916e1` = merge-base with
  `main`): code changes are confined to `body-layer/` (`src/belief/{groups,speech,callouts,
  contacts,crew_console}.py`, `src/perception/object_model.py`, their tests). Plans, agent-memory
  and `body-layer/ROADMAP.md`/`BACKLOG.md` are the only other touched paths. One subproject to
  verify.
- `body-layer/.venv` did not exist in the worktree; built fresh (`python3 -m venv .venv`, then
  `ruff`/`mypy`/`pytest`/`pyproj` installed). All four commands run from inside `body-layer/`:
  - `.venv/bin/ruff format --check src tests` → **113 files already formatted**
  - `.venv/bin/ruff check src tests` → **All checks passed!**
  - `.venv/bin/mypy src` (cwd `body-layer/`, per the CWD-only config-discovery note) → **Success:
    no issues found in 53 source files**
  - `.venv/bin/pytest tests -q` → **1367 passed, 4 xfailed** — matches the task's expected count
    exactly.
- `git diff 63916e1..6d6ea3f -- body-layer/src` grepped for `print(`/`TODO`/`FIXME`/`XXX`/
  `pdb.set_trace`/`breakpoint(` in added lines — **none found**.
- `git status --porcelain` is clean (confirmed before and after this gate's own doc edits, which
  are staged/committed below).

### Scope & Correctness

- Implementation matches `plans/group-cohesion-redesign/plan.md` (Stages 1-3 all present:
  `CohesionBackstop`/`EAGER` infantry release, `installation_component`/500 m cap on the corrected
  key, the six-branch delta taxonomy) — confirmed by Reviewer's two full reads, re-confirmed by
  reading the plan directly against `review.md`'s findings above.
- One deliberate plan deviation, already flagged by the implementer and Reviewer rather than
  silently patched: the plan's Stage 2 acceptance wording ("S-300 forms one four-member group")
  is stale against the plan's own §1 finding that narrowed `installation_component` off
  `OP_LRSAM`; the real S-300 ground-truth trace forms a 3-member cluster + 1 isolated component
  instead, which is the *correct* behaviour under the settled design, not a regression.
- No invariants violated: no-omniscience boundary unchanged (Security's deep analysis confirmed
  all composition/delta code reads only from already-tracked `Contact`/`member_facts`, never
  fabricates a member); single-player scope untouched; module independence untouched (no new
  cross-subproject import).
- `git status --porcelain` clean — no untracked new files outside this gate's own additions.

### Testing

- Core logic tested: cohesion-policy cases, kind-coherence/installation cases (including the
  regression pin for the `OP_SRSAM`-conflation bug found mid-revision), all six delta-taxonomy
  branches, and a real-sortie-ground-truth replay (`test_real_s300_site_ground_truth_geometry_
  forms_a_three_member_cluster`).
- Tests are meaningful: Reviewer's round-1 pass found two defects by *running* the renderer, not
  reading the assertions, and both were traced to shape-only assertions (`"in" not in
  speech.text`) rather than literal-string checks; round 2 confirmed every surviving composition
  assertion in scope now pins the literal rendered string (grepped directly, not taken on the
  implementer's word).
- No existing tests broken: baseline was 1351/4 at the branch's fork point; 1367/4 now, net +16
  tests, 0 regressions.

### Documentation

- Reviewer findings addressed: both Round-1 required fixes (indefinite-article defect,
  undifferentiated-member aggregation) resolved in Round 2, re-verified by the Reviewer actually
  running the fixed code, not just reading the diff. Round 2 verdict: APPROVED, no new findings.
- Non-obvious behaviour explained: module docstrings updated per the plan's Stage 4 (the
  `installation_component` vs `op_class` distinction and why `AIR_DEFENSE_INSTALLATION_CLASSES`
  was replaced); `body-layer/ROADMAP.md` carries the milestone narrative in full.

### Security

- `plans/group-cohesion-redesign/security-review.md`: **APPROVED** (deep analysis, post-Reviewer).
  No new dependency, no widened attack surface, no path that fabricates a spoken member. (This
  feature's own plan — not a change-request branch — so a plan-stage security review would
  normally also be expected; it is folded into the architect/explore chain this plan describes
  rather than a separate file, consistent with `plans/group-undermerging/debug.md`'s debug-fix
  origin. Not flagged as a gap — the deep-analysis APPROVED is the gating document here.)

### Performance

- `plans/group-cohesion-redesign/performance.md`: **APPROVED — MONITOR**. `_cluster_contacts`
  stays in its pre-existing O(n²) complexity class (a few extra dict lookups per pair); the real
  long-sortie growth risk (`ContactStore` never pruning) is pre-existing, not introduced by this
  diff, and is now tracked as `BL-B23` in `body-layer/BACKLOG.md` rather than left as a review
  comment. No blocking finding.

### Verdict: PASS (mechanical gate)

All four mechanical checks pass at the exact expected counts. Reviewer, Security and Performance
have all signed off. **This PASS is the fixture/static-review gate only** — see "Acceptance
boundary" below and the published test card for what it structurally cannot verify.

---

### Acceptance boundary — what this PASS cannot see

Every check above is a fixture, unit, or static-review pass. None of them can observe:

- Whether the *right* contacts merge in a real, continuously-moving scene rather than a
  hand-placed synthetic one.
- Whether the 500 m installation cap and the `AIR_DEFENSE_OP_CLASSES` membership guess — both
  named by the plan itself as one-source-of-evidence calls — hold up against a real mission's
  unit placement.
- Whether the delta taxonomy's rendered lines land correctly *by ear*, under cockpit task load,
  rather than merely rendering the correct string in a test assertion.

The project's own worked precedent for exactly this gap: the F10 command vocabulary passed DoD on
fixtures (2026-09-16), and the next sortie found `Scan` driving the 9K113 sight instead of this
project's own naked-eye perception (a fixture cannot detect the wrong subsystem being driven
correctly), and `Cancel Task` speaking a raw task id aloud (only a defect when a human *hears*
it — correct as text in a log). This feature's mechanical PASS carries the same boundary: a
fixture pass is not a flight pass.

Live acceptance is tracked as debt, not a blocker — see `body-layer/ROADMAP.md`'s live-acceptance
debt list, new entry for this branch — per the project's "never block a merge on live acceptance
the user cannot currently perform" posture. **Not merged by this gate** — the user's acceptance
call (test now, or merge ahead of the flight and track it as debt) is theirs to make; see the
published acceptance card.
