### Definition of Done: BL-B133 (PTT speech hold)

**Scoped to tip `997770ff1acc65efd24c27a1fc40eef8e8ba080d`** on
`feature/bl-b133-ptt-speech-hold` (main is `c3ed21b4`). Method: branch was already checked out at
this exact sha in `/Users/sg/Code/DCS-petrobrain-ptthold` on a clean tree — `git rev-parse HEAD`
confirmed the match before anything else, so no detach/archive fallback was needed.

#### Code Quality

- [x] Subprojects touched, derived from `git diff --name-only c3ed21b4 HEAD` (merge-base = main
  tip), not from memory: **body-layer only**. No `world-model`/`aircraft-layer` files touched.
- [x] `ruff format --check src tests` (body-layer): pass, 230 files already formatted.
- [x] `ruff check src tests` (body-layer): pass, all checks passed.
- [x] `cd body-layer && .venv/bin/mypy src` (strict, run from inside the subproject): pass —
  `Success: no issues found in 93 source files`.
- [x] **Full suite**, `.claude/scripts/fast-tests.sh --full body-layer` (parallel via
  pytest-xdist, foreground): **3754 passed, 4 xfailed** (the 4 xfails are pre-existing, unrelated
  to this change — matches the count Reviewer's re-review reported). Ran to completion in 148s.
  Tested tree sha: `997770ff1acc65efd24c27a1fc40eef8e8ba080d`.
- [x] No unhandled errors/panics in data paths: `PttHoldGate`'s failure posture (unavailable →
  released, stale → released, never held forever) was reviewed by both Reviewer and Security;
  both confirmed it fails open to released, not closed to a permanent mute, and never raises
  past `_get_json`'s own `AircraftLayerError` boundary.
- [x] No debug output or leftover TODOs introduced by this feature — grepped the diff for
  `print(`, `TODO`, `FIXME`, `XXX`, `pdb`: none in the new/changed files.
- [x] All new files staged with `git add`: confirmed via the file list below; `git status
  --porcelain` is clean of anything not committed by the time this report is written (two
  `notes/` edits and this file itself, staged in the same commit as the roadmap update — see
  "Commit" below).

#### Scope & Correctness

- [x] Implementation matches the spec in `body-layer/ROADMAP/BL-B133.md` — both of the user's
  verbatim decisions ("say urgent ones even when I hold trigger", "let it play") are built and
  tested (`test_urgent_line_speaks_while_ptt_held`,
  `test_already_playing_line_is_not_interrupted_when_ptt_goes_down`,
  `test_held_routine_line_is_dropped_by_an_urgent_arrival_while_waiting`). The one deviation from
  the item's own text — the real endpoint is `GET /ptt/state`, not the item's stated `GET
  /ptt/latest` — is explicitly named in both the ROADMAP entry and `implementation.md`, not a
  silent substitution.
- [x] No unplanned scope added silently: the two review-driven changes (telemetry-keyed
  staleness, mission-reset wiring, the interrupt-race fix) are all inside `belief/ptt_hold.py`
  and `belief/speech_worker.py`, the one module this feature exists to add — Reviewer's own
  verdict says so explicitly ("not scope creep, not a nit").
- [x] No invariants from `CLAUDE.md` violated: no multiplayer path added, DCS-sourced data
  (telemetry/PTT state) treated as authoritative and never overridden, no behaviour-affecting
  constant left as a bare literal (`PTT_RELEASE_DEBOUNCE_S`/`PTT_FEED_STALE_AFTER_S` both went
  through `tuning.py` with `lo`/`hi` bounds, per the project's standard-practice rule).
- [x] All new/modified files staged: confirmed by `git diff --name-only` against the merge-base,
  all 18 files are the ones implementation.md/review.md/performance.md/security.md each name.
  `.claude/agent-memory/security/project_nan_infinity_comparison_not_just_int_conversion.md` is
  the Security role's own memory file from this pass, correctly placed at the tree root (not
  nested under `body-layer/`).

#### Testing

- [x] Core logic (hold/debounce/staleness decision, the interrupt-race fix, the mission-reset
  wiring) is covered by tests described in detail in `implementation.md`'s "Tests Added"
  section — 68+ tests across `test_ptt_hold.py`, `test_speech_worker.py`,
  `test_aircraft_client.py`, `test_mission_start_reset.py`.
