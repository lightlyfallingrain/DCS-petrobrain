### Implementation Summary

Implemented Stages 1 and 2 of `plans/configurable-constants/plan.md` on `feature/configurable-constants`
(via `worktree-agent-xt26`). Stage 3 (remaining ~80 body-layer keys), Stage 4 (audio-adapter), Stage 5
(world-model query path) are explicitly out of scope and untouched.

Scope note: the task dispatch's HEAD was already at the target tip sha (`27098c8`); no merge was
needed. The dispatching session was unexpectedly the main checkout on `main`, not a pre-made
isolated worktree, so I created my own worktree (`/Users/sg/Code/worktrees/xt26-configurable-constants`,
branch `worktree-agent-xt26`) off `feature/configurable-constants` before touching anything, per
`AGENTS.md`'s "all work happens in a worktree" rule.

### Files Changed

- `body-layer/src/tuning.py` — **new.** The loader: `real`/`whole`/`fraction`/`table`/`sequence`
  accessors (each resolves and type/bounds-validates its own key at call time, since the `Final`
  constant must bind immediately); `validate_against_defaults()` (catches unknown/typo'd keys by
  checking the override file's keys against `config/defaults.toml`, independent of import order);
  `Resolution`/`AppliedEntry`/`RejectedEntry`/`DefaultedEntry`; `render_startup_block`/
  `render_print_tuning`. Implements Decision 4 REVISED (warn-and-continue) and Decision 4a
  (missing/unreadable named file is *also* not fatal — see below).
- `body-layer/tools/generate_defaults.py` — **new.** AST scan over `src/**/*.py` for `tuning.*`
  calls; extracts key/default/lo/hi/status from the call and a description from the first sentence
  of the `#:` block immediately above (stopping at a blank `#:` paragraph break or a non-`#:` line,
  and rejoining wrapped lines backtick-aware so a dotted identifier split across two comment lines
  does not read as a false sentence break). `--write` regenerates `config/defaults.toml`; without it,
  exits 1 if stale.
- `body-layer/config/defaults.toml` — **new, generated, committed.** The 15 curated keys.
- `body-layer/src/belief/attack_run.py`, `perception/visibility.py`, `belief/callouts.py`,
  `perception/gaze.py`, `belief/decay.py`, `perception/estimation.py` — one literal → one
  `tuning.*` call each, for the plan's curated 15 keys. No value changed. Provenance `#:` comments
  untouched except: three new one-line descriptions above `LOWRES`/`MEDRES`/`HIRES_ANGULAR_RADIUS_RAD`
  (they previously shared one block, per the plan's explicit instruction to write one each — I wrote
  all three, not just the two the plan named, because the shared block's *first* sentence would
  otherwise have been attributed to whichever tier's bullet came first, not to `LOWRES` itself); and
  one added sentence on `SPEECH_RATE_WPS` noting it retires when `AC-B6` lands (plan's "AA-B5
  ordering" section specifies this).
- `body-layer/src/logger.py` — `--print-tuning` (works standalone, without `--aircraft-layer-url`);
  `--aircraft-layer-url` changed from `required=True` to an explicit `parser.error()` check skipped
  only when `--print-tuning` is given; `validate_against_defaults()` + `render_startup_block()`
  called right after `args = parser.parse_args()`, before any other validation.
- `body-layer/pyproject.toml` — added `tuning` to `known-first-party` (isort).
- `.gitignore` (root) — `*/config/tuning.toml`.
- `body-layer/CLAUDE.md` — new "Tuning" section: how to override, startup/`--print-tuning`
  behaviour, regenerating `defaults.toml`, and the residual cross-key coupling risk (see Notable
  Discoveries).
- `plans/configurable-constants/plan.md` — appended Decision 4a's resolution.
- `todo/todo/X-T26.md` — marked `[~]` (Stages 1-2 done, 3-5 not started).

### Decision 4a — resolved per dispatch instruction

Implemented as **not fatal**: a named-but-missing/unreadable `PETROBRAIN_TUNING` file warns loudly
(states the path, says no overrides are in force) and runs entirely on code defaults — same policy
as every other bad-value case, just louder because the blast radius is the whole file rather than
one key. This declines the architect's plan-time recommendation ("yes, still fatal") per the
dispatching instruction's own stated rationale. Text appended to the plan under "Decision 4a
RESOLVED".

### Tests Added

- `tests/test_tuning.py` — one test per row of the plan's "Failure behaviour" table: unset, missing,
  unreadable-TOML, key-absent (silent default), applied override reaches the accessor's return value,
  unknown key (independent of whether anything claimed it — the typo case), wrong type (`real`,
  `whole`, `bool`-is-not-a-number), out of range, `sequence` wholesale replace + wrong-type rejection,
  `table` per-entry merge + unrecognised-entry + per-entry out-of-range/wrong-type + whole-key wrong
  type, startup block vs. `--print-tuning` agreement (same `Resolution`), empty-`rejected` renders as
  confirmation. Two subprocess tests (`test_a_real_constant_resolves_an_override_in_a_fresh_process`,
  `..._a_rejected_value...`) exercise a real production constant (`perception.estimation.
  BEARING_SIGMA_DEG`) end to end in a fresh interpreter — required because this test file's own
  `import tuning` runs in the same process as every other test, which has already resolved every
  real constant once; only a fresh process actually exercises "resolves at import, from the
  environment."
- `tests/test_tuning_defaults_toml.py` — `test_defaults_toml_matches_the_generator`: runs the
  generator in check-only mode as a subprocess, fails if `config/defaults.toml` is stale.
- `tests/test_logger.py` — `test_main_print_tuning_works_without_aircraft_layer_url` (asserts the
  exact "unset" startup line and that `--print-tuning`'s output includes "at default"),
  `test_main_rejects_missing_aircraft_layer_url_without_print_tuning` (the new `parser.error` path).

### Checks (body-layer/, the only subproject touched)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (59 source files, no issues)
- `pytest -q`: pass — 1864 passed, 4 xfailed (unchanged xfail count; no existing test needed
  rewriting, confirming no constant's value changed)

`mypy tests` was not run as part of this task's scope (`body-layer/CLAUDE.md`'s own Commands
section only lists `mypy src`); a bare run surfaces ~150 pre-existing errors in `test_crew_console.py`,
`test_callouts.py`, and `test_logger.py` at line numbers far from anything touched here (528-2814,
none inside the new tests) — confirmed pre-existing, not introduced by this change.

### Notable Discoveries

- **A genuine cross-key coupling the loader's per-key bounds cannot close.** `belief/decay.py`
  asserts `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` at **module import time**
  (`OBSERVED_WINDOW_S` = `perception.gaze.SCAN_CYCLE_PERIOD_S` = `len(SCAN_PLAN) * FOCUS_DWELL_S`).
  All three of `POSITION_HALF_LIFE_S`, `FOCUS_DWELL_S`, and `SCAN_PLAN` are now independently
  tunable. I chose `POSITION_HALF_LIFE_S`'s `lo=20.0` and `FOCUS_DWELL_S`'s `hi=5.0` specifically to
  keep the *default* `SCAN_CYCLE_PERIOD_S` (16.0) safely under any single-key override, but tuning
  `POSITION_HALF_LIFE_S` down and `FOCUS_DWELL_S`/`SCAN_PLAN` up *simultaneously* can still trip the
  assertion and crash at import — which is itself a disguised "refuse to start," in tension with
  Decision 4 REVISED's intent. This is a real, if narrow, gap: closing it fully needs a cross-key
  validator, which is out of scope for Stages 1-2 (the loader validates one key against its own
  declared bounds, never against another key it is coupled to). Documented in `tuning.py`'s module
  docstring is not where this lives — it's in `body-layer/CLAUDE.md`'s new "Tuning" section instead,
  since the coupling is specific to these three constants, not a property of the loader itself.
- **Generating a usable one-sentence description from hand-wrapped `#:` prose has two real failure
  modes**, both found by actually running the generator rather than reasoning about it: (1) a shared
  intro paragraph followed by several per-item bullets with no blank line between — the naive
  "walk up until non-`#:` line" rule merges all of them, so I added a second stop condition (a blank
  `#:` paragraph-break line, already this project's own comment convention) and found it insufficient
  for `LOWRES_ANGULAR_RADIUS_RAD` specifically (it has no code line directly above it to stop the
  walk, only more shared-block prose), so I wrote it its own one-line description too, matching what
  the plan already required for `MEDRES`/`HIRES`; (2) a backtick-quoted dotted identifier wrapped
  across two comment lines (`` `perception.estimation. `` / `` BEARING_SIGMA_DEG` ``) reads as a
  false sentence break once rejoined with a naive space — fixed by tracking backtick parity across
  the joined lines and omitting the space while a code span is open. Three attack-run gate
  descriptions still carry a cosmetic stray backtick (the per-constant bullet's own leading
  backtick-quoted name), and `IDENTITY_HALF_LIFE_S`'s description has a stray leading `*` from a
  markdown-emphasis artifact — both are readable, accurate, and untouched provenance text; I left
  them rather than editing the authoritative comments to make the generator's output prettier.
- No existing test needed its assertions changed — confirms the stage constraint ("no constant's
  value changes") held throughout the conversion.
