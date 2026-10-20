### Definition of Done Check: taking-fire-visible-shooter

**Verified at tip `629dc5abafcba896072c06e63fdb7cf7715bb335`** (`Security deep analysis:
taking-fire-visible-shooter — APPROVED`), branch `fix/taking-fire-visible-shooter`. This verdict
is scoped to that exact commit. `git rev-parse fix/taking-fire-visible-shooter` resolves to the
same sha — the branch ref is not lagging what was reviewed.

Diff vs. `main`'s merge-base (`1b777fe7`) also carries `docs/open-flight-tests-2026-10-20`'s own
docs commits up to `431b5598` (sortie-feedback/results docs, `BL-B83`) — expected per dispatch, not
this fix's scope, and not re-reviewed here (already its own cut).

#### Code Quality

| Check | Result |
|---|---|
| `ruff format --check src tests` (body-layer) | PASS — 155 files already formatted |
| `ruff check src tests` (body-layer) | PASS — all checks passed |
| `mypy src` (body-layer, `cd body-layer && .venv/bin/mypy src`) | PASS — 68 source files, no issues |
| `pytest tests -q` (body-layer) | PASS — 2248 passed, 4 xfailed, first run, no flake observed |
| Invariant scan (`.claude/skills/invariant-check`) | PASS — no-omniscience boundary, module independence, no `sys.path` hacks, `BINOCULAR_RANGE_MULTIPLIER` still retired, no stray `print()`, no bare `except:` all clean. Two pre-existing WARN categories (`except: pass` ×7, `type: ignore` ×10) — none touched or added by this diff, confirmed by `git diff` on the one hit that looked close (`contacts.py:882`, pre-existing) |
| Debug output / TODO / FIXME introduced by this diff | None — `git diff main..HEAD -- body-layer/src` greps clean for `print(`, `TODO`, `FIXME`, `XXX`, `pdb.set_trace`, swallowed `except: pass` |
| Only body-layer touched (`git diff --stat main..HEAD`) | Confirmed — `perception/naked_eye_source.py`, `belief/{percept,contacts,events,speech}.py`, their tests; no other subproject's `src/` touched, so no other subproject's own commands apply |

Only one subproject (`body-layer`) is in this diff's scope — confirmed from the diff itself, not
assumed.

#### Scope & Correctness

- **Matches the spec**: `docs/acceptance/2026-10-20-sortie-feedback.md` F6 + F6-follow-up (shooter
  visible unaided, firing at ownship, never produced "taking fire") — fixed exactly as described,
  verified independently by both Reviewer passes with mutation testing (disabling each new branch
  and confirming the right tests go red) and by Security's own trace of the `visible`-only loop
  scope.
- **Second half ("firing at others") — in scope but not independently traceable to the acceptance
  doc.** `debug.md`/`implementation.md` quote the user — *"someone shooting is important,
  especially if they are close -> report"* — as the authorizing direction, attributed to "dispatch
  instruction." That exact sentence is **not** in
  `docs/acceptance/2026-10-20-sortie-feedback.md`; the F6 section only ever states the
  targets-ownship case. Checked this is not an invented-scope problem: Reviewer (review-2.md) and
  Security both independently confirm the extension is exactly what `BL-B73`'s own schema already
  provisioned for (`fired_on`'s `targets_ownship: bool` field exists specifically to represent
  either case), not new scope. Not blocking — filed as
  `.claude/agent-memory/dod/project_scope_extension_via_dispatch_not_written_to_acceptance_doc.md`
  (first occurrence) and flagged to the user below, since root `CLAUDE.md`'s flight-feedback
  capture protocol exists precisely so this kind of direction stays in the written record.
