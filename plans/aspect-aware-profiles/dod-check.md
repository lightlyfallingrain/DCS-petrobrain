# DoD Check: aspect-aware-profiles

Branch: `feature/aspect-aware-profiles`. Reviewer verdict: APPROVED WITH MINOR FIXES
(`plans/aspect-aware-profiles/review.md`); both required fixes confirmed landed in `232ecc6`
(per-field provenance comments on the two S-300 rows, including the 64H6E height's circularity
warning) — read the actual diff, not just the review's claim.

## Scope of touched subprojects

`git diff --name-only $(git merge-base main feature/aspect-aware-profiles) feature/aspect-aware-profiles`:
only `body-layer/` (src, tests, research, plans, and two agent-memory files) is touched.
`world-model/` and `aircraft-layer/` are untouched by this branch — the three untracked files under
`world-model/` (`run.sh`, `syria-full-build.log`, `syria-theatre-unfiltered.osm.pbf`) predate this
work and are out of scope; left unstaged per instruction.

## Code Quality — PASS

All run myself, from `body-layer/`, using `body-layer/.venv/bin/python`:

```
$ .venv/bin/python -m ruff format --check src tests
81 files already formatted

$ .venv/bin/python -m ruff check src tests
All checks passed!

$ .venv/bin/python -m mypy src
Success: no issues found in 38 source files

$ .venv/bin/python -m pytest tests -q
........................................................................ [  9%]
...(...)...
769 passed in 9.21s
```

769 passed, matching both the implementation notes' and the review's claim. No debug output, no
TODOs introduced (grepped the diff; none). No unhandled errors in the new code path — the `None`-
dimensions branch returns early and unconditionally before any trig runs.

## Scope & Correctness — PASS

- Implementation matches `plans/aspect-aware-profiles/plan.md`, including the corrected
  (post-coordinator-review) design: `size_m` stays a required scalar, dimension fields are optional
  and default `None`, ~148 unmigrated rows are untouched source text (confirmed independently by
  the reviewer's diff-based check and re-confirmed here: `git diff main...HEAD -- object_model.py`
  shows only additions in the table region plus the two S-300 rows).
- No unplanned scope: `clustering.py` has zero diff (grep + `git diff --stat` confirm), still reads
  the plain `size_m` field — this was an explicit, stated scope cut in the plan, not a silent gap.
  **Verified, not just asserted, that this is still benign**: the two S-300 rows previously fell
  back to the *generic 5.0 m profile* (no table entry existed for them before this feature), so
  `clustering.ClusterCandidate.size_m` for these two types actually improved incidentally (5.0 m →
  24.0 m / 13.2 m) rather than regressing. No new hazard introduced by leaving clustering scalar.
- No invariants violated: DCS-authoritative-truth, no-omniscience, and provenance/uncertainty
  invariants are all directly reinforced here (the tri-state `heading_true_deg` never guesses; the
  two estimated S-300 figures are flagged in-code, not silently asserted as fact).
- All new files staged: verified via `git status --porcelain` post-check (see below).

## Testing — PASS

24 new tests. Confirmed meaningful, not decorative: the 45°/135° trig-projection test asserts
against the actual `sin`/`cos`-computed value; the no-dimensions regression guard and the
unmigrated-row sweep are both parametrized across 7 angles including 45° — exactly the class of
test that would have caught the withdrawn cubic-fallback bug and would fail immediately if it
reappeared. `test_vision_calibration.py` confirmed unedited and still passing (46/46, part of the
769) — its fixture objects never touch the two migrated S-300 rows and never carry a heading, so
`apparent_extent_m` returns `size_m` unchanged for them by construction, not by accident.

## Documentation — PASS

Reviewer's two required fixes addressed at the code level (verified by reading `232ecc6`'s diff
directly, not the review's summary): per-field `# SOURCED` / `# ESTIMATE` comments on both S-300
rows, and the 64H6E height's circularity warning ("cannot be treated as independent evidence...
agreement here is partly built in") now lives in `object_model.py` itself, not only in the research
doc. `plans/aspect-aware-profiles/implementation.md` and the two research docs are complete and
dated.

## Security — N/A

Project `CLAUDE.md` currently exempts `security` and `performance-reviewer` for this phase
(offline, single-user, no hot path, no untrusted input). Not invoked, per that exemption.

## Working tree

```
$ git status --porcelain
 M .claude/agent-memory/architect/MEMORY.md
 M .claude/agent-memory/implementer/MEMORY.md
?? .claude/agent-memory/architect/feedback_trig_fixed_point_proof.md
?? .claude/agent-memory/implementer/project_aspect_aware_profiles.md
?? world-model/run.sh
?? world-model/syria-full-build.log
?? world-model/syria-theatre-unfiltered.osm.pbf
```

