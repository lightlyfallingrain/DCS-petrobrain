# Definition of Done: BL-B71 — the least-capable-optic guidance ladder

**Scope note on this gate's verdict.** This gate ran against `feature/bl-b71-optic-ladder` tip
`8b90fc0371fa4c90fc4379de3937016d31e94905` (confirmed by `git rev-parse HEAD` after a clean
`git merge --ff-only 8b90fc0371fa4c90fc4379de3937016d31e94905`, exactly the sha named in the
dispatch — fast-forward succeeded cleanly). **The verdict below is scoped to that commit.** If the
branch moves after this report is written, re-run this gate before treating the verdict as
current.

## Base-commit discipline

- `git rev-parse HEAD` at worktree start: `24f217fc` (`origin/main`/`origin/HEAD`), a strict
  ancestor of the named tip, tree clean.
- `git merge --ff-only 8b90fc0371fa4c90fc4379de3937016d31e94905`: fast-forwarded cleanly to
  `8b90fc03`, no divergence, no conflicts.
- `main` (local ref in this worktree) sits at `8c30148a`, ahead of this branch's fork point —
  **not merged in**, per the dispatch's explicit instruction. Fork point used for the diff below:
  `git merge-base main HEAD` → `98ee1f7a`.

## Diff scope — derived from `git diff --name-only`, not assumed

```
.claude/agent-memory/implementer/feedback_tuning_comment_leading_backtick_strip_asymmetric.md
.claude/agent-memory/reviewer/feedback_untested_not_reachable_docstring_claims.md
.claude/agent-memory/security/project_optic_revocation_two_poll_lag.md
body-layer/config/defaults.toml
body-layer/src/belief/attack_run.py
body-layer/src/belief/crew_console.py
body-layer/src/belief/optic_policy.py
body-layer/src/logger.py
body-layer/tests/test_attack_run.py
body-layer/tests/test_logger.py
body-layer/tests/test_optic_policy.py
plans/attack-run-sortie-fixes/implementation.md
plans/attack-run-sortie-fixes/performance-bl-b71.md
plans/attack-run-sortie-fixes/review-bl-b71-fix.md
plans/attack-run-sortie-fixes/review-bl-b71.md
plans/attack-run-sortie-fixes/security-bl-b71.md
```

**`body-layer` is the only subproject touched.** No other `pyproject.toml`-bearing directory
appears in the diff — confirmed by this listing, not taken from the dispatch prompt.

## Mechanical checks — run by this gate, not cited from any prior report

All run with `cwd` inside this worktree's `body-layer/`, invoking the main checkout's venv
binaries directly (`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/<tool>`), since a fresh
worktree has no `.venv` of its own.

| check | result |
|---|---|
| `ruff format --check src tests` | **133 files already formatted** |
| `ruff check src tests` | **All checks passed!** |
| `mypy src` (CWD-only config discovery, run from inside `body-layer/`) | **Success: no issues found in 60 source files** |
| `pytest tests -q` | **2090 passed, 4 xfailed** |
| `pytest tests/test_tuning_defaults_toml.py -q` (the generator-staleness test, run explicitly) | **1 passed** |
| `git status --porcelain` (after merge, before any edits) | clean |

All five counts match every prior role's reported figures exactly (Implementer's final round,
Reviewer's fix-round re-run, Performance, Security) — no drift between what was reported and what
is actually on the branch.

## Code Quality

- [x] Format/lint/type/test all pass for the one touched subproject, run by this gate directly.
- [x] No unhandled errors or panics in data paths — Security's deep analysis traced the full
  revocation/clamp call chains and found none; this gate did not re-run that trace independently
  but has no reason to doubt it given the other independently-reproduced findings below.
- [x] No debug output left in committed code — `git diff` reviewed; no `print`/debug scaffolding
  outside the existing `_print` funnel.
- [x] No leftover TODO comments introduced by this feature — none found in the diff.

## Scope & Correctness

- [x] Implementation matches `body-layer/ROADMAP/BL-B71.md`'s specification (read in full above):
  the ladder, the three-guard hysteresis, the structural sight-ceiling hard gate, the
  `attack_run` requests / `optic_policy` grants boundary, the Co-moving Fields exit-transition
  enumeration (one additional transition found and fixed beyond the plan's own list — the two
  fresh-`OpticState(...)` construction sites — matching this project's own recurring pattern,
  `.claude/agent-memory/dod/project_recurring_stale_state_on_transition.md`).
