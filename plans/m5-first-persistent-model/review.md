### Review Summary

Stage 3 (`a448c67..HEAD`, commits `6fd853d`..`e9eede5`) delivers the elevation/surface_type
probe: parser extension, `ingest_probe`, pipeline wiring, three Lua probe rungs, and the live
DCS round-trip. Verified independently: `ruff format --check`, `ruff check`, `mypy --strict`
(src+tests), and `pytest` all pass (137 tests). Grid coverage was queried directly against the
real `data/world-model/latakia-20km.sqlite` — confirmed 1,681/1,681 populated cells for both
`elevation` and `surface_type`, and `elevation.stats["srtm"]` is genuinely `null` (not a
placeholder or fabricated value). Scope is correctly held to elevation+surface_type wiring —
no Stage 4 control-point/tolerance-band tests or formal spot-check tables were added; the
reported spot-checks are ad-hoc CLI runs in the research note, which is appropriate. The
incremental ladder (121 → 441 → 1,681) was genuinely followed, evidenced by three separate
commits and a research note that grew rung-by-rung with real numbers at each step, not
retrofitted. SRTM delta handling matches the plan exactly: metadata-only in `stats_json`, no
grid/grid_sample rows, and a real synthetic-tile test (`test_ingest_probe.py`) exercises the
code path — the honest gap is reported, not silently glossed over. `getSurfaceType`'s output was
sanity-checked (enum range, spatial plausibility, cross-subsystem RUNWAY/ROAD placement vs. the
Stage 1 airfield point) before being trusted at scale, as required. `describe_position` needed no
logic changes — confirmed correct, since Stage 1 already wired grid reads through
`store.reader.sample_grid`.

One required fix: the probe scripts do not follow the checklist's mandated
`timer.scheduleFunction` chunking / append-mode pattern, and the implementation log's Stage 3
section claims "append-mode `io.write`" for a script that in fact opens the file in `"w"`
mode once and writes the whole grid in a single blocking loop.

### Required Fixes

- **Probe scripts use a single blocking loop, not `timer.scheduleFunction` chunking, contradicting
  an explicit checklist instruction — and the implementation log misdescribes this as "append-mode
  `io.write`".** `checklist.md` Stage 3 (line 77) and `plan.md`'s Finding E are unambiguous:
  "`timer.scheduleFunction` chunking, append-mode `io.write`... never one giant loop holding
  results in memory." All three scripts (`terrain_probe_smoke.lua`, `terrain_probe_500.lua`,
  `terrain_probe_full.lua`) instead open the output file once with `io.open(..., "w")`, run a
  single `for _, p in ipairs(points) do ... end` loop over the entire rung (up to 1,681 points ×
  2 blocking `land.*` calls each), and close the file only after the whole loop finishes — this is
  exactly the "one giant loop" pattern Finding E says to avoid, and it is not append mode (it
  truncates and writes fresh each run, never resuming a partial write). `implementation.md`
  (line 529) asserts "`pcall`-wrapped calls, append-mode `io.write`, one JSON object per line" for
  this script, which does not match what the code does — the file is opened in `"w"` mode, and
  writes only "append" to that one open handle, not across scheduled ticks. The scripts do mirror
  M4's `elevation_probe.lua` structure, which is true and stated, but M4 ran only 100 points; the
  checklist raised the bar to explicit chunking specifically for Stage 3's larger workload
  (1,681 points × 2 calls), and that instruction was not followed and not flagged as a deliberate
  deviation anywhere in the decision log. In practice DCS did not hang on any of the three live
  runs (per the research note), so this did not cause a failure this time — but the risk the
  checklist was written to close (busy-wait-hangs-DCS on a long unscheduled loop) was not actually
  mitigated, and the report's description of the mitigation being in place is inaccurate. Fix:
  either rewrite the three scripts to use `timer.scheduleFunction` self-rescheduling chunking with
  true append-mode writes (`io.open(..., "a")`, opened/closed per chunk or kept open across scheduled
  calls), or explicitly document in `implementation.md` why the single-loop approach was judged
  safe for this workload and correct the "append-mode" claim to describe what the code actually
  does.

### Optional Refinements

- **The "three independent live runs returned bit-identical results" determinism claim is
  narrated only, not asserted by any test.** It's a genuine and useful finding recorded in the
  research note and agent memory, but nothing in `tests/` pins it — a small test that loads the
  smoke and full fixture subsets (or a literal shared point) and asserts equal `height_m`/
  `surface_type` would let this claim survive a future refactor rather than resting on a
  point-in-time manual comparison. Not a checklist requirement, so optional. (optional)
- **No wall-clock/cost numbers were recorded for any of the three Lua probe rungs**, unlike
  Stage 2's `.routes` walk which got an explicit timing measurement. The checklist's "stop and
  reassess if any rung shows non-linear cost" instruction has no data behind it in the research
  note beyond "it worked, no hang was observed" — worth a rough in-mission timestamp or DCS log
  timing next time a probe scales up, so the non-linear-cost check has something to compare
  against. (optional)

### Verdict

