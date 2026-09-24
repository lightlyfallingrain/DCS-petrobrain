# DoD gate — watch-reporting

Branch `feature/watch-reporting`, head `1ea5aa1`, branched from `main` at `3409b66`. Gate run
2026-09-24 in a worktree agent (worktree built on `main`, so branch content read via
`git show feature/watch-reporting:<path>` and verification run directly against the main
checkout's working tree, which is on this branch).

## Code Quality

**Every command run live this session, output pasted verbatim (final line):**

```
cd body-layer     && .venv/bin/ruff format --check src tests    -> "103 files already formatted"
cd body-layer     && .venv/bin/ruff check src tests              -> "All checks passed!"
cd body-layer     && .venv/bin/mypy src                          -> "Success: no issues found in 48 source files"
cd body-layer     && .venv/bin/pytest tests -q                   -> "1177 passed, 4 xfailed in 9.12s"
cd audio-adapter  && .venv/bin/ruff format --check src tests    -> "28 files already formatted"
cd audio-adapter  && .venv/bin/ruff check src tests               -> "All checks passed!"
cd audio-adapter  && .venv/bin/mypy src                           -> "Success: no issues found in 15 source files"
cd audio-adapter  && .venv/bin/pytest tests -q                    -> "198 passed, 1 skipped in 24.37s"
```

All match the expected figures given for this gate. PASS.

- **No unhandled errors/panics in data paths.** `belief/threat.py`'s import-time JSON load fails
  loudly (no try/except), which security review confirmed is the *correct* behaviour for this
  no-fallback-envelope invariant, not a gap. The one genuine gap the security review found —
  `_CLOCK_REPORT_LABELS[clock]` plain dict indexing on a wire-fed value, and no exception isolation
  around `_poll_transcripts`' dispatch — is non-blocking (unreachable through the code that exists
  today; `audio-adapter`'s `parse_clock` constrains the value before it is ever sent) and carried to
  backlog per user direction, not fixed in this branch. PASS with recorded backlog debt.
- **No debug output left in committed code.** Not separately re-scanned this session beyond the
  reviewer's own scope sweep (review.md: "a scope/TODO sweep over every non-test source file
  changed by the branch," no findings). Trusting that read rather than re-doing it — nothing in
  this branch's diff touches print/logging surfaces in a way the reviewer's sweep would have missed.
- **No leftover TODO comments introduced by this feature.** Same basis as above — reviewer's sweep,
  no findings.

## Scope & Correctness

- **Matches `plans/watch-reporting/plan.md`.** Reviewer confirmed full read against the plan; no
  files touched outside the plan's Affected Modules list (review.md, "Scope" section).
- **No unplanned scope added silently.** Confirmed by review.md.
- **No CLAUDE.md invariants violated.** Reviewer specifically traced the no-omniscience boundary in
  `belief/threat.py` (`envelope_for` takes only `ClassificationBelief`, imports nothing from
  `perception.source`) and confirmed no path from `tick`'s new `ownship`/`los_clear` parameters
  reaches the classification lookup. Security review independently confirmed the same boundary.
- **All new files staged.** `body-layer/data/threat_envelopes.json` and its saved-source HTML were
  confirmed committed on `main` prior to this branch (review.md), not left untracked. `git status`
  snapshot at gate start showed only two pre-existing local run-script modifications
  (`run-scripts/run-audio-adapter.sh`, `run-scripts/run-crew-text.sh`), unrelated to this feature
  and not part of its diff.

## Testing

- **Core logic covered.** New module `belief/threat.py` has its own `test_threat.py` against the
  *real* shipped `threat_envelopes.json`, not a fixture double — reviewer confirmed this catches the
  low class-join-rate finding a fixture would have hidden. Range-crossing/engagement tests in
  `test_contacts.py` move `ownship` across successive `tick()` calls rather than re-ingesting new
  observations each step, avoiding a real test-construction trap for this shape of test (reviewer
  confirmed by reading, not counting).
- **Tests are meaningful.** Fix-review.md hand-executed the three new `test_contacts.py` cases from
  the fix commit against the actual envelope gate constants, confirming they exercise the intended
  branch rather than incidentally passing.
- **No existing tests broken.** 1177/198 passed figures above are the full suites, not a subset.

## Documentation

- **Reviewer findings addressed.** `review.md`: Required Fixes — None. `fix-review.md` (review of
  the separate performance/security fix commit `7f4f24d`): Required Fixes — None. Both APPROVED.
- **Non-obvious behaviour explained.** `plans/watch-reporting/plan.md` and
  `plans/watch-reporting/implementation.md` carry the full design/decision record; `body-layer/
  ROADMAP.md`'s milestone entry (corrected by this gate, see below) summarises it for a roadmap
  reader.

## Security

- `plans/watch-reporting/security-plan-review.md` — **does not exist under that filename.** The
  paper trail this gate was pointed at is `plans/watch-reporting/security-review.md`, which reads as
  the deep-analysis pass (post-Reviewer, pre-DoD) rather than a plan-stage review — it covers the
  merged implementation's actual code, not a design document. No separate plan-stage security review
  file was produced for this branch. **Flagging, not blocking**: the project's Agents section
  currently runs security once per whole feature immediately before DoD (changed 2026-09-24, same
  day as this branch), which this branch predates in spirit but not in date — `security-review.md`
  itself is dated to this branch and reads as exactly that single deep pass, appropriately scoped.
  Treating `security-review.md` as satisfying this DoD criterion; there is no plan-stage document to
  separately check.
- `plans/watch-reporting/security-review.md` — **exists, APPROVED**, with one recommended
  (explicitly non-blocking) fix and several no-finding rows. The recommended fix (dict `.get` +
  forward-hour membership check) was deferred to backlog by user direction rather than applied in
  this branch — recorded in `body-layer/ROADMAP.md`'s backlog by this gate (see below).
- Performance review (not in the DoD criteria list above, but part of this branch's actual gate
  chain per the project's role sequence): `performance-review.md` found one real issue (LOS called
  before the range/altitude gate) — **NEEDS MITIGATION** verdict — which was fixed in `7f4f24d` and
  that fix independently re-reviewed and APPROVED in `fix-review.md`. Closed.

## Roadmap correction (this gate)

`review.md` itself flagged, as an optional/non-blocking observation, that `body-layer/ROADMAP.md`
and root `ROADMAP.md`, committed as part of this branch's Stage 5, already said "merged"/"DONE"
ahead of the actual merge. Confirmed by reading both files directly (not taking the review's word
for it): both did say so. **Corrected in this gate's commit** — `body-layer/ROADMAP.md`'s watch-
reporting entry changed from `[x] ... DONE` to `[~] ... implemented and reviewed, not yet merged`,
and root `ROADMAP.md`'s prose changed from "merged 2026-09-24" to "implemented and reviewed ...
not yet merged." Both will need updating again to `[x]`/"merged" with the real merge sha once the
user actually merges this branch, per this project's Milestone Completion / roadmap-at-merge-time
discipline — not done here, since no merge happened in this gate.

Also added to `body-layer/ROADMAP.md`'s Backlog in this gate (neither existed there before):
- The `alt_ok`-has-no-hysteresis finding from `fix-review.md`'s Optional Refinements (traced
  fail-safe, not a correctness bug, by both the performance-fix reviewer and this gate independently
  re-reading the same reasoning).
