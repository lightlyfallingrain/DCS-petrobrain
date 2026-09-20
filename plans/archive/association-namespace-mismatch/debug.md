### Debug Report

### Observed Issue
`todo/todo.md` backlog item ("`association.py` matches across two different DCS name
namespaces and scores 0 on most real units") claims `HybridPerceptionSource` matches HelperAI's
*reporting-name* detection text (`"Slava cruiser"`, `"SA-3 launcher"`, `"Tarantul III
corvette"`, `"SA-3 Low Blow radar"`) directly against `LoGetWorldObjects`'s raw DCS *type*
names (`MOSCOW`, `5p73 s-125 ln`, `MOLNIYA`, `snr s-125 tr`) via
`association._type_match_score`, scoring 0 on all four real pairs and only working for `"Ural
truck"` vs `Ural-375` by word coincidence — meaning the scope/HelperAI channel's association was
described as near-nonfunctional for ships, SAM sites, and most armour.

### Hypothesis
Working hypothesis going in: `_type_match_score` needed to be changed to resolve
`object_type` through `reporting_names.reporting_name_for` before scoring against
`classification_raw`, and `hybrid_source.py` needed to read all five HelperAI list-text leaves
instead of only `middle_list_text`.

### Evidence
Reading the current state of both files (branch point `613248a`, no prior commits on this
branch) showed both fixes already present:

- `body-layer/src/perception/association.py`'s `_type_match_score` (lines 249-273) already
  resolves `object_type` via `reporting_names.reporting_name_for` and scores
  `classification_raw`'s keywords against **both** the raw type and the resolved reporting
  name, taking the max. Landed in commit `23f7157` ("Score association type-match against
  reporting name too (PB-2 Stage 0a)", 2026-09-09) — i.e. after the backlog item was filed but
  before this branch started, as part of BL-2/PB-2 Stage 0 (`todo/todo.md` line 57 already
  documents this, but the standalone backlog entry below it was never marked done/removed).
- `body-layer/src/perception/hybrid_source.py` already reads all five `LIST_TEXT_FIELDS`
  (`upper_upper_list_text`..`lower_lower_list_text`), deduplicates, and associates each distinct
  leaf independently, removing a claimed candidate from the pool before resolving the next leaf
  — the multi-contact gap flagged in the same backlog item's "also worth checking" note.

Ran the four real pairs from the backlog item directly against the installed code
(`body-layer/.venv/bin/python`, `PYTHONPATH=src:../world-model/src`):

```
Slava cruiser | MOSCOW -> 2
SA-3 launcher | 5p73 s-125 ln -> 3
Tarantul III corvette | MOLNIYA -> 3
SA-3 Low Blow radar | snr s-125 tr -> 5
Ural truck | Ural-375 -> 2
```

All five score nonzero — the reported 0/0/0/0 does not reproduce against current code.

`body-layer/tests/test_association.py`'s "PB-2 Stage 0a" section (`test_type_match_score_is_
nonzero_for_real_reporting_name_tuples`, parametrized over exactly these four real DCS
type/reporting-name pairs, plus `test_two_distinct_sa3_units_each_associate_to_their_own_
candidate`) and `body-layer/tests/test_hybrid_source.py`'s
`test_sa3_launcher_and_radar_leaves_yield_two_observations` /
`test_slava_cruiser_and_tarantul_corvette_leaves_yield_two_observations` already cover this
exact regression end-to-end (leaf text -> `associate()` -> distinct `Observation`s), reproducing
Finding 6's real sampled multi-leaf tuples.

### Fix Applied
No code change — the root cause (raw-type-only keyword scoring) and the related multi-leaf gap
were already fixed in commit `23f7157` and the hybrid_source.py multi-leaf read, both part of
BL-2/PB-2 Stage 0, landed on `main` before this branch was cut. This branch adds no new
production code. The only change is closing out the stale backlog entry in `todo/todo.md`,
which still listed this as `[ ]` open and undocumented-as-fixed, to prevent it from being
re-investigated as if it were live.

### Verification
Full body-layer gate run clean on the current branch (no changes needed):
- `ruff format --check src tests` — 52 files already formatted
- `ruff check src tests` — all checks passed
- `mypy src` — no issues found in 24 source files
- `pytest tests -q` — 374 passed

**Live verification note**: as instructed, no live DCS re-test was performed (out of scope for
this role and this agent's execution boundary). What would still need live confirmation before
fully closing the loop: a real sortie against ship/SAM-site contacts (not just Ural trucks, per
PB-1's original acceptance test) through `--console`, confirming `associate()` actually resolves
those detections to contacts end-to-end against a live `LoGetWorldObjects` feed and real HelperAI
indication text — the fixture/unit-level evidence above is strong but PB-1's own live acceptance
test is exactly what missed this namespace bug in the first place, so a live re-test remains the
authoritative confirmation.
