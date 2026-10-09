# BL-W17 — Scope-channel type-namespace mismatch, re-verified

- [x] **Scope-channel type-namespace mismatch, re-verified (closed as a stale backlog item, not
  new work; `fix/association-namespace-mismatch`).** #status/done The fix was already in `main` under BL-2/PB-2
  Stage 0 (`association._type_match_score` resolves DCS type names through `reporting_names`
  before scoring); this item had just never been checked off. A 2026-09-10 debugger pass
  re-measured the four originally-0-scoring real pairs (Slava cruiser, SA-3 launcher, Tarantul III
  corvette, SA-3 radar) directly against current code — all score nonzero, regression-tested in
  `test_association.py`/`test_hybrid_source.py`. Still open, not tracked separately: a live re-test
  against ship/SAM-site contacts specifically (the original PB-1 acceptance test used only Ural
  trucks, the one case where the two naming vocabularies happen to coincide).

