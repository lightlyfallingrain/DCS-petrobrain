# Definition of Done — X-B29 DCS-driven line of sight, Stages 1-3

Branch: `feature/dcs-driven-los`, tip `43520086c2ab3af25ed97b6e82d2f442c115a48c`.
Fork point: `be1273433219cd6844094ded9126621a26d4e0bc` (`main`, same sha the dispatch named `be12734`).
Verified against this exact tip — this worktree's own commit history was checked out on a new
local branch (`dod-check-dcs-driven-los`) pointed directly at the feature tip, after the first
`git rev-parse HEAD` landed on `main` (the branch was already checked out in the main checkout, so
the worktree's default landing spot was `main`, which predates this feature entirely — the known
trap `AGENTS.md` rule 4 documents). `main`'s own current tip has since moved on with unrelated
bookkeeping (elevation-cost-probe writeups, other feature merges) that do not touch this feature's
files.

## Gates already passed (not redone here)

Architect (two revisions) → Security plan review APPROVED (2 required fixes, both implemented) →
Implementer → Reviewer APPROVED (full read) → Security deep analysis APPROVED (no required fixes) →
Performance APPROVED — MONITOR. Reports: `plans/dcs-driven-los/{plan.md, security-plan-review.md,
implementation.md, review.md, security-deep-analysis.md, performance.md}`.

## Mechanical checks (this gate's own run)

Run directly on the feature branch tip (`dod-check-dcs-driven-los` branch, same commit), each
subproject's own `.venv` resolved from the main checkout:

| subproject | ruff format --check | ruff check | mypy --strict | pytest | expected |
|---|---|---|---|---|---|
| aircraft-layer | pass (56 files) | pass | pass (21 files) | **252 passed** | 252 — match |
| body-layer | pass (115 files) | pass | pass (53 files) | **1457 passed, 4 xfailed** | 1457/4 — match |
| world-model | pass (118 files) | pass | pass (72 files) | **550 passed, 3 skipped** | 550/3 — match |

All three match the implementer's and Reviewer's claimed counts exactly. `main`'s own baselines
(210 / 1440+4 / 548+3) are strictly lower on every line — this is not a stale-worktree false pass.

## Code quality

- No `TODO`/`FIXME`/debug `print`/bare `except: pass` introduced by this feature (`git diff
  <fork-point>...<tip> -- '*.py' '*.lua'` grepped for the usual markers — none in added lines).
- The two Security-required fixes (NaN/Inf-guarded clamp, one-`dostring_in`-call-per-frame
  coalescing) are both implemented and independently re-verified by Reviewer and Security's deep
  pass, not merely re-trusted.
- `MAX_SIGHTLINES_PER_CALL = 128` exists as two independent literals (outer Lua local and inside the
  `LOS_CODE` string literal) with no mechanical drift guard — Reviewer flagged this as an optional
  refinement, not blocking. Carried forward, not re-litigated here.

## Scope & correctness

- Implementation matches `plans/dcs-driven-los/plan.md`'s revised (2026-10-05) scope exactly:
  cone-scoped Hook script computing both building and terrain LOS, the look-direction command
  channel, collector/API/client plumbing, body-layer's live-first/offline-fallback join at gate 4,
  belief carrying the observed boolean (the old `_threat_has_los`/`LOS_UNCERTAINTY_SAMPLES`
  mechanism deleted, not patched around).
- **No unplanned scope**: building occlusion (X-B30) was explicitly folded into this slice by user
  direction (2026-10-05, "yes please"), not added silently — the plan's own §ion records the
  decision and its caveat (the `through_buildings` aimed-check vs. broader-sweep discrepancy,
  stated as unresolved, not swept under).
- No-omniscience invariant holds: LOS stays a perception-side fact joined onto belief; belief never
  computes it. Confirmed independently by both Reviewer and Security's deep analysis via a traced
  end-to-end read of the boolean's path, not asserted on the plan's word.
- All new files are staged — `git status --porcelain` on this exact tip is clean (confirmed before
  any edit here).

## Testing

