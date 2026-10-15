### Review Summary

Reviewed `feature/configurable-constants` @ `87f8e406c67667235db243a3c81a2702964436e3` (commits
`b1682f6` implementation, `87f8e40` agent memory) against `plans/configurable-constants/plan.md`
and `todo/todo/X-T26.md`. Branch verification: my dispatched base (root checkout, `main` @
`79fc290`) had diverged from the feature branch (both descend from `27098c8` but neither is an
ancestor of the other — `79fc290` is unrelated `BL-B64` work on `main`). Per the dispatch
instructions I did not merge or touch the root; I added a separate scratch worktree
(`/tmp/cc-review-scratch/wt`) checked out directly at the named tip sha and reviewed there, with
`body-layer/.venv` symlinked in from the main checkout (gitignored, not part of the diff) so the
project's own tools could run.

Stages 1-2 are implemented essentially as planned: a lazy, import-time-resolved loader
(`tuning.py`), a generated/committed `config/defaults.toml`, `--print-tuning`, a staleness test,
and the 15 curated constants converted with no value changes. I verified the core mechanism by
mutation and by direct execution (see below), not just by reading — the import-time-binding claim,
the staleness test, the out-of-range rejection path, and `--print-tuning` standalone all behave as
specified when exercised directly.

One real gap, already found and documented by the implementer rather than hidden, is serious enough
that I do not think it should ship undecided (see Required Fixes).

### Required Fixes