- [x] Tests are meaningful, not decorative: the race-fix test was verified by mutation (revert
  the fix, confirm the new test hangs against the pre-fix code) by the Reviewer's re-review, not
  just by reading the lock scheme — the strongest form of verification this project's testing
  convention asks for. Two genuine bugs in the implementer's own first draft were caught by
  `test_idle_untouched_trigger_is_never_reported_stale`, confirming the test fixtures are not
  circular.
- [x] No existing tests broken: `test_body.py` (237 passed, re-run specifically because
  `body.py`'s `_reset_mission_state`/`_check_for_new_mission` signatures changed) and the full
  suite count (3754 passed) both confirm no regression.

#### Documentation

- [x] Reviewer findings addressed: both Required Fixes from the first review pass (staleness
  keyed to the wrong clock; the interrupt/wait race) are resolved and the re-review verdict is
  **APPROVED**, with Fix 2 additionally confirmed by mutation. The re-review's one optional
  refinement (a docstring line about the "no telemetry yet at startup" edge case) was left
  optional, not required — consistent with the Reviewer's own judgment that it is a documented,
  tested, consistent application of the module's existing posture, not a new defect.
- [x] Accepted-items ledger: `.claude/scripts/accepted-items-ledger.sh plans/bl-b133-ptt-speech-hold`
  produced no output (exit clean, no gap reported). This feature has no `plans/<feature>/plan.md`
  with `**U<n>` ids — it is a backlog item (`body-layer/ROADMAP/BL-B133.md`) carrying the user's
  verbatim decisions in prose, not an Architect-authored plan, so the ledger has nothing numbered
  to check against. Both of the user's verbatim decisions are nonetheless traced above under
  "Scope & Correctness" as built and tested, not merely mentioned.
- [x] Non-obvious behaviour explained: the module docstring in `ptt_hold.py` states the
  telemetry-vs-PTT-sample staleness tradeoff explicitly (quoted and confirmed by Reviewer); the
  ROADMAP entry's "Built"/"Review fixes" paragraphs and `implementation.md` both carry the full
  reasoning chain. Two `notes/` topic files were updated with the generalizable lessons (see
  "Knowledge harvest" below).

#### Security

- [x] `plans/bl-b133-ptt-speech-hold/security.md` exists, verdict **PASS**. One low/low finding
  (non-finite float — `NaN`/`Infinity` — at the `received_wall_clock_s` wire-boundary parse,
  reusing a pre-existing `isinstance`-only guard already present on `last_ias_kmh`) filed as a
  new backlog item rather than blocking. **Filing verified, not just claimed**: `body-layer/
  ROADMAP/BL-B135.md` exists with the full finding, and `body-layer/ROADMAP/body-layer-backlog.md`
  indexes it (`grep` confirmed both). No dependency change; no new listening socket.

### Acceptance boundary — what these fixtures structurally cannot reach

Every test here runs against a controllable fake gate, a real loopback `http.server`, or
fast-forwarded fake clocks. None of them can tell us:

- **Whether the 0.1s release debounce and the 120s telemetry-staleness bound feel right against
  a real two-stage PTT trigger's actual mechanical transit and a real, possibly-long radio call
  on the Mi-24P's actual SPU-8 intercom.** The debounce duration is measured from
  `ptt_source.py`'s own instrumentation (19-32ms transit), but whether 0.1s is comfortably above
  that in practice, under real trigger hardware/binding behaviour, is not something a fixture can
  show.
- **Whether Petrovich's actual held-then-released cadence sounds natural** — a fixture proves the
  *start* of a routine line is gated correctly; it says nothing about how the gated-then-released
  sequence sounds when a real line was mid-queue during a real, variable-length radio exchange.
- **The real wire shape under real DCS export conditions** — `_PTT_STATE_BODY` and the telemetry
  fixtures are hand-built against the schema, not captured from a live `Export.lua` session.

This is the same class of gap the F10-vocabulary worked example names: a fixture that is
internally consistent can still be testing against the wrong assumption about what the aircraft
actually does. Nothing in this pass found evidence that it is — but nothing in this pass could
rule it out either.

### Verdict

**PASSED.**

Live acceptance: **PENDING (live)** — tagged `#needs-flight` on `body-layer/ROADMAP/BL-B133.md`,
per root `CLAUDE.md`'s "never block a merge on live acceptance" rule. Card published (see report).
