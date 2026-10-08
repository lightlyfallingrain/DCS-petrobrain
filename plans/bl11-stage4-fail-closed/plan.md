### Goal

Stop `body-layer`'s live naked-eye LOS gate from falling back to world-model's offline
`line_of_sight_clear` primitive when a poll carries no live DCS verdict (`BL-11` Stage 4 step 3,
"fail closed"), and add a cheap, always-on coverage counter that makes a dead live-LOS feed
observable in the logs rather than silently indistinguishable from an empty sky (step 4).

Authorised 2026-10-08 on evidence from `docs/acceptance/2026-10-08-los-statics-population-sortie.md`:
145/145 evaluated objects and 85/85 admitted objects received a live verdict this sortie (baseline
before the statics fix: 76% of admitted objects had none). Standing user direction:
*"world model LOS must not be used — it is to be a testing-only tool, not for live flight. Not only
because of performance, but especially for correctness."*

### Affected Modules / Files

- `body-layer/src/perception/visibility.py` — gate 4 (`check_visibility`, ~L780-791): drop the
  `elif not line_of_sight_clear(...)` branch. `candidate.live_los_clear is None` becomes "not
  admitted," same as `False`. Add the coverage-counter increment at this gate (see Stage 2 below).
  `line_of_sight_clear` stays imported and callable — it is still the offline/fixture primitive
  (`WM-B8`'s intended consumer) — just no longer reached from this function at all.
- `body-layer/src/perception/naked_eye_source.py` — `NakedEyePerceptionSource` gains an always-on
  `live_los_coverage` counter instance, constructed in `__init__`/as a dataclass field, passed into
  every `check_visibility` call alongside the existing `trace=self.trace_sink` parameter.
- `body-layer/src/logger.py` — the poll loop reads `source.live_los_coverage` each poll (wherever
  `NakedEyePerceptionSource.poll()` is called — verify whether `--console` and `--crew-text` share
  one runner or two; if two, the read belongs in both) and logs via the standing `logging.getLogger(__name__)`
  channel when the cumulative no-verdict count is nonzero and growing. No new CLI flag — unlike
  `--detection-trace`, this must be on by default to do its job.
- `body-layer/tests/test_visibility.py` — the `_candidate()` factory's default for `live_los_clear`
  changes from `None` (today's implicit default) to `True`, so every test in this file that is not
  specifically testing the LOS gate keeps testing what it was built to test. Two tests are rewritten
  outright, not extended (see Decisions below):
  - `test_live_los_clear_none_falls_back_to_the_offline_primitive` — the behaviour it asserts no
    longer exists; replace with a test asserting `None` now rejects (fail-closed), with a
    negative-space assertion that `line_of_sight_clear` is never called.
  - `test_terrain_los_blocked_drops_an_otherwise_visible_candidate` — monkeypatches the now-dead
    `line_of_sight_clear` to simulate "blocked." Replace with a candidate built with
    `live_los_clear=False` directly (the only way to express "blocked" once the fallback is gone).
- `body-layer/tests/test_naked_eye_source.py` — `FakeAircraftClient.get_line_of_sight_latest`
  (currently always `None`) and `_world_object()` (currently has no `unit_name` key) both need to
  synthesize a working live-LOS join by default: every object gets a `unit_name`, and the fake
  client returns a verdicts dict marking every present `unit_name` clear, timestamped to match
  `now_sim` (inside `LOS_MAX_AGE_S`). Delete the now-vacuous autouse `clear_line_of_sight` fixture
  (monkeypatches a function nothing calls anymore). A per-test override hook (pass a unit name that
  should resolve to blocked, or omit one to simulate "no verdict for this object") replaces what
  that fixture used to provide.
- `body-layer/tests/test_player_bubble.py` — has its own separate `_world_object`/`FakeAircraftClient`
  pair; needs the identical fix, independently (it does not import `test_naked_eye_source`'s).
- `body-layer/tests/test_vision_calibration.py` — no shared factory; ~5 literal `WorldObjectCandidate(...)`
  constructors each need `live_los_clear=True` added directly.
- `body-layer/tests/test_detection_trace_writer.py` / wherever `annotate_los`'s four fields are
  exercised — check these still pass once gate 4's control flow changes; expected unaffected since
  the annotation already records `live_los_clear` verbatim regardless of which branch admitted/rejected.

Not touched: `world-model/src/query/*` (the offline primitive itself, including its known
all-void-returns-`True` bug — `world-model/ROADMAP.md`'s `M11` Stage 1 — stays out of scope and
out of the live path either way), `replay.py` (drives fixture-built candidates through
`PerceptionSource`s exactly as today; unaffected by a live-path-only change as long as its own
fixtures set `live_los_clear` the same way the other test files now do), `aircraft-layer`'s Hook
script, `BL-B42`'s cap amortisation.

### Implementation Plan

1. **Measure the blast radius first, before writing the real change** (already done during
   planning, recorded here so the Implementer does not need to re-discover it): with the `elif`
   branch deleted and nothing else touched, `70 of 1540` body-layer tests fail — all of them in
   `test_visibility.py` (29), `test_vision_calibration.py` (4), `test_naked_eye_source.py` (7),
   `test_player_bubble.py` (2), and — the actual count observed — concentrated in exactly the four
   files named above. None elsewhere. This is bounded and mechanical: in three of the four files a
   single shared fixture factory needs one default changed; only `test_vision_calibration.py` needs
   per-call-site edits, and there are few of those.
2. **Step 3 — fail closed.** In `visibility.py`, replace the `if ... elif ...` pair with a single
   `if not candidate.live_los_clear:` (Python's falsy treats `None` and `False` identically, which is
   exactly the fail-closed semantics wanted — no separate `is None` branch needed). Update the
   surrounding comment: it currently says the `elif` "is also what every test fixture and the
   replay harness still exercises" — that sentence becomes false the moment this lands, so rewrite
   it to say the opposite and point at this plan.
3. **Step 4 — the coverage counter.** Add a small counter (e.g. a `LiveLosCoverage` dataclass with
   two `int` fields, `evaluated` and `no_verdict`) as an always-constructed attribute on
   `NakedEyePerceptionSource` (not optional, not gated by any flag — see Decision 2 on why this is
   deliberately *not* the `trace_sink`/`DetectionTraceCollector` pattern). `check_visibility` takes
   it as a new keyword parameter next to `trace`, increments `evaluated` every time gate 4 is
   reached (i.e. every candidate that passed gates 0-3) and `no_verdict` whenever
   `candidate.live_los_clear is None` specifically (not `False` — a confirmed "blocked" is not a
   coverage gap). `logger.py`'s poll loop reads `source.live_los_coverage` after each `poll()` call
   and logs a `logging.getLogger(__name__).warning(...)` line with the cumulative counts whenever
   `no_verdict` is nonzero. This needs no new CLI flag and is on for every run, including ordinary
   sorties with no debugging flags set — that is the whole point (see Decision 3).
4. **Fix the four test files** per "Affected Modules" above, in the order the blast-radius
   measurement suggests: the three shared-factory files first (one-line default changes each,
   recovering most of the 70), then the two outright rewrites in `test_visibility.py`, then
   `test_vision_calibration.py`'s per-call-site additions last.
5. **Add the fail-closed-specific tests** the brief's own question 4 asks for, as new tests (not
   covered by the rewrite above): a candidate with `live_los_clear=None` is rejected; one with
   `True` is admitted (already exists: `test_live_los_clear_true_admits_a_candidate_without_consulting_the_offline_primitive`,
   keep it); one with `False` is rejected (already exists, keep); and the negative-space assertion
   that `line_of_sight_clear` is never called from `check_visibility` regardless of which of the
   three values the candidate carries (extend the existing `_fail_if_called` monkeypatch pattern
   from the `True`/`False` tests to also cover `None`).
6. **Add coverage-counter tests**: a poll where every candidate resolves a live verdict leaves
   `no_verdict` at 0; a poll where `get_line_of_sight_latest()` returns `None` (feed absent) or an
   object's `unit_name` never appears in `verdicts` increments `no_verdict` by exactly the number of
   candidates that reached gate 4 (not the number of candidates in the poll — gaze/bubble-rejected
   candidates must not count, since they never reach gate 4; see Decision 1). Verify this with a mix
   of in-gaze and out-of-gaze candidates in one poll.
7. **Run the full body-layer suite** (`cd body-layer && .venv/bin/ruff format/check src tests`,
   `.venv/bin/mypy src`, `.venv/bin/pytest tests -q`) and confirm it is clean, not just that the
   count matches the pre-measured 70.

### Risks & Unknowns

- **The four causes of `live_los_clear is None` are collapsed into one at gate 4, and that is a
  deliberate choice, not an oversight** — see Decision 1. If a future defect turns out to need the
  breakdown (e.g. "this is always stale skew, never feed-absent"), the data to reconstruct it
  (`skew_s`, whether `get_line_of_sight_latest()` returned `None` at all, whether the `unit_name` was
  non-unique) already exists in `naked_eye_source.py`'s join step and in `detection_trace.py`'s
  `annotate_los` fields when `--detection-trace` is running — it does not need to be duplicated into
  the always-on counter now.
- **The always-on counter runs every poll on every sortie, unconditionally** (unlike every other
  diagnostic flag in this module, which defaults off). It is two integer increments and one
  dict-free dataclass mutation per candidate that reaches gate 4 — no allocation, no I/O — so the
  per-poll cost is negligible against the ~12.6 ms median poll cost `BL-11` Stages 1-3 already
  measured. Flagging this only because it breaks the module's own "new things default off" pattern
  (see Decision 3 for why that pattern does not apply here).
- **Fixing the `FakeAircraftClient`/`_world_object` helpers in two separate test files
  (`test_naked_eye_source.py`, `test_player_bubble.py`) duplicates the same fix twice** rather than
  sharing one helper module. That duplication already exists today (they are already two independent
  copies of a similar shape) and this plan does not propose un-duplicating them — doing so now would
  be an unrelated test-infrastructure refactor riding along on a fail-closed change, which is exactly
  the kind of scope creep `CLAUDE.md` asks to be surfaced rather than done quietly. Left as a
  candidate for a future, separate cleanup if the user wants it.
- **`replay.py`'s own fixtures** (`tests/fixtures/`, committed, per `body-layer/CLAUDE.md`'s testing
  section) were not individually audited for whether they set `live_los_clear`. If any committed
  fixture frame is replayed through `NakedEyePerceptionSource` and expects admission without a live
  verdict, it will now fail closed. The Implementer should grep `tests/fixtures/` for consumers of
  the naked-eye channel and check this before declaring the suite clean — the 70-test measurement in
  step 1 above was run with `pytest` and should already have caught any such fixture-driven test, but
  call it out explicitly since fixtures are also read by non-pytest tooling (`replay.py` run
  standalone).

### Decisions Requiring User Input

1. **Test-rewrite scope, per `AGENTS.md`'s escalation rule ("existing tests must be rewritten rather
   than extended").** The honest shape, measured rather than guessed: of the 70 failing tests, ~68
   are fixed by a one-line default change in three shared test factories (the `_candidate()` default
   in `test_visibility.py`, and the `FakeAircraftClient`/`_world_object` pair in each of
   `test_naked_eye_source.py` and `test_player_bubble.py`) plus a handful of per-call-site additions
   in `test_vision_calibration.py` — all genuine *extensions*, not rewrites, since none of those
   tests' assertions change. **Two tests are genuine rewrites**: `test_live_los_clear_none_falls_back_to_the_offline_primitive`
   (asserts the exact behaviour being removed) and `test_terrain_los_blocked_drops_an_otherwise_visible_candidate`
   (monkeypatches a function that stops being called). My recommendation: proceed — the rewrite count
   is two, both are a direct, obvious consequence of the one-line production change (not a creative
   reinterpretation of what the code should do), and blocking step 3 on this would block the
   milestone the user already authorised on sortie evidence. Flagging per the letter of the rule
   rather than because I think it is a close call.
2. **Why the coverage counter is a new, separate always-on mechanism rather than reusing
   `DetectionTraceCollector`.** `detection_trace.py`'s own module docstring frames its `None`-default
   as "a proven no-op" specifically because tracing is optional diagnostic detail the pilot does not
   pay for unless `--detection-trace` is passed. The brief is explicit that this counter must be
   visible without that flag — "a coverage counter living only [in detection_trace] is invisible on
   an ordinary sortie, which defeats the purpose." Those are two different design intents (opt-in
   deep diagnostic vs. always-on regression guard) wearing similar shapes, and collapsing them into
   one mechanism would make the always-on guard conditional on a flag it must not be conditional on.
   I built it as a second, independent, always-constructed counter rather than touching
   `DetectionTraceCollector`'s optionality — local, reversible, not escalating, but naming it since
   it is a real design choice rather than an obvious one.