- **The `belief/decay.py` cross-key `assert` is a disguised "refuse to start," and it is reachable
  through two of the curated 15 keys exposed by this exact feature.** Verified by direct mutation
  test, not just reading:

  ```toml
  [perception.gaze]
  FOCUS_DWELL_S = 5.0        # within its own declared bounds [0.5, 5.0]
  [belief.decay]
  POSITION_HALF_LIFE_S = 20.0  # within its own declared bounds [20.0, 120.0]
  ```

  Running `logger.py` (or any import of `belief.decay`) with this file set as `PETROBRAIN_TUNING`
  raises an uncaught `AssertionError` at import — the process never comes up, no startup block is
  printed, nothing is logged to the tuning registry. Both values are individually valid; the plan's
  per-key bounds cannot see the coupling between `FOCUS_DWELL_S`, `SCAN_PLAN`'s length, and
  `POSITION_HALF_LIFE_S` because `OBSERVED_WINDOW_S` is derived from the first two and the assert
  compares it against the third.

  This is not a hypothetical edge case: `FOCUS_DWELL_S` and `POSITION_HALF_LIFE_S` are both in the
  advertised "pilot would plausibly touch" set the plan itself names, and the two are exactly the
  kind of pair someone fiddling with scan timing and decay together would try. The feature's
  entire premise — stated three times in the plan (Decision 4, Decision 4 REVISED, Decision 4a) —
  is that a bad tuning file must never block a sortie. This does, with a raw traceback instead of
  the startup block, and it does so for a combination of two in-bounds values rather than an
  obviously-wrong one.

  **Verdict: not acceptable to merge as a documented-but-unfixed gap.** The implementer's own
  write-up (and `body-layer/CLAUDE.md`'s new Tuning section) frames this as a known limitation
  rather than a defect, but it directly contradicts the decision the whole feature exists to
  implement, in the two most-likely-to-be-combined knobs of the curated set. Recommended fix, cheap
  and in scope for "mechanism, not calibration": convert the hard `assert` in `belief/decay.py`
  into the same warn-and-continue shape as every other rejection in this feature — detect the
  violated invariant after both constants have resolved (e.g. a small cross-key check called from
  the same place `validate_against_defaults()` is called, or inline where the assert sits now,
  printed through the existing `Resolution`/startup-block mechanism) and clamp or widen to restore
  the invariant rather than crashing, with a loud warning naming both keys and which one was
  adjusted. A full general cross-key validator is unnecessary for Stages 1-2 — one targeted check
  for this one known coupling is enough, and the mechanism for rendering it already exists.

- **`body-layer/tools/generate_defaults.py` fails `ruff format --check`.** Confirmed by running the
  checks myself (the implementer's report, correctly, only ran `ruff format --check src tests`,
  which is what `body-layer/CLAUDE.md`'s Commands section documents — not their defect). But
  `tools/` is new surface this feature introduces and ships unformatted:

  ```
  $ cd body-layer && .venv/bin/ruff format --check tools
  1 file would be reformatted, 5 files already formatted
  ```

  Four small reformats (two long conditional-expression lines, one f-string, one dict comprehension
  wrapped). Trivial, mechanical, `ruff format tools/generate_defaults.py` fixes it. Not a reason to
  reopen the Commands-section question (`research/` has a pre-existing, out-of-scope unformatted
  file that is not this feature's problem and should stay out of this fix), but the new file itself
  should be clean before merge.

### Optional Refinements

- **The generator's self-name-stripping produces three cosmetic stray backticks and one stray
  asterisk in `config/defaults.toml`.** Confirmed in the generated file: the three `attack_run`
  gate descriptions read `ATTACK_RUN_CHANGE_THRESHOLD_DEG\`` (3.0): ...` — the opening backtick
  around the constant's own self-reference is dropped but the closing one survives, because the
  generator's first-sentence extraction starts mid-way through the source comment's own
  backtick-quoted name. `IDENTITY_HALF_LIFE_S`'s description drops the closing `*` of a markdown
  emphasis span (`what a contact *is.` instead of `*is*.`). All four are readable and the
  information is intact — this is purely a markup-balance artifact in a comment-only generated
  file, not a functional defect, and the implementer already identified and explained both causes
  precisely in "Notable Discoveries." Worth a follow-up polish to the generator (strip a leading
  backtick-quoted self-reference as a unit, track the asterisk the same way backticks are already
  tracked) but not worth blocking merge over four comment lines in a file whose own header says the
  code comment is the authority.
- **`generate_defaults.py`'s AST-plus-regex comment extraction is inherently fragile** (acknowledged
  by the implementer as the one place real complexity went) — it is already the one place in this
  feature with nontrivial logic, and Stage 3 (if ever taken) will exercise it against ~80 more
  comment blocks with more shapes. Not a blocker now; worth one extra pass of robustness before
  Stage 3 is scoped, if it is.

### Checklist walked

- **Type hints / `mypy --strict`**: `mypy src` clean (59 files) and `mypy tools` also clean (6
  files, not part of the documented gate but checked anyway since `tools/` is new). `mypy` was not
  run on `tests/`, matching `body-layer/CLAUDE.md`'s own documented gate; a bare `mypy` run surfaces
  ~150 pre-existing errors confined to `test_crew_console.py`/`test_callouts.py`/`test_logger.py`
  at line numbers (528-2814) nowhere near the new test code — confirmed pre-existing, not this
  change's defect, and nothing this feature added to `tests/` would have been caught by a gate that
  already does not run there.
- **Provenance/confidence**: not applicable in the GIS sense — this feature's own provenance
  question is "does the `#:` comment stay the authority," and it does: nothing moved, the generator
  only reads, `config/defaults.toml`'s header states the authority explicitly, and the staleness
  test (verified by mutation, see below) makes drift mechanically impossible rather than a matter of
  discipline.
- **No DCS-internals claim encoded as fact**: not applicable, no DCS internals touched.
- **Coordinate transforms**: not applicable.
- **No writes to the DCS installation**: not applicable, no DCS access in this feature.
- **No large datasets staged**: confirmed — `*/config/tuning.toml` added to root `.gitignore`;
  `defaults.toml` is 92 lines, committed deliberately.
- **Parallel-treatment grep check** (the standing check from a prior finding): the plan claims the
  mechanism is import-time-resolved for every one of the 15 keys, including through derived
  constants. I did not take the file list as sufficient — I ran it: set `PETROBRAIN_TUNING` to
  override `perception.gaze.FOCUS_DWELL_S`, imported `belief.decay`, and confirmed the override
  propagated through the derived chain (`FOCUS_DWELL_S` → `SCAN_CYCLE_PERIOD_S` →
  `OBSERVED_WINDOW_S`), not just at the directly-tunable constant itself. It does.
- **Scope fit**: matches Stages 1-2 exactly. No Stage 3/4/5 creep — diff touches only body-layer,
  no audio-adapter or world-model files. `todo/todo/X-T26.md` correctly marked `[~]`, not `[x]`.
- **Module responsibility**: `tuning.py` is the one place that classifies a key; both renderers
  (`render_startup_block`, `render_print_tuning`) read the same `Resolution` object, verified by
  reading the code — they cannot disagree because there is only one object to disagree about.
- **Tests present and meaningful**: verified by mutation, not just reading. Removing the
  out-of-range rejection branch in `real()` causes `test_out_of_range_is_rejected_and_default_
  stays_in_force` and the fresh-process test to fail — real regression detection. Mutating
  `config/defaults.toml`'s committed value causes `test_defaults_toml_matches_the_generator` to
  fail — the staleness guard genuinely guards.
- **Unnecessary abstraction/duplication**: none found. The five accessor shapes (`real`/`whole`/
  `fraction`/`table`/`sequence`) are each used by at least one real constant in this stage;
  `fraction` delegates to `real` rather than duplicating bounds logic.
- **Performance regression risk**: none — one file read and dict build per process, at import,
  confirmed by reading `_build_state`/`_get_state`'s lazy-singleton shape; zero per-tick cost.
- **New files staged**: confirmed via `git diff --stat` on the two commits; nothing untracked.
- **Format/lint/type/test gates, run by me, not taken from the report**:
  - `ruff format --check src tests`: pass (129 files)
  - `ruff format --check .` (whole body-layer): **fails** — 2 files, one pre-existing and
    out-of-scope (`research/`), one new and in-scope (`tools/generate_defaults.py`) — see Required
    Fixes.
  - `ruff check .`: pass, all checks passed.
  - `cd body-layer && .venv/bin/mypy src`: pass, 59 files, no issues.
  - `pytest -q`: pass, **1864 passed, 4 xfailed** — matches the implementer's reported count
    exactly.
- **Debug code / TODOs**: none found in the diff.

### Verdict

NEEDS REVISION

Two required fixes, both narrow and cheap: (1) the `decay.py` cross-key assert must not be able to
crash the process on two individually-valid overrides from the curated set — convert it to the
same warn-and-continue shape the rest of this feature uses; (2) `ruff format` the new
`tools/generate_defaults.py`. Everything else — the mechanism's correctness (verified by mutation
and direct execution, not just reading), the inclusion-test fidelity of the 15 conversions, the
provenance preservation, the `--print-tuning`/startup-block agreement, the staleness guard, and the
test suite's genuineness — held up under adversarial checking and I would approve on those grounds
alone. The optional refinements (cosmetic generator artifacts) are not blockers.

---

## Fix-pass review (2026-10-15) — `ba45c3b` on `feature/configurable-constants`

Reviewed the single fix commit `ba45c3b` on top of the previously-reviewed `7acce1a`, against this
review's two Required Fixes above, `plans/configurable-constants/implementation.md`'s fix-pass
writeup, and `.claude/agent-memory/implementer/project_tuning_crosskey_coupling.md`. Worked in a
fresh worktree created from `feature/configurable-constants` outside the repo root (HEAD matched
the dispatched tip sha `ba45c3b32def1b5b7899780e6ffcccfe5d703889` exactly, tree clean, no merge
needed). Verified by direct execution/mutation throughout, not by reading the report.

### Required Fix 1 — the cross-key crash

**Fixed, and the import-order premise the fix depends on checks out.** Read `perception/gaze.py`
and `belief/decay.py` directly: `belief.decay` imports `FOCUS_DWELL_S, SCAN_CYCLE_PERIOD_S` from
`perception.gaze` (line 64), so `gaze`'s module body — including both `tuning.real`/`tuning.sequence`
calls that bind `FOCUS_DWELL_S` and `SCAN_PLAN` as `Final` — finishes executing before
`belief.decay` exists at all. Confirmed the "other modules import `SCAN_CYCLE_PERIOD_S` directly
from `gaze`" claim too: `belief/optic_policy.py`, `perception/naked_eye_source.py`, and `logger.py`
all do, independent of `belief.decay`. The design conclusion that follows from this — the check has
to sit inside `gaze`'s own accessor calls, not in `decay`'s assert — is correct, not merely
plausible.

**Re-ran the reviewer's exact reproduction TOML myself**, directly against the real production
modules (not the test harness): process starts, `FOCUS_DWELL_S` and `POSITION_HALF_LIFE_S` both
land at their code defaults (2.0, 30.0), and the rejection is visible with reason
`invariant violation` naming both keys — reproduced identically through `logger.py --print-tuning`,
the real CLI entry point, and through a bare Python import, not just the subprocess test.

**Tried to break "provably sufficient" rather than accept the claim:**
- All three coupled keys overridden together, still violating → all three correctly rejected, all
  fall back to defaults.
- `SCAN_PLAN` alone overridden (lengthened) to violate the invariant against the other two
  defaults → rejected alone, correctly; the other two were never touched by the file so needed no
  action.
- A fully safe override of all three (within bounds and non-violating) → all three applied
  normally, zero false positives.
- A wrong-typed `FOCUS_DWELL_S` (`"nope"`) alongside a violating `POSITION_HALF_LIFE_S` → correctly
  classified `wrong type`, not swallowed by the coupling check — precedence holds as claimed.

Every case I constructed behaved as documented. `assert OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S`
in `decay.py` still fires for a genuine code-defaults violation (did not need to mutate this to
confirm — the logic is unchanged, only a comment was added, and the four scenarios above all show
the assert being satisfied post-rejection, which is the only way it could be reached now). No
second hardcoded copy of the defaults: `_defaults_registry()` reads the same committed
`config/defaults.toml` `validate_against_defaults()` already reads, confirmed by reading the code —
there is nothing here for the generator's staleness test to miss.

**The double-fault case the implementer self-declared as an accepted imprecision — I reproduced it
too**, rather than taking the writeup's word: `FOCUS_DWELL_S = 10.0` (independently out of its own
`[0.5, 5.0]` bounds) alongside `POSITION_HALF_LIFE_S = 25.0` (independently safe, inside
`[20.0, 120.0]`, and would have resolved fine against the real default `FOCUS_DWELL_S = 2.0`).
Result: `FOCUS_DWELL_S` is correctly classified `out of range`; `POSITION_HALF_LIFE_S` is
classified `invariant violation` and falls back to its default, even though it was never actually
unsafe. **This is real, and the characterization is accurate** — the pre-check uses `10.0`, the raw
out-of-bounds value, because `_check_scan_decay_coupling` runs before `FOCUS_DWELL_S`'s own bounds
check. **I judge this acceptable to merge, not a blocker**: the startup block still shows both
rejections side by side, and `POSITION_HALF_LIFE_S`'s own detail text states the exact
`FOCUS_DWELL_S` value the coupling check used — a pilot reading both lines can correctly infer
"fix `FOCUS_DWELL_S` first," which is also the correct action. Nothing crashes, nothing silently
picks an unsafe value, and engineering this away would mean re-ordering the bounds check ahead of
the coupling check for exactly three keys, which is more structural change than the task scoped for
one targeted check. The tradeoff the implementer made — document it, don't build around it — is the
right one.

**One gap I would still ask for, short of blocking**: no test constructs this double-fault case.
Per this project's own standing lesson ("a guard entry no test defends is a comment, not a
contract"), an accepted-but-untested edge case is exactly the shape that regresses silently later —
e.g. if precedence in `real()`/`sequence()` were ever reordered, this specific behavior (which key
wins, which reason text appears) would change with no test noticing. I'm not requiring it for this
merge — the behavior is safe and the task was explicitly scoped to the reviewed reproduction — but
recommend filing it as a quick follow-up test, named for exactly this scenario, before the next time
this mechanism is touched. Listed under Optional Refinements, not Required Fixes, because the
behavior itself is correct and safe; only its test coverage is thin.

### Required Fix 2 — `ruff format` on `tools/generate_defaults.py`

Confirmed fixed: `ruff format --check tools/generate_defaults.py` and the other three changed files
all report clean individually. `ruff format --check .` across the whole subproject still fails, but
only on the one pre-existing, out-of-scope file this review already named
(`research/2026-10-05-security-audit.md`) — unchanged by this commit, confirmed by `git show
ba45c3b --stat` not touching it.

### `tools/` and the documented gate

Agree with the implementer's call not to edit `body-layer/CLAUDE.md`'s Commands section inside this
narrow fix pass. Checked myself: `audio-adapter/`, `brain-layer/`, and `world-model/` all also carry
a `tools/` directory, so widening the gate is a decision with the same shape across (at least) four
subprojects, not a one-line edit local to this feature — and `research/2026-10-05-security-audit.md`
already shows that a naive `ruff format --check .` would break on unrelated, pre-existing content in
at least one of them. The right scope, if and when this is taken up: widen each subproject's
documented gate to its own `tools/` (where real source lives there), and either exclude
`research/*.md` code-block content from ruff's purview explicitly (it's documentation containing
illustrative snippets, not source) or fix it in its own unrelated pass — not fold it into whichever
feature happens to touch `tools/` next. This belongs in `todo/backlog/` as a cross-cutting item, not
as code in this fix.

