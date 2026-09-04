---
name: feedback-verify-rebuild-row-counts
description: build_world_model.py CLI flags with no registered default silently degrade builds; verify row counts directly, don't trust CLI summary alone
metadata:
  type: feedback
---

`tools/build_world_model.py <region>` only has registered defaults (in
`_DEFAULT_RAW_PATHS`) for `--towns`/`--beacons`/`--osm-cache`/`--routes` on
`latakia-20km` — `--probe-output`/`--srtm-tile` have none. Omitting
`--probe-output` doesn't error; it silently produces a smaller build ("probe:
skipped") and can **overwrite** an existing `.sqlite` that had more data (e.g.
dropping a previously-ingested 1,681-point elevation/surface_type grid to
0 rows). This actually happened during M5 Stage 5's rebuild-timing measurement.

**Why:** the CLI's own summary output ("Built ... probe: skipped") looks like
successful, expected output if you aren't specifically watching for the word
"skipped" — it doesn't read as a regression. The only way this was caught was
querying `grid`/`grid_sample` row counts directly against the rebuilt store
after the fact, and separately confirming via a `describe_position` sanity
check that `elevation`/`surface_type` come back non-null on a real point.

**How to apply:** any time you re-run `build_world_model.py` against a store
that already has real ingested data (probe grid especially, since it's the
one layer requiring an out-of-band live-DCS-probe artifact that isn't part of
the raw-input defaults), pass every optional flag whose data you don't want
silently dropped, and verify row counts / a `describe_position` spot check
against the *result* — don't trust "no error" or the CLI's own printed
summary as proof nothing regressed. This is a real recurring risk, not
hypothetical: it's the CLI's own defaults design, not a one-off mistake.
