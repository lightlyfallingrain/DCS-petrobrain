# Definition of Done — `fix/guidance-ready-edge`

**Scope of this verdict:** tip `1390acfdf34511ece90526f6070521ea2594c473`, fast-forwarded cleanly
from `origin/main` `6dfece18` (strict ancestor, clean tree). This verdict is scoped to that sha;
if the branch moves, re-run.

## Code Quality (body-layer — the only subproject the diff touches)

Diff `6dfece18..1390acfd` touches only:
`body-layer/src/belief/crew_console.py`, `body-layer/src/belief/sight_effector.py`,
`body-layer/src/logger.py`, `body-layer/tests/test_logger.py`, plus the four
`plans/guidance-ready-edge/*.md` role reports. No other subproject touched.

- `ruff format --check src tests` — PASS (163 files already formatted)
- `ruff check src tests` — PASS (all checks passed)
- `cd body-layer && mypy src` (strict) — PASS (71 source files, no issues)
- `pytest body-layer/tests -q -p no:randomly` — PASS (2445 passed, 4 xfailed)

All four re-run fresh in this worktree, not taken from the implementer's/reviewer's own report
(which matched).

No debug output, no TODOs, no unhandled errors introduced — confirmed by Reviewer's full read
of all three changed production files plus the full test diff, and by the ruff/mypy passes above.

## Scope & Correctness

- Matches `plans/guidance-ready-edge/implementation.md` and the cited decision
  (`plans/9k113-sight-pointing/plan.md` row "`ready_observed` / `sight_ready`" — "announcement
  latch per Decision 2"). Confirmed by direct read of that row (line 396 of plan.md).
- Reviewer traced the full chain (not just the diff): `refresh_cockpit_switch_readback`'s
  sticky-on-missing-sample behaviour, call order in `logger.py`, `reset_for_new_mission`'s
  reset of the new field — and ran a genuine mutation test (checked out pre-fix production code
  against the new tests; both new tests and the modified existing test fail against old code,
  for the right reason). Required Fixes: none.
- No unplanned scope: four files touched, matches the implementation report exactly.
- No CLAUDE.md invariant violated — this is a pure in-process state-machine fix on an
  already-trusted `bool | None` value; no omniscience boundary, no provenance field, nothing
  DCS-authoritative is touched differently.
- All new/modified files were staged (verified via the fast-forward diff; nothing left
  uncommitted on the branch).

## Testing

- Two new tests + one existing test extended to drive a genuine cold-start edge rather than the
  old "first-ever-lit" case the old code conflated with an edge.
- Reviewer mutation-tested all three against pre-fix code — not decorative.
- No existing test broken (full suite: 2445 passed, 4 xfailed, same xfail count as the
  pre-existing baseline on `main`).

## Documentation

- Reviewer findings: none required, so nothing outstanding.
- Non-obvious behaviour (`None` is not `False`, the "every poll unconditionally" contract) is
  explained in both the dataclass field docstring and the function docstring per the
  implementation report — read directly, matches.

## Security

- `plans/guidance-ready-edge/security.md` — deep analysis (this bug fix has no plan review;
  bug-fix path is Debugger → Reviewer → Security → DoD per `AGENTS.md`). **APPROVED.** No new
  dependency, no new input source, no attacker-reachable surface change — the fix only changes
  which transition of an already-trusted `bool | None` triggers a hardcoded string being printed.

## Performance

- `plans/guidance-ready-edge/performance.md` — **APPROVED** (MONITOR on the now-unconditional
  per-poll call, ~1 Hz, same cost class as the loop's existing 16 other per-field `replace()`
  calls; not a blocker).

## Acceptance boundary — what this cannot verify

Both new tests and the mutation-tested existing test drive the real poll loop
(`_run_crew_text_poll_loop`) against a fake aircraft-layer client, not real DCS. **Structurally
out of reach of any fixture here:**
- Whether the real DCS 960 lamp actually transitions `1 -> 0 -> 1` on a genuine power-down/
  power-up the way the fixtures assume, rather than staying latched, bouncing, or reading
  differently through the real cockpit-switch channel.
- Whether the spoken/pushed "Guidance unit ready." line is audible/legible through the real
  TTS/overlay pipeline at the moment the edge fires in a live cockpit — this fix only verifies
  *when* the line is queued, not that it is heard correctly.
- Whether `960` is in fact the READY lamp at all — that identification is `BL-B80`'s own open
  question (Flight A, Part 2), not something this fix's tests assume or re-verify; this fix is
  correct *given* that identification, and silent on whether the identification itself is right.

## Flaky test — reported, not filed

The implementer and Reviewer both independently observed
`test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop` failing intermittently
under `pytest-randomly`'s default random ordering (passes in isolation, passes reliably with
`-p no:randomly`), and judged it pre-existing and unrelated to this diff (git blame: content
predates this branch, commit `a5def59e`).