### Verification — run myself, not taken from the report

```
cd body-layer && .venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/mypy src && .venv/bin/pytest -q
```

- `ruff format --check .`: fails only on `research/2026-10-05-security-audit.md` (pre-existing,
  out of scope) — matches the claim.
- `ruff check .`: all checks passed.
- `mypy src`: success, no issues found in 59 source files.
- `pytest -q`: **1869 passed, 4 xfailed** — matches exactly. Confirmed all 5 new tests exist and
  pass **by name**, not by `-k` filter: `test_cross_key_coupling_rejects_both_overrides_and_falls_
  back_to_defaults`, `test_cross_key_coupling_trips_from_a_single_overridden_key`, `test_cross_key_
  coupling_does_not_fire_for_a_safe_override`, `test_cross_key_coupling_does_not_override_a_more_
  specific_rejection`, `test_reviewer_repro_scan_decay_coupling_does_not_crash_the_process` — all
  `PASSED` in `-v` output.

### Fix-pass Required Fixes

None. Both of the original Required Fixes are resolved.

### Fix-pass Optional Refinements

- **Add a test pinning the double-fault precedence case** (one coupled key independently
  out-of-range and large enough to make the pre-check wrongly flag a second, genuinely in-bounds
  key) — the behavior is correct and safe as verified above, but currently defended only by prose
  in the docstring/implementation writeup, not by a test. Low effort; prevents silent regression if
  the check ordering is ever touched.