The four `.claude/agent-memory/{architect,implementer}/*` changes are this feature's own
Architect/Implementer memory writes (the trig-fixed-point-proof lesson and the aspect-aware-profiles
implementation summary) — legitimate feature output, staged as part of DoD closeout below. The
three `world-model/` files are pre-existing, unrelated to this branch, and are **not** staged, per
instruction.

## Milestone-completion question (root CLAUDE.md)

**Does this change what the next milestone should be, or invalidate a downstream assumption?**

- **Threshold recalibration (`LOWRES`/`MEDRES`) — was deferred pending aspect. Aspect has landed.
  Still blocked, for a different reason.** `body-layer/research/2026-09-21-first-cones-sortie-
  results.md`'s own post-aspect section measured the fix against the live 2026-09-21 sortie data:
  presence went from 4× short to roughly right (S-300 mast: 1665 m → 8000 m against an observed
  6700 m), but classification range is now split by *object kind*, not by threshold — still short
  for both radars (~2.6× short, down from 13×) while ~20% too generous for vehicles (median 0.82×)
  in the same tier. No single `LOWRES`/`MEDRES` pair can absorb an error that has opposite signs by
  object kind. The doc's own conclusion — "this strengthens the case for waiting" — names a missing
  "silhouette distinctiveness" term as the likely cause and explicitly declines to fit constants
  around it. **So: not unblocked. Re-blocked by a newly-surfaced gap** (distinctiveness), not the
  same gap aspect was meant to close. This should be recorded as the reason, not silently left as
  "still deferred" with the old rationale.
- **Detection-cones slice 2 (scanning/dwell/attention)** — per `body-layer/ROADMAP.md`, slice 2 is
  gated on the ED-internals research deep pass, not on aspect. Aspect landing does not unblock it.
  It does, however, add a second open question slice 2 (or the eventual classification-range design)
  will need to account for, and this is the sharpest thing in this report so it is stated plainly
  and should be carried into whatever plan/roadmap section actually scopes slice 2, not left only
  here: **distinctiveness is a silhouette property, not a scanning/dwell one, and dwell time is the
  obvious knob that would appear to fix it without actually doing so.** A mast is identifiable at
  4.5 km because nothing else on a battlefield looks like it, not because more dwell time resolved
  detail on it — tuning `MEDRES` or a future dwell-time constant against the radar rows would
  silently absorb a shape error into a scanning-behavior constant, produce a number that happens to
  work for radars and is wrong for vehicles, and read as if slice 2's attention model were doing its
  job. This is a real trap, not a hypothetical one — flag it explicitly when slice 2 is next scoped,
  not only in this report.
- **`clustering.py`'s scalar `size_m` proxy** — verified above, not just asserted: still benign,
  and incidentally improved for the two migrated rows (5.0 m generic fallback → real 24.0 m /
  13.2 m). No action needed.

## Acceptance boundary — what this feature's fixtures structurally cannot reach

The fixture/unit-test suite proves the formula is correct and that unmigrated rows are provably
unaffected. It **cannot** prove the formula is *calibrated* — no fixture encodes what a crewman
actually sees at a given aspect, only what the code computes. That gap is exactly what the
2026-09-21 sortie data (already flown, already analyzed) partially closes for presence, and
explicitly does not close for classification, per the distinctiveness gap above. A second,
independent structural gap: **the 64H6E height figure is circular** (estimated from the same
sortie whose numbers "validate" it) — any acceptance claim that cites the 64H6E's post-fix presence
number as confirmation is partly checking the model against its own input. The 40B6M mast height
(24 m, independently sourced) does not have this problem and is the cleaner data point.

## Live acceptance debt

This is not new sortie-dependent debt in the usual sense — the relevant sortie (2026-09-21) has
*already been flown and analyzed*, and its results are folded into the research doc above. What
remains open is not "fly it," it's "the recalibration this was meant to unblock is still blocked,"
which is tracked as a plan/backlog state, not a `[ ]` sortie item. No new entry added to
`body-layer/ROADMAP.md`'s "Live acceptance debt" list for this feature specifically — **there is no
pending flight this feature's own formula is waiting on**, narrowly. Broader than the formula: the
user is gathering binocular-optic observations right now, and those will exercise aspect further —
not as a gate on this merge, but as the next real evidence. The two aspect-corrected S-300 rows
against the ~148 uncorrected rows form an accidental control group for that dataset, with one
caveat already established above: only the 40B6M side of that pair counts as independent evidence,
since the 64H6E's height is circular with the very sortie it would be checked against. (If a future sortie is flown to gather the aspect-tagged
binocular dataset the research doc calls for, that is new data collection, not confirmation of
*this* feature, and belongs to whatever milestone consumes it, most likely the eventual
distinctiveness/threshold work.)
