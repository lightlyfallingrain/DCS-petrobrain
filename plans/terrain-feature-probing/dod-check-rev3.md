# Definition of Done — terrain Stages 3a-5 (Revision 3)

Branch `feature/terrain-callout-stages-345`, expected tip `3345696`, fork point from `main` at
`947895d`. Verified sha confirmed via `git rev-parse HEAD` inside a detached-HEAD checkout of the
branch tip in this worktree (the branch itself is checked out in the main repo checkout, so the
worktree's own `HEAD` landed on `main`/`0a8c86c` on creation — not verified against; see
`AGENTS.md` rule 4). `git merge-base main feature/terrain-callout-stages-345` confirmed `947895d`,
matching the dispatching task's stated base.

## Code Quality

**Mechanical checks, both touched subprojects**, run from a `git archive feature/terrain-callout-
stages-345 | tar -x -C <scratch>` snapshot (not the worktree, which was on `main`), using the main
checkout's `<subproject>/.venv/bin/{ruff,mypy,pytest}`, cwd inside each subproject's own snapshot
directory (`pyproject.toml`'s `pythonpath = ["src", "../world-model/src"]` resolves relative to
pytest's own rootdir — confirmed the body-layer run actually imported `world_model` from the
snapshot's `world-model/src`, not any installed copy, by checking that bare `import world_model`
fails outside that pythonpath wiring).

| subproject | ruff format | ruff check | mypy --strict | pytest |
|---|---|---|---|---|
| world-model | clean (118 files) | All checks passed | Success, 72 source files | **548 passed, 3 skipped** |
| body-layer | clean (114 files) | All checks passed | Success, 53 source files | **1434 passed, 4 xfailed** |

Both match the task's expected figures exactly. body-layer's count is 20 above `main`'s own
1414/4 baseline (new tests for Stages 3a-5's wiring).

- No unhandled errors/panics found in the diff (`git diff 947895d 3345696 -- world-model/src
  body-layer/src`).
- No debug output or TODO/FIXME/print/pdb/breakpoint markers introduced by this diff (grepped the
  full diff, zero hits).

## Scope & Correctness

- Implementation matches Revision 3 of `plans/terrain-feature-probing/plan.md` — divide counter
  (`query/divides.py`), `closest_point_on_feature`/`bearing_deg` (`store/reader.py`,
  `query/describe.py`), Stage 5 displacement wiring in the callout path.
- No unplanned scope added. BL-B14 (world-model half) correctly marked unblocked-not-done, per
  the plan's own scoping.
- No invariants violated: no-omniscience boundary untouched (terrain qualifier is computed from
  world-model query results already flowing through the existing describe/enrichment path, not a
  new ground-truth leak); DCS-authoritative-geometry invariant untouched (query-time divide count
  reads the already-built, already-gated `ridge`/`valley` store rows, no theatre rebuild).
- All new files staged: `git status --porcelain` against `3345696` is clean (confirmed inside the
  detached checkout before any of this gate's own edits).

## Testing

- Core logic (`divides_between`, `closest_point_on_feature`, `bearing_deg`, the Stage 5 dominance/
  displacement rule) is covered by `world-model/tests/test_query_divides.py` (140 new lines) and
  the corresponding body-layer tests added during Reviewer round 2 (closed the round-1 "zero
  tests for Stage 5 wiring" required fix).
- Reviewer round 2 re-ran the disable-the-mechanism proof itself (review-rev3.md) rather than
  trusting the implementer's claim — tests are load-bearing, not decorative.
- No existing tests broken: both counts are at-or-above their respective baselines, no new
  failures.

## Documentation

- Reviewer required fixes addressed: round 1's sole required fix (Stage 5 wiring had zero tests)
  closed in round 2, which re-verified it directly rather than accepting the fix on description.
- Non-obvious behavior (the dominance rule, the >=2-divides-means-silence choice, the four
  first-guess constants) is documented in `plan.md` Revision 3 and the implementation docs; no
  `NOTES.md` entry was needed beyond the harvest below.

## Security

- `security-plan-review-rev3.md` — APPROVED.
- `security-deep-analysis-rev3.md` — APPROVED, no required fixes.

## Performance

- `performance-rev3.md` — APPROVED, MONITOR. Filed `BL-B26` (group tick gathers member facts up
  to 3x per tick) as a pre-existing finding, escalated to Architect rather than patched inline —
  confirmed filed in `body-layer/BACKLOG.md` with the next-unused ID (BL-B26, after BL-B25) and
  that BL-B20 through BL-B25 were not renumbered.

## Verdict

**PASSED.** All mechanical, scope, testing, documentation, and security/performance gates hold.
Not merged — this role does not merge without the user's acceptance sign-off.

## Acceptance boundary — what fixtures structurally cannot reach

Every check above ran against fixtures and a real-but-static `syria-full.sqlite` read. None of it
can answer whether the qualifier fires *where the pilot would say it* or stays silent where they
wouldn't — that is a perceptual judgment fixtures cannot encode. Two risk directions specifically
require a human ear: over-naming (the terrain qualifier now displaces the "near X" fragment, so a
wrong qualifier doesn't just add noise, it removes something that might have been more useful),
and whether the four shipped constants (300 m, 2x, 400 m, >=2-divides-silence) feel right in a
real cockpit. Fixture testing (the Baalbek real-store read: 1 divide across the flank at 8 km, 0
along the valley floor to 16-20 km) only confirms the mechanism does what the plan predicted on
that one geometry — not that the prediction itself is what a pilot wants to hear.

## Milestone completion question

Does this change what the next milestone should be, or invalidate a downstream assumption?
**No invalidation.** Stages 3a-5 close the last unbuilt part of the landform consumer line that
`WM-B6`'s reopening condition named. `WM-B5` (valley boundary extraction — stored lines are
centre-lines, not extents) remains the named fallback if the dominance rule's cheap approximation
proves too crude in the air; that is a live question the pending sortie (riding along with the
contact-report-flood/redundant-group-disclosure flight) is positioned to answer, not something
this gate can resolve. `BL-B26`'s 3x-per-tick gather is pre-existing and does not change scope
here; it is correctly left to Architect rather than folded into this fix.

## Live acceptance

Not waived — deferred. Recorded on `body-layer/ROADMAP.md`'s "Live acceptance debt" list, riding
along with the already-pending `fix/contact-report-flood`/`fix/redundant-group-disclosure` sortie
rather than scheduling a separate flight. Acceptance card published: updated
https://claude.ai/artifact/VJZnmdF3aqxhVGZea3iKN4 (source: `docs/acceptance/
2026-10-05-contact-report-flood-sortie.md`, sections 6-7 and the updated bring-back list).

## NOTES.md harvest

See `NOTES.md` diff in this same commit. One candidate insight added (see below); others
reviewed and judged either obvious from the code or already covered by existing entries.