- **The agent-memory entry (`project_tuning_crosskey_coupling.md`) states the rejection-scope claim
  as unconditionally "provably sufficient" without carrying forward the double-fault caveat** that
  `implementation.md` documents candidly. A future reader of memory alone (without the plan/review)
  could reasonably assume full precision. Worth a one-line addition pointing at the caveat, not a
  rewrite.
- File the `tools/`-gate widening question (see above) as a `todo/backlog/` cross-cutting item
  rather than letting it live only in this review and the implementation writeup.

### Fix-pass Verdict

**APPROVED.** Both required fixes are genuinely fixed, verified by direct execution and mutation
against the real production modules and the real CLI entry point, not by trusting the report. The
one self-declared imprecision (double-fault precedence) is real, reproduced, and judged acceptable
to merge as documented behavior — safe, and the startup block gives the pilot enough information to
self-diagnose correctly even in that case. Proceeds to Performance Reviewer and Security (deep
analysis), then DoD, per the standing sequence.

### Fix-pass Review Confidence

Full read of the fix commit's diff (`tuning.py`, `decay.py`, `test_tuning.py`,
`generate_defaults.py`, the implementation writeup, the memory file). Verified by direct execution
against the real modules rather than trusting the test suite alone: the import-order premise (read
the actual import statements), the reviewer's original reproduction (re-run via both a bare import
and `logger.py --print-tuning`), four additional hand-constructed override combinations beyond the
implementer's own five tests (all three coupled, one alone, a fully safe set, and the self-declared
double-fault case), and the format/lint/type/test gate commands run myself with actual output
inspected, not summarized counts accepted on faith.

