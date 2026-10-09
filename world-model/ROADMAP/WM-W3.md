# WM-W3 — `fix/landform-relief-gate` — relief gate and storage decimation

- [x] **`fix/landform-relief-gate` — cleared by the user's 2026-10-04 23:59 `syria-full` rebuild
  (verified 2026-10-05).** #status/done All three blocks of
  `docs/acceptance/2026-10-04-landform-relief-gate-rebuild.md` pass against the rebuilt store:

  - **Block A — zero relief-gate violations.** The query returns an empty list; no stored
    ridge/valley line has under 50 m of relief.
  - **Block B — `ridge=122,567, valley=112,232` = 234,799 combined**, hitting the predicted
    230-240k band exactly (it was a direct SQL measurement, and it did not move).
  - **Store size 720 MB, against a predicted 2.4-2.5 GB.** The prediction overshot ~3.3x. That is
    the safe direction, and the mechanism checks out rather than the geometry having been
    destroyed: median stored line is **5-6 vertices over ~1 km** (≈200 m vertex spacing, right for
    a 90 m DEM) and median relief is **90 m**, sitting in the middle of the user's own 50-150 m
    maskable-behind band with a hard floor at exactly 50.0 m. The extrapolation was from a
    geometry-byte reduction measured on sample data; at theatre scale the relief gate and the
    decimation compound, which the sample could not show. **This is the second time a reduction
    estimate on this feature has been off in the conservative direction** — the earlier one was a
    deviation check overstated by 5x. Treat these sample-derived size predictions as order-of-
    magnitude only.
  - **Block C — by eye, both renders.** Baalbek: the Bekaa floor is clean, lines confined to the
    flanking ranges and their real drainage (297 ridge / 282 valley lines in the 40 km window,
    611/672 dropped by the gate). Palmyra: the long isolated chains survive intact, crest-following,
    longest 6.06 km, flat desert clean.

  Original entry, for what it was clearing, follows. The 2026-10-02 build above, checked against the user's own acceptance
  criteria, found the ridge/valley layer had no relief gate (89-92% of stored lines under 50 m of
  relief; the Bekaa floor at Baalbek read as a valley) and stored geometry ~16x denser than a 90 m
  DEM supports (`feature` was 7.98 of 8.1 GB). Both fixed — see
  `plans/landform-relief-gate/implementation.md`. The theatre-wide feature count after the gate
  (234,799) is a direct SQL measurement against the existing store, not an extrapolation; the
  resulting store size (~2.4-2.5 GB, down from 8.1 GB) *is* extrapolated from a measured
  36.5-36.7x geometry-byte reduction, not from a full rebuild. It cleared on the user's own
  2026-10-04 23:59 rebuild, which fully invalidated the terrain cache as designed
  (`EXTRACTOR_VERSION` 1→2 plus two new knobs in the key — a full cold reprocess, not the warm
  path). Card: `docs/acceptance/2026-10-04-landform-relief-gate-rebuild.md` /
  https://claude.ai/artifact/S6sod3ZdB1mCWSYj8twCPP.
