## Security Deep Analysis: BL-11 Stage 4 (steps 3-4, fail-closed live LOS gate)

Reviewed at tip `77faae3bd3e0d9e3b8f19685adbc134131e5bac6` (worktree landed on `main`, scaffolding
branch had no commits of its own, moved via `git checkout -B` — no content changed).

### Dependency Status

No dependency change. Pure `body-layer/` source + test change; no new import, no new third-party
package.

### Framing

This is a fail-closed safety change, not an input-validation surface. The two questions that
matter: (1) does removing the offline-LOS fallback stop a path that manufactured false knowledge,
and (2) does fail-closed create a new silent-failure mode worse than what it replaces, and is the
counter that is supposed to make that visible actually trustworthy.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/perception/visibility.py:840` | `if not candidate.live_los_clear:` | Correct, verified by mutation (restored the old `elif` fallback locally, confirmed the negative-space test fails for the right reason — `_fail_if_called` raised inside `check_visibility`, not a value mismatch — reverted, clean diff). `None`/`False` both reject; `line_of_sight_clear` import stays unreachable from this function. | None |
| `body-layer/src/perception/visibility.py:836-839` | `LiveLosCoverage` increment at gate 4 only | Denominator correctly excludes gaze/mask/FOV/range-rejected candidates by control flow (confirmed by the two dedicated coverage tests, both executed). | None |
| `body-layer/src/logger.py:896-924` | `_warn_live_los_coverage_gap_once` edge-trigger | Re-mutated the fix myself: removed the `if already_warned: return True` early-return, reran the five coverage tests — reproduced the Reviewer's exact pre-fix failure mode (10/10 polls logged under continuous growth, the flood this fix exists to kill). Reverted with `Edit`; `git diff --stat` empty afterward. The fix holds. | None |
| `body-layer/src/logger.py:927-955` | `_log_live_los_coverage_summary`, unconditional, `try/except Exception` | Runs first in each loop's `finally:`, ahead of `trace_writer`/`belief_truth_writer`/`world_model_conn` teardown; wrapped so a failure here can't skip that teardown. Verified the real exit path: both `_run_console_repl`/`_run_crew_text_repl` catch `KeyboardInterrupt` (the way the user actually stops the process), call `stop_event.set()`, `poll_thread.join()` — the background thread's own `while not stop_event.is_set()` loop then exits normally into its `finally:`. Ctrl-C is not a crash path here; it reaches the summary log correctly. | None |
| `body-layer/src/logger.py:2446-2465` (`main()`'s bare `else:` branch, `PerceptionLogger`, no `--console`/`--crew-text`) | **Third call site of `NakedEyePerceptionSource`, uninstrumented** | `_build_sources` is shared across all three entry points, so this plain-logger path also builds a `NakedEyePerceptionSource` with gate 4 now fail-closed — but neither the per-poll warning nor the end-of-run summary is wired into this branch at all; its `finally:` only closes `world_model_conn`. If this path is ever run, a dead live-LOS feed produces **zero** signal, not even post-flight — strictly worse than the two instrumented paths, where the gap is at least logged once/summarised. See Risk below. | See Risk below — advisory, not blocking |

### Risk: plain-logger entry point has no live-LOS coverage visibility at all

**Finding:** `main()`'s `else:` branch (reached when neither `--console` nor `--crew-text` is
passed) runs `PerceptionLogger` over sources from the same `_build_sources` call, so it is subject
to the identical fail-closed gate 4 as the two instrumented loops, but its `finally:` block never
calls `_warn_live_los_coverage_gap_once` or `_log_live_los_coverage_summary`. A dead feed here is
silent in the strongest sense this plan exists to prevent: not delayed-to-post-flight, simply never
reported.

**Location:** `body-layer/src/logger.py:2446-2465`.

**Probability:** low — `body-layer/CLAUDE.md`'s own "Running the live logger" section documents
only `--console`/`--crew-text` (plus their additive flags) as how this process is actually run;
the plain-logger branch predates the belief layer (PB-1) and reads as legacy/dev-only rather than
a path anyone flies with. Nothing in this plan or the roadmap suggests it is used for real sorties.

**Impact:** medium if it were used — it reproduces, with no mitigation at all, the exact
observable-perception-gap problem this whole plan was written to close.

**Recommended action:** either wire the same `finally:`-block summary call into this branch (one
line, mirrors the pattern already proven in the other two loops), or — if the plain-logger path is
genuinely dead/unused — say so in `logger.py`'s module docstring so the next reader does not
assume parity across all three `_build_sources` call sites. I would not block this plan on it: it
is outside the two named poll loops the dispatching brief and plan both scoped step 4 to, and the
real, documented, pilot-facing paths are both correctly instrumented and both verified by mutation.

Options:
  (A) Ignore — document acceptance of risk (plain-logger path is legacy/dev-only, not flown)
  (B) Add to todo.md — fix in a future session (one-line parity fix)
  (C) Fix now — I'll address it before continuing
  (D) Stop — do not proceed until this is resolved

### The coverage counter's trustworthiness, checked directly rather than assumed

- **Healthy-case firing rate, not just the broken-case one** (the project's own standing lesson
  from the SRTM-fallback miss): the authorising sortie evidence
  (`docs/acceptance/2026-10-08-los-statics-population-sortie.md`) measured **145/145 evaluated,
  85/85 admitted, with a live verdict** — i.e. the counter's healthy-case firing rate is
  empirically ~0% in the one real flight measured since the statics fix, not merely argued from
  "the feed would have to crash." That is reassurance the warning will not be noise in ordinary
  operation, not a guarantee against every cause.
- **Four causes collapse into one `None`, and this is a stated, accepted design choice** (plan
  Risks section, Decision 2): feed absent, stale skew (`> LOS_MAX_AGE_S` = 3.0 s), object outside
  the Hook's queried wedge, and non-unique `unit_name` within a poll. Of these, **a mission author
  can induce the last one** by placing two units with the same display name — DCS does not enforce
  name uniqueness. The consequence under this change is strictly worse than before: previously such
  an object fell back to world-model's offline primitive (itself imperfect, but at least an
  attempt); now it is permanently rejected from the naked-eye channel for as long as the name
  collision persists, with no cockpit signal, same as every other `None` cause. This is exactly the
  class of thing the always-on counter exists to surface — it does (both `evaluated`/`no_verdict`
  increment, same as any other `None`) — and the plan's own Decision 3 already scoped this to a
  log-only, post-flight signal rather than an in-cockpit one, which I agree is the right scope for
  this plan specifically. Not a new finding; confirms the existing scoping decision still covers
  this induced case.
- **The `;`-in-name class of inducible defect was already found and fixed on the Hook side**
  (`aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua:442-454`, `nameRejects` counter,
  Security deep analysis finding from the X-B29 review) — re-read, confirmed still in place and
  unaffected by this branch's diff (not in this branch's changed-file list).
- **Process-lifetime cumulative counter across a mission restart:** the skew check
  (`abs(world_objects_t_sim - line_of_sight_dcs_model_time_s)`) is an absolute difference, so a
  DCS mission restart produces a correct, transient `no_verdict` bump (a genuine momentary gap),
  not a misleading one. The counter itself never resets mid-process, which is intentional — it is
  explicitly a whole-sortie total, not a per-restart one.
- **One real, accepted limitation, already named by the Reviewer and not reopened here:** the
  edge-triggered warning fires exactly once per process lifetime. A brief early hiccup that fully
  recovers and a sustained dead feed both produce the same single warning; only the end-of-run
  summary's magnitude distinguishes them. This is documented in `review.md` and accepted as
  adequate for "did this sortie have a gap at all" — I agree with that scoping and am not
  reopening it as a new finding.

### Also checked

- **No sensitive content in the new log lines** — both the transition warning and the summary
  carry only integer counts and a static explanatory string, no object names, positions, or
  speech text. `BL-B36` (speech log PTT-gating) is not reopened, correctly.
- **Fixture content** (`tests/fixtures/mock_flight_canonical.json`) verified directly: all
  `unit_name`/verdict keys across all 20 frames are synthetic (`unit_101`, `unit_102`), nothing
  real or identifying.
- **Offline primitive genuinely unreachable, not merely unused**: confirmed by the Reviewer's own
  mutation test (restoring the `elif` and observing the negative-space test raise inside
  `check_visibility`), and independently by reading every call site in `visibility.py` — there is
  exactly one reference to `line_of_sight_clear`, the `# noqa: F401` import, with no call
  expression anywhere in the module.

### Verification

Re-ran independently (not inherited): `ruff format --check` (118 files formatted), `ruff check`
(clean), `mypy --strict src` (clean, 54 source files), `pytest tests -q` (1547 passed, 4 xfailed,
0 failed) — exact match to both the Implementer's and Reviewer's reports. Additionally ran my own
mutation test against `_warn_live_los_coverage_gap_once`'s early-return (removed, reran the five
coverage tests, reproduced the Reviewer's flood signature — `10 == 1` on the fires-exactly-once
test — reverted, confirmed empty `git diff --stat`).

### Verdict

**APPROVED.**

No confirmed exploitable vulnerability and no probable risk in the feature diff. One low-risk
finding (plain-logger entry point has no coverage visibility) presented above for the user's
decision — it does not block, since the two real, documented, pilot-facing entry points
(`--console`, `--crew-text`) are both correctly instrumented and independently mutation-verified.

### Required Fixes

None.