---

### Review Confidence

Full read of the plan, brief, and implementation account; full read of `tuning.py`,
`generate_defaults.py`'s behaviour (not every line of its AST-walking logic), the six converted
source files' diffs (all 15 constants spot-checked against the plan's curated list — none changed
value), `logger.py`'s CLI wiring, and the generated `defaults.toml`. Verified by running the actual
checks (`ruff format --check`, `ruff check`, `mypy src`/`tools`, `pytest -q`) rather than trusting
the implementation report, and by direct execution/mutation rather than reading alone: the
import-time propagation through a derived constant, the cross-key assert crash, the staleness
test's sensitivity to a changed default, and the out-of-range rejection's test coverage were all
reproduced live, not inferred. Not independently re-derived: the full AST-walking logic inside
`generate_defaults.py`'s comment-extraction helper (spot-checked its *output* against source
comments instead, which is where the cosmetic artifacts were found) and the ~150 pre-existing
`mypy` errors in `tests/` (confirmed their line numbers fall outside anything this feature touched,
did not read all 150).

---

## Fix pass 2 review — security.md's one Recommended finding (commit `8339a57`)

Reviewed in isolation: the single commit `8339a570f5774bc1640f5aeb2865bd847a429666`, in a dedicated
worktree at that exact tip (`git worktree add --detach /Users/sg/Code/worktrees/review-xt26-fixpass2
8339a57...`), base verified by `git rev-parse HEAD` before any check ran. Scope is the one
Recommended finding in `security.md` — the undefended `RESOLUTION_ANGULAR_RADIUS_RAD <=
LOWRES_ANGULAR_RADIUS_RAD` coupling — not a re-review of the whole feature, which stands as already
APPROVED by Reviewer, Performance and Security.

