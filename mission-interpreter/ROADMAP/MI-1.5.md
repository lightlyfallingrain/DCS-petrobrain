# MI-1.5 — Author-only-knowledge filter

- [x] **MI-1.5 — Author-only-knowledge filter.** #status/done Done: `src/filter/crew_available.py` produces
  `CrewAvailableMission` from a `RawMission`, dropping every `hidden`/`hiddenOnPlanner`/
  `hiddenOnMFD`/`lateActivation` group entirely -- `CrewAvailableMission` has no raw-passthrough
  field, so a hidden group's existence cannot leak back in through an unfiltered catch-all.
  `trigrules`/`mission["trig"]` are never surfaced on `CrewAvailableMission` (kept as raw
  research/debugging data on `RawMission` only); `src/filter/trigrules.py` parses `trigrules`' raw
  `predicate`-string schema (Decision 1a) for that research/debugging use. Tests
  (`tests/test_filter.py`) prove the invariant against both the committed synthetic fixture (must
  pass in every checkout) and the real sample mission (skipped if absent).
