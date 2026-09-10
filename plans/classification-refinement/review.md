## Review: duplicate-contact spatial-gate fix (commit 7581928)

### Review Summary

Reviewed the bug fix at `7581928` against `plans/classification-refinement/debug.md`'s
report. The fix is minimal, correctly scoped, and lands in the right module
(`belief/association_over_time.py`'s gate formula, plus the `Contact.last_position_uncertainty_m`
field needed to feed it). It does not touch `ContactStore.ingest`'s anti-guessing invariant or
the classification fold/compatibility machinery, matching the debugger's own claim of what was
and wasn't in scope.

Verified directly, not just read:

- **Diff is real and minimal.** `spatial_gate_radius_m` now sums `uncertainty_radius_m(percept)
  + contact.last_position_uncertainty_m + GATE_GROWTH_RATE_MPS * elapsed_s` — genuinely
  symmetric, not a one-sided pad. `Contact.last_position_uncertainty_m` is set from
  `uncertainty_radius_m(percept)` in both `from_percept` (founding) and `record` (every merge),
  so it never goes stale — checked both call sites in `contacts.py`.
- **`ContactStore.ingest` untouched.** The commit's diff does not touch `contacts.py`'s `ingest`
  method at all (confirmed via `git show --stat` and reading the method directly); the
  "exactly-one-pass -> merge, zero-or-two-or-more -> new contact, never a tiebreak" rule and its
  docstring are byte-identical to before the fix.
