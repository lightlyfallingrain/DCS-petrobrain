# DoD Check — Cones Slice 2A (per-tier multipliers, distinctiveness, clamp)

Branch: `feature/cones-2a-tiers-distinctiveness`. Implementation commit `ba4e40f`. Review commit
`b284f27` (Reviewer: **APPROVED, no required fixes**, full-read confidence).

## Code Quality

- **Subprojects touched**: `git diff --name-only $(git merge-base main HEAD)...HEAD` shows only
  `body-layer/` source/tests, `plans/detection-cones-slice2/`, and `.claude/agent-memory/`
  entries. `world-model/` and `aircraft-layer/` are untouched by this branch — the three untracked
  files at repo root (`world-model/run.sh`, `world-model/syria-full-build.log`,
  `world-model/syria-theatre-unfiltered.osm.pbf`) are pre-existing, unrelated build artifacts, not
  part of this diff, and were **not** staged.
- Ran the full body-layer verification sequence myself, from `body-layer/.venv`, per
  `body-layer/CLAUDE.md` "Commands":
  - `ruff format --check src tests` → **81 files already formatted** (PASS)
  - `ruff check src tests` → **All checks passed!** (PASS)
  - `cd body-layer && mypy src` → **Success: no issues found in 38 source files** (PASS)
  - `pytest tests -q` → **778 passed, 4 xfailed** (PASS — exact match to the claimed/expected result)
- No debug output or TODO/FIXME/pdb/breakpoint introduced: `git diff` over the touched source
  files grepped for `print(`/`TODO`/`FIXME`/`pdb.set_trace`/`breakpoint(` — no hits.
- No unhandled errors/panics in data paths — this slice touches pure geometry/threshold
  functions only (`optics.py`, `object_model.py`, `visibility.py`, `clustering.py`,
  `naked_eye_source.py`), no new I/O.

## Scope & Correctness

- Matches the 2A sections of `plans/detection-cones-slice2/plan.md` exactly: per-tier optic
  multipliers, the distinctiveness default+exception field, the `min()` clamp with tier
  monotonicity, and the clustering-floor parameterisation (hard part 4). Confirmed independently
  via the diff (not just the commit message) — same files the Reviewer checked, spot-verified
  arithmetic in this pass and cross-checked the reviewer's own derivations.
  - Correction to the task framing: the plan calls the clustering-floor issue "hard part 4" in the
    consolidated slice-2 plan doc's numbering, but the invariant is real regardless of numbering —
    `_separable`'s floor (A) now takes the active optic's `presence_range_mult` instead of the
    hardcoded `BINOCULAR_RANGE_MULTIPLIER` constant, and a regression test
    (`test_floor_would_have_broken_under_the_old_hardcoded_constant`) demonstrates the old constant
    would have silently merged two separable contacts at `presence_range_mult = 5.81`.
- No unplanned scope: no `gaze.py`, no `ScanPlan`, no scan-loop code exists on this branch (2B/2C/2D
  are plan-only). `belief/decay.py` has no diff. No `perception → belief` import introduced.
- No CLAUDE.md invariants violated: DCS/ground-truth stays authoritative (thresholds derived from
  measured sorties, not invented); provenance is preserved (every derived constant carries its
  arithmetic in a code comment, matching the "estimate flags must reach the code" standard from
  prior review findings); no multiplayer scope; no world-model data committed.
- All new/modified files staged with `git add` — confirmed via `git status --short`: only the
  three unrelated pre-existing untracked `world-model/` files remain untracked; nothing from this
  branch's work is unstaged.

## Testing

- Core logic covered: `test_tier_thresholds_never_invert` (property test across every profile ×
  every shipped optic), `test_infantry_class_clamps_to_presence_at_every_optic`,
  `test_floor_would_have_broken_under_the_old_hardcoded_constant`, plus updated
  `test_visibility.py`/`test_vision_calibration.py`/`test_clustering.py`/`test_optics.py`/
  `test_object_model.py` cases. These are meaningful — they assert the actual measured pattern
  (infantry class == presence at both shipped optics), not just "doesn't crash."
