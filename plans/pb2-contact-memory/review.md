## Review: Stage 3 (Emission policy and pipeline wiring)

Branch: `feature/pb2-contact-memory`. Reviewed against `plans/pb2-contact-memory/plan.md`'s
"Stage 3 — Emission policy and pipeline wiring" section and "Interface confirmation" gap 2, and
`plans/pb2-contact-memory/implementation.md`'s Stage 3 entry. Stages -1, 0, 1, 2 already
reviewed/approved above and not re-reviewed here.

### Review Summary

Read every changed file's full diff directly (not just the implementer's self-report) and ran
all verification commands myself.

- **Pre-Stage-3 behavior preservation.** `git diff` on `test_hybrid_source.py`, `test_logger.py`,
  and `test_naked_eye_source.py` shows pure additions — every hunk is a `+` block appended at
  end-of-file; no existing assertion line was touched. `logger.py`'s diff confirms `main()`'s
  original no-`--console` path now calls `_build_sources(..., emit_mode="on_change")` where it
  previously constructed the same two classes with no `emit_mode` argument at all — since the
  field defaults to `"on_change"`, this is behavior-preserving by construction, not just by test
  coverage. `hybrid_source.py`'s debounce check became
  `if self.emit_mode == "on_change" and distinct_texts == self._last_emitted_texts` — for the
  default mode this is identical to the prior unconditional check.
- **Naked-eye acquisition-cap vs. emission-cap split**, read directly in
  `naked_eye_source.py:195-311`: `_acquired_ids` is a genuinely separate field from
  `_previously_visible_ids`, both reset together on a telemetry gap. `_acquire_on_change` is
  the original logic verbatim (renamed into a method, `_previously_visible_ids` still updated
  unconditionally on every currently-visible id, capped-out objects still never retried). 
  `_acquire_every_poll` grows `_acquired_ids` by at most `NAKED_EYE_MAX_NEW_PER_POLL`
  not-yet-acquired objects per poll (nearest-first, same throttle), intersects with
  currently-visible each poll (so a departed object re-acquires on return), and emits every
  object currently in the acquired set regardless of when it joined — so an already-acquired
  object is never re-capped for repeat emission. This matches the plan's "gates entry into the
  acquired set, not emission" instruction exactly.
- **`test_every_poll_mode_progressively_acquires_capped_overflow`** genuinely exercises two
  sequential polls with 5 simultaneous candidates against a cap of 3: first poll asserts
  `len(first) == NAKED_EYE_MAX_NEW_PER_POLL` (3), second poll (all 5 still visible) asserts
  `len(second) == 5` — 3 re-emitting plus 2 newly acquired. This is a real multi-poll
  progressive-acquisition test, not a single-poll check with a misleading name.
- **The plan's core acceptance test**, `test_emission_pipeline.py`, drives a real
  `NakedEyePerceptionSource` (monkeypatched geometry/LOS the same way
  `test_naked_eye_source.py` does) through 61 polls at 1 Hz into a real
  `belief.contacts.ContactStore.ingest`/`tick`, then asserts
  `certainty_of(contact, 60.0) == "observed"` under `every_poll` and `!= "observed"` under
  `on_change` for the same stationary, continuously-visible object over the same window. This is
  exactly the wiring the plan calls for — belief-layer decay is what's being tested, not just
  that Observations keep being emitted.
- **`--console` scope.** `ConsolePerceptionRunner.run_once()` does ingest+tick and print one
  `t_sim=... contacts=N observations=N` line — no REPL, no command parsing, nothing beyond the
  minimal wiring the plan describes for this stage. Confirmed no `belief/tools.py` or
  `belief/console.py` exist yet (`ls body-layer/src/belief/`: `__init__.py`,
  `association_over_time.py`, `contacts.py`, `decay.py`, `events.py`, `percept.py` — unchanged
  file list since Stage 2's last commit, `git log -1 -- body-layer/src/belief/` still points at
  `2626c6c`). Stage 3 touched zero files under `belief/`.
- **Type discipline.** `Literal["on_change", "every_poll"]` is declared once per source
  (`hybrid_source.py`, `naked_eye_source.py`) and once in `logger.py`'s `_build_sources` — no
  bare `str` parameter anywhere in the call chain. Verified mypy actually catches a typo: edited
  `logger.py`'s `emit_mode="every_poll"` call site to `"every_pol"` and reran
  `mypy src` — it failed with `Argument "emit_mode" to "_build_sources" has incompatible type
  "Literal['every_pol']"`; restored the file and reran clean. Not a decorative annotation.
- **Module boundary.** Only `hybrid_source.py`, `naked_eye_source.py`, `logger.py`, their tests,
  and `body-layer/CLAUDE.md` changed this stage (confirmed via per-commit `git diff --stat` for
  all four Stage 3 commits). No `belief/tools.py`, `belief/console.py`, `decay.py`, `events.py`,
  `percept.py`, or `association_over_time.py` touched.
- **`body-layer/CLAUDE.md`** gained a "Running the live logger" `--console` paragraph and a
  `src/belief/` Structure bullet (the latter backfilling a gap the Stage 0/1 review had already
  flagged as optional/deferred) plus a `src/logger.py` bullet update — matches what actually
  landed, no aspirational claims about Stage 4 functionality.

Ran all verification myself rather than trusting the log:

- `ruff format --check src tests`: pass (35 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from `body-layer/`): pass, no issues in 18 source files
- `pytest tests -q`: **163 passed** — confirmed via `git diff --stat` that Stage 3 added exactly
  12 new `test_*` functions (2 in `test_hybrid_source.py`, 4 in `test_naked_eye_source.py`, 4 in
  `test_logger.py`, 2 in `test_emission_pipeline.py`) and 0 existing test bodies were modified;
  163 = 151 (Stage 2's confirmed count) + 12.
- `git status`: clean working tree. `git log` shows exactly the four claimed Stage 3 commits
  (`c019787`, `dc93004`, `206aff8`, plus the implementation-log commit `ac7f7a0`) on top of
  Stage 2's last commit, all on this branch. The unrelated `todo/todo.md` modification noted in
  implementation.md as "outside this stage's scope" is correctly not part of any Stage 3 commit
  and the working tree is clean, so it isn't a loose end here.

### Required Fixes

None.

### Optional Refinements

- **`hybrid_source.py`'s `_last_emitted_texts` is still updated unconditionally under
  `every_poll`**, per the implementer's own note, even though `every_poll` never reads it. Dead
  writes, not a correctness issue — harmless and cheap to leave as-is rather than special-casing
  the assignment for a mode that doesn't consume it (optional, no action needed).
- **`_acquire_on_change`/`_acquire_every_poll` duplicate the "sort by range, slice to cap" shape**
  (`naked_eye_source.py:262-266` and `:293-297`). Both are short and the underlying set semantics
  genuinely differ (as documented at length in the module docstring and implementation.md), so
  extracting a shared helper would likely cost more clarity than it saves at this size — worth
  revisiting only if a third acquisition mode is ever added (optional).

### Verdict

APPROVED

### Review Confidence

Full read — read the complete diffs for `hybrid_source.py`, `naked_eye_source.py`, `logger.py`,
`body-layer/CLAUDE.md`, and all four Stage 3 test files (`test_hybrid_source.py`,
`test_naked_eye_source.py`, `test_logger.py`, `test_emission_pipeline.py` in full, the latter
being the plan's core acceptance test). Ran format/lint/type/test myself and independently
verified the mypy typing claim by introducing and reverting a real typo rather than trusting the
report. Did not re-verify Stage -1/0/1/2 files, per the existing approvals above.
