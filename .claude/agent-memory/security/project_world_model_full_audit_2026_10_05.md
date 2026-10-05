---
name: world-model-full-audit-2026-10-05
description: Mode 3 world-model audit — provenance carried everywhere except line_of_sight_clear; the measured SRTM error is computed by the pipeline and never written to the store (WM-B3's real mechanism)
metadata:
  type: project
---

Full-subproject audit of `world-model` @ `19143fa`, 2026-10-05. Report:
`world-model/research/2026-10-05-security-audit.md`. 11 findings in §1 (provenance), 9 in §2
(live-tick/read-path), 5 in §3 (build-time input).

**The one thing to carry forward: this subproject's provenance discipline is excellent in
`describe_position` and absent in its siblings.** Thirteen `*Info` dataclasses each carry
`provenance` + `confidence` + `position_uncertainty_m`, and `grid_provenance()` exists specifically
so SRTM is never reported as DCS-probed. Then `line_of_sight_clear` returns a bare `bool`, and
`raster.dcs_to_tile_pixel` returns a bare int tuple from a `confidence="provisional"` registration.
**So on a future pass, do not sample `describe.py` and conclude the invariant holds — check each
`query/` entry point's return type individually.** The well-implemented one is what made the gap
invisible for a month.

**The root cause is upstream of all of it and is worth recognising by shape:**
`build/validate.py:192`'s `compare_probe_to_srtm` computes the mean/median/stddev of the
DCS-vs-SRTM delta, and its only caller is a tool that prints it to stdout for a human to paste into
a research note. Nothing writes it into the store. `11.52` appears in `ROADMAP.md` and five research
notes and in **zero lines of code**, while `_TERRAIN_TOLERANCE_M = 12.0` is a hand-copy of it. That
is the literal mechanism of the open `WM-B3`. **Pattern to look for elsewhere: a pipeline that
measures its own data quality and delivers the measurement as prose.** The fix shape is always the
same — put it in the artifact (here: the `grid` row's existing `stats_json`, no schema bump) so the
consumer reads it instead of a constant.

**A reasoning error to avoid repeating, from my own prior pass.**
`plans/dcs-driven-los/security-deep-analysis.md:109-121` rated this exact fallback low/low. Both
halves were wrong for instructive reasons:
- Probability was reasoned from *failure modes* ("the Hook would have to crash") and never from the
  *steady state*. The fallback fires whenever a verdict is merely absent, which at 0.7 Hz against a
  5 Hz design is normal, not exceptional. **When rating a fallback, compute how often it fires in
  the healthy case, not only what breaks to reach it.**
- Impact was rated "low — reverts to the already-reviewed primitive", i.e. it *borrowed another
  component's acceptability*. The user withdrew that acceptability the same day and nothing re-ran
  the rating. **An impact rating that depends on another component being acceptable needs a lapse
  condition, exactly like a standing exemption does.**

**Verified-by-execution results worth not re-deriving:**
- `f"file:{path}?mode=ro"` is bypassable **two** ways — a path containing `?mode=rwc&x=1`, and a
  path containing `#` (SQLite discards the fragment and everything after). Both produced a
  read-write connection and created the file. Five sites in-repo. A first-pass claim that the `?`
  form "fails loudly" is wrong — it depends on the suffix, so treat *neither* form as safe.
- `ATTACH DATABASE ?` is **not** URI-interpreted (no injection — the string is taken literally,
  producing a file named `probe.sqlite?mode=rwc`), but the attached DB opens **read-write even over
  a `mode=ro` main connection**.
- `?x=nan` / `?x=inf` on `/describe_position` pass `float()`, propagate through `dcs_to_wgs84` as
  `(nan, nan)`/`(inf, inf)` without raising, and die at `store/chunks.py:39` `math.floor` —
  `ValueError` for nan, `OverflowError` for inf. `do_GET` has no catch-all, so the client gets
  `RemoteDisconnected` with no status and no body. The server survives.
- `SQLITE_LIMIT_VARIABLE_NUMBER` is **250,000** on the bundled SQLite 3.53.4 here but 32,766 on
  stock ≥3.32 — so `features_in_bbox`'s unbounded `IN (?...)` list is a build-dependent cliff, not
  a theatre-independent safe one. Do not re-measure on this machine and conclude it is fine.
- `sqlite3.connect` on a non-existent path **creates** it, which is why `api/__main__.py:46`'s
  missing `mode=ro` means a typo'd `--db` starts a server cleanly against an empty store.

**False positives / explicitly not findings, so they are not re-investigated:**
- `position_uncertainty_m=0.0` for DCS roads is *correct* — DCS geometry is authoritative by project
  invariant. The finding is only about a route that failed its own plausibility check inheriting
  that claim.
- `probe_store`'s `schema=` SQL identifier interpolation: every caller passes a hardcoded `"main"`
  or `"probe"` literal. Not reachable from HTTP, CLI or DB content. Fragile, not injectable.
- The read-only-against-DCS invariant **holds on every current path** — `--out` is structurally
  separate from all nine input flags and no write target derives from a DCS path. Enforcement is
  convention, not a guard, but there is no bug to fix today.
- `body-layer`'s theatre validation (`logger.py:1949`, `THEATRE_PROJECTIONS` membership) is strict
  and does block both URI bypasses above. That earlier finding is properly closed.
- An *empty or foreign* sqlite file IS caught by body-layer's startup guard (no `region` table →
  `sqlite3.Error` → `parser.error`). Only a **schema-valid, region-row-less** store slips through.
  I corrected a first-pass overstatement here; check the `except` clause before claiming a guard is
  absent.

See also [[project_los_terrain_tolerance_accepted_omniscience_trade]] (the 12 m trade as originally
approved — still correct for Syria/Mi-24P/SRTM, which is exactly the scope the code does not
enforce) and [[project_terrain_cache_resumable_fail_closed_approved]] (the cache mechanism, which
remains sound; 1.9 is about the key's contents).