- 42 new aircraft-layer tests, 17 new body-layer tests, 2 new world-model tests — enumerated in
  `implementation.md`'s "Tests Added," each tied to a specific behavior (wire parsing, malformed
  payloads, the live-first/offline-fallback short-circuit via a spy that fails if the offline
  primitive is consulted when it shouldn't be, the overwrite-not-fold semantics on `Contact`,
  fail-open on missing/stale verdicts). Not decorative — Reviewer independently re-ran the clamp's
  naive-failure-mode case under a local Lua interpreter rather than taking the test's word for it.
- No existing tests broken; four pre-existing `los_clear`-callable tests were rewritten (not
  patched) because the plan's own deletion of the `los_clear` parameter required it — a required
  rewrite, not an unplanned one.
- Lua syntax validated (`luac5.1 -p`) on both the outer Hook script and the extracted `LOS_CODE`
  string literal.

## Documentation

- Reviewer findings: **zero required fixes** — both items raised were explicitly optional
  (duplicated `128` literal; fallback-visibility observability), neither blocking, both carried
  forward as stated rather than silently dropped.
- Non-obvious behavior is explained in code/plan rather than needing a NOTES.md entry at this
  stage: the 12 m terrain-tolerance test-path-only boundary is documented at its own definition site
  in `world-model/src/query/line_of_sight.py` and in `plan.md`'s "What happens to the 12 m tolerance
  and the probe grid" section (corrected with a forward pointer, original text preserved beneath
  it, per the mid-task correction note in `implementation.md`).

## Security

- `plans/dcs-driven-los/security-plan-review.md` — APPROVED, 2 required fixes, both implemented.
- `plans/dcs-driven-los/security-deep-analysis.md` — APPROVED, no required fixes. One low/low
  observability gap noted (no alert on silent full-session fallback to the offline primitive),
  explicitly not blocking.

## Milestone Completion question (root `CLAUDE.md`)

**Does this change what the next milestone should be, or invalidate a downstream assumption?**

Yes, in three concrete ways:

1. **`WM-B8` (fixture-scale fine elevation grid) is now unblocked.** `WM-B7`'s original form
   (coarse-everywhere) was explicitly gated "do not start before `X-B29` lands" — that gate is now
   cleared. `WM-B7` was separately rejected the same day it was filed (user: offline accuracy vs.
   DCS is not achievable and not wanted) and replaced by `WM-B8`, which carries no such gate in its
   own text but exists *because* this feature demoted the offline primitive to fixtures-only. There
   is nothing further blocking `WM-B8` from X-B29's side.
2. **`fix/los-elevation-tolerance`'s unflown live-acceptance debt (world-model/ROADMAP.md,
   "Live acceptance debt") is now largely moot for the question it was tracking.** That debt entry
   exists to confirm, on a real sortie, that the 12 m tolerance (a) fixed the missed-AAA case and
   (b) doesn't silently mask genuinely ridge-hidden units. Once a live DCS LOS verdict exists for a
   unit, gate 4 never calls the tolerance-bearing primitive at all (`candidate.live_los_clear is not
   None` short-circuits it) — the question "does the live sortie now detect the AAA" gets answered by
   *this* feature's own Stage 4 sortie instead, via a cleaner mechanism than the tolerance. What
   remains of the original debt is narrower: whether the tolerance is still sensibly calibrated for
   the one path that still reads it (gate 4's fallback branch when the live feed is absent/stale, and
   fixtures/`WM-B8`) — a smaller, lower-stakes question than the one the debt entry currently states.
   Updated below rather than cleared outright, since nobody has yet flown confirmation that the live
   path actually resolves the missed-AAA geometry — that is Stage 4's own acceptance card, not
   something this gate can mark flown.
3. **Downstream of Stage 4's sortie, the probe-grid-as-live-LOS-source line of work (everything
   `X-B29`'s "original entry" text in `todo/backlog.md` reasoned about theatre-scale batched calls)
   is superseded in practice** — not by removing code, but because the live path this feature built
   is the thing that reasoning was describing. No further backlog action needed beyond marking
   `X-B29`/`X-B30` done; done below.

