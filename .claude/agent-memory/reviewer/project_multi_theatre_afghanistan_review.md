---
name: multi-theatre-afghanistan-review
description: multi-theatre-afghanistan (Stages 1,2,3,5) reviewed APPROVED clean; technique for distinguishing a real data-authoring property from a code defect using geometric ground-truth queries against the built store
metadata:
  type: project
---

`feature/multi-theatre-afghanistan` (tip `381f828`) reviewed APPROVED, no required fixes. All
checks (ruff format/check, mypy --strict, pytest) reproduced from scratch in fresh venvs in both
world-model and body-layer, matching the implementer's reported numbers exactly.

**Technique worth repeating: when asked "is this real or a defect" about a sparse/dense output
(here: Afghanistan's junction count looking implausibly low next to Syria's), don't just read the
detection code's docstring and accept its stated limitation — independently measure the *input*
geometry against the real built store and compare the same measurement across both theatres.**
Here that meant: pull real road polylines from `afghanistan-full.sqlite`/`syria-full.sqlite`
around a comparable urban sample (Kabul/Damascus, same window size), grid-bucket segments and
compute actual geometric crossings, then check what fraction of *clean, single* crossings land
within 1m of either road's own endpoint (catchable by `roadnet/junctions.py`'s endpoint-based
union-find) vs not (the detector's documented interior-interior blind spot). Result: both
theatres showed 100% of clean crossings as uncatchable interior-interior crossings — the
detector's blind spot is identical everywhere, not Afghanistan-specific. The *density* gap (1
junction per ~400km of road vs ~42km) traced instead to Afghanistan's roads being authored as
~2x longer polylines on average (fewer explicit route splits per km), a DCS authoring property,
not a parsing or detection defect. This is the kind of claim that would have been wrong if
asserted from documentation alone in either direction — "the detector is broken for Afghanistan"
or "nothing is wrong here" both read plausibly without the cross-theatre measurement.

Second finding verified the same way: airfield coverage (7 of ~26 real Afghanistan airfields) is
by-design (`ingest_beacons.py` only derives `airfield` features from `beacons.lua`
`airfield<N>_<M>` groups — zero-navaid airfields are invisible to it), confirmed by listing the
real `AirfieldsTaxiways/` directory on the mounted DCS install (26 files) rather than trusting
the task's stated number. Consumer-grep (`nearest_airfield`/`AirfieldInfo`) showed zero runtime
consumers — only a diagnostic CLI — same "no real consumer yet" shape as the plan's own stated
raster-registration exclusion, so this currently costs the pilot nothing. Recommended (not built)
that Stage 4's live probe output (`coord_probe.lua`'s `world.getAirbases()` dump, independent of
beacons.lua) is a ready-made seed for a future full airfield layer.

See [[project_mi1_mi15_review]]-style verification discipline and
[[feedback_verify_pipeline_wiring_not_just_module]] for the general pattern this extends: don't
trust a module's own docstring characterization of its limitation without checking it against
real data from more than one angle.