APPROVED WITH MINOR FIXES

---

## Stage 4 (validate correctness) + resync false-positive fix review

Reviewed `git diff 9b8a543..HEAD` (commits `fbb2c80`, `527a0e8`, `56ff90c`, `c237d26`): Stage 4
validation deliverable (`analyze_m5_stage4_validation.py`, one pinnable control-point test, the
dated research note) plus the same-day Debugger fix for the resync false-positive Finding 1
uncovered while running it. Independently re-ran `ruff format --check`, `ruff check`,
`mypy --strict` (src+tests), and `pytest` from `world-model/` — all pass, 142 tests, matching the
claimed counts exactly. `git status` is clean; all new files (including both agents' memory
writes) are committed — no repeat of the recurring unstaged-agent-memory gap noted in past
reviews.

### Stage 4 validation itself

All 8 checklist bullets are genuinely addressed, not skipped:
- Control-point test (`test_describe_position_control_point_latakia_arp`) is real, CI-pinnable,
  and non-circular — traced to `control_points.py`'s `real_lat`/`real_lon` (published SkyVector
  ARP) vs. `dcs_x`/`dcs_z` (live `coord.LOtoLL` probe), asserting a tolerance band
  (`residual_m <= expected_max_residual_m`), not an exact value. Verified by reading the fixture
  and the test directly.
- R\*Tree-vs-brute-force is correctly identified as already satisfied by Stage 1's
  `test_store_reader.py` rather than re-implemented — a reasonable scope call, not corner-cutting,
  since that test already proves the structural property independent of what data is loaded.
- The 8-point spot-check table genuinely exercises the outside-coverage-degrades-to-null case
  (two rows, both showing explicit nulls) and documents *why* the originally-planned `(0,0)` point
  was swapped for a far-southwest point — because `(0,0)` was contaminated by Finding 1, not
  because it was inconvenient.
- Airfield gap/bearing/axis-length checks land within noise of the plan's own hand-worked numbers
  (1504.28 m vs. ~1504 m predicted; 2635.04 m vs. ~2635 m; bearing agreement 0.0085° vs. ~1°
  expected) — confirmed against `ingest_beacons.py`'s actual `beacon_direction_deg` tag key, which
  matches what the analysis script reads.
- The cross-subsystem `getSurfaceType` ROAD/RUNWAY-vs-`.routes` check reports a real, plausible
  distribution (median 129 m, well under the 500 m grid spacing) rather than asserting an
  unjustified pass/fail threshold, per the plan's own instruction not to assume one before seeing
  the data.

**DCS-vs-OSM displacement (~5 m median vs. ~1.0-1.3 km predicted).** The explanation — M1's figure
is a single hand-placed point object's absolute placement error, while DCS and OSM road
centerlines are plausibly two independent digitizations of the same satellite/aerial reference
imagery and so should agree far more tightly — is sound reasoning, not a post-hoc rationalization.
It's checked, not just asserted: verified the underlying `distance_point_polyline` function is the
same one already exercised by Stage 1's R\*Tree agreement test (so no reason to distrust it here),
and the distribution is smooth (min 0.11 m, p90 47.0 m, max 171.5 m) rather than bimodal or
clustered at exactly 0, which would suggest a degenerate-input artifact. The "coverage-mismatch
sampling bug" claim is real and correctly scoped: read `ingest_roadnet.py` directly — DCS routes
are kept in full whenever *any* single point intersects the bbox (`clipped` flag), while
`analyze_m5_stage4_validation.py`'s `_osm_displacement_check` confirms `ingest_osm` only ingests
ways fully inside the bbox. The fix (restricting the sample to the 56,092 in-bbox DCS vertices) is
a like-for-like correction, not a number-massaging move — the note is explicit that the unfiltered
run's wider numbers (p90 13.6 km) were the artifact, not the corrected tight numbers. Items 7 and 8
are also explicitly noted as unaffected by the later resync fix, since both already excluded the
corrupted feature via the script's own `_is_subnormal_point` filter before the fix landed — checked
against the script and confirmed true.

### The resync false-positive fix

- **Root cause and fix are correctly implemented.** `_triple_plausible` in
  `world-model/src/roadnet/container.py` now rejects any coordinate component that is nonzero but
  has magnitude `< 1e-6` (`_is_denormalized_garbage`), applied to both the pre-filter and full
  N-point validation. Exact `0.0` is explicitly still accepted and pinned by
  `test_find_next_point_block_accepts_exact_zero_coordinates` — correctly guards against
  over-tightening (a real DCS coordinate, e.g. sea-level y, can legitimately be exactly zero).
