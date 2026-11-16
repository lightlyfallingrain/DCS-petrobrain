# Definition of Done: seat-change-triggers

Branch `feature/seat-change-triggers`, fast-forwarded cleanly onto this worktree's `main` tip
(`a55f7e97`) to tip `12470f4434797f89f402ee2a78d83f3ead3ddbaf`. **This verdict is scoped to that
sha** — `12470f44` (`Review feature/seat-change-triggers: APPROVED`). If the branch moves after
this report, the verdict is stale.

No `plan.md` exists for this feature. Per the dispatch instructions, commit `e2ee3f98`'s message
is the spec: *"Add effector sequence triggers for when Player changes to pilot seat / copilot
seat"* (user, verbatim). Only `body-layer` is touched (confirmed by `git diff --name-only
a55f7e97..12470f44`).

## Code Quality

- [x] **Full body-layer suite** (`PYTHONPATH=src:../world-model/src
  /home/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python -m pytest tests -q`, run from this
  worktree's `body-layer/`, serial — `pytest-xdist` is not installed in this venv so `-n auto`
  errors with "unrecognized arguments"; ran without it instead of guessing a different flag):
  **3326 passed, 4 xfailed in 406.60s**. Tested tree sha: `12470f4434797f89f402ee2a78d83f3ead3ddbaf`.
- [x] `ruff format --check body-layer` — one pre-existing finding
  (`research/2026-10-05-security-audit.md`), untouched by this diff (confirmed: that file is not
  in `git diff --name-only`). No finding in any file this commit touches.
- [x] `ruff check body-layer` — all checks passed.
- [x] `cd body-layer && mypy --strict src` — Success: no issues found in 84 source files.
- [x] No unhandled errors/panics in data paths — `_as_seat` is a closed three-branch allow-list
  (`"pilot"`/`"operator"`/else `None`), never raises; `seat_change` is a pure comparison over
  already-constrained `Literal` values.
- [x] No debug `print`/console output introduced (`git diff a55f7e97..e2ee3f98 -- body-layer |
  grep -niE '^\+.*print\('` — no hits).
- [x] No TODO/FIXME/XXX introduced (same diff, grepped — no hits).

## Scope & Correctness

- [x] Matches the commit-message spec exactly: two triggers (`SEAT_PILOT`/`SEAT_COPILOT`), fired
  on a change between two *known* seats only — not the mission's starting seat, not while a
  mission (re)start resolves (same suppression window as `TAKEOFF`, confirmed by Reviewer by
  mutating the suppression clause and watching the restart test fail).
- [x] No unplanned scope: the diff is exactly the 7 files `git show e2ee3f98 --stat` lists — one
  field, one parser, one pure function, two enum members + their `TriggerInfo`, the `body.py`
  wiring, docs, tests. No touch to `effector_engine.py`'s dispatch machinery (reused as-is, per
  Security's review).
- [x] No invariant violated. Checked against `body-layer/CLAUDE.md`'s "Invariants" section
  directly: no-omniscience boundary untouched (this is a mechanical mirror of a DCS-reported
  camera seat into an effector trigger, not a belief/perception change); new CLI-flag posture N/A
  (no new flag); module independence untouched; nothing here touches `Contact`/classification/
  cardinality at all.
- [x] All files staged — confirmed by the fast-forward itself; `git status --porcelain` was
  (and is) empty.

## Testing

- [x] Core logic covered: `seat_change`'s four decision branches (first reading, no-op, going
  unknown, a real move each direction) and `_as_seat`'s three branches, all unit-tested in
  `test_ai_pilot_wheel.py`'s new `TestPlayerSeat`.
- [x] **Meaningful, not decorative** — Reviewer mutation-verified both absence-asserting tests
  (the mission-restart suppression test and the unknown-seat-value test) by breaking the code
  under test and watching them fail, then restored. I did not re-run the mutations myself (no
  reason to re-verify a check Reviewer already ran and that the same unchanged diff still holds),
  but did read `test_body.py`'s new `test_seat_changes_fire_seat_copilot_then_seat_pilot` and
  `test_a_seat_read_across_a_mission_restart_fires_nothing` in full: they drive the *real*
  `_run_crew_text_poll_loop` against a fake aircraft client and assert the real cockpit-switch
  write list, not a mock of `fire_effector_trigger` — an actual end-to-end exercise of the wiring,
  not a unit test of `seat_change` in isolation.
- [x] No existing tests broken — full suite above, 0 failures.

## Documentation

- [x] Reviewer findings addressed: `review.md` verdict is **APPROVED**, **Required Fixes: None**.
  Two Optional Refinements noted (a docstring cross-reference between `seat_change` and
  `ai_pilot_seat_from_camera`'s held-value behaviour; naming in the test card/acceptance note that
  no sequence files ship yet) — both optional, not gating.
- [x] `accepted-items-ledger.sh plans/seat-change-triggers` — empty output (no `plan.md`, no
  `U<n>` decisions to ledger; consistent with Reviewer's own note that the ledger does not apply
  here).
- [x] Non-obvious behaviour explained via code structure: `body-layer/CLAUDE.md`'s "Belief —
  observation consumption" section gained a paragraph on `seat-pilot`/`seat-copilot` (verified
  present in the diff, consistent with every other trigger documented in that same list); the new
  `ParkedFlightState.player_seat` field and `_as_seat`/`seat_change` carry their own docstrings;
  `config/sequences/triggers.md` was regenerated and matches `TRIGGER_INFO` (Reviewer re-ran the
  generator and diffed; I spot-checked the committed file against the current `TRIGGER_INFO`
  source by eye and it matches word for word).

## Security

- [x] `plans/seat-change-triggers/security-review.md` exists, verdict **APPROVED**, **Required
  Fixes: None**. One low-risk item presented with the standard options (a LAN actor forging
  `apw_seat` can fire the triggers at will) — recommended action **accept**, as an extension of
  the standing BL-15 LAN-trust acceptance, with a stated lapse condition (multiplayer/shared-
  machine scope change). Not a gating finding; not filed as a new backlog item, by Security's own
  stated reasoning (same boundary, narrower blast radius than the mission-start acceptance it
  extends).

## Notes harvest

`/notes-harvest seat-change-triggers` produced **zero candidates** — the extraction looks at
`implementation.md`'s "Notable Discoveries", `debug.md`'s sections, and `review.md`'s "Required
Fixes"; this feature has no `implementation.md`/`debug.md`, and `review.md`'s Required Fixes
section is empty. I also read both review files end-to-end for anything non-obvious worth a
`notes/` entry beyond what the mechanical extraction catches: nothing qualifies — the Lua
held-value behaviour is already in two places (the Python comment and `Export.lua`'s own
comment), the LAN-trust reasoning is a restatement of an already-filed acceptance
(`[[project_bl15_mission_start_plan_review]]`), and the "no sequence files ship" fact is already
in the commit message and `CLAUDE.md`. Nothing staged under `notes/`.

`memory-search.py -r dod seat change trigger camera` — no match (not indexed, not "does not
exist"). Reviewer's Required Fixes list is empty, so there is no recurring-fix category to flag as
process debt here.

## Unblock-condition check

No accepted-debt entry states an executable clearing condition for this feature (no roadmap entry,
no `#needs-flight` tag written anywhere yet — see below). There is nothing to run.

