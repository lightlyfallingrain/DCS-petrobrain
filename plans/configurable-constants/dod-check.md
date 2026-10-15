# Definition of Done — X-T26 / configurable-constants

Verdict scoped to `feature/configurable-constants` tip `da6ceb32bdcf6791775bf96c9cbdc4cd1bd31499`
(matched the dispatch's named tip exactly; no merge was needed). Checked in a dedicated worktree at
`/private/tmp/pb-wt-configurable-constants`, never in the repo root.

## Code Quality — PASS

All run from inside `body-layer/` with its own `.venv` (rebuilt pinned: `ruff==0.16.6`,
`mypy==2.3.1`, `pytest==9.1.1`, `numpy==2.4.6`, `pyproj==3.8.0`, matching every prior pass):

| check | command | result |
|---|---|---|
| format | `ruff format --check src tests tools` | 135 files already formatted |
| lint | `ruff check src tests tools` | All checks passed |
| type | `cd body-layer && .venv/bin/mypy src` | Success: no issues found in 59 source files |
| type (tools) | `cd body-layer && .venv/bin/mypy tools` | Success: no issues found in 6 source files (ran manually — see note below) |
| test | `pytest tests -q` | **1870 passed, 4 xfailed** — matches the expected count exactly, the evidence no constant's value moved |

Only `body-layer/`, `plans/`, `todo/` and `.claude/agent-memory/` touched (confirmed by diff against
merge-base); no other subproject needed its own gate run.

No `print(`/debug statements beyond `logger.py`'s own CLI output (`--print-tuning`, startup block,
help text) and `generate_defaults.py`'s tool-status messages — both legitimate, user-facing CLI
output, not debug leftovers. No TODO/FIXME/XXX/`pdb`/`breakpoint()` in any touched file.

**Advisory, not a fail**: `body-layer/CLAUDE.md`'s documented Commands section
(`ruff format body-layer/src body-layer/tests`, `mypy src`) still does not mention `tools/`, which
is exactly the gap `X-B36` already files against every subproject with a `tools/` dir. I ran
`ruff`/`mypy` against `tools` manually above and both pass today, but the *documented* gate would
not have caught a regression there. Not blocking — `X-B36` already owns the fix, filed 2026-10-15,
open.

## Scope & Correctness — PASS

- Matches `plan.md`'s amended scope exactly: Stage 1 (declare + load) and Stage 2 (curated 15 keys)
  implemented; Stage 3 (~80 more body-layer keys), Stage 4 (audio-adapter), Stage 5 (world-model
  query path) explicitly deferred per the plan's own Implementation Plan — not silently dropped.
- `config/defaults.toml` has exactly **15** keys (counted: `grep -cE '^[A-Z_]+ =' config/defaults.toml`),
  matching the curated set named in `todo/todo/X-T26.md` and `plan.md`'s Stage 2 list.
- No constant's **value** changed — the unchanged xfail count (4, stable throughout every prior
  pass per the dispatch brief) plus the full 1870-pass suite is the evidence; nothing in the diff
  touches a numeric literal's magnitude, only where it's declared and how it's resolved.
- No invariant from `CLAUDE.md` violated: no change to DCS-authoritative data paths, no world-model
  `data/` touched, no multiplayer scope, no in-process import added beyond the one documented
  exception.
- `git status --porcelain` empty at the named tip — all files already staged/committed, nothing
  left loose.
- Three `review.md` Required Fixes (the cross-key decay/gaze coupling, the `tools/` ruff-format
  miss, the three ~4x-wrong range figures) all independently confirmed **APPROVED** across three
  review passes, each citing direct execution/mutation verification, not just re-reading the diff.

## Testing — PASS

- `tests/test_tuning.py`, `tests/test_tuning_defaults_toml.py`, and `tests/test_logger.py` additions
  cover the loader's `real`/`whole`/`sequence`/`table` accessors, the cross-key decay/gaze coupling
  guard, and the CLI's `--print-tuning` rendering.
- **The staleness test is not decorative — verified by deliberately breaking it**: edited one value
  in the committed `config/defaults.toml` without touching the generator, ran
  `pytest tests/test_tuning_defaults_toml.py -q`, got a clean, correctly-worded failure
  (`AssertionError: config/defaults.toml is stale...`); reverted, confirmed `git diff` clean again.
  This is the test that would have caught a calibration commit that forgot to regenerate.
- No existing test broken: full suite result (1870/4 xfail) matches the baseline every prior pass
  reported.

## Documentation — PASS