- **No invariants violated.** No-omniscience: both new per-candidate dicts
  (`targets_ownship_by_object_id`, `firing_by_object_id`) loop over `visible` only — candidates
  `check_visibility` already gate-admitted — confirmed independently by Security reading the loop
  bodies. Classification tier never raised by the emitter fact — asserted in every new test
  (`classification_raw == "T-72B"`/`"BMP-2"`, the exact hires tier, never `DEFAULT_OP_CLASS`).
  `visibility.py`, `emitters.py`, `gaze.py` are byte-identical (`git diff --stat` confirms zero
  changes) — gaze gating (confirmed correct by the user), cockpit mask, optic FOV, terrain LOS, and
  the tier-clamp bypass are all untouched.
- **All new/modified files staged.** `git status --porcelain` clean at the reviewed tip (confirmed
  before DoD's own edits below); this report and the bookkeeping edits below are staged as part of
  this pass.
- **One required fix from `review-2.md` already resolved on-branch**: 17 stray
  `plans/taking-fire-visible-shooter/plan.md` citations (a plan file that was never written — this
  is a Debugger→Reviewer flow, not Architect→Implementer) were mechanically corrected to
  `debug.md` in commit `59eea085`, confirmed content-identical to a pure string swap by Security's
  own line-by-line read of that commit.

#### Testing

- Core logic is covered: `test_a_visible_unit_firing_at_ownship_sets_the_targets_ownship_provenance`
  (red on `431b5598`'s base code, green after the fix — Reviewer's own repro-on-base check),
  `test_a_visible_unit_firing_at_others_gets_the_firing_visible_provenance` (rewritten, spec-flip,
  justified against the quoted direction), plus two genuine 2-member cluster-fold tests
  (`test_two_clustered_visible_units_both_firing_at_others_get_the_firing_visible_provenance`,
  `test_a_mixed_firing_cluster_degrades_to_ordinary_provenance`,
  `test_a_cluster_mixing_targets_ownship_and_firing_at_others_degrades`) that close the first
  review's own "every fold test is single-member" gap for the new branches specifically (the
  equivalent gap for the pre-existing `member_emitter_kinds`/`BURNING` branch remains open and
  pre-existing — not introduced or worsened here, noted by both Reviewer and Security).
- Tests are meaningful: both Reviewer passes mutation-tested the load-bearing branches (disabled
  each new `if`/`elif` arm, confirmed the right test goes red, restored, confirmed
  `git status --porcelain` clean throughout).
- No existing tests broken: full body-layer suite green at this tip (2248 passed, 4 xfailed);
  known timing flakes (`test_logger.py::test_connection_reporter_*`,
  `test_log_live_los_coverage_summary_*`, `test_mission_start_reset.py` connection tests) did not
  trigger on this run, so no rerun was needed.

#### Documentation

- Reviewer findings addressed: review.md → no required fixes (approved outright). review-2.md → one
  required fix (stale `plan.md` citations), resolved in `59eea085`, confirmed by Security.
- Non-obvious behaviour explained: updated doc comments/docstrings in the diff itself (the
  bypass-independence rationale, the three-step provenance-fold priority order); two insights
  harvested to `notes/petrobrain-runtime-and-perception.md` (see below).

#### Security

- `plans/taking-fire-visible-shooter/security-review.md` — APPROVED, no required fixes. (No
  separate `security-plan-review.md` — this is a Debugger→Reviewer flow with no Architect plan, so
  there was no plan-review stage to run; confirmed this is the correct cadence, not a skipped step,
  per root `CLAUDE.md`'s "Security... plan review (after Architect)" — there is no Architect here.)
- Performance: `plans/taking-fire-visible-shooter/performance-review.md` — APPROVED. Two new O(n)
  per-poll dict builds measured at 0.09 ms/poll at the sortie's own 440-candidate scale (linear
  scaling confirmed via a 10x scale-up ratio check); the one real question (does the new
  `firing_visible` speech branch add enrichment cost) traced to "no — `describe_contact` was
  already paid for unconditionally by the pre-existing `CONTACT_FIRING_SEEN` handling; this changes
  only how the already-computed result is rendered."

#### Milestone-completion question (root CLAUDE.md "Milestone Completion")