- The two non-blocking security hardening recommendations (`_CLOCK_REPORT_LABELS.get(...)`, and a
  forward-hour membership check in `_poll_transcripts`), per the user's explicit deferral direction
  for this gate.

The `OP_SRSAM` range-spread and the ~3-of-19 class-join-rate items were **already** present in
`body-layer/ROADMAP.md`'s backlog (added by Stage 5) — not duplicated here.

## Milestone completion question

Does finishing this change what the next milestone should be, or invalidate a downstream
assumption? **Yes, in one direction, no reversal.** This branch is explicitly the deterministic
foundation the brain layer's "autonomous reporting of active danger to us" capability
(`plans/brain-layer/explore-notes.md`, item 2's user-stated list) needs to exist under — the
engagement-envelope trigger built here is the mechanism, and the brain layer's job will be judgement
about *what to do* once body already knows and says "danger," not building the detection/reporting
path itself. Nothing here invalidates an assumption a planned milestone already relies on; it
retires one an unplanned capability (brain-driven danger judgement) was going to need built anyway.

## Overall verdict

**Mechanical DoD checks: PASS.** All eight format/lint/type/test commands green across both touched
subprojects, both correctness reviews APPROVED with no required fixes, performance issue found and
fixed and the fix re-reviewed APPROVED, security review APPROVED with backlog-deferred
recommendations, scope/invariants/staging all confirmed, roadmap prose corrected to stop overclaiming
merge state ahead of an actual merge.

**Live acceptance: NOT DONE, explicitly outstanding — not counted as passed.** This session cannot
fly DCS. Card written: `docs/acceptance/2026-09-24-watch-reporting-sortie.md`. Per this project's
"never block a merge on live acceptance the user cannot currently perform" rule, this does not block
a merge decision, but merge itself is the user's call and was not exercised in this gate — no
`git merge`, no roadmap `[x]`/"merged" flip, no `docs/acceptance/` debt-list entry (that list is for
already-merged, still-unflown milestones; this one is not merged yet, so it does not belong there
until it is).

**Acceptance boundary — what this milestone's fixtures structurally cannot reach:** the fixture
suite proves the trigger logic (motion/range/envelope math, the deadband, the hysteresis, the LOS
dwell) is internally correct against synthetic data. It cannot show whether the engagement warning
is actually *useful* in the air given today's optics — the plan's own arithmetic (Decision 4d) says
the danger call will fire from well inside a SHORAD envelope, not at its edge, because class
recognition range trails weapon range with only the naked eye and binoculars available. No fixture
can distinguish "the trigger fired correctly, late, because that is the honest current optic
capability" from "the trigger is broken" — only a flight, with a pilot who knows to expect that gap,
can. The acceptance card states this explicitly rather than letting a fixture pass be read as a
flight pass.