- **`class_compatibility("T-90A", "OP_ARMORED")` claim checked against the real code**
  (`belief/classification.py`'s `_op_class_of`/`class_compatibility`), not trusted from the
  report: `"OP_ARMORED"` short-circuits as an already-bucketed `OP_*` string, `"T-90A"` resolves
  via `object_model.profile_for`'s keyword table to the same `OP_ARMORED` bucket, both non-`None`
  and equal -> `"compatible"`. Confirms the debugger correctly ruled out the classification-gate
  hypothesis.
- **Regression test genuinely reproduces the bug, traced by hand.** Reverted
  `association_over_time.py` and `contacts.py` to their pre-fix state (`7581928^`) in the working
  tree and re-ran `test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` alone:
  it fails, producing exactly 39 contacts for one simulated real object over 40 polls (matching
  the report's own before/after figures). Restored the fixed files and re-ran the full suite —
  246 pass, tree clean except the pre-existing, out-of-scope `run-body.sh` local edit (confirmed
  it's an unrelated `--overlay` flag addition, not part of this commit).
- **Fixture updates in `test_decay.py`/`test_contacts.py` are real updates, not loosening.**
  `test_decay.py`'s `_contact()` helper just adds the new required field at `0.0` (irrelevant to
  that module). `test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`'s distances
  (400m->800m separation, percept moved to the new midpoint) are recomputed correctly against the
  new formula's actual doubled floor (SCOPE_UNCERTAINTY_M=300 on each side = 600 total at t=0);
  the assertion itself (ambiguity -> new contact, never a merge) is unchanged.
- **All checks pass**, run directly against `body-layer/.venv`: `ruff format --check` (42 files
  already formatted), `ruff check` (all checks passed), `mypy src --strict`-equivalent config (no
  issues, 21 files), `pytest -q` — 246 passed.
- **Cross-checked against BL-2's own prior art on this exact risk class.**
  `plans/pb2-contact-memory/plan.md` Stage 5's acceptance criterion is literally "two genuinely
  distinct nearby objects stay two contacts," implemented as
  `tests/test_cross_channel_fusion.py::test_two_distinct_nearby_objects_stay_two_contacts` (two
  real objects ~1414m apart, one per channel, same poll). This test is untouched by the commit and
  still passes — at t=0 the new gate's radius tops out around ~577m (naked-eye ~277m +
  scope-channel-founded contact's stored 300m), nowhere near 1414m, so this specific case's margin
  is unaffected by the widening.

### Required Fixes

None.

### Optional Refinements

- **The gate is now roughly ~2x wider at the close end than before (both sides' uncertainty
  budgeted instead of one), which is the correct fix for the bug at hand but also raises the
  false-merge risk for two genuinely distinct real objects separated by roughly
  300-600m** (previously only objects within ~300m of each other risked a spurious merge on the
  scope channel's fixed 300m budget; now it's ~600m, before the elapsed-time growth term is even
  added). This is an inherent, correctly-accepted tradeoff of the fix — not a bug — but it's the
  opposite failure mode from the one just fixed (under-merge -> duplicate contacts vs.
  over-merge -> lost distinctness), and BL-2's plan flags "weak cross-channel class
  compatibility" as a known under-merge risk but has no equivalent prior note about this specific
  over-merge risk at the new, wider radius. Worth an explicit line of attention during the Stage 8
  re-flight below (e.g. two infantry/vehicle contacts near each other unexpectedly folding into
  one) rather than assuming the existing `test_two_distinct_nearby_objects_stay_two_contacts`
  fixture (1414m separation) is representative of the closest realistic case. (optional — watch
  during acceptance, no code change needed now)
- `GATE_GROWTH_RATE_MPS`/`SCOPE_UNCERTAINTY_M` remain placeholders, as documented; this fix
  doesn't change that status and doesn't need to. (optional, no action)

### Verdict

APPROVED

### Review Confidence

Full read — read the actual diff (not just the debug report), read and hand-traced the
regression test both with the fix reverted (fails, 39 contacts) and applied (246 total pass),
read `class_compatibility`/`_op_class_of` directly rather than trusting the report's claim, read
`ContactStore.ingest` directly to confirm it's untouched, and cross-referenced
`plans/pb2-contact-memory/plan.md`'s own prior Stage 5 risk note against the still-passing
`test_two_distinct_nearby_objects_stay_two_contacts` fixture. Ran all four verification commands
myself from `body-layer/.venv`.

### Note for DoD: Stage 8 live acceptance still outstanding

This fix addresses the *mechanism* (duplicate-contact runaway) with a fixture-based regression
test that does not require live DCS. It does not and cannot re-validate BL-2.6's Stage 8
live-acceptance judgment (calibration feel, contact volume, chatter rate) — that judgment was
made on a session whose contact count was inflated 3-4x by this bug, so its conclusions about
"does this feel right" are not trustworthy as-is. Recommend: DoD can proceed on the mechanism/
bugfix alone (checks pass, regression test proven, invariants intact), but Stage 8's live
acceptance should be explicitly re-flown before BL-2.6 as a whole is marked done — both to
confirm the duplication is actually gone in a live session (fixtures are a faithful but not
100%-identical stand-in for real `naked_eye_source` behavior) and to re-form the calibration
judgment (including the optional refinement above: watch for any *new* under-differentiation
between close, genuinely distinct real objects) on a now-trustworthy contact count.

---

## Stage 10 (docs) review — commit `168c136`

Scope: documentation only, final stage of BL-2.6 before DoD. Reviewed against
`plans/classification-refinement/plan.md`, `plans/classification-refinement/session-state.md`,
and the actual source in `body-layer/src/`.

### Review Summary

Stage 10 touches exactly the four files it should (`body-layer/CLAUDE.md`,
`plans/body-layer/plan.md` §6, `plans/pb1.5-naked-eye-detection/plan.md`, `todo/todo.md`), plus
`plans/classification-refinement/implementation.md` (the stage's own log — expected, not scope
drift). `git show 168c136 --stat` confirms zero `src`/`tests` changes in this commit. Format,
lint, `mypy --strict`, and `pytest` all pass clean (246/246, matching the branch's expected
count).

Spot-checked every accuracy claim in the task against the real source:

- `belief/classification.py`'s module docstring, `SpecificityLevel`, `fold_classification`,
  `PRESENCE_CLASS`, and the re-homed `_op_class_of`/`class_compatibility` all match what
  `body-layer/CLAUDE.md`'s new entry claims.
- `naked_eye_source._classification_for_tier` matches the CLAUDE.md description exactly,
  including the `hires`-miss-falls-back-to-class nuance CLAUDE.md calls out.
- The `Contact.classification` vs `Contact.last_class_raw` dual-field warning is not a passing
  mention — CLAUDE.md explains what each field means, why `last_class_raw` must stay the
  association gate's input (feeding it the folded claim would make the gate monotonically
  stricter), and flags it in bold as "a real readability cost, not an oversight." This matches
  the plan's own instruction that both docstrings carry the warning, and `contacts.py`'s
  in-source docstring (lines ~92, ~119) says the same thing independently.
  `Contact.last_position_uncertainty_m` is documented in the same entry, correctly attributed to
  the live-acceptance bug fix rather than folded silently into the classification narrative.
- PB-1.5 supersession note: placed immediately after PB-1.5's own worked range table (verified —
  no duplicate of that table exists anywhere in `plans/body-layer/plan.md`, confirmed by grep;
  §6's BL-2.6 entry has its own prose summary of current tier semantics, not a second copy of
  PB-1.5's numbers). The note names what superseded it (BL-2.6, gate `medres`->`lowres`,
  `NAKED_EYE_RANGE_CAP_M`) and where current numbers live (`plans/body-layer/plan.md` §6 and
  `perception/visibility.py`) — a future reader lands in the right place either way.
