# DoD Gate: emitter-visibility Stage A (BL-B72 + AC-B7)

**Verdict: PASS — scoped to tip `7213a1adda4bbfc98e41e177cc5732a3e61bccb0`** (`feature/emitter-visibility`).
This adds one commit on top of the dispatch's named tip `42ee83c1b7c5c0b9972cb2c32882e21b00e52432`:
the retroactive Security plan review this gate found missing (see below). If the branch moves
again before merge, this verdict no longer covers it.

## Address

Checked out `feature/emitter-visibility` directly into a fresh worktree
(`/Users/sg/Code/DCS-petrobrain-dod-emitter-visibility`); HEAD landed exactly on the named tip
`42ee83c` (not a fast-forward — the branch has diverged from local `main`'s `2d9f101`, confirmed by
`git log --oneline main..feature/emitter-visibility` / `..main` both showing unique commits).

## Gap found and closed before this gate could pass

**Security's plan-review step never ran.** The commit log shows plan (`4b29c8a`) → decisions
recorded (`474266d`, same message as "go ahead and implement") → straight to implementation
(`94a8f29`), with no plan-review commit between. `plans/emitter-visibility/` had `security.md`
(deep analysis, APPROVED) but no `security-plan-review.md`, which `root CLAUDE.md`'s DoD criteria
require to exist and be APPROVED. Dispatched Security (isolated worktree) to run it retroactively
against `plan.md` as finalized. Result: **APPROVED**, committed as `7213a1a`
(`plans/emitter-visibility/security-plan-review.md`). Its own "would this have changed the plan"
section is honest: no — the one real catch on this feature (`Observation.provenance` almost
crossing into `Percept`) is exactly the class of thing a plan-level pass cannot catch and the
implementation-stage pass exists to catch, and it did.

**Process signal, not code debt:** the user's "go ahead and implement" collapsed two
turns into one and the sequence silently skipped a gate as a result. Recorded as a pattern-memory
candidate below.

## Code Quality

- Touched subprojects (from `git diff --name-only main...HEAD`): `aircraft-layer`, `body-layer`
  (plus `.claude/` and `plans/`, docs/memory only — no code). Both run against their own `CLAUDE.md`
  "Commands" sections, independently, rebuilding each venv from the pinned versions named in the
  dispatch (`ruff==0.16.6`, `mypy==2.3.1`, `pytest==9.1.1`, `numpy==2.4.6`, `pyproj==3.8.0`):

  | subproject | format | lint | mypy --strict | pytest |
  |---|---|---|---|---|
  | body-layer | `132 files already formatted` | `All checks passed!` | `Success: no issues found in 60 source files` | `2000 passed, 4 xfailed` |
  | aircraft-layer | `56 files already formatted` | `All checks passed!` | `Success: no issues found in 21 source files` | `262 passed` |

  All run myself, not taken from any report. Numbers match every prior role's reported counts
  exactly (Reviewer, Performance, Security all independently rebuilt and matched too).
- No unhandled errors/panics in data paths: confirmed by Security's deep analysis (fail-safe to
  `"nil"`→`None` on malformed life field, never a guessed `0`; the one raise path is caught by the
  receiver, not propagated) and independently spot-checked (`collector/unit_velocity_receiver.py`'s
  except clause).
- No debug output or TODO/FIXME introduced: `git diff main...HEAD --name-only -- '*.py' '*.lua' | xargs grep -nE "TODO|FIXME|print\(|console\.log|debugger"` → no hits.
- All new files staged: `git status --porcelain` → empty.

## Scope & Correctness

- Matches `plans/emitter-visibility/plan.md`'s Stage A exactly: the shared `emitter` bypass on
  gates 3 (range/size) and 5 (forest) only, tier-clamped to detection-only, burning-unit emitter via
  `getLife()`/`getLife0()` riding the existing `/unit_velocity/latest` feed. `BL-B73`/`BL-B74`/`AC-B8`
  confirmed untouched (`git diff --stat` names no gun-fire/SAM-event files; `implementation.md`
  states this explicitly).
- No unplanned scope added: the one deviation from the plan's literal text (provenance mechanism:
  `Percept.emitter_kind` via a closed mapping, not `Percept.provenance` as first drafted) was caught
  by Reviewer, is narrower than what was first shipped, and is documented in `percept.py`'s
  docstring — a correction, not scope creep.