No assumption downstream milestones relied on is invalidated — body-layer's "must run with no live
DCS and no collector" hard requirement is explicitly preserved (the offline primitive stays as the
test/fixture path, demoted but not removed).

## Roadmap/backlog bookkeeping performed by this gate

- `todo/backlog.md` — `X-B29` and `X-B30` marked `[x]` done, done-entries added.
- `aircraft-layer/ROADMAP.md` — new Status entry for the Hook/collector/API/command-channel work
  (Stages 1-3).
- `world-model/ROADMAP.md` — the `fix/los-elevation-tolerance` live-acceptance-debt entry narrowed
  to what it still actually tracks (see Milestone Completion point 2); `WM-B8`'s entry gains a note
  that `X-B29` has landed and the gate it inherited from `WM-B7` is clear.
- `body-layer/ROADMAP.md` has no existing LOS-tolerance live-acceptance-debt entry to update
  (checked directly — the only entry of that kind lives in `world-model/ROADMAP.md`, not
  `body-layer/ROADMAP.md`; the dispatch's phrasing pointed at the wrong file for that specific
  item). `body-layer/ROADMAP.md` is otherwise unaffected by this feature's own scope.

## Acceptance boundary — what fixtures structurally cannot reach

Every test in this feature (aircraft-layer's 42, body-layer's 17, world-model's 2) runs against a
synthetic UDP payload, a fake clock, or a monkeypatched grid. None of them can observe:

- **Whether the `atan2`-derived heading/bearing convention inside `LOS_CODE` actually matches DCS's
  own Mission Scripting Engine convention.** If it is wrong, the symptom is a wedge that silently
  doesn't track where Petrovich is actually looking — a coverage *loss*, not a wrong detection (the
  plan's own stated safety property) — and no fixture can distinguish "wedge pointed correctly" from
  "wedge pointed at a fixed offset that happens to still catch the fixture's test geometry."
  Fixtures cannot manufacture DCS's own coordinate convention; only a flight can.
- **Whether `tonumber("nan")`/`tonumber("inf")` on DCS's bundled Lua/CRT actually behaves the way the
  clamp assumes.** The clamp is written to be correct under either outcome, but "written to be
  correct under either outcome" and "confirmed correct against the real runtime" are different
  claims, and only the second is acceptance.
- **Whether the per-frame look-direction socket poll produces any felt stutter.** No DCS-side Lua
  profiler exists in this environment; Performance's own verdict says this explicitly — "reasoned
  cheap by precedent, never measured."
- **Whether a building actually occludes a real unit in the live game** — the single highest-value
  new capability this feature claims. A fixture can assert that the join logic correctly ANDs
  `building_clear` and `terrain_clear` when both are present; it cannot assert that DCS's own
  `world.searchObjects`/`SEGMENT` call finds a real building between two real positions in the
  installed Syria terrain.
- **Whether the missed-AAA geometry from `plans/missed-aaa-detection/debug.md` now resolves without
  the 12 m tolerance** — this is precisely the live-vs-offline distinction the 12 m tolerance exists
  to paper over, and no offline fixture can stand in for the live DCS terrain it was built to
  approximate.

This is the same class of gap the worked example in this role's own brief names: fixtures proving
the code does what it says, against a subsystem (here, DCS's own LOS engine) that only a live
session can confirm is the one actually being asked.

## Verdict

**DoD: PASSED** on mechanical checks, code quality, scope, testing, documentation and security.
**Live acceptance: OUTSTANDING** — Stage 4's sortie (acceptance card, published separately) is the
only thing that can confirm the items in "Acceptance boundary" above. Per root `CLAUDE.md`'s
live-acceptance-debt convention, this is tracked as debt in `world-model/ROADMAP.md`, not a merge
blocker.

**No merge performed** — explicitly out of scope for this gate's dispatch. The main checkout stays
on whatever branch it was on; the user tests on `feature/dcs-driven-los` directly per the acceptance
card, or on `main` after a future merge.