- `todo/todo.md`'s backlog split is honest on the certainty half: `git log`/`git diff` across the
  whole BL-2.6 commit range (`a7733f5..168c136`) touches `decay.py` in **zero** commits, and
  `decay.certainty_of` is untouched — confirmed by reading the function directly. The
  classification half of the claim is also accurate: `Contact.record` now calls
  `fold_classification` instead of overwriting (`contacts.py`).

### Required Fixes

- **`body-layer/CLAUDE.md`'s `classification.py`/`contacts.py` entries and `plans/body-layer/plan.md`
  §6's Decision 4 both assert that `decay.classification_confidence_at` now "finally consumes
  `IDENTITY_HALF_LIFE_S`" and decays `Contact.classification.confidence` over time. This is not
  true of the shipped code.** `IDENTITY_HALF_LIFE_S` is declared in `decay.py` but its own
  docstring still says "Not yet consumed (no per-attribute identity confidence field exists on
  `Contact` yet)" — unchanged by this branch. There is no `classification_confidence_at` function
  anywhere in `body-layer/src/`, no caller of `IDENTITY_HALF_LIFE_S` outside its own declaration,
  and no decay-over-time test for `classification.confidence` (`test_decay.py`'s only BL-2.6-era
  edit is a fixture update to keep `Contact` construction valid, not a new decay test). What
  actually ships: `ClassificationBelief.confidence` is set once per fold (`_DEFAULT_CONFIDENCE_BY_LEVEL`
  on refine, nudged toward a ceiling on reinforcement, floored on collapse) and never revisited by
  elapsed time — `classification.py`'s own module docstring is honest about this ("Real
  calibration (and `belief.decay.IDENTITY_HALF_LIFE_S`-driven decay of this confidence over time)
  is later work this stage does not build"). The plan's Affected Modules section scoped this
  exact helper into `decay.py`, and it silently never landed across Stages 1–9; Stage 10 then
  documented it as done. This is a documentation-accuracy bug in the file whose entire job is
  accuracy, and it directly contradicts the in-source docstring next to it — a future reader who
  trusts CLAUDE.md over the source will believe confidence decay is calibrated and working when it
  is static. Fix: correct both `body-layer/CLAUDE.md` (the `contacts.py` entry's decay clause and
  the `classification.py` entry's closing sentence) and `plans/body-layer/plan.md` §6 Decision 4
  to state that only the *level*-sticky/no-decay half of Decision 4 shipped — confidence is set at
  fold time and does not currently decay with elapsed time, `IDENTITY_HALF_LIFE_S` remains declared
  but unconsumed, same status as before this milestone. Either fix the docs to match the code, or
  (if the omission itself is judged worth closing before DoD) implement the helper — that's a
  scope decision for the user/architect, not something Reviewer should silently pick.

### Optional Refinements

- `body-layer/run-body.sh` has an uncommitted local change (`+--overlay`) sitting in the working
  tree, unrelated to Stage 10. Not a docs-accuracy issue and not blocking this review, but worth
  clearing (commit or discard) before DoD's clean-working-tree check, since it isn't part of any
  reviewed commit.

### Verdict

**NEEDS REVISION** — one required fix, confined to two documentation files
(`body-layer/CLAUDE.md`, `plans/body-layer/plan.md` §6). No code changes needed unless the user
elects to implement the missing decay helper instead of correcting the docs. Everything else in
Stage 10 — file scope, the dual-field warning, the PB-1.5 supersession placement, the todo.md
backlog split, and all four verification commands — is accurate and passes clean. Once the
confidence-decay claim is corrected (or the helper is implemented and then accurately described),
this stage is ready to re-review and the whole BL-2.6 milestone (Stages 1–10 plus the
live-acceptance bug fix) is otherwise ready for a full DoD pass.

### Review Confidence

Full read. Read the plan and session-state in full, read the actual diff for all four Stage 10
files, cross-checked every accuracy claim in the task against the live source (`classification.py`,
`naked_eye_source.py`, `contacts.py`, `decay.py`, `tools.py`), checked `git log`/`git diff` across
the entire BL-2.6 commit range for `decay.py` and `test_decay.py`, and ran the full verification
suite (ruff format, ruff check, mypy --strict, pytest) myself.

## Stage 11 (bug fix) review — commit `faa5372`

Scope: closes the one required fix from the Stage 10 review above — implements
`decay.classification_confidence_at`, the function that CLAUDE.md/plan.md §6 had documented as
already working but that no code across BL-2.6's Stages 1-9 actually built. Reviewed against the
Stage 10 review section, `plans/classification-refinement/plan.md`'s "Does classification decay?"
design section, and `plans/classification-refinement/implementation.md`'s Stage 11 log.

### Review Summary

`git show faa5372 --stat` confirms the diff touches exactly `decay.py`, `classification.py`,
`tools.py`, `run-body.sh`, two test files, and the two plan-log markdown files — no scope drift.

- **`established_sim` vs `last_seen_sim` is the correct key.** Read `classification.py`'s fold
  helpers directly: `_fold_same_level`'s reinforce branch (line 252) and `_collapse` (both call
  sites, lines 289/295, covering both the refine-then-disagree and same-level-disagree
  contradiction paths) all stamp `established_sim=now_sim`. The `hold` branch in
  `fold_classification` (line 216, `return FoldOutcome(classification=held, ...)`) returns `held`
  untouched — `established_sim` stays frozen while `Contact.last_seen_sim` keeps advancing on
  every poll. This is exactly the scenario the plan's design section describes ("a crew member who
  identified a T-72 two minutes ago... becomes less sure") and exactly what the implementer's
  reasoning claims. Reinforcement correctly resets the decay clock (a fresh confirmation makes the
  claim fresher, not just higher-confidence); hold correctly does not (a coarser re-observation is
  not a new confirmation of the specific claim). `classification_confidence_at` reads
  `contact.classification.established_sim`, matching this.