### The duplicated-literal question — resolved, no action needed

Both of the implementer's reasons for writing the literal `0.00128` rather than a name reference
are independently verified true, not merely plausible:

1. **Module order.** `grep -n` on `body-layer/src/perception/visibility.py` confirms
   `LOWRES_ANGULAR_RADIUS_RAD` (line 312) and `MEDRES_ANGULAR_RADIUS_RAD` (line 327) are both bound
   by `tuning.real(...)` calls that execute at line 312/327, strictly before
   `RESOLUTION_ANGULAR_RADIUS_RAD`'s own assignment at line 405. A forward `Name` reference there
   would raise `NameError` at import — confirmed by reading execution order, not inferred from
   position in the file alone (Python binds top-to-bottom at module load, so textual order here is
   execution order).
2. **The generator's AST literal-reader.** `body-layer/tools/generate_defaults.py`'s `_literal()`
   (lines 64-78) matches only `ast.Constant`, `ast.Tuple`, `ast.List`, `ast.Dict`, and
   `ast.UnaryOp(USub)`; anything else falls through to `raise ValueError(f"unsupported literal
   node: {ast.dump(node)}")`. There is no `ast.Name` branch. A name reference in `lo=`/`hi=` would
   make `generate_defaults.py --write`/the staleness test fail loudly with that `ValueError`, not
   silently misrender.

Both failure modes are loud (`NameError` at import, `ValueError` at generation), not silent, so the
residual risk from the duplicated literal is exactly what the implementer's own in-line comments
say it is: if `RESOLUTION_ANGULAR_RADIUS_RAD` is ever changed, these two `lo=` bounds silently stop
matching the floor they exist to enforce, and **nothing fails** — the two failure modes above guard
against a *reference*, not against the two copies drifting apart by independent edits. **A cheap,
concrete guard is available and I recommend adding it, but not as a blocker**: a test that calls
`generate_defaults.collect_declarations()` and asserts
`decl.lo == RESOLUTION_ANGULAR_RADIUS_RAD` for the `LOWRES`/`MEDRES` keys would read the *current*
value of the floor dynamically (not a second hardcoded `0.00128`) and would fail the moment the two
go out of sync. The in-line comment naming the source constant is honest and well-written, but a
comment is read, not enforced. Given this coupling's low churn and the explicit two-directional
comments already in place, I would not block merge on this, but it belongs in `todo/backlog/` as a
named follow-up rather than only in this review.

### Required Fix — the three new "approximate range" figures are wrong by ~4x

Judging the new sentences as the pilot-facing text they are (per the dispatch), two of the three
claims each sentence makes are correct — the inverse-relationship direction, and that `lo` is the
dangerous bound — but the **numeric range each one states is wrong**, and wrong in a way that
re-introduces exactly the failure mode the original security finding exists to prevent: a reader
trusting a stated number that doesn't match the code.

Each new sentence states both a formula and a figure:

- `LOWRES`: "`range = size_m / threshold`... the default puts the presence boundary at **~9.3 km**
  for a 7 m vehicle."
- `MEDRES`: "...the default puts the classification boundary at **~2.0 km** for a 7 m vehicle."
- `HIRES`: "...the default puts the type-ID boundary at **~1.0 km** for a 7 m vehicle."

