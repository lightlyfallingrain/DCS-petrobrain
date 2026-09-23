### Review Summary

Scope: `feature/binocular-optic` merged into this worktree (sha `0bbe02e`), reviewing only the
voice-command-completeness Stages 1–5 commits (`63d7421`, `6fc607c`/`6c84f0b`, `4bec784`/`9bc9c6b`/
`0bbe02e`). The prior binocular-optic milestone (`plans/binocular-optic/review.md`) was **not**
re-reviewed, per instruction.

All six specifically-flagged risk areas were checked against the actual code (not just the
implementation log's claims), and two were verified empirically rather than by reading:

1. **`ScanPlan`'s three directional fields.** `__post_init__` enforces `commanded_sector`/
   `commanded_legs` mutual exclusivity and the `command_t_sim` pairing, but does **not** forbid
   `fixed_look` being set alongside `commanded_sector`/`commanded_legs`. That combination is in
   fact directly constructed in `tests/test_gaze.py::test_fixed_look_wins_over_commanded_legs`,
   which asserts `gaze_at`'s fixed tie-break (`fixed_look` always wins). No production call site
   ever constructs that combination — `ScanPlan.fixed_look_at()` always sets `commanded_sector`/
   `commanded_legs` to `None`, and `logger._apply_active_gaze` only ever *replaces* `resolved_plan`
   wholesale with a fresh `fixed_look_at(...)`, never merges it onto an existing commanded plan.
   `gaze_at` is a pure function of `(t_sim, plan)` in all paths verified. Not a defect — a
   deliberately loose invariant, exercised and documented, not a silent gap.

2. **Absolute→relative conversion / wrap / thrash.** Hand-verified `legs_within_wedge` at heading
   350°/0°/10° for a commanded-north scan (`legs_within_wedge((0 - heading + 180) % 360 - 180,
   45.0)`): all three headings resolve to the same `(11, 12, 1)` legs with no discontinuity at the
   360°/0° wrap — confirmed by direct execution, not just reading the modulo arithmetic. The
   binocular lockout (`belief.optic_policy.decide`'s `scan_complete = now_sim -
   state.phase_started_sim >= scan_cycle_period_s`) is keyed to a **fixed** constant
   (`SCAN_CYCLE_PERIOD_S`, passed in by `logger.py`) and to `OpticState.phase_started_sim`, which is
   untouched by `_active_gaze` recomputing a different `commanded_legs` tuple every poll as heading
   drifts — `decide()` never reads `ScanPlan` identity or content at all. No thrash risk found.

3. **Report families' spoken output.** `_handle_report` drops `certainty == "lost"` before the
   family filter, computes `rear_hemisphere` only for the `sector` (compass/numeric) family (the
   clock family is safe by construction, matching `FORWARD_CLOCK_POSITIONS`), and speaks
   `render_no_view` (`"Can't see <direction>."`) instead of `render_clear` (`"<Direction>, clear."`)
   exactly when `rear_hemisphere` is true. A believed contact in the rear hemisphere still reports
   normally (`test_report_bearing_s_still_reports_a_contact_believed_to_be_there`). Verified the
   swap cannot happen: `rear_hemisphere` is computed once, from `COCKPIT_MASKS[STATION_CO_PILOT]`
   (the same mask the real naked-eye visibility path uses), and both directions I checked
   (dead-ahead-north, dead-astern-south) are far from the 130° boundary — clean-cut, no boundary
   test exists but none is needed to resolve those two cases correctly.

4. **`lost` contacts excluded from every report family, not just `report_all`.** Confirmed in code:
   the `certainty == "lost"` drop happens once, before the `clock`/`sector` family filter is
   applied, so it covers `report_all` and every `report_clock_*`/`report_bearing_*` token
   identically — not two separate checks that could drift. `test_report_all_drops_a_lost_contact`
   exercises it end to end.

5. **Numeric bearing wire.** `TranscriptEvent.bearing_degrees: int | None = None` has a default, so
   an older adapter's JSON (missing the key) round-trips through `item.get("bearing_degrees")` as
   `None` in `logger._poll_transcripts` — confirmed this does not crash, it degrades gracefully
   (the same per-field validation posture as every other field). Quantisation itself
   (`_nearest_sector`) is defined once and called from exactly three sites (`_describe_token_for_
   confirm`, `handle_command`'s `scan_bearing_deg` branch, `handle_command`'s `report_bearing_deg`
   branch); all three are consistent — no duplicated bucket logic.

6. **Test quality.** Ran a hand-built five-contact scenario through the real `handle_command
   ("report_all", ...)` dispatch path (not a unit test, a throwaway script) to check the seam
   between `group_facts` (unit-tested in isolation in `test_callouts.py`) and `render_report`'s
   truncation (unit-tested in isolation in `test_speech.py` with hand-built strings) — the two
   halves this brief specifically warned could be individually green while the wiring between them
   is wrong. Result: five distinct contacts correctly grouped, sorted by `report_priority`, capped
   at `REPORT_MAX_GROUPS` (3), and spoken as one utterance ending in `"And more."` — the seam works.
   **No automated regression test exercises this multi-contact/truncation path end to end through
   `_handle_report`** — every existing report test in `test_crew_console.py` uses at most one
   contact. Flagged below as optional, not required, because the behaviour was independently
   verified correct by direct execution, not merely assumed from the two halves' own tests.

### Required Fixes

None.

### Optional Refinements

- **No end-to-end test for `_handle_report`'s multi-contact grouping/truncation.** Every
  `report_*` test in `tests/test_crew_console.py` uses zero or one contact; `group_facts`'s
  bucketing and `render_report`'s `REPORT_MAX_GROUPS`/"And more." truncation are each tested in
  isolation but never together through the real dispatch path. Verified correct by hand this
  review, but a regression here (e.g. a future change to `report_priority`'s sort key, or to the
  `[:REPORT_MAX_GROUPS]` slice) would have no test catching it. Add one test constructing 4+
  distinct contacts and asserting the spoken truncation, mirroring the throwaway script this review
  used. (optional — the code is correct today, this only closes a coverage gap)
- **No test for the absolute→relative wrap case** (`350°→0°→10°` heading with a commanded compass
  scan) that Decision 2/this review's own brief specifically named as a risk. Verified correct by
  direct execution this review, but `tests/test_logger.py`'s compass-conversion tests only cover
  heading 0 and heading 90 — neither exercises the 360°/0° boundary the modulo arithmetic is meant
  to handle. (optional — same reasoning: correct today, worth a cheap regression test)
- **`ScanPlan.__post_init__` does not forbid `fixed_look` co-existing with `commanded_sector`/
  `commanded_legs`.** No production path constructs that combination, and the one place it *is*
  constructed is a test proving the tie-break (`fixed_look` wins). Still, a future caller
  constructing `ScanPlan` directly (rather than via `fixed_look_at`) could silently get a plan whose
  commanded-scan fields are dead by construction, with no error to say so. Worth a defensive
  `ValueError` in `__post_init__` if a future stage starts constructing `ScanPlan` from more call
  sites than today's two. (optional — currently unreachable, not a live bug)
- **No boundary test at the cockpit mask's `rear_cutoff_deg` (130°) for the report-family
  rear-hemisphere carve-out.** The two existing tests (dead-ahead, dead-astern) are far from the
  boundary and both resolve correctly; a test at ~129°/131° relative would pin the `>=` comparison
  explicitly. (optional — low risk, the comparison itself was read and is correct)

### Verdict
APPROVED

### Review Confidence
Full read of the plan, both implementation-log stages, and the complete Stage 1–5 diff
(`body-layer/`, `audio-adapter/`, prose/roadmap/todo files). All six specifically-flagged risk
areas were verified against running code — two (the compass-scan wrap arithmetic, and the
multi-contact report grouping/truncation seam) by direct execution in this worktree's venv, not
just by reading. Both test suites run in full with real numbers: body-layer `ruff format --check`
+ `ruff check` + `mypy --strict` all clean, `pytest tests -q` → **1076 passed, 4 xfailed** (matches
expected); audio-adapter `ruff format --check` + `ruff check` + `mypy --strict` all clean,
`pytest tests -q` → **179 passed, 1 skipped** (matches expected). No spot-checking — this is a
full read.
