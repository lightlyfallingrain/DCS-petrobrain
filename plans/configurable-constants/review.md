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