- **Decay formula is standard and correctly composed.** `contact.classification.confidence *
  math.pow(0.5, elapsed_s / IDENTITY_HALF_LIFE_S)`, `elapsed_s = max(0.0, now_sim -
  established_sim)`. Verified via the five new `test_decay.py` cases: unchanged at zero elapsed,
  exactly halves at one half-life, `held/16` at four half-lives (asymptotic toward but never
  reaching zero, confirmed structurally — the function can only return exactly 0 if the stored
  confidence itself is 0, which no fold path produces), and the `established_sim`-vs-`last_seen_sim`
  distinction test (`last_seen_sim=1000`, `established_sim=0`, decay measured from 0 — correct).
  The "negative-clamp" test (`established_sim=100`, `now_sim=0`) guards a `now_sim` that lands
  before the claim's own `established_sim` — an edge case that shouldn't arise in the live poll
  loop (sim time is monotone) but mirrors the exact same clamp `certainty_of` already applies for
  the identical reason; real guard, not decorative, and consistent with the module's existing
  pattern rather than a new one.
- **`level`/`value` genuinely stay raw.** `tools.py`'s `_classification_facts` reads
  `classification.value` and `classification.level.name.lower()` straight off the held claim
  (unchanged lines) and only routes `confidence` through `classification_confidence_at`. The new
  `test_describe_contact_classification_confidence_decays_with_elapsed_time` integration test
  confirms this end-to-end through `describe_contact`: confidence halves at one half-life while
  `level`/`value` are asserted equal between the fresh and elapsed reads. Matches the plan's "level
  stays sticky, only confidence decays" invariant exactly.