## Live acceptance

**PENDING (live), and currently unobservable rather than merely unflown.** Two separate things are
outstanding, and they are not the same gap:

1. **Whether `Export.lua`'s `apw_seat` reports real seat changes correctly in the cockpit.** This
   is `fix/ai-wheel-pilot-seat-gate`'s own dependency (merged immediately before this branch,
   `793968ee`/`a55f7e97`), not introduced by this commit. Reviewer verified the assumption against
   the Lua source directly (held-value behaviour, `nil` only on `LuaExportStop`) but that is a
   source read, not a flight.
2. **Whether the new triggers fire a cockpit switch correctly once a sequence file exists.** This
   commit ships **no** `seat-pilot.md`/`seat-copilot.md` sequence files — by design, per the
   commit message ("the user writes those"). I checked whether there is any other way to observe
   the trigger firing live in the meantime (a debug log, a `--verbose` flag): there is not.
   `belief/effector_engine.py`'s own logger (`belief.effector_engine`) is never configured by
   `body.py`'s `_configure_logger_for_main()` (which only raises *its own* module's logger,
   `body.py`'s, to `INFO` — by explicit design, so as not to flood every other module's logger
   globally), and no CLI flag exists to change that. So until a sequence file is authored, this
   feature has **zero observable effect** in a live sortie, by design, not by omission — there is
   nothing a test card could ask the user to look at yet.

I am not minting a roadmap entry or `#needs-flight` tag for this (per dispatch instruction: no
roadmap entry exists for this feature, and I was told not to mint one unless the checklist
required it — it does not; this is a trigger-mechanism addition analogous to `mission-start`/
`mission-start-in-air`, which also shipped without its own roadmap entry). The outstanding live
item is carried here, in this report, and in the commit message's own account, rather than as a
roadmap tag with nowhere natural to live.

**What this means for the user:** nothing to fly for *this* branch specifically yet. Once you
author a `seat-pilot.md`/`seat-copilot.md` sequence file (same format as `mission-start-in-air.md`
— see `config/sequences/<aircraft-dir>/*.md` and `switch-reference.md`), a flight that moves seats
mid-mission (not at the mission's starting seat) and checks the mapped switch is the acceptance
test; I am not fabricating a card with a command to run against behaviour that does not exist yet.

## Milestone-completion question

Does this change what the next milestone should be, or invalidate a downstream assumption? **No**
— this adds two new, independently-triggered no-op-until-authored hooks into the existing effector
trigger system; it changes no existing trigger's behaviour, touches no belief/perception state,
and nothing downstream depends on it firing.

## Verdict

**PASSED.**