Does this change what the next milestone should be, or invalidate a downstream assumption? **No.**
This is a defect fix within `BL-B73`'s own already-shipped, already-`#needs-flight`-tagged design
(the `targets_ownship`/firing-wording split BL-B73 itself introduced) — it does not change
`BL-B74`'s (SAM smoke tail) scope, and the one pre-existing test-coverage gap it partially closed
(multi-member cluster folds) remains open for the `BURNING` branch exactly as before, not newly
discovered or worsened by this fix.

#### Roadmap/backlog bookkeeping (prepared this pass, on this branch)

- **No new backlog entry needed.** This defect belongs under `[[BL-B73]]` (gun-fire visibility),
  which already carries `#needs-flight` for exactly the cockpit-judgement question this sortie
  exercised and found failing. Appended a dated addendum to `body-layer/ROADMAP/BL-B73.md`
  recording what the sortie found, what was fixed, and renewing `#needs-flight` (narrower: the fix
  itself is unflown, batched with the entry's two pre-existing open flight questions — mid-burst
  `SHOOTING_START` retrigger, and multi-unit clustering sanity — all three can likely clear on one
  sortie). Verified `BL-B73.md` was byte-identical between this branch and `main` before editing
  (`roadmap-edit-target-feature-vs-main` memory check), so this edit is safe to carry on the
  feature branch and merge normally.
- `body-layer/ROADMAP/BL-B83.md` and the `body-layer-backlog.md` one-liner for it are pre-existing
  on this branch (inherited from `docs/open-flight-tests-2026-10-20`, not this fix) — left
  untouched, out of scope.
- Root `ROADMAP.md`'s status table: no phase-status change (body-layer's overall phase is
  unaffected by a bugfix inside an already-"delivered, needs-flight" entry).

#### Knowledge harvest

Two insights added to `notes/petrobrain-runtime-and-perception.md` (pulled fresh from `main`, which
holds `notes/` — this feature branch forked before the `NOTES.md` → `notes/` split and does not
carry the directory itself; confirmed `BL-B73.md` was identical between branches using the same
check before editing it, and did the same spot-check here by diffing against `main`'s copy before
appending):

1. The root-cause class: a boolean answering "did the bypass fire" silently stood in for "is the
   fact true," dropping the fact exactly when the bypass was least needed (the easiest, closest
   shooter).
2. The design principle the fix's low-cost `callout_priority` integration demonstrates: key
   threat/priority logic on an event's semantic properties, not on which code path derived them, so
   a new derivation of an already-modeled property needs no priority-logic change.

Neither is obvious from the code alone or already in `CLAUDE.md`; both are the kind of
root-cause/design-principle lesson this project's harvest step is for. Did not add anything about
the mission-memory `fired_on` confirmation (already established design, not a new insight) or the
mutual-exclusivity-by-construction note (narrow to this fold, already documented in the code
comments).

#### Recurring-fix pattern check

Checked `review-2.md`'s one required fix (stale `plan.md` citations, 17 occurrences across 8
files) against `.claude/agent-memory/dod/MEMORY.md`'s categories — no prior DoD-level occurrence of
"citing a plan file that was never written because this is a Debugger→Reviewer flow with no
Architect stage." First occurrence; not yet a pattern (threshold is 2+). The debugger/reviewer roles
already filed their own memory for the specific mechanics
(`.claude/agent-memory/debugger/project_emitter_kind_bypass_conflation.md` and a reviewer-side
citation memory new to this branch) — not duplicated here.

Separately (not a "required fix" pattern, but worth naming as a process signal): the second half's
scope-authorizing quote not appearing in the cited acceptance doc (see Scope & Correctness above)
is a new category, filed as
`project_scope_extension_via_dispatch_not_written_to_acceptance_doc.md`, occurrence count 1.

### Verdict

**PASS**, scoped to tip `629dc5abafcba896072c06e63fdb7cf7715bb335`. No blocking findings. Two
non-blocking process notes reported to the user (see report). Live acceptance of the fix itself is
outstanding (`#needs-flight` on `[[BL-B73]]`, batched with that entry's two other open flight
questions) and does not gate this merge, per this project's standing live-acceptance policy.