- Two new `xfail`s in `test_vision_calibration.py`, each with a full worked derivation in its own
  docstring, are an honest regression record (per-tier multipliers individually undercut the old
  flat 4.0 at two specific calibration points), not a silently weakened suite. Vehicle rows (the
  plan's own explicit regression guard) were re-checked and are unmoved.
- No existing tests broken: 778 passed / 4 xfailed matches the pre-stated expectation exactly.

## Documentation

- Reviewer findings: **none required.** Two Optional Refinements were logged (a fixture that now
  exercises `BINOCULAR_OPTIC` rather than the production `UNAIDED_OPTIC` call path, and the
  unshipped 9K113 figures living only in prose/tests) — both explicitly optional, no defect today,
  and both already carry their own documentation of the gap. Not blocking.
- Non-obvious behaviour is explained in-code: every derived constant (infantry 5.0, S-300 2.6, the
  clamp's `min()` chain, the floor's slackness proof) carries its derivation as a comment at the
  declaration site, plus the decisions doc (`body-layer/research/2026-09-21-slice2-model-decisions.md`)
  and `implementation.md` for the full narrative.

## Security

- Project posture (`CLAUDE.md` "Agents"): security review is explicitly skipped for this project
  phase (offline, single-user, local pipeline, no hot path, no untrusted-input surface) unless the
  user asks for it. Not requested for this feature. No `security-plan-review.md`/`security-review.md`
  expected or present — consistent with every other recent merge in this repo.

## Verdict: DoD PASSED

---

## Acceptance boundary — what 2A's fixtures structurally cannot reach

2A is a pure-function model correction: given a range/size/distinctiveness/optic, does the
threshold arithmetic come out right. The fixture suite proves the *arithmetic* reproduces the
already-measured pattern (infantry class collapses onto presence; the clamp holds under nested
`min()`s by construction). It cannot prove two things a fixture has no way to see:

1. **Whether the corrected thresholds change what Petrovich actually calls out in a live sortie**
   in a way that reads correctly to the user's ear — a fixture asserts a number, not a callout's
   timing or tone.
2. **The remaining absolute-range gap.** The plan states this explicitly and it is worth repeating
   here rather than letting a fixture pass be mistaken for "ranges are now correct": **2A does not
   fix the measured 1.33× presence shortfall for vehicles**, and separately, the class/type ranges
   this slice computes for infantry (naked 600 m via the clamp) and the S-300 (per-type 2.6) still
   sit below the directly-observed sortie figures once the clamp's computed value is compared
   against the *measured* value rather than the *modelled-before* value — the review's own
   arithmetic shows infantry's binocular class computes to 1452 m against a directly-observed
   2.0 km, narrow to 3486 m against 4.5 km. The **structural** collapse (ratio 1.00, i.e. class no
   longer trails presence) is proven; the **absolute** range is not calibrated to match the sortie
   numbers exactly, by design — recalibrating `LOWRES`/`MEDRES`/`HIRES` themselves is explicitly
   out of scope for 2A (plan, "Explicitly out of scope").

No fixture can distinguish "the shape is right and the absolute number is knowingly short" from
"the shape is wrong" — that distinction requires reading the plan's own scope cut, which is why
it's stated here rather than left implicit in a passing test suite.

## Live acceptance position

**What is verified now, without a new sortie:** the structural claim this slice exists to prove —
class-tier ranges collapse onto presence-tier ranges for indistinct-by-default-turned-distinct
object classes (infantry, and the S-300 via its per-type exception) — is reproduced by the shipped
arithmetic at both optics 2A actually ships (`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`), verified two ways:
by `test_infantry_class_clamps_to_presence_at_every_optic` and by the Reviewer's independent
hand-check of the same arithmetic against `object_model.py`'s inline derivation comments. This
reproduces the *shape* of the already-flown 2026-09-21 sortie's measurement (ratio 1.00 at all four
instruments the user actually flew — naked/binocular/9K113-wide/9K113-narrow, 0.6/0.6, 2.0/2.0,
2.0/2.0, 4.5/4.5 km) for the two instruments this slice puts in the live code path. The 9K113
wide/narrow rows are **not** live-reachable this slice (no selectable 9K113 optic exists yet, by
explicit scope cut) — their agreement was checked by hand against the unshipped constants, not
exercised by running code, and that is a documented, deliberate gap, not an oversight.

