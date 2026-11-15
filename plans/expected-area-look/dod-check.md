# Definition of Done: BL-B111 "expected-area look"

**Branch:** `feature/expected-area-look`. **Verdict scoped to tip `f91658d85f56cedd873d2667ef15efe042e5aaeb`**
(Performance review commit) — this worktree's base (`main@b92d59c9`) was a strict ancestor, the
tree was clean, and `git merge --ff-only f91658d8...` landed cleanly with no divergence. If the
branch moves past this sha before merge, this verdict is stale.

## Inputs present (all at tip)

| File | Status |
|---|---|
| `plan.md` | present, 28 commits of architect work, Decisions 1–4 + third-concurrent-check answered "as recommended" |
| `alignment.md` | present — CONCERNS resolved (3 findings, all settled via the plan's own Decisions) |
| `explore-notes.md` | present |
| `implementation.md` | present — 3 passes, each ending green on both subprojects' checks |
| `review.md` | **APPROVED**, Required Fixes: **none** |
| `security.md` | **PASS** (deep analysis; plan review is off-sequence per current project cadence) |
| `performance.md` | **APPROVED — MONITOR** |
| `test-card.md` | present, names `main`, 5 flight cases + log-triage step |
| `test-card-windows.md` | present, names `main`, Stage 1 aircraft-layer-only |

`security-plan-review.md`/`security-review.md` are correctly absent — this project dropped
Security's plan-review step from the sequence (2026-10-30 user direction); `security.md` is the
deep-analysis gate this feature actually needed, and it is present with verdict PASS.

## Mechanical checks (re-run, not taken on faith)

Both subprojects' `.venv` did not exist in this worktree (gitignored); recreated with
`python3.12` (3.11 unavailable on this machine, same substitution `review.md`/`implementation.md`
already made) and the pinned dev versions `implementation.md`/`review.md` record: `ruff==0.16.6`,
`mypy==2.3.1`, `pytest==9.1.1`, plus body-layer's own `pyproj>=3.6`/`numpy>=1.26,<2.5`.

**body-layer:**
- `ruff format --check src tests` — 198 files already formatted. PASS.
- `ruff check src tests` — All checks passed. PASS.
- `mypy src` (strict, run from inside `body-layer/`) — Success, 81 source files. Matches
  `review.md`'s reported count exactly.
- `pytest tests -q` — **3160 passed, 4 xfailed** in 266.63s. Matches `implementation.md`'s Pass 3
  report and `review.md`'s report exactly, byte-for-byte on the count.

**aircraft-layer:**
- `ruff format --check src tests` — 75 files already formatted. PASS.
- `ruff check src tests` — All checks passed. PASS.
- `mypy src` (strict) — Success, 26 source files. Matches `review.md`.
- `pytest tests -q` — **702 passed** in 78.17s. Matches `review.md` exactly.
- `luac5.1 -p` on the outer Hook file (`petrobrain-line-of-sight-hook.lua`) — clean. (The inner
  `dostring_in`-bridged chunk was separately extracted and syntax-checked by the Reviewer, per
  this codebase's own documented caveat that `luac5.1 -p` cannot see inside a string literal — not
  re-done here since `review.md` already shows the extraction and result.)

**`/invariant-check`** (re-run against the live tree, not read off `review.md`):

| Invariant | Status |
|---|---|
| No omniscience (`derived_world_position` outside the Percept boundary) | PASS |
| Module independence (no unsanctioned cross-subproject import) | PASS |
| No `sys.path` smuggling | PASS |
| `BINOCULAR_RANGE_MULTIPLIER` has not returned | PASS |
| No stray `print()` in `perception`/`belief` core | PASS |
| No bare `except:` | PASS |
| Swallowed exceptions (`except: pass`) | WARN, 4 (pre-existing entrypoint pattern per `review.md`) |
| `# type: ignore` suppressions | WARN, 10 repo-wide (includes pre-existing instances; `review.md` separately confirmed the 5 new `self.__init__(...)` reset-pattern instances match this codebase's existing shape) |
| TODO/FIXME markers | PASS |

No FAIL. Both WARN categories are the same pre-existing, already-accepted patterns `review.md`
names, not new introductions.

## Plan/scope/invariant conformance

- All four implementation passes (Stage 0/1 pre-existing on branch, Pass 1/2/3) match
  `plan.md`'s "Remaining build" instructions. The one deliberate amendment —  "A was not seen this
  poll" replaced by "A out of view" (`FOCUS_DWELL_S` window) — is documented in `plan.md` itself
  with its own measured justification (18→0 false-eligible on the continuous-tracking tests, no
  change to any of the plan's own modelled/measured numbers), not a silent scope change.
- No unplanned scope found. The two files the plan's "Affected Modules" named but Pass 1 initially
  missed (`aircraft-layer/CLAUDE.md`, `WORKFLOW.md`) were caught and closed in Pass 3, documented
  as such rather than silently dropped.
- Reviewer's two cross-reference findings (non-continuity re-detection opening a second held check
  against the same A; the Co-moving Fields table) were both read and confirmed correct against the
  real diff, not the plan's file list — no required fix resulted from either.
- `git status --porcelain` clean at tip; all new files (the new modules, 8 new test files, 5 new
  `.claude/agent-memory/` files, `plans/expected-area-look/*`) are committed, none untracked.

## Production acceptance (Stage 3c, re-read not re-run — ~several minutes per `review.md`)

Every fence in `plan.md`'s Acceptance table passed in production mode
(`tools/measure_expected_area_look.py --production 200 300`), per `implementation.md`'s Pass 3
report:

| measure | fence | measured |
|---|---|---|
| Different groups, B announced, area-fits-one-look cells | ≥ 85% | 92.5–100% |
| Same group duplicate, 6 s | ≤ today + 4 pts | max +0.7 pts |
| Same group duplicate, 700 s | ≤ today + 1 pt | every cell equal or decreased |
| Armour, 700 s (area > one look) | = today | 0.0% → 0.0% exactly (Decision 1 confirmed) |
| `CONTACT_RELOCATED`, same-optic | ≤ 5% | 0.0–3.0% |
| SAM vignette, 700 s, "different" | ≤ 2% | 0.0% |

No fence failed; none needed the plan's own "stop and report rather than retune" escape.

## BL-B114 relationship

`BL-B114.md` ("merge-echo rule silences real second groups") is explicitly carried, not closed, by
this feature: Decision 2 keeps the merge-echo case silent on cannot-look (including budget-spent),
so `BL-B114`'s open defect narrows to *only* the cannot-look remainder rather than being resolved.
`plan.md`'s own "Second-order effect" section and `review.md`'s Optional Refinements both state
this correctly — no roadmap edit needed from DoD; the main loop's merge-time update should reflect
"narrowed to cannot-look cases," matching the plan's own wording, not "closed."

## Milestone Completion question

**Does this change what BL-B112 (motion-aware contact certainty, next in body-layer's roadmap)
should be, or invalidate a downstream assumption?**

Yes, in one specific way the plan already names and I confirm by re-reading it against Decision 1:
Decision 1 excludes any remembered group whose belief area has outgrown one binocular sweep
(half-width > 15°) from ever getting an expected-area check — armour at 700 s is the measured case,
with a 5–6 km-wide belief area today. That exclusion's width is a direct function of how fast
belief-area uncertainty grows while a group is unobserved, which is exactly what BL-B112 is meant
to narrow (a stationary/near-stationary group should not keep growing an ever-wider belief
ellipse the longer it goes unseen). **So BL-B112 is not merely "the next independent milestone" —
landing it will mechanically widen the set of remembered groups this feature's Decision 1 currently
excludes**, meaning armour-class re-sightings go from "always folds silently" (100% unannounced,
unchanged by this feature) toward being covered by the look this feature just built, with no further
code change to `expected_area.py` itself. BL-B112's own acceptance criteria should include a check
against `EXPECTED_AREA_MAX_HALF_WIDTH_DEG` for exactly this reason — confirming the narrowing
actually happens, not just that belief area computes differently. This is restated from `plan.md`'s
own "Second-order effect" section, re-confirmed here rather than taken on faith.

## Acceptance boundary — what this feature's fixtures structurally cannot reach

Stating this explicitly, per this role's own standing lesson (the F10-vocabulary case: code can do
exactly what it says against the wrong subsystem, or produce an outcome only a human listener can
judge, and no fixture sees either):

1. **The entire DCS-side mechanism is unverified live.** `land.isVisible`/`land.getHeight` on a
   real terrain point, through the new `probe_points` Hook op, has never run against a real DCS
   session. The production acceptance numbers above are all produced with probe answers **stubbed
   to "clear"** (Pass 3's own stated simplification) — so "every fence passed in production" is
   conditional on the Hook actually returning truthful terrain visibility once flown, not evidence
   that it does. The Stage 1 Windows card is the only thing that can close this, and it is still
   owed (`#needs-flight`).
2. **"Cannot look" due to real terrain, towns, or a `land.getHeight` failure is entirely
   unexercised by any fixture or the harness.** Test Case 4 in `test-card.md` (a group parked in a
   settlement) is the first time this path will run against real DCS data at all.
3. **The ≤ 2 s "A out of view" boundary is explicitly unmeasured even in the harness** — no cell
   under 6 s exists, per `plan.md`'s own Risks section. Whether a crest-masked contact within one
   gaze dwell of a new sighting on its bearing behaves correctly is a pure judgment call until a
   sortie produces that exact geometry.
4. **Whether the trigger fires at a sane rate in a busy real scene, without crowding the shared
   12 s glass budget, is unmeasured** — `plan.md`'s own top Risk. `--expected-area-log` plus
   `sortie-log-triage`'s `expected_area_report` is the instrument, not a guarantee; Case 5 of
   `test-card.md` is the first real read of it.
5. **The relocation line's wording** (*"That group, now two o'clock, three kilometres"*) is
   production-correct by construction (templated, tested) but whether it reads as "neutral" to a
   human pilot — as opposed to sounding like Petrovich is claiming the group moved when he cannot
   tell that from a misjudged range — is exactly the kind of judgment no fixture can render. The
   general "things to listen for" section of `test-card.md` names this directly.

None of this blocks DoD: live acceptance does not gate a merge under the current project rule
(root `CLAUDE.md`, "Workflow", 2026-10-26), and every item above is already named, in these same
terms, in `plan.md`'s Risks section or `test-card.md` — this section is a restatement/confirmation
that those honest limits are on record, not a new finding.

## Unblock condition executed

`plans/expected-area-look/test-card.md` names an exact `sortie-log-triage` command as the way the
user reduces a flown sortie's log. Ran it against a hand-built sample JSONL
(`{"kind":"open",...}`/`{"kind":"verdict",...}` rows) to confirm the command as written actually
executes rather than erroring on a missing flag or wrong invocation:

```
python3 .claude/skills/sortie-log-triage/scripts/triage.py --expected-area <path> --skip-trace
```

Ran clean, printed the `EXPECTED-AREA CHECKS` section header and summary line (0 rows, because the
hand-built sample used a schema I did not match exactly — not a defect in the command, confirmed
`--expected-area` is a real, documented flag on `triage.py --help`). The command in the card is
correct as written.

## Acceptance testing

**Live acceptance is PENDING.** No DCS session is available on this machine. Per the current
project rule, this does not gate the merge. Both test cards (`test-card.md`, `test-card-windows.md`)
name branch `main` and are ready to publish/fly. `BL-B111` carries `#needs-flight` already in its
own entry (`body-layer/ROADMAP/BL-B111.md`), consistent with this report — the main loop's merge-
time status update should keep that tag, not clear it.

## Notes harvest

Two insights added (both non-duplicate, checked against `notes/notes-index.md` topic files and the
existing bullets in each target file before writing):
- `notes/type-checking-and-python-conventions.md` — `mypy --strict` cannot see a circular import
  introduced only through a lazy annotation's *value* dependency (not its type), under
  `from __future__ import annotations`; only the test suite surfaces it.
- `notes/planning-and-process-lessons.md` — two bullets: (1) a trigger precondition of the shape
  "X's timestamp is before Y's" is checking causality, not recency, and is nearly tautological by
  construction; (2) a "declared known state" overriding a derived decay reading (`mark_lost_now`)
  is a reusable pattern worth naming on first use.

Not harvested: the Lua `dostring_in` syntax-check caveat (already documented, not new); the trigger
tautology's own resolution mechanics (already fully captured in
`.claude/agent-memory/architect/feedback_temporal_precondition_tautology.md` and
`.claude/agent-memory/implementer/feedback_tautological_trigger_precondition.md`, which this
feature's own commits added — the `notes/` bullet above restates the generalizable shape for a
wider audience than agent memory reaches, so both are kept, not duplicated against each other).

## Recurring-fix pattern check

`review.md`'s Required Fixes list is **empty** — nothing to check against
`.claude/agent-memory/dod/MEMORY.md`'s prior "recurring fix" categories this time. No new pattern
entry warranted.

## Verdict

**PASSED**, scoped to tip `f91658d85f56cedd873d2667ef15efe042e5aaeb`.

Reviewer confidence: full read, not a spot-check (`review.md`'s own "Review Confidence" section).
Security: PASS, full deep analysis. Performance: APPROVED — MONITOR, six findings all MONITOR/LATER,
none blocking.