Applying the sentence's own stated formula to the actual default values (`LOWRES=0.003`,
`MEDRES=0.014`, `HIRES=0.028`, confirmed by reading the `tuning.real(...)` calls) gives:

- `7 / 0.003 ≈ 2333 m` (**~2.3 km**, not 9.3 km)
- `7 / 0.014 = 500 m` (**~0.5 km**, not 2.0 km)
- `7 / 0.028 = 250 m` (**~0.25 km**, not 1.0 km)

All three stated figures are exactly ~4x the value the sentence's own formula produces. That 4x is
not noise — it is the retired flat `BINOCULAR_RANGE_MULTIPLIER` (confirmed in
`perception/optics.py`: "`BINOCULAR_RANGE_MULTIPLIER` is retired, not carried forward"), and the
9333 m / ~1990 m / ~1000 m figures the new sentences quote are lifted from the pre-existing
calibration note two paragraphs above them in the same docstring, which derives them with
`size / threshold * BINOCULAR_RANGE_MULTIPLIER` (explicitly, in its own prose) — a binocular-ladder
figure, not a plain-naked-eye one. The function these constants actually feed
(`_recognition_thresholds_m`/`_achieved_tier` in the same file) defaults its `optic` parameter to
`UNAIDED_OPTIC`, whose `presence_range_mult`/`class_range_mult`/`type_range_mult` are all `1.0`
(confirmed in `perception/optics.py` lines 141-143) — so "the default", read as the function's own
default parameter, is the naked-eye case, and the naked-eye case is the ~2.3/0.5/0.25 km figures,
not the binocular ones the new text states.

**This is a correctness bug in new pilot-facing prose, not a style nit**, and it sits in the exact
sentence the security finding asked for specifically because a pilot without it "moving a number
the 'safe' direction" has no way to judge the consequence — a wrong number is worse than no number,
because it reads as authoritative. Fix: either state the correct naked-eye figures (~2.3 km / ~0.5
km / ~0.25 km) or, if the binocular figures are intended as the illustrative case, say so explicitly
and include the multiplier in the stated formula rather than presenting `range = size_m / threshold`
as complete.

### Recommended (disclosed by implementer, not hidden) — the new text never reaches the file the finding was about

`security.md`'s own framing of this finding is explicit: *"Nothing in **the rendered file** says
the relationship is inverse... nothing says a value below 0.00128 breaks a documented invariant."*
"The rendered file" is `config/defaults.toml` — its own header says "To override a value, copy the
key you want into `config/tuning.toml`", i.e. it is the document a pilot actually reads before
tuning. I confirmed by direct inspection that the two changed entries in
`body-layer/config/defaults.toml` read:

```
# Presence tier ("something is there") -- see the block above for the calibration this is the `lowres` row of.
# status: measured | range: 0.00128 .. 0.01
```

