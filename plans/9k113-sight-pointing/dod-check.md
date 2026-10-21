# Definition of Done: BL-B80 Stages 1-3 (9K113 sight pointing)

**Scope note:** this batch is Stages 1-3 of `plans/9k113-sight-pointing/plan.md`. Stage 4 (the
live sortie) is explicitly not part of this DoD pass — it is the acceptance step this report
hands off. **This DoD does not mark BL-B80 done.**

**Verdict scoped to tip `8b2967008f7654f41be52d2779cc430c5605c32d`** on
`feature/9k113-sight-pointing`. HEAD at dispatch (`9284cd34`) was a strict ancestor of this tip;
fast-forwarded cleanly, tree clean throughout. If the branch moves past this sha before merge,
re-run.

## Code Quality

| Check | Subproject | Result |
|---|---|---|
| `ruff format --check` | aircraft-layer | PASS (1 pre-existing unrelated file flagged — `research/2026-10-06-unit-id-join-reduce.py`, last touched `bc680887`, not in this branch's diff) |
| `ruff check` | aircraft-layer | PASS (same pre-existing file, `EXE001` shebang-not-executable) |
| `mypy --strict src` | aircraft-layer | PASS — 26 source files, no issues |
| `pytest` | aircraft-layer | PASS — 469 passed |
| `ruff format --check` | body-layer | PASS (1 pre-existing unrelated file flagged — `research/2026-10-05-security-audit.md`, a markdown research note, not in this branch's diff) |
| `ruff check` | body-layer | PASS — all checks passed |
| `mypy --strict src` | body-layer | PASS — 70 source files, no issues |
| `pytest` | body-layer | PASS — 2418 passed, 4 xfailed |
| `luac5.1 -p Export.lua` | aircraft-layer | PASS — syntax OK |

All commands run fresh in this worktree, not copied from a prior report. The two flagged files
are both outside this branch's own diff (confirmed via `git log` on each path showing only a
pre-existing commit) and are not blockers.

- No unhandled errors/panics in data paths — confirmed via Reviewer's full read plus Security's
  deep analysis; no open findings.
- No debug output left in committed code — none found.
- No leftover debug code or TODO comments introduced by this feature — none found.

## Scope & Correctness

- Implementation matches `plans/9k113-sight-pointing/plan.md`, including the 2026-10-22
  coordinator amendments — confirmed by Reviewer's full read and independently spot-checked here
  (Co-moving Fields table, elevation formula derivation, `EXPORT_SCRIPT_VERSION`/
  `EXPECTED_EXPORT_VERSION` pairing at `2026-10-22b`).
- No unplanned scope added silently — Reviewer's review confirms this; the one post-review fix
  (the exponent-float bug) is an in-scope bug fix on code this batch introduced, not scope
  expansion, and went through the standard bug-fix role sequence (Debugger implicit in the fix,
  Reviewer, Security) per `AGENTS.md`.
- No invariants from CLAUDE.md violated — no-omniscience boundary, module independence, and the
  fixed cockpit-write vocabulary precedent are all explicitly checked in `security-plan-review.md`
  and `security-review.md`.
- All new files staged — confirmed, see below.

## Testing

- Core logic covered: `sight_effector.py`'s new conversion functions, `in_gyro_alignment`,
  `advance_sight_aim`'s readback-preference branch, `sight_target` wire validation (both API and
  Export.lua sides), the exponent-float fix's live-Lua-interpreter round trip.
- Tests are meaningful: Reviewer independently re-ran the implementer's edge cases against a live
  Lua interpreter rather than trusting the implementer's account; one gap (missing `run_once`-level
  integration test for the gyro-alignment optic cap) was flagged and left as a documented residual,
  not silently dropped.
- No existing tests broken — full suite green both subprojects (above).

## Documentation

- Reviewer findings addressed: all five required fixes from `review.md`'s first pass verified
  present and correct by Reviewer's own fix-diff re-review; the exponent-float fix's own required
  fixes (bound documentation, precision-ceiling note) are optional refinements, not blocking.
- Non-obvious behaviour explained: `sight_effector.py`/`Export.lua` docstrings state which
  functions are command-domain vs. readback-domain (post-fix); `notes/the-9k113-sight-bl-b64.md`
  now carries both the domain-distinction lesson and the shared-field/optic-gating lesson from this
  batch (see Notes Harvest below).

## Security

- `plans/9k113-sight-pointing/security-plan-review.md` — APPROVED.
- `plans/9k113-sight-pointing/security-review.md` — APPROVED (Stages 1-3, as originally written)
  and APPROVED (exponent-float fix, the post-review addendum) — both verdicts present, no open
  findings.