- **`console.py` needed no change — confirmed directly, not taken on faith.** Grepped
  `console.py` for `classification`: the only hits are `Event.classification`/
  `Event.previous_classification` (the `CONTACT_CLASSIFICATION_CHANGED` transition-rendering
  fields, an unrelated `belief.events.Event` attribute pair) and the `find <text>` help string.
  Nothing in `console.py` reads `Contact.classification.confidence` or
  `ClassificationBelief.confidence` directly — every render goes through `tools.py`'s
  already-decayed `facts.classification`. The implementer's claim holds.
- **CLAUDE.md / plan.md §6 "no edits needed" claim verified against current text, not taken on
  faith.** `body-layer/CLAUDE.md`'s `decay.py` and `classification.py` entries (read in full)
  both now correctly describe `classification_confidence_at` as the consumer of
  `IDENTITY_HALF_LIFE_S`, decaying only `.confidence`, keyed off `established_sim` — text that was
  false at Stage 10 review time and is true now that the function exists. `plans/body-layer/
  plan.md` §6 Decision 4 (line ~824) reads the same way. Since the Stage 10 review's fix was
  "make the docs true," and the docs' existing wording was already accurate once the function is
  real, no second edit was needed — confirmed by direct comparison, not by trusting the log entry.
- **`run-body.sh`'s `--overlay` addition is a simple flag pass-through** — one line, adds
  `--overlay` to the existing `python -m logger --console ...` invocation. `--overlay` is an
  existing, tested `main()` flag (BL-2.5) that mirrors belief events to the DCS text overlay;
  nothing new or unreviewed is introduced by wiring it into the launch script. Correctly separated
  from this commit's actual fix in the commit message.
- **Verification suite reproduced independently**: `ruff format --check`, `ruff check`, `mypy
  src --strict` (21 source files, from `body-layer/`), and `pytest -q` all pass clean —
  252/252, matching the implementation log's count exactly.
- Working tree has only unrelated pre-existing reviewer/implementer agent-memory changes staged
  (from prior sessions, not this commit) — nothing from `faa5372` itself is left uncommitted.

### Required Fixes

None.

### Optional Refinements

None. The negative-elapsed clamp and the asymptotic-never-zero property are both structural
rather than tested at the boundary (e.g. no test drives `elapsed_s` to a very large multiple to
confirm it doesn't underflow to exactly 0.0 in floating point) — not worth a test given
`math.pow(0.5, x)` never reaches exactly zero for finite `x` and the existing four-half-life test
already establishes the shape. Not blocking.

### Verdict

**APPROVED.**

### Review Confidence

Full read. Read the Stage 10 review section, the plan's full "Does classification decay?" design
section, and the Stage 11 implementation log before starting. Read the actual `faa5372` diff for
every changed file (`decay.py`, `classification.py`, `tools.py`, `run-body.sh`, both test files),
traced `established_sim` through every `fold_classification` branch in `classification.py`
directly (reinforce, both collapse call sites, and the hold branch) rather than trusting the
implementation log's description, grepped `console.py` for any direct `classification.confidence`
read, diffed `body-layer/CLAUDE.md` and `plans/body-layer/plan.md` §6 against the Stage 10
review's exact complaint to confirm it's actually resolved, and ran the full verification suite
myself (ruff format, ruff check, mypy --strict, pytest — 252/252).

---

**BL-2.6 status: all ten stages plus the live-acceptance duplicate-contact fix (commit `7581928`)
plus this Stage 11 confidence-decay fix (`faa5372`) are reviewed and approved. No open required
fixes remain on this branch. Ready for a full-milestone DoD pass.**
