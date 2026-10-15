### Review Summary

Reviewed `BL-B64` Stage 1 (two sight `Optic` rows + field of regard), Stage 1b (`BL-B55`
per-optic position sigma), the §15a desired/actual aim split, and the §14
`UNAIDED_OPTIC` FOV change, on `feature/9k113-sight` at `4ba4d2f9e580cdae19641fe025925fd6c36c504c`
(single commit). Scope matches the task brief exactly: no selection, no cone, no
optic-aware range cap, no `optic_policy` resting-phase change, no slew controller.

**Address verification.** HEAD was already the named tip sha in a fresh worktree created
from `origin/HEAD` at `git worktree add`, tree clean, no merge needed. All four input
documents present and read in full. `body-layer/.venv` rebuilt with the pinned versions
(`ruff==0.16.6`, `mypy==2.3.1`, `pytest==9.1.1`, `numpy==2.4.6`, `pyproj==3.8.0`) via
`python3 -m venv .venv && .venv/bin/pip install -q ruff==... mypy==... pytest==... numpy==... pyproj==...`
inside `body-layer/` — no editable install needed since mypy/pytest resolve `src`/`tests`
and world-model's `src` via `pyproject.toml`'s `mypy_path`/`pythonpath`.

**Verification — matches every claimed number exactly.**
- `ruff format --check .`: fails only on pre-existing out-of-scope `research/2026-10-05-security-audit.md`.
- `ruff check .`: all checks passed.
- `mypy src`: success, 0 errors, 59 source files.
- `pytest -q`: **1883 passed, 4 xfailed** (baseline 1870/4, net +13), matching the
  implementer's own count exactly.

**Sourced numbers verified against the source, not the implementer's arithmetic.**
`research/2026-09-20-9k113-sight-optics-from-manual.md` confirms the FOV half-angles
(5.75°/3.00°, half of sourced 11.5°/6.0° full angles) and the field of regard
(±60° azimuth, +20°/−15° elevation, sourced from the English Mi-24P manual §3.4).
`research/2026-09-21-aspect-magnification-and-distinctiveness.md` and
`2026-09-21-slice2-model-decisions.md` confirm the multipliers (wide 3.55/7.00/6.50,
narrow 5.81/13.75/15.00) exactly. `NAKED_EYE_RANGE_CAP_M`'s corrected docstring figure
(2333 m) checks out arithmetically against the current `LOWRES_ANGULAR_RADIUS_RAD = 0.003`
(7/0.003 = 2333.3). The §14 "~102° true separation" claim for the flipped test was
recomputed independently via the spherical law of cosines and matches (≈101.9°).

**Mutation testing, not just reading, on the two highest-risk claims:**
1. *"The carry-forward falls out for free / nothing is dropped."* Temporarily removed
   both `actual_aim_*` carry-forward kwargs from `decide()`'s two fresh-`OpticState(...)`
   branches (`SEARCHING`, `GLASSING`) — both of `TestOpticStateActualAimCarriesForward`'s
   tests failed immediately with the exact defect the implementer's memory note
   describes. Restored; tree clean. Confirmed by `grep` that these are the *only* two
   fresh `OpticState(...)` construction sites in `src/` — the implementer's "check there
   is not a third" claim holds.
2. *"UNAIDED_OPTIC/BINOCULAR_OPTIC sigma is unaffected."* `test_binocular_optic_gets_the_same_sigma_as_the_naked_eye`
   and the two per-optic dicts (`_RANGE_SIGMA_SCALE_BY_OPTIC`, `_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC`)
   default any unlisted `optic.name` to `1.0` via `dict.get` — read, not just trusted,
   and the test asserts exact equality against the pre-change formula.
3. Staleness test (`test_tuning_defaults_toml.py::test_defaults_toml_matches_the_generator`)
   verified to actually fail: hand-edited one rendered value in `config/defaults.toml`
   without regenerating — test failed with the expected "stale, run with --write" message.
   Restored; tree clean.

**The group-ranged-once rule (§11/§14) is architecturally guaranteed, not incidental.**
`_build_observation` is called exactly once per `Cluster` from `_build_observations`'s
single `for cluster in clusters` loop, and `Observation` itself carries one
`estimated_bearing_deg`/`estimated_range_m` pair for the whole cluster — there is no
per-member position field anywhere in the data model that a future refactor could
redirect to a per-member draw without a visible type change. So this is stronger than
the implementer's "falls out for free, because the call site runs once" — it falls out
from the `Observation` type itself having no per-member slot, which is harder to break
silently than a call-count coincidence. No dedicated new test names this property
directly, but it is load-bearing enough (and structurally protected enough) not to need
one; noted as a minor optional refinement below.

