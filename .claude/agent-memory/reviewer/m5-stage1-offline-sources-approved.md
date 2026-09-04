---
name: m5-stage1-offline-sources-approved
description: M5 Stage 0+1 (census + offline sources) review outcome and what a clean multi-trap implementation looks like in this project
metadata:
  type: project
---

M5 Stage 0 (census) + Stage 1 (offline sources: geometry, towns/beacons parsers, store, build
pipeline, airfield layer) reviewed 2026-09-04 on `feature/m5-first-persistent-model` (11 commits
on `d4216fe`) — APPROVED, no required fixes. This was a checklist-heavy stage with two named traps
(towns.lua list-not-dict, beacons.lua `{x,y,z}` middle-is-elevation) plus a derived-geometry layer
(airfield/runway from beacons) carrying its own overclaiming risk — all landed clean on first pass.

What made this reviewable quickly and confidently, worth expecting again from this
implementer/plan pairing:
- Every "trap" and every plan-specified numeric constant (runway uncertainty 300.0, airfield
  500.0/1000.0, ILS/PRMG pairing) had a dedicated test pinning it by name
  (`test_ils_and_prmg_are_never_crossed`, `test_derived_features_carry_derived_provenance_and_
  nonzero_uncertainty`) — scope guards expressed as tests, not just comments.
- Circularity trap (`positionGeo` must never validate/position anything, per M1 Finding 2) was
  checked by grep across `build/`, `query/`, not just trusted from the docstring's claim.
- `test_store_reader.py`'s R*Tree-vs-brute-force test reimplements the brute-force reference
  independently in the test file using `geometry` primitives directly, not by calling into
  `store.reader` — this is the right shape for an index-honesty test; check for this pattern
  whenever a spatial index ships in this project.
- Ambiguity was resolved conservatively and *documented* rather than silently picked: towns.lua's
  positional-uncertainty question (DCS in-game position ~0m vs terrain-artist-pasted ~1300m) had
  no plan-mandated value, so the implementer ran the plan's own suggested n=1 diagnostic, found it
  inconclusive, and chose the conservative (larger) uncertainty + downgraded confidence rather than
  the optimistic one — see `implementation.md`'s `ingest_towns.py` note. This is the right call
  when a plan explicitly leaves a value open as risk rather than deciding it.

One recurring environment quirk, not a code defect: `mypy world-model/tests` gives 32 spurious
`import-not-found` errors when invoked from the repo root instead of `cwd=world-model` — same root
cause as the ruff isort cwd-dependence already on file (see
[[project_ruff_cwd_dependent_isort]]). `world-model/CLAUDE.md`'s canonical command only lists
`mypy world-model/src` (not tests), so this doesn't block a canonical-command check, but flag it
early in future reviews so it isn't mistaken for a real regression.

One live-but-currently-unreachable optional finding: `query/describe.py` defaults
`feature.position_uncertainty_m or 0.0` in several builder functions. `StoredFeature.
position_uncertainty_m` is typed `float | None`, but no current ingest module ever leaves it
unset — if a future one did, this pattern would silently report "zero uncertainty" for an unknown
quantity, which is the exact collapsed-fact failure the provenance/confidence invariant exists to
prevent. Worth checking this defaulting pattern again in Stage 2/3 reviews (roadnet, probe grid)
once more ingest paths exist that could plausibly leave uncertainty unset.
