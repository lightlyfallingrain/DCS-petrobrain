# Definition of Done: overlay-speech-callouts (final pass)

## DoD Checklist

### Code Quality
- [x] **Format/lint/type/test commands pass** (body-layer only, single affected subproject)
  - `ruff format --check body-layer/src body-layer/tests` — pass (62 files already formatted)
  - `ruff check body-layer/src body-layer/tests` — pass
  - `cd body-layer && mypy src` — pass (no issues in 29 source files)
  - `pytest body-layer/tests -q` — pass (446 tests passed)
- [x] **No unhandled errors or panics in data paths**
  - Overlay push failures wrapped in `try/except AircraftLayerError`, log-and-continue (matching BL-2.5 pattern)
  - All degrade-on-failure paths tested (`test_failed_overlay_push_degrades_without_raising_and_does_not_block_remaining_lines`)
- [x] **No debug output left in committed code**
  - Searched committed diff for `print|debug|TODO|FIXME` — no new debug statements introduced
- [x] **No leftover debug code or TODO comments introduced by this feature**
  - No new TODO/FIXME comments in `git diff main body-layer/src/`

### Scope & Correctness
- [x] **Implementation matches the plan** (`plans/overlay-speech-callouts/plan.md`)
  - Part (1): routing mechanism — overlay_client field, _print funnel, urgency prefix, logger.py wiring all match plan exactly
  - Part (2): lifecycle-event content fix — _contact_report_text extraction, id-prefix prepend, lost/classification unchanged all match addendum exactly
- [x] **No unplanned scope added silently**
  - All file changes are in the "Affected Modules" list; no surprise refactors or unrelated edits
  - Two pre-existing test assertions in test_crew_console.py required updates (old format -> new format) — these are mechanical follow-throughs of the intended change, not scope creep
- [x] **No invariants violated**
  - DCS: read-only (no DCS modification)
  - Code owns facts: speech.py templates own the contact-report format, not model/brain interpretation
  - Provenance: OutgoingSpeech carries no new provenance fields (existing design for rendered text)
- [x] **All new/modified files staged and committed**
  - `git status` shows clean working tree; all files committed on feature branch

### Testing
- [x] **Core logic covered by tests**
  - Routing: 7 new tests in test_crew_console.py (no-op, readback, contact report, lifecycle event, urgent call, injection error, failed push + degrade)
  - Content fix: 2 new tests in test_speech.py (detected with enrichment, render_contact_report with enrichment), plus 2 pre-existing test updates
- [x] **Tests are meaningful (not decorative)**
  - FakeOverlayClient captures actual `pushed` lines; assertions check exact content, not "no exception"
  - Enrichment tests use realistic fixture with EnrichmentContext
  - Degrade test injects real AircraftLayerError, confirms failed line absent and later line succeeds
- [x] **No existing tests broken**
  - Full pytest run: 446 passed (no failures, no regressions)

### Documentation
- [x] **Reviewer findings addressed**
  - Review summary: APPROVED, no required fixes
  - Addendum review summary: APPROVED, no required fixes
- [x] **Non-obvious behavior explained**
  - crew_console.py: _print docstring explains the two sinks (output + overlay), why it's the funnel point, the error-handling pattern
  - logger.py: docstring and help strings updated to describe --crew-text --overlay combination
  - speech.py: module docstring updated to explain the shared _contact_report_text helper, the detected/reacquired format with id prefix, semantic-fragment selection, and which lifecycle kinds get which templates
  - body-layer/CLAUDE.md: "Running the live logger" section and crew_console.py Structure entry both updated

### Security
- [x] **No security plan or deep analysis required**
  - This feature has no new untrusted-input surface, no auth/crypto changes, no execution-risk changes
  - Applies to offline pipeline phase with no external clients yet (CLAUDE.md: "Skip `performance-reviewer` and `security` for now")

## Summary

**Result: PASSED**

All automated checks pass. No required fixes from Reviewer (both review passes explicitly stated "Required Fixes: None"). Core logic tested meaningfully. Implementation matches plan for both parts (routing mechanism + content fix).

**Live acceptance testing status (precise):**
- Part (1) — overlay routing mechanism: CONFIRMED LIVE by user (readback/contact-report/lifecycle/urgent-call all showed correctly on overlay)
- Part (2) — CONTACT_DETECTED/REACQUIRED content fix: NOT YET LIVE-TESTED (blocked by execution boundary: agents do not run live DCS sessions; user to verify acceptance-test instructions below)

---

## Acceptance Testing Plan: Overlay Speech Callouts

**Goal:** Verify that (1) the routing mechanism delivers all crew-spoken text to the in-cockpit overlay correctly, and (2) the lifecycle-event content fix formats CONTACT_DETECTED/CONTACT_REACQUIRED as proper radio callouts with unit type, clock, range, and enrichment.

**Prerequisites**
- [ ] Type-checked and importable (`cd body-layer && mypy src`)
- [ ] All tests pass locally (`pytest body-layer/tests -q`)
- [ ] `--crew-text --overlay` combination wired in logger.py (checked at merge time)
- [ ] Live DCS session with aircraft-layer running, `POST /text/push` endpoint functional

**Test Cases (Part 2 only — Part 1 already live-acceptance-tested)**

1. **CONTACT_DETECTED event renders full callout format**
   - Trigger detection of a unit near a mapped feature (e.g., truck 2 km from a road)
   - Expected: overlay shows `"CONTACT_1: UNKNOWN truck, 2 o'clock, 2.0 km near a road (120m)."`
   - Verify: unit type, clock direction, range in km, and semantic enrichment fragment all present

2. **CONTACT_REACQUIRED event renders full callout format**
   - After a detected contact leaves LOS and re-enters, trigger reacquisition
   - Expected: overlay shows `"CONTACT_2: UNKNOWN [type], [clock] o'clock, [range] km [enrichment]."` (same format as CONTACT_DETECTED)
   - Verify: full callout format, not the old enum-value minimal line

3. **CONTACT_LOST remains minimal (unchanged)**
   - After any detection, trigger contact loss (move out of LOS or line of sight breaks)
   - Expected: overlay shows `"CONTACT_1 lost."` (no colon after id, no positional data)
   - Verify: confirms CONTACT_LOST was not over-extended (only DETECTED/REACQUIRED got the full format)

4. **Enrichment fragment omitted gracefully when unavailable**
   - Trigger a detection in a region with no mapped OSM features nearby
   - Expected: overlay shows `"CONTACT_3: UNKNOWN [type], [clock] o'clock, [range] km."` (no enrichment clause)
   - Verify: absent-not-null convention holds; no `None` or placeholder text

**Edge Cases to Probe**
- **Multiple detections in quick succession** — confirm all are pushed (not dropped by burst/last-wins behavior, which is inherited from TextOverlaySender and noted as acceptable in the plan)
- **Detection before EnrichmentContext is built** — confirm it renders without enrichment fragment, not as an error
- **Invalid/unknown coalition** — confirm it renders as `"UNKNOWN"`, which is expected (backlog item, not a bug)

**Pass Criteria**
The feature passes if:
1. All CONTACT_DETECTED and CONTACT_REACQUIRED events show the full `"id: type, clock, range [enrichment]."` format (not the old enum-value line)
2. CONTACT_LOST remains minimal (`"id lost."`)
3. No regressions visible in existing callout paths (readbacks, player-initiated contact reports, urgent calls all still show on overlay)
4. Enrichment fragments render when available, omit gracefully when absent (no error, no null placeholders)