**§15a's determinism property survives.** `gaze_at(t_sim, plan)`'s signature and body
are unchanged — it remains a pure function of its two arguments. The actual/desired
split lives entirely in `OpticState` (frozen, replaced not mutated) and the one
conversion point `logger._apply_active_gaze`, exactly as planned. `dt_s` is computed
from `self.last_t_sim` *before* it is overwritten later in `run_once` (line ordering
checked directly) — correct poll-to-poll delta, 0.0 on the first poll. The `Gaze`/`ScanPlan`
is built from `actual_azimuth_deg`/`actual_elevation_deg`, never from `decision`'s desired
values directly. For `UNAIDED_OPTIC`/`BINOCULAR_OPTIC`, `advance_sight_aim`'s pass-through
body (`return desired`) is correctly documented as *permanently* correct, not a
placeholder — nothing in the call site singles out optics for different treatment, which
is exactly what "must never be imposed on them" requires (there is no optic-conditional
branch to later misapply a rate limit through).

**§14's one real behaviour change is correctly handled.** The reverted test
(`test_the_unaided_eye_ignores_the_boresight_entirely`) asserted the old `None`-means-
unconditional-pass behaviour; it was moved (not silently edited) to
`test_unaided_optic_field_of_view_now_rejects_past_90_degrees_true_separation`, now
asserting the opposite, with the boundary case and its companion both present. The claim
that no other test in the pre-existing suite exercises geometry near the 90° true-
separation boundary was spot-checked by grepping for azimuth/elevation values near 90
across all test files; the one hit (`test_cockpit_mask.py:59`, azimuth=90°) exercises
`cockpit_mask.is_visible`, an unrelated gate that runs earlier in the pipeline and does
not call `within_optic_fov` — consistent with the claim.

**Tuning pattern (role file's new section).** Both new constants
(`SIGHT_WIDE_RANGE_SIGMA_SCALE` 0.5, `SIGHT_NARROW_RANGE_SIGMA_SCALE` 0.3) go through
`tuning.real(...)` with `lo=0.05, hi=1.0`, `status="judgement"`, and a `#:` doc comment.
`config/defaults.toml` was regenerated and the *rendered* entries read directly (not the
source comment): both render as a single clean first-sentence description, correct
status/range line, correct default value — no truncation, no corrupted markup, no second-
sentence warning lost in rendering. The `hi=1.0` bound is itself doing useful work here:
it caps the sight's down-range coefficient at the naked eye's own 0.17, so no retune can
make the sight's modelled down-range precision worse than the unaided eye's, without
anyone having to assert that separately.

**Cross-key coupling, checked rather than assumed.** `SIGHT_WIDE_RANGE_SIGMA_SCALE` and
`SIGHT_NARROW_RANGE_SIGMA_SCALE` have an implicit ordering requirement (narrow should stay
≤ wide) that nothing enforces at import — they are not in `tuning.py`'s `_COUPLED_KEYS`
mechanism. However `test_sight_optics_get_a_smaller_down_range_sigma_than_the_naked_eye`
reads the *live* module-level constants (populated from `defaults.toml` at import) and
asserts `down_narrow < down_wide < down_eye`, so a future retune that inverted the
ordering would fail this test before merge — not an import-time crash, but not silent
either. Flagged as optional below because the existing mechanism (`_COUPLED_KEYS`) is
reserved for a documented, more severe coupling (scan/decay) and extending it here would
be disproportionate to a judgement constant meant to be hand-tuned from flying.

### Required Fixes

None.

### Optional Refinements

- **Group-ranged-once could carry one line of its own test**, naming the invariant
  directly ("`_build_observation` is called once per cluster, and `Observation` has no
  per-member position field") rather than relying on it being implied by the existing
  one-observation-per-cluster architecture. Low priority: the property is currently
  protected by the type shape itself, not merely by a call count, so the risk this
  guards against is smaller than it looks (optional).
- **The narrow-≤-wide down-range ordering** between `SIGHT_WIDE_RANGE_SIGMA_SCALE` and
  `SIGHT_NARROW_RANGE_SIGMA_SCALE` is currently defended only by a unit test reading live
  constants, not by any runtime or import-time check. Given both are hand-tunable
  judgement constants meant to move from flying, this is acceptable as-is; a one-line
  comment on each constant noting the sibling it must stay below would make the
  relationship discoverable to whoever retunes it later without having to find the test
  (optional).

### Verdict
APPROVED

### Review Confidence
Full read — plan, direction document, implementation summary, and every file in the
diff read in full; the three highest-risk claims (carry-forward correctness, sigma
no-change, group-ranged-once) verified by mutation or structural inspection rather than
by trusting the implementer's account; all claimed numbers (sourced figures, test counts,
docstring arithmetic) independently recomputed or grepped against source, not accepted on
the author's word.