- [x] No unplanned scope added silently. Two optional review findings (the tuning-comment
  first-sentence fix, the first-grant hands-busy baseline comment) were folded in explicitly and
  flagged as such in `implementation.md`, not silently expanded.
- [x] No invariants from `CLAUDE.md`/`body-layer/CLAUDE.md` violated — no-omniscience holds (the
  ladder reads `home_phase`/range/profile, never a ground-truth field); the default-optic
  invariant is untouched (the ladder's floor is still `UNAIDED_OPTIC`).
- [x] `git status --porcelain` clean after the fast-forward; nothing new to stage.

## Testing

- [x] Core logic covered: `TestLeastCapableSufficientOptic` (5), `TestGuidanceRequestFor` (5),
  `TestGuidanceOverride` (11), `TestRequestedOptic` (6), plus two fix-round regression tests
  (`test_no_look_cause_optic_param_lowers_the_too_far_threshold`,
  `test_decide_with_granted_binoculars_resolves_tier_1_instead_of_losing_sight`) and one final
  correction-round test (`test_crew_text_poll_loop_passes_the_used_optic_not_the_guidance_grant`).
- [x] Tests are meaningful, not decorative — three structural counterfactuals were independently
  re-run by this gate's predecessors (Reviewer and Security both performed the hard-gate mutation
  themselves, with `shasum` restore confirmation; the Reviewer fix-round pass re-ran the
  `granted_optic`→`guidance_optic` revert and reproduced the exact reported `AssertionError`).
  This gate did not re-run the mutations a third time — two independent roles already did, with
  matching results, and re-deriving a third time would not change the verdict.
- [x] No existing tests broken — net test count only grows across every round (2061 → 2087 → 2089
  → 2090), confirmed by name in each round's own `-v` output per `implementation.md`.

## Documentation

- [x] Reviewer required fix addressed — see "The judgement this gate owes" below for why the
  *end state* of that fix, not merely its existence, is what closes this item.
- [x] Non-obvious behaviour explained: `optic_policy.py`'s module docstring, `attack_run.py`'s
  `decide`/`_no_look_cause` docstrings, and the rendered `config/defaults.toml` comments all
  describe the used-optic contract correctly (confirmed directly by both Reviewer-fix and
  Security passes, and spot-checked by this gate against the rendered TOML, not the source
  comment).

## Security

- [x] `plans/attack-run-sortie-fixes/security-plan-review.md` — **not present as a separate file
  for this specific sub-item**; `BL-B71` was planned as part of the same
  `attack-run-sortie-fixes` plan whose other entries (`BL-B70`) already carry a plan-level
  security pass per the project's once-per-feature cadence
  (`.claude/agent-memory/dod/project_current_cadence_one_security_pass_per_feature.md`). The
  deep-analysis pass below is the security gate for this sub-item and is unambiguously present
  and APPROVED.
- [x] `plans/attack-run-sortie-fixes/security-bl-b71.md` — **APPROVED**. Deep analysis
  specifically probed the two properties this feature could have broken (the 9K113 hard gate,
  the no-omniscience range-gate invariant) and confirmed both hold under independent mutation and
  call-chain tracing, plus surfaced one new finding (the two-poll revocation lag) that is bounded
  and does not block DoD.

## The judgement this gate owes, beyond the mechanical checks