**What still needs a sortie, and is not claimed done here:** the plan's own acceptance gate for 2A
(the "Gate to the next slice" column) is "A sortie with BL-9 tracing: infantry class ≈ presence;
S-300 class within ~1.5× of 4500 m; vehicle class/presence unchanged within noise." **That flight
has not happened since 2A landed** — the 2026-09-21 sortie the decisions doc and this slice's
constants are derived from was flown *before* 2A's code existed, to gather the numbers 2A now
encodes; it confirms the model decisions, not this implementation of them. Flying with BL-9 tracing
against 2A's actual code is the outstanding item, and it belongs on `body-layer/ROADMAP.md`'s "Live
acceptance debt" list once this branch merges — it is deferred, not waived, per the plan's own
acceptance-gate language.

**This does not block the merge decision.** Per root `CLAUDE.md`'s "Live Verification" guidance,
live acceptance happens in bursts and the user's Windows-box access governs when. Nothing about 2A
needs to be re-verified before 2B can start — 2B is behaviour-preserving by construction (default
`FULL_GAZE`) and does not depend on 2A having been flown.

## Answers to the milestone-completion question (root `CLAUDE.md`)

**1. Does 2A's outcome still support 2A-before-2C sequencing, or does anything argue for a
different next slice?** It still supports it, more strongly than before. The ordering rationale was
that 2C's calibration is unreadable if a sortie can't attribute a changed detection range to *either*
"whether" (2A) or "when" (2C). 2A landed clean, with no scope drift and no surprises the plan didn't
already carry (the vehicle-row movement was explicitly flagged as an unavoidable, xfailed
consequence, not a defect). Nothing in the actual implementation changes that reasoning. The next
slice per the plan's own ordering is **2B** (gaze as a filter) — it is explicitly behaviour-preserving
(`FULL_GAZE` default) and cost-neutral, so it can land and be tested on fixtures alone before 2C's
scan loop (which is where the real subjective/feel risk and the cost saving both land together, per
hard part 3). No reason surfaced here to reorder ahead of 2B.

**2. Is threshold recalibration now unblocked?** No. The plan named three reasons recalibration was
deferred: tier-dependent magnification, silhouette distinctiveness, and the unanswered
calibration-target question. 2A implements the first two and both are now live and tested. The
third is **not** resolved by 2A, and it is two separate open items, not one — both must clear, and
clearing one does not clear the other:

- **The calibration-target question itself is still unanswered by the user**: whether presence
  should be fit to what a player sees on a monitor, or kept conservative for what a real crewman in
  the cockpit would see. This is a decision only the user can make, and nothing in 2A resolves it —
  2A's own arithmetic (infantry binocular computing to 1452 m against a directly-observed 2.0 km) is
  itself downstream of this unanswered choice, not independent of it.
- **The 2026-09-17 screenshot calibration ladder is separately compromised** (plan, Risks &
  Unknowns): DCS detection-aid dots were enabled during capture, so `LOWRES`/`MEDRES`/`HIRES` remain
  pinned to optimistic ground truth regardless of which target the user eventually picks. A clean
  (dots-off) re-capture is needed independent of the target question.

So recalibration now sits behind **both** the contaminated ladder **and** the unanswered
calibration-target question, with 2A having cleared only the two model-*shape* reasons
(tier-dependent magnification, distinctiveness). Clearing the ladder alone would not be sufficient —
the target question would still block. Consistent with the plan's explicit scope cut ("Threshold
recalibration beyond what the decisions doc fixes" is out of scope for the whole milestone, not just
2A).

**3. Does anything in 2A make the `OBSERVED_WINDOW_S = 16.0` derivation (2C) wrong?** No. That
derivation depends only on `SCAN_CYCLE_PERIOD_S`/`FOCUS_DWELL_S` (both 2C constants, not yet
declared) and `belief/decay.py`'s existing `POSITION_HALF_LIFE_S`. 2A has zero diff in
`belief/decay.py` (confirmed above and independently by the Reviewer's own grep) and does not touch
scan cadence, gaze, or attention timing in any way — it only changes *which* range a tier is
achieved at, not *when* a poll looks in a given direction. Nothing here bears on that derivation.