**Checked for an existing backlog item covering it — found none.** `body-layer/ROADMAP/BL-B80.md`
(the most recent prior DoD pass, 2026-10-22) already noted a flake in the *same test group* under
the *same root cause* (logging-handler state leaking across tests, same originating commit
`a5def59e`) but names a **different test function**,
`test_connection_reporter_announces_the_first_connection`, and that note is prose inside a
roadmap entry, not a tracked `BL-B<n>`/`X-B<n>` backlog item with its own ID. `grep` over
`body-layer/ROADMAP/` and `todo/backlog/` for `test_connection_reporter` found only that one prose
mention — no ID, no entry dedicated to this flake class. Per instruction, **not filing one** —
flagging for the main loop to put to the user: likely the same underlying `caplog`-isolation
issue across (at least) two test functions in this group, worth one backlog item covering the
class rather than per-test notes scattered across roadmap prose.

## Flight A card — checked, no change needed

`docs/acceptance/2026-10-22-bl-b80-v2-flight-a.md` runs no body-layer process at all — Part 1 is
the aircraft-layer Lua calibration probe plus manual pilot observation, Part 2 is a manual
cold-start lamp-timing observation against "production Export.lua or the probe." Neither part
exercises `logger.py`'s `--crew-text` poll loop or `CrewConsole`, so the pre-fix latch bug (silent
re-announcement on a warm air start masking the actual defect) was never reachable from this card
and nothing in it needed correcting. Noted directly in `body-layer/ROADMAP/BL-B80.md` what a
future Flight B card (not yet written, since it covers Stage 4's held-world-direction behaviour,
which does run the real poll loop with `--crew-text`) should state: expect "Guidance unit ready."
spoken once, on the lamp's observed off→on transition, not automatically at mission start if the
unit is already warm.

## Roadmap

Added a dated note to `body-layer/ROADMAP/BL-B80.md` recording that the merged build's
ready-callout divergence from the plan's own Decision 2 is fixed on `fix/guidance-ready-edge`
(not yet merged). **Milestone-completion question:** this fix does not complete BL-B80 (still
`[~]`, Flight A/B outstanding) and does not change what BL-B80's next step should be or
invalidate anything downstream relies on — it corrects an implementation detail inside an
already-known, already-tracked risk area of a milestone that was merged ahead of its own
pre-merge condition.

## Notes harvest

Added one bullet to `notes/the-9k113-sight-bl-b64.md` (closest existing topic — the lamp/edge
behaviour this fix corrects is part of that milestone's own callout mechanism): the general
"speak once when a lamp lights" pattern needs a previous-*observed* edge, not a has-it-ever-fired
latch, because a latch cannot distinguish "just became true" from "was already true before we
started watching" — which is exactly why the old bug was invisible on a warm air start and only
showed on a real power cycle. Not duplicating anything already in that file (checked the file in
full first).

No recurring-fix pattern to log in `.claude/agent-memory/dod/`: Reviewer's required-fixes count
for this feature is zero (approved on first pass), so there is nothing to compare against prior
"recurring fix" categories.

## Verdict

**DoD: PASSED**, scoped to tip `1390acfd`. Acceptance testing with the user cannot happen here
(no DCS session reachable from this worktree) — see "Acceptance boundary" above for what is and
is not verified, and the main loop should carry the flaky-test and Flight-B-card notes to the
user alongside the merge decision.
