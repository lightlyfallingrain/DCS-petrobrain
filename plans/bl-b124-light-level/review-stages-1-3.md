### Review Summary

Reviewed BL-B124 Stages 1–3 on `feature/bl-b124-light-level`, range `7a1c70b3..47d12096` (fast-
forwarded into this worktree; no divergence, tree clean before and after).

**Scope matches the plan's 2026-11-25 amendment exactly.** Stage 1 (amended: mission date + wall
clock ride the firing-events Hook's existing 1 Hz poll, not a `.miz`/MI-3/MI-6 thread), Stage 2
(`perception/light_level.py`, pure astronomy + anchored light-factor curve) and Stage 3 (thread
`light_factor` through `tier_ranges()`/`check_visibility()`/`optic_policy.py`/`attack_run.py`,
default `(1.0, 1.0, 1.0)`) are what's built. Stage 4 (real wiring into `body.py`), Stage 5
(`LAUNCH_FLASH`) and Stage 6/`BL-B136` (`EXPLOSION`, deferred per U1) are correctly **not** in this
batch — matches `implementation.md`'s own stated scope.

**U1/U2 (plan's "Decisions requiring user input") are both accounted for** —
`.claude/scripts/accepted-items-ledger.sh plans/bl-b124-light-level` finds no `**U<n>`/`**Answered`
markers to check mechanically (this plan answers them inline in the 2026-11-25 amendment section,
not in a separate ledgerable block), so I read the decisions by hand: U1 (explosions) is filed as
`body-layer/ROADMAP/BL-B136.md`, present in this diff, with the outline carried over correctly; U2
(mission wall clock) is Stage 1 itself, amended and built. Nothing promised and dropped.

**Anchor derivation checked against source data, not against the author's own restated figures**
(per root `CLAUDE.md`'s instruction to check the arithmetic against the code's own constants, the
exact trap that produced the 4×-high BL-B124-unrelated `X-T26` defect). Recomputed every one of the
twelve `_MEASURED_FACTORS` entries by hand from `docs/concept/detection-in-non-perfect-conditions.md`'s
raw table and `optics.py`'s own `presence_range_mult`/`class_range_mult`/`type_range_mult` —
e.g. 9K113 narrow, −18 min: class `3.4 / (0.4 × 13.75) = 0.618`, matches the table's `0.618`
exactly; binocular +2 min: `0.8/0.4=2.0` and `0.25/0.2=1.25`, both correctly clamped to `1.0`. All
twelve entries check out; the −5.3°/−3.5°/+0.3° anchor conversion from the explore-notes' minutes-
from-sunrise table is internally consistent with the `sun_elevation_deg` formula (verified live
below). The two end-point tunables (`−12.0`/`+6.0`) are honestly labelled first-cut estimates with
`lo`/`hi` bounds chosen to keep a margin from the nearest fixed anchor on each side (`hi=-6.0` for
the dark end vs. anchor `-5.3`, `lo=1.0` for the daylight end vs. anchor `+0.3`) — this also closes
the cross-key-coupling question without needing an explicit coupling check, since `hi < lo` for the
two keys is structural (`-6.0 < 1.0`), not merely likely.

**Backward compatibility and fail-safety on the Hook wire change, verified by reading the Lua and
the schema together, not assumed from the docstring:** `mission_clock` rides as a new, optional
JSON envelope key (mirrors the LOS Hook's own `probes` key); an old collector ignores the unknown
key; a new collector against an old Hook sees the key simply absent (`mission_clock_raw=None` ->
`FiringEventBatch.mission_clock=None`). The `timer.getAbsTime()`/`env.mission.date` reads inside
`EVENT_POLL_CODE` are `pcall`-guarded independently of the event-queue drain, so a failed clock read
degrades to the `"unavailable"` sentinel (parses to `None`, not an error) without ever losing that
poll's firing events — confirmed in the Lua source, not just its comment. `MissionClockSample.from_wire`
correctly treats a malformed (but non-"unavailable") sub-wire as a drop-to-`None`, not a raise that
would fail the whole batch.

**Stage 3's one real correctness trap (gate 3 / `tier_ranges()` desync) is fixed, but has zero test
coverage.** See Required Fixes.

**The tuning-pattern rendered-file check (root `CLAUDE.md`'s explicit instruction to read the
rendered `defaults.toml`, not the `#:` comment) found a real defect**, the same shape the project
has now hit three times before. See Required Fixes.

All mechanical checks run and green: `ruff format --check`/`ruff check`/`mypy --strict` clean on
both `aircraft-layer` and `body-layer`; `aircraft-layer` full suite 1062 passed; `body-layer`
`-m "not slow"` 3741 passed, 27 deselected, 4 xfailed (matches implementation.md's reported full-
suite 3768 passed, 4 xfailed). `/invariant-check`'s greppable checks (no-omniscience boundary,
module independence, no stray `sys.path`, `BINOCULAR_RANGE_MULTIPLIER` retirement, no stray
`print()`/bare `except`) all pass. `luac5.1 -p` not re-run here (no `luac5.1` in this environment);
implementation.md reports it clean and the Lua diff read cleanly by hand.

### Required Fixes

- **The rendered `defaults.toml` drops the "dangerous direction" warning for both new tunables —
  exactly the trap root `CLAUDE.md` names by name ("a warning written as a second sentence reaches
  nobody").** `tools/generate_defaults.py`'s `_SENTENCE_SPLIT` emits only the first sentence of a
  `#:` block. For `SIGHT_FULL_DARK_SUN_ELEV_DEG`, the rendered line is "Below this sun elevation,
  every optic -- including the 9K113's orange filter -- sees nothing but light sources..." — the
  very next sentence ("A *smaller* (more negative) value here keeps the 9K113 usable deeper into
  the night than measured; a *larger* (less negative) value goes fully blind earlier... which is
  the dangerous direction for the no-omniscience goal this feature exists for") never reaches a
  pilot editing `config/tuning.toml`. Same gap for `EYE_FULL_DAYLIGHT_SUN_ELEV_DEG` — its own
  "dangerous direction: it under-dims a still-dim morning" sentence is dropped identically.
  `test_tuning_comment_renders.py`'s own cross-key check does not catch this (correctly — it is
  deliberately narrow to cross-key couplings, and neither sentence names a sibling tuning key), so
  this is a real gap that test cannot see by design. The existing convention elsewhere in this same
  file (`LOWRES_ANGULAR_RADIUS_RAD`/`MEDRES_ANGULAR_RADIUS_RAD`'s comments) already solves this by
  folding the dangerous-direction clause into the *first* sentence as one long sentence — rewrite
  both new `#:` blocks the same way, then regenerate `config/defaults.toml` and re-read the
  rendered output (not the diff) to confirm the warning actually survives.
- **`light_factor`'s one real correctness fix — scaling `check_visibility()`'s `size_curve_
  threshold_m` by `light_factor[0]` to stay in sync with `tier_ranges()`'s own presence threshold —
  has no test anywhere.** `grep -rn light_factor body-layer/tests/` outside `test_light_level.py`
  finds exactly one hit: the per-poll field-coverage bucket in `test_naked_eye_source.py`, which
  only confirms the field is declared, not that it is threaded correctly. `test_visibility.py` has
  no `check_visibility()`/`tier_ranges()` test that passes a non-default `light_factor` at all.
  Today this is cosmetic — the default is a no-op and every existing test exercises only that
  default — but it means the one correctness trap `implementation.md`'s own "Notable Discoveries"
  calls out as caught and closed is proven only by inspection, not by a test that would fail if a
  future edit (Stage 4, or anyone touching this code later) reintroduced the desync. Add at least
  one test in `test_visibility.py` that calls `check_visibility()` with a `light_factor` that
  shrinks presence (e.g. `(0.1, 1.0, 1.0)`) and asserts (a) a candidate inside the *unscaled*
  presence range but outside the *scaled* one is rejected at gate 3 (`RANGE_OR_SIZE`), proving gate
  3 actually reads the parameter, and (b) a candidate within the scaled range still resolves via
  `_achieved_tier` rather than falling through to the "beyond even lowres" fallback — the exact
  pairing the Notable Discoveries note describes as the risk.

### Optional Refinements

- `test_tier_ranges_presence_threshold_uses_the_optic_s_own_cap`-style direct tests of `tier_ranges()`
  itself with a non-default `light_factor` (no DCS/geometry scaffolding needed) would be a cheaper
  complement to the `check_visibility()` test above, and would isolate the pure-function behaviour
  from the gate-ordering behaviour. Optional because the `check_visibility()` test covers the
  correctness trap end to end; this would just make a future failure easier to localise.
- The module docstring's claim that `sun_elevation_deg` "reproduces the explore-notes' own UTC+3 for
  Syria's longitude exactly" via `round(lon_deg / 15.0)` is correct for this test mission's
  longitude (40.28° / 15 = 2.69 → round to 3) but is only ever exercised at one longitude by the
  test suite. Not a defect — the explore-notes only ever gave one data point to anchor against, and
  the module docstring itself is honest that this is "the same timezone convention... no political
  timezone is supplied" rather than a verified-for-every-theatre claim — but a future theatre with a
  longitude near a 7.5°-boundary (where `round` could tip either way) is worth a one-line note if
  this module is ever revisited for a non-Syria mission.

### Verdict
APPROVED WITH MINOR FIXES — both required fixes are narrow (a docstring restructure plus
regeneration, and one new test in an existing file) and neither changes scope, module boundaries,
or any behaviour Stage 4 will later wire in. Re-run this loop (Implementer → Reviewer) once they
land; no new Security/Performance pass is needed for either fix on its own, but they should still
ride along with whatever batch review covers Stage 4 per root `CLAUDE.md`'s batching rule.

### Review Confidence

Full read of `plan.md` (with its amendment), `explore-notes.md`, `alignment.md`, `implementation.md`,
every changed file in `git show` for both commits (`f93ae567`, `5fdb9b5c`), the full text of
`perception/light_level.py`, `perception/visibility.py`, `perception/optics.py`,
`petrobrain-firing-events-hook.lua`, `schema/firing.py`, and the anchor source
`docs/concept/detection-in-non-perfect-conditions.md`. Hand-recomputed all twelve `_MEASURED_FACTORS`
entries against the source doc and `optics.py`'s multipliers rather than trusting the module
docstring's restated numbers. Ran the full checks myself (not just re-reading implementation.md's
claims): `ruff format --check`/`ruff check`/`mypy --strict` on both subprojects, `aircraft-layer`'s
full test suite, `body-layer`'s `-m "not slow"` suite, and the invariant-check script. Did not
re-run `luac5.1 -p` (not installed in this environment) or fly the live dawn-pass test card —
neither is this role's job (the plan's own "no visual smoke test" posture; a live sortie is DoD's/
the user's acceptance step). `optic_policy.py`'s and `attack_run.py`'s full diffs were read in full,
not sampled, since mechanical parameter-threading is exactly the kind of change where a skim misses
one dropped call site.

### Fix round (commit `0ba18855`)

Re-reviewed `0ba18855` ("BL-B124 Stages 1-3: apply review required fixes") on
`feature/bl-b124-light-level`, fast-forwarded cleanly into this worktree (`HEAD` was a strict
ancestor, tree clean before and after).

**Required Fix 1 (rendered-`defaults.toml` warning).** Read the *rendered* file, not the diff:
both `#:` blocks were restructured into one long first sentence, the same pattern
`LOWRES_ANGULAR_RADIUS_RAD`/`MEDRES_ANGULAR_RADIUS_RAD` already use. Confirmed in
`body-layer/config/defaults.toml` lines 610-621 — `EYE_FULL_DAYLIGHT_SUN_ELEV_DEG`'s comment now
reads through to "...which is the dangerous direction since it under-dims a still-dim morning..."
and `SIGHT_FULL_DARK_SUN_ELEV_DEG`'s reads through to "...which is the dangerous direction for the
no-omniscience goal this feature exists for..." — both warnings survive generation. **Fixed.**

**Required Fix 2 (no test for the gate-3/`tier_ranges()` desync).** `test_visibility.py` gained
three new tests (`test_light_factor_shrinks_presence_range_and_gate_three_tracks_it`,
`test_light_factor_candidate_within_scaled_range_still_resolves_a_tier`,
`test_tier_ranges_light_factor_scales_the_presence_threshold`) — the first two are exactly the
pairing the required fix asked for (a scaled-out candidate rejected at gate 3, a scaled-in
candidate still resolving a real tier), the third is the optional direct-`tier_ranges()` pin,
built anyway. **Verified by mutation, not by reading**: removed the `* light_factor[0]` term from
`check_visibility`'s `size_curve_threshold_m` in `src/perception/visibility.py` and re-ran —
`test_light_factor_shrinks_presence_range_and_gate_three_tracks_it` failed exactly as expected
(the previously-rejected 300 m candidate now resolves to `tier='lowres'`), the other two still
passed (they only exercise `tier_ranges()` directly, so a `check_visibility`-only regression is
invisible to them — correctly scoped, not a gap). Reverted the mutation; tree confirmed clean
afterward. **Fixed, and the fix is load-bearing, not decorative.**

**Checks re-run on `0ba18855`** (body-layer, via the main checkout's `.venv` since this worktree
has none): `ruff format --check`/`ruff check`/`mypy src` all clean;
`.claude/scripts/fast-tests.sh body-layer` — smoke clean, 58 targeted files selected (parallel),
2381 passed, 4 xfailed, no failures.

### Verdict (fix round)
APPROVED — both required fixes landed as asked, the second is confirmed load-bearing by mutation
rather than taken on inspection, and all mechanical checks are green on the exact commit. No new
Required or Optional findings. Ready to proceed per the original verdict's note: ride along with
whatever batch review covers Stage 4 for Security/Performance, no new review needed for these two
fixes alone.

### Review Confidence (fix round)
Full read of both changed hunks in `0ba18855` (the two `#:` comment blocks and the three new
tests), the rendered `defaults.toml` output (not the diff), and a mutation test against the
gate-3 scaling term to confirm the new coverage is real.