- **No plausible false-negative risk.** DCS's real coordinate envelope here is metre-scale
  (`|x|,|z| < 1e6`, `y` in `[-2000, 6000]`); a genuine simulated-world coordinate landing at
  sub-micron nonzero magnitude is not physically meaningful for this data, and the `1e-6` threshold
  was independently validated against real files by the exploratory recon script before this fix
  (cited in both the fix's comment and the research note). No test or code path suggests this was
  guessed rather than measured.
- **Container-layer fix, correctly scoped as shared.** `find_next_point_block`/`_triple_plausible`
  live in `container.py` and are structurally shared by both `.routes` and `.rn4`, per the module
  docstring. However, checked `roadnet/rn4.py` directly: M5's `.rn4` parsing (`parse_header`,
  `read_string_table`, `iter_topology_rows`) never calls `find_next_point_block` at all — decoding
  `.rn4`'s geometry region is an explicit M5 non-goal (plan.md Decision 8), so there is no `.rn4`
  code path in this milestone that could exercise, or be silently broken by, this fix. The "shared"
  framing in the fix's docstring/commit message is accurate as a statement about the module's
  design (a future `.rn4` geometry walker inherits the fix automatically) but not about anything
  currently tested — worth being precise about so a future reader doesn't assume `.rn4` behavior
  was verified here. Not a defect; just a note for the log.
- **`describe_position(0,0)`'s new answer (3689.37 m to route `id=3716`) is genuinely re-verified,
  not just plausible-looking.** The correction section confirms this route is smooth,
  envelope-compliant, contains no denormalized values, and legitimately spans `x=-13305` to
  `x=194333` under the same "any point inside bbox keeps the whole route" rule already validated
  against a sibling route (`id=3717`) in the spot-check table's "outside coverage, far east" row.
  This is a real cross-check against an independently-validated pattern, not a coincidence taken at
  face value.

### Required Fixes

None.

### Optional Refinements

- **The regression test fixtures don't reflect the corrected 3-garbage-point finding.** Both new
  tests (`test_find_next_point_block_rejects_denormalized_garbage_false_positive` in
  `test_roadnet_container.py`, `test_iter_routes_skips_denormalized_garbage_false_positive_route`
  in `test_roadnet_routes.py`) use a 2-garbage-point fixture and were written in commit `527a0e8`,
  before `56ff90c`'s correction established the real feature `id=3711` had 3 garbage leading points,
  not 2 — the docstrings still say "the literal values decoded from the real corrupted DCS road
  feature," which slightly overstates fidelity to the now-corrected finding. Separately, in
  `test_roadnet_container.py`'s garbage fixture, the first garbage point's second literal value
  (`1.36211130863e-312`, the real feature's *z* per `ingest_roadnet.py`'s `geom_json = [(x, z)...]`
  encoding) is placed in the *y* slot of the reconstructed `(x, y, z)` triple rather than *z*
  (`z` is instead a fabricated `0.0`) — the second garbage point places its values correctly. This
  doesn't affect what the tests actually prove (the denormalized-magnitude filter is
  position-independent across x/y/z, and `y` isn't preserved in `geom_json` in the first place, so
  perfect byte-fidelity for `y` was never fully recoverable from the store alone), but it's a minor
  gap against the project's "hardcoded literals copied from the research note... with a provenance
  comment" fixture convention. Worth a follow-up tightening pass, not worth blocking on. (optional)

### Verdict on point 8 (residual false-positive risk across the ~14,833 remaining routes)

**Documentation is clear enough** — the debugger's own doubt ("~27 more false-positive matches
were likely removed by this fix beyond the one investigated, no systematic audit was done") is
stated explicitly in three places that will all surface to a future reader: `debug.md`'s
Verification section, the research note's Correction section ("Does this raise doubt about the
other ~14,860 routes' integrity? Yes, and it should be flagged rather than assumed away"), and
cross-linked from `implementation.md`'s Notable Discoveries. It is not buried or hedged away.

**Opinion: proceed, don't block Stage 5/6 on a systematic audit.** Three reasons. First, the fix
closes a *specific, confirmed* failure signature (denormalized-magnitude values) and the rebuilt
store is confirmed to contain zero such points anywhere in its road geometry — the fix isn't
speculative, it's verified end-to-end against the real file. Second, Stage 4's own independent
cross-subsystem check (item 7: median 129 m agreement between `getSurfaceType` ROAD/RUNWAY cells
and `.routes` centerlines, computed *after* this fix) is itself strong indirect evidence that the
remaining in-region road geometry is sound — a store still containing a meaningful fraction of
garbage/false-positive routes would not produce a tight, smooth agreement distribution against an
independently-probed DCS subsystem. Third, the specific failure mode this milestone's
`describe_position` is exposed to (a plausible-wrong answer instead of an explicit null) was the
thing actually tested for and fixed; a hypothetical remaining false positive with "normal"-magnitude
values would still produce *a* plausible-looking road distance somewhere in the store, which is a
real but bounded and already-flagged risk, not a new unknown. A full per-route smoothness/
plausibility audit is real, valuable future work — correctly identified as such — but it is
theatre-wide (14,833 routes) and out of proportion to what M5 needs from the roadnet layer (an
in-region `nearest_road` distance/orientation, not a routing-grade completeness guarantee). Flag it
into the M6 backlog rather than reopening Stage 2/4 now.

### Overall Verdict

APPROVED. No required fixes. One optional refinement (test fixture literal fidelity) left for a
future touch of `roadnet`.