- All three `review.md` Required Fixes addressed (see above).
- Non-obvious behaviour explained in code: `tuning.py`'s module docstring documents the import-time
  binding constraint, the cross-key coupling fix, and the two-registry design; each constant's `#:`
  comment carries its own provenance (`status: judgement|measured|agreed-guess|uncalibrated`).
- Three accepted-but-not-closed items from the review cycle are durably filed, not just mentioned in
  chat: `X-B36` (`tools/` outside every subproject's documented gate), `X-B37` (generator renders
  only a first sentence + leaks markdown), `X-B38` (duplicated `0.00128` literal + two disclosed
  untested edge cases). All three exist on `main` (merged via `chore/xt26-followups`,
  `eb988e2`) but **not yet on this feature branch** — `feature/configurable-constants` and `main`
  have diverged (neither is an ancestor of the other; confirmed via
  `git merge-base --is-ancestor` both directions, both `no`). They will be present after the
  `--no-ff` merge brings `main`'s history in. Confirmed this is the situation, not a gap to fix now.

## Security — PASS, under the current cadence (not a gap)

`plans/configurable-constants/security.md` is a single deep-analysis pass, **APPROVED**, with one
Recommended (non-blocking) finding: the three visibility-tier `lo` bounds permit ranges 6–14x past
the measured calibration and one is below a fixed invariant floor (`RESOLUTION_ANGULAR_RADIUS_RAD`)
elsewhere in `clustering.py`, with the generated description giving no hint of either. Security's own
recommendation is option (B): file to backlog, don't block. **No `security-plan-review.md` exists,
and that is correct** — root `CLAUDE.md`'s "Agents" section states the cadence enabled 2026-09-24:
Security runs once per whole feature, immediately before DoD, superseding the two-pass
plan-review/deep-review template in `AGENTS.md`'s general sequence diagram. Confirmed against this
role's own memory (`project_current_cadence_one_security_pass_per_feature.md`), which recorded this
exact situation on `WM-B6`.

**The Recommended finding (visibility-tier `lo` bounds) is not yet filed to backlog.** Flagging this
to the user/orchestrator below — it's the kind of finding Security explicitly deferred to a human
decision (options A–D in `security.md`), not something DoD should silently file itself.

## Performance — PASS

`plans/configurable-constants/performance.md`, single pass, **APPROVED**. One pass, before DoD, per
the same cadence.

## Acceptance boundary — what this feature's fixtures structurally cannot reach

This is a startup-path mechanism, not an in-flight one — there is no belief/perception/speech
behaviour change to fly, by design (the whole point is that no constant's value moved). So the
honest boundary is narrower than the usual flight-acceptance gap:

- **What is verified, by direct execution, in this gate**: cold-read intelligibility of
  `defaults.toml`, override-takes-effect-and-is-reported, three classes of bad value (unknown key,
  wrong type, out-of-range) each warn-and-continue with a clear reason and the code default
  genuinely in force, missing-file warns loudly and runs on defaults, `--print-tuning` agrees with
  the startup block by construction (`render_print_tuning` literally calls `render_startup_block`
  first).
- **What this cannot reach**: whether a sortie-revised value (not this feature's concern — Stage 2
  only wires the *mechanism*) actually produces better pilot-perceived behaviour, and whether a real
  pilot copying a key out of `defaults.toml` into his own `tuning.toml` file by hand hits any
  friction a desk test with a hand-written file doesn't surface (e.g. an editor auto-formatting
  quirk, a TOML syntax he gets wrong in a way my deliberately-bad-value tests didn't try). Neither
  of these needs a DCS sortie — they need the user's own hands on his own tuning file, once, which
  is why the acceptance plan below asks him to do exactly that rather than trusting my synthetic
  bad-value file.
- **No `#needs-flight` tag needed anywhere** — nothing here is deferred pending a sortie.

## Inspect-and-adapt: does this change the next milestone?

**Yes, one way.** `X-B37` (generator renders only a first sentence and leaks raw markdown into the
pilot-facing file) argues the generator's rendering contract should be settled *before* Stage 3 adds
~80 more keys through the same generator, not after — fixing the contract once now is cheaper than
fixing it once per already-rendered batch. This doesn't block this merge (Stage 3 isn't started),
but it's worth deciding before Stage 3's Architect pass rather than rediscovering it there.

## Overall verdict: **PASS**

Clear to merge, scoped to tip `da6ceb32bdcf6791775bf96c9cbdc4cd1bd31499`. Acceptance testing plan
below pending the user's own confirmation.
