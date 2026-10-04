### Review Summary

Reviewed `fix/landform-relief-gate` (tip `e970dce`, verified via `git rev-parse HEAD` before
starting) against `plans/landform-relief-gate/implementation.md` and the two named defects (no
relief gate; ~16x-over-dense stored geometry).

Verified independently rather than trusting the implementer's account:

- **Gate placement**: `filter_by_relief` runs in `_process_tile` (`world-model/src/build/ingest_terrain.py`)
  before `to_stored_features`, so gated components never reach the cache or store — confirmed by
  reading the call site directly, not just the file list.
- **Threshold (50.0 m)**: matches the stated derivation (floor of the user's 50-150 m
  "maskable-behind" band; picking the band's middle would discard the near-target 50-100 m regime
  the explore-notes call tactically important). Reasoning holds up against
  `plans/terrain-feature-probing/explore-notes.md`.
- **Decimation rewrite**: `_decimate_for_storage` in `world-model/src/terrain/features.py` checks
  every original point against the *whole* decimated polyline (`distance_point_polyline`, which
  scans every segment — confirmed by reading `geometry.py`), not a windowed per-segment slice.
  I independently reconstructed the old windowed approach and ran it against the committed
  regression fixture (`N35E035.hgt` ridge fragment in
  `test_decimate_for_storage_checks_the_whole_decimated_line_not_one_segment`): the windowed
  reconstruction measured ~139.7 m max deviation (within the claimed 70-155 m range) against a
  true whole-polyline deviation of ~15.9 m (within the claimed 15-30 m range) on the exact same
  points. The regression test is real, not vacuous — it discriminates between the broken and fixed
  implementations on real data.
  - Note: the *direction* of the bug is that the windowed check **overstated** deviation (it was
    overly conservative, causing most decimations to fall back to full density) — matching
    "safe but neutered the fix" and the implementer's own agent-memory file, which correctly says
    "overly conservative." `world-model/ROADMAP.md`'s new entry, however, describes this as the
    windowed check having "understated real deviation by up to 5x," which is backwards given the
    same numbers it cites. Cosmetic only (code and tests are correct either way) — see Optional
    Refinements.
- **Cache invalidation**: constructed the stale-cache case myself (not by reading the tests) —
  a `meta` table missing the two new keys (simulating a v1-era cache) makes
  `terrain_cache.reader.load_cache_meta` return `None`, forcing a full rebuild; a cache with the
  keys present but a different `min_relief_m` value fails `cache_meta_matches`. Both paths work as
  claimed.
- **`inspect_terrain.py` rewrite**: confirmed by diff — the old tool drew `comp.points` (the raw
  traced skeleton, no smoothing or decimation at all); the new tool runs `filter_by_relief` +
  `to_stored_features` and draws `feature.geometry`, i.e. exactly what a real build stores. This
  means **every terrain render this project has judged landforms by before this branch was showing
  something other than what gets stored** — the acceptance renders on this branch are the first
  ones that are trustworthy in that sense.
- **Acceptance renders**: viewed all three directly.
  - `baalbek-relief-gate.png` — the Bekaa floor (the large flat basin) is visibly clean of
    ridge/valley lines; every line sits on the bordering slopes. Confirmed by eye.
  - `palmyra-relief-gate.png` — a long, continuous ridge chain (~6+ km) crosses flat desert in the
    lower-right of the frame and survives. Confirmed by eye.
  - `coastal-hills-relief-gate.png` — consistent with a gated, decimated render; no red flags.
- **Checks** (from inside `world-model/`, fresh venv built from `pyproject.toml`):
  `ruff format --check src tests` pass, `ruff check src tests` pass, `mypy --strict src` pass (71
  files), `pytest tests -q` → 539 passed, 3 skipped — matches the claimed numbers exactly.
- **Seven existing `test_ingest_terrain.py` tests gained `min_relief_m=0.0`**: legitimate. Each of
  those tests exercises something else (cache hits, streaming, cache-invalidation-on-other-knobs);
  the shared `_write_tile` fixture traces a ridge that is flat along its own length by construction,
  so at the production default it is correctly gated to zero and would otherwise break unrelated
  tests. Two *new* dedicated tests exercise the gate itself at the default threshold
  (`test_ingest_terrain_default_relief_gate_drops_a_flat_along_crest_ridge`) and its cache-invalidation
  behavior (`test_ingest_terrain_relief_gate_change_invalidates_the_whole_cache`), so the gate is not
  left unexercised by this change — it is isolated out of tests that aren't about it and tested
  directly where it matters.
- **`world-model/data/renders/*.png` committed**: checked against `.gitignore` — only
  `data/raw/`, `data/processed/`, `data/world-model/`, `data/world-model-backups/` are ignored;
  `data/renders/` is not, consistent with this project's existing convention for acceptance
  renders. No invariant violation.
- **Measured figures**: did not re-run the full-theatre query (no access to the 8.1 GB store in
  this worktree and the project rule against running full builds), but independently reproduced
  the core claim driving the fix — the decimation deviation bound and the magnitude of the old
  bug — directly against the committed regression fixture, which is real `syria-full` SRTM-derived
  data. The 36.7x/32.3m/8.1GB→2.4-2.5GB figures are internally consistent with the measured
  36.5x/45m-cap sample reduction and the real `latakia-20km` rebuild numbers reported in the
  implementation doc; I take these as implementer-reported (not independently re-derived at
  theatre scale) rather than reviewer-verified.

### Required Fixes

None.

### Optional Refinements

- `world-model/ROADMAP.md`'s new entry says the windowed deviation-check bug "understated real
  deviation by up to 5x" — backwards given its own cited numbers (windowed check measured
  70-155 m, true value 15-30 m: the windowed check *overstated* deviation, consistent with "safe
  but neutered the fix" in the same paragraph and with the implementer's own agent-memory file,
  which correctly calls it "overly conservative"). Purely a wording fix in prose; no code or test
  is affected. (optional)
- `tools/inspect_terrain.py`'s `pre_decimation_point_count` hardcodes a `* 16` multiplier
  (four Chaikin passes doubling each time) rather than deriving it from `DEFAULT_CHAIKIN_ITERATIONS`
  or an iterations argument. Harmless today since the tool has no `--chaikin-iterations` flag and
  the pipeline's iteration count is fixed, but it would silently mis-report the ratio if that ever
  became configurable. (optional)

### Verdict

APPROVED

### Review Confidence

Full read of the code diff (`terrain/features.py`, `build/ingest_terrain.py`, `terrain_cache/{models,schema,reader}.py`, `tools/inspect_terrain.py`, both test files). Cache invalidation and the
decimation-regression claim were independently reproduced, not just read. Format/lint/type/test
commands run fresh in a venv built from `pyproject.toml`, matching the claimed 539/3 results.
Theatre-scale figures (8.1 GB store, 234,799 feature count, final ~2.4-2.5 GB extrapolation) are
implementer-reported and were not independently re-derived here — no access to that store in this
worktree and re-running a full-theatre build is explicitly out of scope per the project's
execution-boundary rule. This is a bounded trust gap on numbers that do not change the verdict:
the underlying mechanism (gate placement, decimation correctness, cache invalidation) was verified
directly.