3. **How the pilot — the one who actually needs to know the feed died — finds out.** Per the brief's
   own instruction, this plan does **not** design an in-cockpit observable; the roadmap decision
   (`body-layer/ROADMAP.md`, Stage 4 header) is explicit that this is "a regression guard rather
   than an observable." Concretely: fail-closed means a dead live-LOS feed makes Petrovich call out
   nothing he would otherwise have called out, and from the cockpit that is indistinguishable from
   an empty sky. The only place this becomes visible is the stderr/log line this plan adds, read
   post-flight. I think that is the right scope for *this* plan — an in-cockpit "LOS feed down"
   warning would be a genuine new crew-facing behaviour, needs its own `/explore` with the user
   (per `CLAUDE.md`'s "Direction before speed"), and is exactly the kind of thing that has
   historically turned out differently once discussed. Flagging because the brief asked me to be
   honest about whether the log-only answer is sufficient, and I think it is sufficient *for this
   milestone* but not forever — if a feed outage in practice is only discovered days later from a
   log nobody read, that is the moment to revisit this, not now.

### Second-order effect

None identified beyond what the roadmap already states: this closes `BL-11` Stage 4 entirely (steps
1-2 done 2026-10-08, 3-4 this plan), which removes world-model's `line_of_sight_clear` as a live-path
dependency for good — any future work on that primitive (e.g. fixing `M11` Stage 1's all-void-returns-
`True` bug) is now purely an offline/fixture-correctness concern with no runtime consequence, which
lowers the stakes of touching it.