- `plans/9k113-sight-pointing/performance-review.md` — APPROVED — MONITOR (one item to watch
  under real load, not a blocker).

## Tuning

`GYRO_ALIGNMENT_S` declared via `tuning.real` in `sight_effector.py` (lo=5.0, hi=20.0,
status="measured") and rendered correctly in `body-layer/config/defaults.toml` with its full
`#:`-sourced comment, status, and range — confirmed by reading the rendered file, not the
generator's source comment.

## Acceptance boundary — what Stage 4 structurally cannot be skipped for

Everything above is mechanical and fixture/unit-test-reachable. **Nothing in this batch's own test
suite can reach `Export.lua` live** (this subproject's standing limitation) or verify a physical
quantity against DCS's real mechanical stops. Specifically, this DoD pass cannot and does not
verify:

- Whether the derived (not measured) elevation calibration actually matches the real +20°/−15°
  mechanical limits.
- Whether the gyro-alignment window is cockpit-invisible in practice (no stray `ShowMenu`, no
  premature sight reports).
- Whether the AI-off detector ever fires when DCS's own AI Petrovich is genuinely on and tracking,
  in real ordinary flight rather than a reasoned-about trace.
- Whether `home_phase` actually follows a real DCS-triggered automatic OBSERV-off, not just the
  commanded one.
- Whether the overlay actually reopens after a real manual close.

These five are exactly Stage 4's acceptance list — see the card below.

## Roadmap

`body-layer/ROADMAP/BL-B80.md` updated: title and opening line corrected from "player axis" to
"AI axis" (the body text already carried the 2026-10-21 SUPERSEDED correction; only the heading
and summary line were stale), checkbox state to `[~]` / `#status/in-progress` (not `[x]`/done —
Stage 4 has not flown and this batch is not yet merged), and a new "Status, 2026-10-22" section
naming what Stages 1-3 built, what Stage 4 must still verify, and the `BL-B67` dependency.
**Deliberately not tagged `#needs-flight`**: per `docs/TAGS.md`, that tag is for a shipped, merged
change awaiting its sortie. This entry has not merged, so `#status/in-progress` is the correct
tag — `#needs-flight` would be added only if this merges before Stage 4 flies.

## Milestone-completion question

**Does this batch change what the next milestone should be, or invalidate a downstream
assumption?** Not yet — Stages 1-3 are exactly what `BL-B67` (the ATGM run) was already known to
depend on, and nothing here changes that dependency's shape. What *could* change it: if Stage 4
finds the derived elevation formula wrong at either mechanical stop, that correction must land in
this entry before `BL-B67` is planned (the plan's own "Second-order effect" section already says
so). So the next milestone is unchanged for now, but is conditionally gated on Stage 4's elevation
check specifically, not on the whole sortie.

## Acceptance Testing Plan

**Goal:** confirm the real 9K113 sight follows Petrovich's modelled aim on the AI axis, hits its
real mechanical stops at the derived elevation calibration, stays cockpit-invisible during the
gyro-alignment window, and that `home_phase`/the AI overlay correctly follow DCS's own observed
state rather than only the spoken command.

Full card, with every command either run for real (output pasted) or marked UNVERIFIED:
`docs/acceptance/2026-10-22-bl-b80-sight-pointing-sortie.md`. Published artifact:
https://claude.ai/artifact/NBTX4TmY2oxEJ1hXz8MY6Y

**Branch to fly:** `feature/9k113-sight-pointing` (not merged — check it out explicitly, the repo
root is not parked here).

**Prerequisites**
- [x] `mypy --strict` clean on both touched subprojects (ran above, this report).
- [ ] Export.lua `2026-10-22b` deployed to the Windows box (UNVERIFIED — needs Windows).
- [ ] Collector restarted, no version-mismatch warning (UNVERIFIED — needs Windows + DCS).

**Test Cases** — see the card's five flight blocks (gyro-alignment window + smooth motion, the
two mechanical stops, Observ-off + auto-off following, reopen-after-manual-close, ordinary-flight
false-fire watch).

**Pass Criteria:** all five blocks produce the expected result and no regression appears in
BL-B66's existing switch-power-up/weapons-arming behaviour (unchanged by this batch, worth a quick
sanity check during the same flight since the power-up sequence is a prerequisite for every block
here).

**Live acceptance is not a merge gate.** Per CLAUDE.md's standing direction, this batch can sit
merged-pending or unmerged while the user's Windows/DCS access permits a flight; nothing here
blocks starting other work in the meantime.
