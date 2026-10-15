### Performance Review

Feature: X-T26, configurable behaviour-affecting constants (`body-layer/src/tuning.py` +
15 converted constants + `logger.py` startup block). Once-per-feature pass, immediately before
DoD. Branch `feature/configurable-constants`, reviewed at tip `2f196acdd77990d937e0eb4cdc072c96b10bf456`
(no merge needed — HEAD already at the named tip).

Target for this phase: body-layer's runtime constraint is the per-poll tick, not a startup budget
(no hard real-time budget applies pre-Petrobrain-Runtime, but this project already tracks poll-tick
cost closely — `BL-11`: 1.1 ms median, 12.6 ms worst observed tick). There is no world-model
pipeline angle here at all: this feature touches only `body-layer`, is startup-only by design, and
has no bearing on the Milestone 5/7 whole-theatre build budgets.

### Findings

#### All 15 constants resolve exactly once, at import, module-level

- **Location:** `belief/attack_run.py` (4 keys), `perception/visibility.py` (3),
  `belief/callouts.py` (2), `perception/gaze.py` (2), `belief/decay.py` (3),
  `perception/estimation.py` (1) — grepped every `tuning.(real|whole|fraction|table|sequence)(`
  call site in `body-layer/src`: all 15 are `Final[...] = tuning.*(...)` at module top level, none
  inside a function body, none re-read per call. `tuning._get_state()` is a lazy module-level
  singleton (`if _state is None`), so the TOML file is read and parsed at most once per process
  regardless of how many of the 15 keys end up claiming it.
- **Risk:** none observed. The plan's design intent — "all cost paid once, at startup" — holds
  exactly as stated; there is no case of a value re-resolved per call or per tick.
- **Action:** none.

#### Startup cost is immeasurable against process-launch noise

- **Location:** `tuning._build_state()` (TOML read+parse), `validate_against_defaults()` (second
  read+parse of `config/defaults.toml`, 91 lines), `_check_scan_decay_coupling` /
  `_defaults_registry()` (third read of the same file, cached after first call, triggered from
  inside `perception.gaze`'s two accessor calls).
- **Measurement, not estimate:** ran `logger.py --print-tuning` (full body-layer import graph +
  validate + render) as a subprocess, 5 runs each, comparing `PETROBRAIN_TUNING` unset vs. a file
  setting all 15 keys (exercising every accessor's loaded-path, the coupling check, and
  `validate_against_defaults`):
  - unset: 194–204 ms per process (mean ~197 ms)
  - loaded, 15 keys applied, 0 rejected: 194–197 ms per process (mean ~195 ms)
  - **Delta: within run-to-run noise (~2 ms on a ~195 ms baseline dominated by Python interpreter
    startup and the rest of body-layer's import graph).** The TOML reads/parses/coupling-check
    together are not a measurable fraction of process startup.
  - Harness can fail: confirmed the probe is live, not vacuous — the two runs produce visibly
    different `--print-tuning` output (`applied (15)` vs. an empty applied set when unset), and a
    broken accessor (tried with a deliberately malformed override during this review) produces a
    non-empty `rejected` list and a different exit path, so the timing harness is exercising real
    code, not a no-op.
- **Risk:** none. Body-layer is one process per sortie — tens of milliseconds would already be
  irrelevant per the task's own framing; the actual cost is unmeasurable, not merely small.
- **Action:** none.

#### Cross-key coupling check (`_check_scan_decay_coupling`) reads `defaults.toml` once, cached

- **Location:** `tuning._defaults_registry()` — module-level cache (`_defaults_registry_cache`),
  read at most once per process; `_check_scan_decay_coupling` itself is guarded by
  `state.cross_key_checked` and also runs at most once per process, triggered from whichever of
  `perception.gaze.FOCUS_DWELL_S` / `SCAN_PLAN` resolves first.
- **Risk:** the obvious failure shape here — a registry re-parsed per call, or per module import —
  is exactly what the role's own memory flags as the plausible defect for this kind of coupling
  check, and it is not present: both the cache and the one-shot guard are real, checked by reading
  the code (not inferred from the docstring's claim). `validate_against_defaults()` does a second,
  independent read of the same file (not sharing `_defaults_registry_cache`), so the file is read
  twice per process rather than once — still startup-only, still inside the measured noise above,
  not worth a shared cache for a 91-line file read twice at process start.
- **Action:** none now. **MONITOR**: if Stage 3 (~95 more keys) is ever taken, `defaults.toml` grows
  roughly 6x; still a startup-only cost, but worth re-checking that `validate_against_defaults`'s
  independent read doesn't start to show up once the file is in the thousands of lines. Not a
  concern at today's 91 lines.

#### Poll loop / hot path: clean negative

- **Location:** `logger.py` — `validate_against_defaults()` and `render_startup_block()` are called
  once, directly after `args = parser.parse_args()` in `main()` (line ~2521), strictly before the
  `while True` poll loop (line 2808). Grepped every `tuning.*` call site in `body-layer/src`: all 15
  constant resolutions plus the three validation/render calls are confined to import time and
  `main()`'s startup sequence. **Nothing this feature added touches `handle_command` or the per-poll
  perception tick.** The two filed hot-path entries this project already tracks (`BL-B49`:
  `semantic_facts_for` at 63 ms/contact, `terrain_divide_qualifier` at 6.77 ms/contact uncached) are
  untouched by this feature — confirmed by `git diff`'s file list, neither file appears in it.
- **Risk:** none — stated explicitly because a clean negative is the useful result here, per the
  task's own framing, not a finding to manufacture around.
- **Action:** none.

### Verdict

APPROVED