- No invariants violated: Security's deep analysis traced `getLife()`/`getLife0()` end-to-end and
  confirmed no raw truth value (life fraction) crosses into `Contact`/`Percept`/`Observation` — only
  the already-collapsed `emitter_kind`/`is_burning`. The "did we get it?" non-closure
  (`plans/brain-layer/explore-notes.md` left untouched) is confirmed by diff.
- All new files staged: confirmed above.

## Testing

- Core logic covered: `test_emitters.py` (11, fraction-bracket boundaries, collisions, malformed
  entries), `test_visibility.py` (10, including the regression gate — 9 km burning admitted at
  `lowres`, same unit not burning rejected at `RANGE_OR_SIZE`), `test_contacts_burning.py` (7),
  `test_naked_eye_source.py` (5, end-to-end + the group-salience non-interaction pin).
- Tests are meaningful, not decorative: both required fixes from Reviewer's first pass were about
  exactly this — a vacuous truth-boundary guard and a group-salience test that passed under two
  different mutations of the actual regression it claimed to pin. Both were independently
  re-mutation-tested by Reviewer's own fix-pass and again by Security, at the real call site, not
  by re-reading the pasted red/green. I did not re-run the mutations myself a third time — three
  independent mutation-tested confirmations (Reviewer's fix-pass, Security's deep analysis, and the
  implementer's own) is sufficient; re-mutating a fourth time would be checking the account of the
  account.
- No existing tests broken: full suites green at the counts above, matching pre-fix counts plus
  exactly the new tests added.

## Documentation

- Reviewer findings addressed: both required fixes from the first pass (`820967b` NEEDS REVISION)
  confirmed closed in the fix-pass (`607ba78`) and re-verified independently by Reviewer's own
  second pass (APPROVED) and by Security.
- Non-obvious behavior explained: `percept.py`'s docstring now carries the closed-mapping pattern
  and why the free-form alternative was rejected — confirmed read directly, present and correct.
  `plans/forest-occlusion/plan.md` carries a numbered `Decision REVISED 2026-10-15` sub-decision
  (confirmed: `grep -n "REVISED" plans/forest-occlusion/plan.md` → line 9, numbered form as the
  plan's Risks section required, not an edit to the original sentence).

## Security

- `plans/emitter-visibility/security-plan-review.md` exists and is APPROVED (`7213a1a`, run
  retroactively this session — see "Gap found" above).
- `plans/emitter-visibility/security.md` exists and is APPROVED (deep analysis, `890387f`, all
  findings resolved — two Recommended/non-blocking items, both already folded in by `42ee83c`).

## Roadmap entries

- `body-layer/ROADMAP/BL-B72.md` and `aircraft-layer/ROADMAP/AC-B7.md`: both still `#status/open`,
  correctly — the dispatch's own framing is right. Neither closes with this merge: both entries'
  "one number worth measuring" (`bridge_call_ms`) and the burning-candidate-count-in-a-real-
  engagement question are unmeasured, and BL-B72's entry text itself still reads as the full
  three-emitter item with Stage A as "the first slice," not as fully delivered. Leaving both open
  with the live-sortie item named is correct; I have not marked either `[x]` — that happens after
  the acceptance sortie, per the Deferred-vs-waived distinction below.

## Acceptance boundary — what these fixtures structurally cannot reach

Every test above is a fixture: synthetic `UnitVelocitySample`s, synthetic candidate geometry, a
synthetic life fraction crossing `FIRE_LIFE_FRACTION_MAX`. None of them can tell us:

- **Whether `getLife()`/`getLife0()` behave the same way on a live DCS mission as they did in the
  one closed probe this plan leans on** (`docs/acceptance/2026-09-24-damage-and-firing-probes.md`,
  flown once, 2026-09-25, for a different purpose). The fire-fraction bracket `(0.69, 0.84]` is one
  measurement, not a distribution — a different unit type, a different damage model, or a unit that
  burns without ever being "doomed" in that same sense could all produce a reading no fixture
  anticipates.
- **The actual Lua-side cost** (`bridge_call_ms`), which both Performance's review and `AC-B7`'s own
  roadmap entry name as "the one number worth measuring" and which no fixture measures by
  construction — it is a cost on DCS's own thread, not body-layer's.
- **How many units are burning at once in a real engagement**, and whether the clustering/callout
  behavior that looks right for one or two burning units in a fixture still reads as sane prose when
  a strike leaves a dozen.
- **Whether the callout timing and wording feel right in the cockpit** — *"something burning, two
  o'clock"* is correct text; whether it arrives at a moment that helps rather than clutters is a
  judgment no fixture encodes.

A fixture PASS here is not a flight PASS. The worked example this role exists to repeat: fixtures
cannot see which subsystem is actually driving a behavior, or whether a human finds a line natural
to hear — only a sortie can.

## Acceptance Testing Plan: Emitter Visibility — Burning Units (Stage A)

**Goal:** verify that a burning unit becomes visible to Petrovich at ranges where it otherwise
would not be, through tree cover, while never being identified beyond presence — and measure the
two obligations the reviews left to this flight.

**Branch:** `feature/emitter-visibility`. Checkout: `git checkout feature/emitter-visibility` (your
root is currently on `main` @ `2d9f101` — this does not disturb any agent worktree, all of which
have been removed). **Restart the body-layer service between missions** — `BL-B68` (stale belief
surviving a mission restart) is a known, deferred defect; skipping the restart will contaminate
this sortie's read with the previous mission's contacts.

**Prerequisites**
- [ ] Type-checked and importable: confirmed above (`mypy --strict` on both touched subprojects,
  run this session, both clean).
- [ ] Both services running current code from this branch (body-layer + aircraft-layer's telemetry
  hook) — restart both, not just body-layer, since `AC-B7`'s Lua change is in the mission-telemetry
  hook.
- [ ] A mission with at least one ground unit you can damage into the fire band without destroying
  it outright (burns for a stretch before dying) at a range beyond ~2.3 km (naked-eye presence
  threshold for a 7 m vehicle) from your aircraft.

**Test Cases**
1. Damage a ground unit into its fire state at ~4-9 km, look at it with the naked eye — expect
   Petrovich to call *"something burning, [clock] o'clock"* where he would currently say nothing.
2. Same unit, same range, **before** it catches fire — expect no callout (confirms the bypass is
   conditioned on the emitter, not a general range change).
3. A burning unit **behind a ridge/terrain feature** (not tree cover) — expect no callout; terrain
   LOS must still block per the plan's unchanged gate 4.
4. A burning unit **inside/behind a treeline** at a range the forest gate would otherwise reject —
   expect the callout to fire; tree cover must not block an emitter.
5. Read the detection trace's `emitter_kind` column after the sortie for every admitted burning
   candidate — confirms the bypass path is actually what fired, not a coincidental in-range
   admission.

**Edge Cases to Probe**
- Multiple units burning at once (e.g. after a strike on a group) — does the callout/clustering
  read as sane, or does it clutter? This is the "no hard cap on simultaneous burning candidates"
  question Performance flagged as MONITOR.
- A unit that starts burning, is then fully destroyed — confirm no further callout and no lingering
  "still burning" chatter (the event is one-directional by design; confirm that holds in practice).

**Measurements to record, not just pass/fail**
1. **`bridge_call_ms`** from the mission-telemetry hook's log, before vs. during a scene with
   several burning/live units — Performance's and `AC-B7`'s named obligation. Reasoned-not-measured
   expectation is "roughly doubles the unit-branch per-object cost"; record the actual delta.
2. **The `emitter_kind` trace column's count** of burning-admitted candidates in a real engagement —
   there is no cap in code, only the bubble-filtered population bounds it.
3. **Opportunistic, free check**: if this sortie includes placed smoke (not from this feature —
   ordinary DCS static smoke), note the detection trace's `object_type` values for it. Answers
   `BL-B75`'s open question (does static smoke appear in `LoGetWorldObjects`) for free if it comes
   up; not worth engineering a scenario for.

**Pass Criteria**
All five test cases produce the expected result, no regression in ordinary (non-emitter) naked-eye
detection at the ranges already covered by existing tests, and the two measurements above are
recorded (even if the numbers turn out to need a follow-up tuning pass — recording them is the
acceptance bar, not hitting a specific value).

---

Does the feature pass acceptance testing? (yes / no + details)
