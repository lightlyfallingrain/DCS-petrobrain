### Debug Report

### Observed Issue
DCS road feature `id=3711` (`source_ref="route:3311@464953201"`) in the real built store
`world-model/data/world-model/latakia-20km.sqlite` had corrupted geometry: 64 points, the first 3
denormalized-float garbage (`[-5.607157514132566e-195, 1.36211130863e-312]`,
`[46368.0, 1.371949926365e-312]`, `[3.541463e-318, 0.0]`) followed by 61 points of exact
`(0.0, 0.0)` padding. Downstream, `describe_position(conn, "Syria", 0.0, 0.0)` resolved
`nearest_road` (DCS) to this feature at a misleading, exact `0.0 m` — a plausible-looking wrong
answer instead of an honest degrade, sourced entirely from garbage geometry. First found and
documented (not fixed) in `world-model/research/2026-09-04-m5-stage4-validation.md` Finding 1.

### Hypothesis
Stage 2's implementation notes already flagged an open, unproven risk: the `.routes` scan-forward
resync technique (`roadnet/container.py::find_next_point_block`, used by
`roadnet/routes.py::iter_routes`) could produce false-positive matches — garbage byte sequences
that happen to pass the mandatory first/middle/last pre-filter and full N-point envelope
validation by chance (`sync_loss_events`, ~2% of matched blocks in the whole-file walk). Feature
`id=3711` is a confirmed real instance. Root cause: `_triple_plausible` (the per-point envelope
check both the pre-filter and full validation call) checks `math.isfinite(x/y/z)` plus wide
magnitude bounds (`|x|,|z| < 1e6`, `-2000 < y < 6000`), but never rejects denormalized/subnormal
float64 values. A subnormal value like `1.36211130863e-312` is finite and numerically near zero,
so it trivially satisfies those bounds even though it is never a genuine DCS coordinate — it is
what you get from reinterpreting the bytes of something that isn't a float64 (e.g. mid-trailer
noise) as one. This exact filter was already validated during exploratory recon
(`world-model/research/2026-09-04-m5-roadnet-byte-decode.md` Session 2: "rejecting any value that
is nonzero but has magnitude `< 1e-6` ... without this filter the scan returns thousands of false
positives with y/z values like `1e-312`") but never made it from the throwaway recon script into
the production `_triple_plausible` validator — a real gap between what recon proved necessary and
what shipped.

### Evidence
- Read `feature.geom_json` for `id=3711` directly from the pre-fix store: confirmed the exact
  garbage/padding pattern described above (byte-for-byte match to the Stage 4 note's description,
  with one additional garbage point the original note undercounted — 3, not 2).
- Read `roadnet/container.py::_triple_plausible`: confirmed it checks `math.isfinite` and coarse
  magnitude bounds only, with no lower-bound/denormal check — the exact gap the recon note's
  Session 2 already flagged as necessary for a clean scan.
- Cross-referenced `roadnet/routes.py::_walk`: confirmed `find_next_point_block`'s validated
  candidate is trusted as-is (no independent geometry sanity check downstream), so a false
  positive that clears `_triple_plausible` is yielded as a real route unconditionally.

### Fix Applied
`world-model/src/roadnet/container.py`: added `_is_denormalized_garbage` (nonzero value with
magnitude `< 1e-6`, the same threshold the recon script already proved sufficient) and wired it
into `_triple_plausible`, so both the pre-filter and full-block validation reject it. Exact `0.0`
is still accepted (a genuine coordinate component, e.g. sea-level elevation, can legitimately be
zero) — only nonzero-but-implausibly-tiny values are rejected. This is a container-layer fix,
shared by `.routes` and `.rn4` (both use `find_next_point_block`), not a special case for feature
`id=3711` specifically — no code references that id.

Regression tests added (following the existing hardcoded-fixture pattern):
- `world-model/tests/test_roadnet_container.py::test_find_next_point_block_rejects_denormalized_garbage_false_positive`
  — a candidate block using the literal garbage values from `id=3711`, preceding a real valid
  block; asserts the scan rejects the garbage and recovers sync at the real block.
- `world-model/tests/test_roadnet_container.py::test_find_next_point_block_accepts_exact_zero_coordinates`
  — guards against over-tightening: exact `0.0` must still be accepted.
- `world-model/tests/test_roadnet_routes.py::test_iter_routes_skips_denormalized_garbage_false_positive_route`
  — the full corrupted-route shape (2 garbage leading points + 61 zero-padding points) injected
  between two real routes in a synthetic `.routes` file; asserts `iter_routes` yields only the two
  real routes, never a spurious third one.

### Verification
- `ruff format --check world-model/src world-model/tests`: pass.
- `ruff check world-model/src world-model/tests`: pass, 0 findings.
- `mypy --strict world-model/src world-model/tests`: pass (55 source files).
- `pytest world-model/tests -q`: pass, 142 passed (up from 139; 3 new regression tests, no
  existing test needed to change).
- Re-ran the full `.routes` walk and store rebuild
  (`tools/build_world_model.py latakia-20km --probe-output data/raw/dcs/2026-09-04/terrain_probe_output_full.jsonl`,
  same raw inputs as the original Stage 2/3/4 build):
  - `routes_found_whole_file`: 14,861 → **14,833** (-28)
  - `routes_in_region` (Latakia gate): 131 → **130** (-1, exactly the corrupted route)
  - `sync_loss_events`: 302 → **220** (-82)
  - `road` feature count: 3,267 (3,136 OSM + 131 DCS) → **3,266** (3,136 OSM + 130 DCS)
  - Feature `id=3711` / `route:3311@464953201`: confirmed absent from the rebuilt store.
  - Confirmed directly: zero road features in the rebuilt store contain any nonzero coordinate
    with magnitude `< 1e-6` anywhere in their geometry.
  - `describe_position(conn, "Syria", 0.0, 0.0)`'s `nearest_road` (DCS): **0.0 m → 3689.37 m**,
    sourced from feature `id=3716` (`route:6244@717667470`) — a real, smooth, envelope-compliant,
    non-garbage route that genuinely passes near the origin (it legitimately spans
    `x=-13305.06` to `x=194333.03`, the same "any point inside bbox keeps the whole route"
    pattern already validated as correct for a sibling route in the Stage 4 note's spot-check
    table). **Does not degrade to `null`** — confirmed this is correct, not a miss: `(0,0)` is
    genuinely near real DCS road coverage once the garbage feature is removed, so an honest
    non-null answer is the right behavior, not evidence the fix is incomplete.
  - Numbers *not* affected: Stage 4's cross-subsystem check (median 129.05 m) and DCS-vs-OSM
    displacement check (median 5.30 m) already excluded the corrupted feature via the analysis
    script's own filter before this fix, so they need no correction.
  - Residual risk flagged, not resolved by this fix: the whole-file route count dropped by 28,
    not just 1 — meaning 27 more false-positive resync matches existed outside the Latakia region
    under the pre-fix validator. This fix closes the specific denormalized-magnitude failure mode
    (confirmed: zero such points remain in the rebuilt store's road geometry) but does not prove
    every one of the remaining 14,833 whole-file / 130 in-region routes is sound against every
    other possible false-positive shape (e.g. a false match that happened to decode into small
    but *normal*-magnitude values would still slip through). Recommend a future milestone add a
    systematic per-route smoothness/plausibility audit over the full whole-theatre walk rather
    than relying on spot-checking, as this session (and Stage 4 before it) did.

Full before/after detail and the dated correction (added rather than silently editing the
original numbers, per project convention) are in
`world-model/research/2026-09-04-m5-stage4-validation.md`'s "Correction" section, cross-linked
from `plans/m5-first-persistent-model/implementation.md`'s Stage 4 Notable Discoveries.