— identical prose to before the fix, with only the `range:` lower bound changed. None of the three
new inverse-relationship sentences appear, because `generate_defaults.py`'s `_first_sentence()`
(and the plan's own Stage 1 design: *"The short description is the first sentence of the
constant's `#:` block"*, `plan.md` line 129) takes only the comment block's first sentence, and the
new sentences are the second in each block. The implementer disclosed this plainly in
`implementation.md`'s Fix pass 2 writeup ("Descriptions unchanged in the rendered file because the
generator takes only the comment's first sentence") — this is not a hidden gap, and I want to credit
that it was caught and reported rather than silently left.

Net effect: the numeric floor itself (the actual defect — an override could put `LOWRES`/`MEDRES`
below the optical-resolution floor `clustering.py`'s proof relies on) **is fixed and tested**; the
pilot still cannot learn the inverse-relationship/consequence story from the one file
`security.md` named as the problem. Given the parent finding was Recommended, not Required, and
explicitly reserved the "how much to invest here" call to the user (Options A-D), I read this as the
same shape of residual risk, now partially addressed and explicitly logged rather than resolved. Not
a blocker on its own. Suggest a short `todo/backlog/` item: either extend
`generate_defaults.py`'s rendering for these three keys (or generally) to carry a second line, or
accept that the pilot-facing warning lives in source only. The 4x math error above is independent of
this and blocks regardless of where the text ends up rendering.

### Tier-ordering check — no new finding

Checked whether tightening only `LOWRES`/`MEDRES`'s `lo` leaves any override combination that
inverts `type <= class <= presence` range ordering. It does not: `_recognition_thresholds_m` chains
`class_threshold_m = min(presence_threshold_m, ...)` and `type_threshold_m =
min(class_threshold_m, ...)` (confirmed by reading the function), so tier-range ordering is a
structural `min()` guarantee independent of the angular-radius constants' own relative values — the
module's own docstring states this explicitly ("this is what makes tier monotonicity... a structural
guarantee"). `HIRES_ANGULAR_RADIUS_RAD`'s `lo=0.002` unchanged is correct: `0.002 > 0.00128`, so no
floor violation exists there, confirmed by direct comparison.

### Verification — actual output, not claimed counts

Worktree `.venv` was absent (gitignored), rebuilt matching the root checkout's installed tool
versions exactly (`ruff 0.16.6`, `mypy 2.3.1`, `pytest 9.1.1`, confirmed identical before running
anything):

- `ruff format --check .` — fails on exactly one file, the pre-existing out-of-scope
  `research/2026-10-05-security-audit.md`, matching the claimed baseline.
- `ruff check .` — all checks passed.
- `mypy src` — success, 59 source files, no issues.
- `pytest -q` — **1870 passed, 4 xfailed**, matching the claimed count exactly.
- Mutated the new test: reverted `LOWRES_ANGULAR_RADIUS_RAD`'s `lo` back to `0.0005` and re-ran
  `test_lowres_override_below_the_resolution_floor_is_rejected` alone — it failed red
  (`AssertionError: assert '0.0005' == '0.003'`), confirming the test is not decorative. Restored
  the fix afterward; `git diff` on the file is empty.
- Re-ran the implementer's own sanity check (`PETROBRAIN_TUNING` pointing at a file with
  `LOWRES_ANGULAR_RADIUS_RAD = 0.0005`): process starts, constant resolves to `0.003`, and
  `render_startup_block` shows `rejected (1)` with `perception.visibility.LOWRES_ANGULAR_RADIUS_RAD:
  out of range (0.0005 out of range [0.00128, 0.01])` — matches the claim exactly, new bound
  included.

### Fix-pass-2 Verdict

**NEEDS REVISION.** The numeric-floor fix itself (the actual security-relevant defect) is correct,
tested, and verified by mutation. The duplicated-literal decision is sound and needs no change. But
the three new pilot-facing sentences state range figures that are wrong by ~4x against their own
stated formula — a factual error in new text whose whole purpose was to prevent exactly this kind of
unverified number reaching the pilot. That has to be fixed before this re-enters the Reviewer →
Security/Performance → DoD sequence. The defaults.toml non-propagation is a real, disclosed
residual gap but not, on its own, a blocker — recommend a `todo/backlog/` item rather than holding
the merge for it, unless the user wants it closed now.

**Required fix:** correct the three stated range figures in
`body-layer/src/perception/visibility.py`'s `LOWRES`/`MEDRES`/`HIRES_ANGULAR_RADIUS_RAD` comments
(~2.3 km / ~0.5 km / ~0.25 km for the stated `range = size_m / threshold` formula and the default
`UNAIDED_OPTIC`), or state plainly that the quoted figures are the binocular-ladder case and include
the multiplier in the formula — either is acceptable, but the sentence must not claim a plain
formula and a multiplier-inclusive number together.

### Fix-pass-2 Review Confidence

Full read of the one commit's diff. Verified by direct execution and mutation, not by trusting the
report: ran the full format/lint/type/test gate myself with real output inspected (not summarized
counts accepted on faith), reverted and re-ran the new test to see it fail red, re-ran the
implementer's sanity check independently, read the actual module source to confirm both halves of
the duplicated-literal claim (module order by line number, the AST matcher's exact branch list) and
to recompute the range figures from the actual default constants and the actual default optic's
multipliers, and read `generate_defaults.py`'s `_first_sentence`/`plan.md`'s Stage 1 design note to
confirm the defaults.toml-propagation gap is structural, not a bug introduced by this pass. Not
independently re-derived: the pre-existing calibration note's own screenshot-ladder measurements
(503 m–8.89 km) — taken as given, since they predate this commit and are out of this review's
scope.
