# WM-W12 — OSM ingest optimization + landcover split

- [x] **OSM ingest optimization + landcover split (no M-number — an optimization and data-model
  change on WM-M9, not a milestone; done 2026-09-16, merged 2026-09-16, merge `b9d7c17`, branch
  `feature/osm-landcover-optimization`).** #status/done
  Two changes in one branch: a tags pre-filter step that shrinks the `.osm.pbf` before parsing
  (RUN.md §2.4), and a rework of what OSM contributes — `road` dropped from OSM entirely (DCS
  `.routes` is authoritative, per root CLAUDE.md), `landcover` and `coastline` added as new kinds,
  multipolygon relations gain hole support, and every stored ring/line is simplified at
  `SIMPLIFY_TOLERANCE_M = 30.0` with a `MIN_AREA_M2 = 50_000.0` per-ring floor. New query surface:
  `describe_position`'s `nearest_coastline` (with a `side` of `"sea"`/`"land"`) and
  `inside_landcover`; body-layer turns both into crew-facing semantic facts. New `src/geometry/`
  package holds the ring/polyline primitives.

  Real `syria-full` build (run by the user on Windows against this branch state, 2026-09-15/16,
  ~60 min wall-clock): `landcover=44811` (`fields` 21428, `forest` 9710, `orchard` 7171,
  `scrub` 4027, `barren` 2475), `coastline=1269`, `water=5119`, `settlement=26182`,
  `named_place=23044` (21,862 OSM + 1,182 DCS `towns.lua` — both kinds share `named_place`),
  `road=14833` (DCS-only, unchanged from WM-M7). Simplification: 8,343,864 → 2,010,767 vertices
  (24.1% kept) across 12,450 multipolygon relations, `relations_skipped=0`,
  `ways_skipped_unresolved_nodes=0`. Drops are all counted, per the module's "never a silent
  drop" convention: `rings_dropped_min_area=183492`, `holes_kept=4575` vs
  `holes_dropped_below_min_area=36974`, `lines_skipped_unclassified=291933`,
  `areas_skipped_unclassified=3708`, `unnamed_peaks_dropped=9867`, `unnamed_dams_dropped=689`.

  **`holes_dropped_not_contained_after_simplify=58`** is the number that mattered: the reviewer
  found (and a re-review corrected) that independently simplifying an outer ring and its holes can
  strand a hole partly outside its own outer ring, which `store/reader.py`'s `_distance_to_feature`
  would turn into a fabricated `nearest_feature` distance because it tests holes before the outer
  ring. The small-extract validation never exercised it; the full theatre hit it 58 times. Class of
  bug worth remembering: individually-valid transforms composing into an invalid structure — see
  NOTES.md.

  **Cache-invalidation defect found while reviewing that build's log and fixed here.** The hole fix
  (`638239a`) changed both `_ingest_ring`'s geometry output and `OsmIngestStats`' fields — two of
  the conditions the comment above `CLASSIFIER_VERSION` says must force a bump — but left the
  version at 3, the same value the pre-fix code used. A pre-fix cache would therefore have matched
  the invalidation key and been served as a hit, silently reinstating the invalid hole geometry the
  fix removed. (That one transition happens to raise `TypeError` in `load_cached_stats` instead,
  because the fix also *removed* a stats field — an accident of that change, not the invalidation
  working; any future `_ingest_ring` geometry change that left stats fields alone would have been
  served silently.) Bumped to `CLASSIFIER_VERSION = 4` with the rationale recorded inline. The
  user's own build is unaffected — its cache was written by post-fix code.

  Validation: Stage 6 small-extract control points (Hmeimim relation-derived settlement, sea/land
  sides west and east of Latakia, Lake Assad reservoir at distance 0) all pass; `latakia-20km`
  parse+ingest 9.15s cold / 0.07s cached; `describe_position` p99 34 ms at Lake Assad scale.
  474 world-model + 506 body-layer + 109 aircraft-layer tests pass.

  **Follow-ups, updated 2026-09-16 after a second `syria-full` build (Mac, cold cache, full
  log at `world-model/syria-full-build.log`):**

  - *OSM parse time* — **answered: 87.2 s**, against a plan estimate of ~2 min. That build genuinely
    parsed (no cache-hit line; it then wrote a 119 MB `syria-full-osm-cache.sqlite`), unlike the
    2026-09-15 Windows run whose 21.3 s Stage 3 was a warm-cache read of 99,243 rows.
  - *Peak RSS* — still unmeasured; nothing in the pipeline logs it. The plan's ~1–1.5 GB estimate
    stands unverified.
  - *Largest post-simplification polygon (the tiling gate)* — **answered, and it corrects an earlier
    claim**: Atatürk Baraj Gölü at 13,097 outer + 127 hole = 13,224 vertices, 3.9x the Lake Assad
    figure Stage 6's extract-scale validation had named. Still under the "tens of thousands"
    threshold, so no tiling — but at ~1.5x margin, not ~6x. See `world-model/CLAUDE.md`'s corrected
    paragraph.
  - *`describe_position` p99 at full-theatre scale* — **answered** (user-run
    `tools/measure_m7_stage4_perf.py latency --region syria-full`, 348 points: 8 control + 300
    random + 40 boundary): mean 53.4 ms, median 24.5 ms, p95 211.6 ms, **p99 440.7 ms**, max
    551.3 ms. Every quantile is roughly half WM-M7's recorded baseline (mean 136.8 / median 52.4 /
    p95 497.7 / p99 803.4 ms), which also retires WM-M7's own open flag that its p99 tail ran "~3x
    WM-M5's baseline".

    **The apparent halving against WM-M7 is not a code effect — do not cite it as one.** Resolved
    2026-09-16 by measuring the *same* milestone's store on both hosts:

    | | Mac | Windows (WSL, store on `/mnt/d`) | ratio |
    |---|---|---|---|
    | mean | 53.4 ms | 339.3 ms | 6.4x |
    | median | 24.5 ms | 151.0 ms | 6.2x |
    | p95 | 211.6 ms | 1101.4 ms | 5.2x |
    | p99 | 440.7 ms | 1929.2 ms | 4.4x |
    | min | 0.31 ms | 27.7 ms | 89x |

    Same store content, same code, ~4.4x apart at p99. **Host variance is several times larger
    than any delta this milestone could plausibly have caused**, and WM-M7's 803 ms baseline has no
    recorded host and falls *between* the two — so it cannot support a claim in either
    direction. Any future `describe_position` latency comparison must name its host and,
    ideally, re-measure the baseline store on that same host; a bare number is not evidence.

    The `min` row is the diagnostic one. A best-case query does almost no work, so an 89x gap at
    the floor is near-constant per-query overhead rather than compute — **and the cause is
    storage hardware: the Windows `D:` holding that store is a large mechanical HDD, while every
    other drive on that box is SSD** (user, 2026-09-16). A `describe_position` call needs a
    handful of random R*Tree and row reads; at ~8-12 ms of seek each, two or three of them land
    squarely on the observed 27.7 ms floor. An earlier note here blamed WSL's `drvfs` boundary
    instead — plausible, but it does not explain a floor that high, and the simpler hardware
    explanation fits the measurement much better.

    **Not being investigated further** (user direction 2026-09-16): which box runs which service
    is a placement decision, not a code problem, and the user manages it directly. Recorded only
    so nobody re-derives it from the numbers later, or reads the Windows column as a world-model
    regression.

    **This is a placement input, not just dev-box trivia.** Body-layer imports world-model
    in-process, and body-layer's host is *not* pinned — only aircraft-layer (Windows) and local
    LLM inference (Mac) are. So whichever box runs body-layer is the box that runs every
    `describe_position` call. Run body on the Mac and the budget is 440.7 ms p99; run it on the
    Windows box with the store on `D:` and it is 1929 ms, a 4.4x runtime cost decided entirely
    by where a file sits. If body-layer ever moves to Windows, put `syria-full.sqlite` on one of
    that box's SSDs first — it is a file copy, not an engineering task.
  - *§2.4 pre-filter node/way counts* — still open, upstream of the build log.

  **Cross-platform determinism confirmed** as a side effect: every OSM statistic from the Mac build
  is byte-identical to the Windows one — same 44,811 landcover, same
  `holes_dropped_not_contained_after_simplify=58`, same 8,343,864 → 2,010,767 vertices — from a
  fresh parse on a different OS. Same for the SRTM stats (47,484 void, `tiles_used=79`). Nothing
  in the ingest path is platform- or iteration-order-dependent.

  Next-milestone impact: none — all changes are additive except the `road`-from-OSM removal, which
  restores the DCS-authoritative invariant rather than breaking a consumer (mission-interpreter
  reads only `nearest_settlement.name`, untyped). Unblocks two previously-blocked follow-ups:
  landcover-aware detectability in body-layer perception, and a Mission Interpreter place-name
  fallback to `named_places_within_radius`. See `plans/osm-landcover-optimization/plan.md`,
  `.../review.md` (APPROVED), `.../dod-check.md` (PASS), `.../implementation.md`, and
  `research/2026-09-13-osm-landcover-optimization-validation.md`.