**1. Does the fix answer the user's actual direction, not just the review's narrower wording?**
Yes, and only after a second correction. The Reviewer's required fix named `OpticState.
guidance_optic` (the ladder's own standing grant) as the target. The first fix round wired exactly
that — and reintroduced the original bug in miniature, because `guidance_optic` is `None` through
ordinary glassing with no guidance grant standing, a case the review's wording didn't name but the
defect's own English description ("the range gate must use the optic actually resolving the look")
already covered. Asked directly whether this was a test artefact or real behaviour, the user ruled
**"actual behavior must measure by used optic."** The second, final round rewired the call site to
`runner.optic` (renamed `resolving_optic`) — the value that actually admitted the tick's percept —
confirmed independently by Reviewer (fix-round pass) and Security, both tracing the full call chain
(`logger.py` → `naked_eye_source.py` → `visibility.check_visibility`) rather than trusting the
implementation log's own account. The end state satisfies the direction. **This generalises**: see
the new memory note filed below.

**2. The acceptance boundary, stated plainly.** Everything on this branch is verified against
fixtures, unit tests, and three independently-reproduced mutation counterfactuals (sight-ceiling
clamp, fresh-construction carry-forward, guard-1 placement). No fixture can confirm whether the
ladder's *cadence* — escalating when it should, de-escalating as range closes — feels right at the
controls rather than merely correct on paper. **The sight rung is unreachable without the pilot's
own prior "Observ on" command**, so the common case the next flight will actually exercise is
naked-eye ↔ binoculars; exercising the full four-rung ladder, including the 9K113, needs a run
flown with OBSERV already commanded on. The acceptance card (below) states this up front rather
than leaving it to be discovered mid-flight.

**3. Two accepted gaps, carried rather than fixed, now named where a flight planner sees them**
(moved from review documents into `body-layer/ROADMAP/BL-B71.md`'s entry, not left only in
`review-bl-b71.md`/`security-bl-b71.md`):
- `GUIDANCE_OPTIC_MIN_INTERVAL_S`/`HANDS_BUSY_DURATION_S` cross-key coupling — at the declared
  bound extremes, a grant could re-charge hands-busy before the previous charge finishes. Not
  reachable at shipped defaults; only a risk under hand-tuned `tuning.toml` extremes.
- A two-poll (not the usual one-poll) revocation lag on `disengage`/`drop_target` — bounded to
  roughly one extra poll, symmetric across both exit paths, and provably cannot grant a sight rung
  that was not already pilot-authorized (Security's own finding, traced independently).

**4. Milestone impact.** Does not change what `BL-B66` or `BL-B76` should do next. `BL-B66`'s
planned `OpticPhase.GUIDING` consolidation (already rewriting these files for the slew controller)
should absorb both the known gaze/optic structural seam `BL-B71.md` already named as deliberately
unfixed and the two-poll revocation lag found by Security — noted in the roadmap entry rather than
newly assigned as separate work. `BL-B76` (the `", obstructed"` dead-code gap) is untouched and
independent: this ladder reads `_no_look_cause`'s cause taxonomy but not the `live_los_clear`
admission path `BL-B76` is about.

**5. Roadmap updated.** `body-layer/ROADMAP/BL-B71.md` marked `[x]` `#status/done #needs-flight`,
with a real done-entry (what shipped, the two-round fix story, the acceptance boundary, the two
accepted gaps, and the milestone-impact line) written directly on its own entry file — not the
four-line `ROADMAP.md` pointer.

**6. NOTES.md harvest.** Two bullets added under "Attack-run guidance design (BL-14)" (the
existing section this feature's lessons belong beside):
- the "not reachable in practice" docstring claim pinned to the system that made it true when
  written, going stale the moment the feature that changes that system ships (generalises
  `.claude/agent-memory/reviewer/feedback_untested_not_reachable_docstring_claims.md` past this
  one item);
- a review's required fix naming a correct-sounding but narrower target than the defect it
  describes, and a fix that faithfully implements the named target still missing the point.

**Process signal for the user, not code debt.** The second NOTES.md bullet above recurred
*within this single item* (first fix round, then the correction round) rather than across
features, so it is one occurrence under this exact shape, not yet a confirmed 2+-feature pattern
like `recurring_stale_state_on_transition` or `recurring_correct_conclusion_unearned_reason`.
Filed as a new, separate memory
(`.claude/agent-memory/dod/project_fix_answers_review_wording_not_user_direction.md`) rather than
folded into either existing pattern, with an explicit note to compare against it if a second
instance shows up on a different feature — at which point it would be worth raising at Architect
or Reviewer time rather than catching it at DoD a second time.

## Acceptance Testing Plan

Published as a card rather than left in this file, per this role's own standing instruction (the
user flies, they do not scroll a plan mid-sortie):

**Card:** https://claude.ai/artifact/AM35VzYb3Xu1KBQjW5SeQt
**Source:** `docs/acceptance/2026-10-16-bl-b71-optic-ladder-acceptance-card.md`
**Branch named in the card:** `feature/bl-b71-optic-ladder`

Every spoken command in the card was run through the real command matcher on this branch
(`audio-adapter`'s `command_matcher.match_transcript`) before being written down, with the actual
token returned pasted into the card's own table — not guessed. The launch command's flags were
verified against this worktree's own `logger.py --help` output.

## Verdict

**PASS**, scoped to tip `91b3c489...` (full `8b90fc0371fa4c90fc4379de3937016d31e94905` after the
ff-only merge). All mechanical checks green and independently re-run by this gate. Both judgement
items this gate owed — whether the fix answers the user's real direction, and stating the
acceptance boundary — are satisfied and recorded. Live acceptance is outstanding
(`#needs-flight`), not blocking the merge per this project's standing direction that live
acceptance is batched into sorties and never gates a merge.
