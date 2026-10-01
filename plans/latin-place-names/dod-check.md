### Definition of Done: WM-B1 — Latin-1 romanisation preference at OSM ingest

Branch `fix/latin-place-names`, tip `1226686` (confirmed via `git rev-parse HEAD` before any other
command — matched the dispatch brief exactly).

### Code Quality

Subproject touched: `world-model` only (`git diff main...HEAD --stat` confirms no other subproject
in the diff). All commands run from inside `world-model/` against a freshly built `.venv`
(`python3 -m venv .venv && pip install -e . ruff mypy pytest` — no `.venv` existed in this worktree):

- `ruff format --check src tests` → **pass** — "104 files already formatted"
- `ruff check src tests` → **pass** — "All checks passed!"
- `mypy src` (strict, per `[tool.mypy] strict = true` in `pyproject.toml`) → **pass** — "Success: no
  issues found in 62 source files"
- `pytest tests -q` → **pass** — "511 passed, 3 skipped in 17.72s", matching the briefed expectation
  exactly (baseline on `main` is 491 passed / 3 skipped, 494 collected; branch adds the 20 new tests
  from `TestIsLatin1Renderable`/`TestSelectName`/per-call-site coverage with zero regressions)

No unhandled errors/panics introduced: `_select_name`/`_is_latin1_renderable` are pure, total
functions (`str.encode` inside a try/except, no bare `except`, no new exception path). No debug
output (`print`/`console.log`/`pdb.set_trace`) and no new `TODO`/`FIXME` anywhere in the diff
(`git diff main...HEAD -- world-model/src | grep -niE "print\(|TODO|FIXME|debugger|pdb"` — no hits).

### Scope & Correctness

No `plans/latin-place-names/plan.md` exists — per the task, the `WM-B1` roadmap entry itself was the
spec, and the implementation matches it line for line: `_select_name` prefers
`name:en` → `int_name` → `name`, checked for Latin-1 renderability per candidate (not just preferred
by tag presence), applied uniformly across all four name-producing call sites (`_ingest_node`, the
dam-point branch of `_ingest_line`, the line branch of `_ingest_line`, `_ingest_area`/`_ingest_ring`)
— read the actual diff of `ingest_osm.py` and `store/models.py` directly rather than trusting the
implementation log's file list. `CLASSIFIER_VERSION` bumped 4→5 with a changelog comment. No scope
beyond this: `git diff main...HEAD --stat` shows only `ingest_osm.py`, `store/models.py`,
`test_ingest_osm.py`, `world-model/ROADMAP.md`, plan files, and Reviewer/Security's own
agent-memory writes — nothing in `body-layer` or any other subproject. No invariant violated:
DCS/OSM provenance is preserved (`provenance=dict(_PROVENANCE)` untouched), nothing claims knowledge
beyond what the source tag carried, and the fallback to raw `name` when no romanisation renders
preserves the pre-existing (not invented) behaviour. All files staged/committed — confirmed below.

### Testing

20 new tests covering the renderability predicate, the selection priority (including the
diacritic-heavy-`name:en`-still-fails case — the actual risk the brief named), and one integration
test per call site including the "unnamed feature gets no `name_source` tag" negative case. These are
meaningful, not decorative: each asserts the actual selected name/tag/source triple, not just
"no exception raised." No existing test was broken; three pre-existing `_ingest_ring` call sites
needed a new positional argument (signature change), not a behaviour rewrite.

### Documentation

Reviewer found **no required fixes** (one optional refinement, about `body-layer`'s
`displayable_name` docstring being stale — out of this branch's touched subproject, not blocking).
Security found **no findings requiring action** across dependency, injection-surface, reserved-tag-
collision, and cache-invalidation-correctness checks. `store/models.py`'s reserved-tags docstring
documents the new `name_source` key in place. `world-model/ROADMAP.md`'s `WM-B1` entry explains the
non-obvious behaviour (per-candidate renderability check, not tag-priority-only) and the honest
measured yield (67%/33% split) — this DoD pass added a DoD-status paragraph and a concrete
post-rebuild verification query (see Acceptance below).

### Security

- `plans/latin-place-names/security-review.md` — **APPROVED**, deep analysis (post-Reviewer). No
  plan.md/`security-plan-review.md` was produced or expected — per this project's standing note,
  a roadmap-entry-as-spec change with no architect pass does not get a plan-review gate; the
  deep-analysis gate is the one that applies here and it ran.

### Performance

**Deliberately not run, and this is a judgement call recorded here rather than an omission.** The
diff adds a few `dict.get` lookups and one `str.encode("latin-1")` call per named feature, inside an
OSM ingest that already runs 25-30 minutes end to end — unmeasurable against that baseline. The one
question with real scaling consequences — whether the `CLASSIFIER_VERSION` bump forces a full
re-classify rather than silently serving a stale cache — is a *correctness* property (does
invalidation fire at all), not a performance one, and Security's deep analysis covered it directly:
reproduced `cache_meta_matches` returning `False` for a stale-vs-current `OsmCacheMeta` pair by
construction, and confirmed `build/pipeline.py` reads the live `CLASSIFIER_VERSION` constant at
build time rather than a captured value. Security's own report independently agrees with this
framing in its "Performance note" section. No performance regression risk exists for this change to
miss.

### Mechanical repo state

- `git status --porcelain` → **clean** before this DoD pass's own edits (NOTES.md harvest,
  `world-model/ROADMAP.md` DoD-status addition); all new files from Implementer/Reviewer/Security
  were already staged and committed on the branch.
- Merge-conflict check against `main`: the dispatch brief predicted a benign doc-only conflict in
  `body-layer/src/belief/enrichment.py`'s docstring. Checked directly: `git diff main...HEAD --
  body-layer` is **empty** — this branch never touches `body-layer` at all (it forked before `main`'s
  `4f44b2b`, but the branch's own diff doesn't re-touch that file). Ran `git merge-tree
  <merge-base> main HEAD` and grepped for `CONFLICT`/conflict markers: **none found**. The predicted
  conflict will not actually occur — `main`'s `4f44b2b` will simply carry through untouched. Worth
  correcting rather than repeating the prediction uncritically.

### DoD Verdict: PASS

### Acceptance boundary (what this change's fixtures structurally cannot reach)

The unit tests exercise `_select_name`/`_is_latin1_renderable` and the four call sites against
synthetic `tags` dicts. They cannot and do not touch: (1) whether the real `syria-theatre.osm.pbf`'s
actual `name:en`/`int_name` tags produce the predicted 13,073/6,480 split at scale — that was measured
separately (Implementer, spot-checked by Reviewer against the roadmap's own numbers, not
re-derived) against read-only copies of the real data, not via pytest; (2) whether DCS's cockpit
overlay actually renders the newly-accepted Latin-1 names correctly end-to-end — that requires the
full-theatre rebuild plus a live or exported check, not just the encode-succeeds predicate; (3)
whether `CLASSIFIER_VERSION`'s bump actually triggers a full re-classify on the *real* cache file
during a real rebuild, as opposed to the synthetic `OsmCacheMeta` pair Security constructed. None of
these are testable without the full-theatre rebuild, which is the user's to run.

### Acceptance decision: no separate acceptance card

This change produces **zero observable effect** until a full-theatre rebuild runs. It is already
expected to ride along with `WM-B6` (geomorphons)'s own rebuild rather than triggering a second one —
both are in flight on separate branches gated independently. Writing a card for "fly the aircraft and
check place names" now would test nothing, since no rebuilt store exists yet.

**Concrete post-rebuild verification**, recorded in `world-model/ROADMAP.md`'s `WM-B1` entry so it's
found at the moment the rebuild lands, not buried in this plan file:

```sql
SELECT
  SUM(CASE WHEN json_extract(tags_json, '$.name_source') = 'name:en' THEN 1 ELSE 0 END) AS via_name_en,
  SUM(CASE WHEN json_extract(tags_json, '$.name_source') = 'int_name' THEN 1 ELSE 0 END) AS via_int_name,
  SUM(CASE WHEN json_extract(tags_json, '$.name_source') IS NOT NULL THEN 1 ELSE 0 END) AS any_name_source,
  COUNT(*) AS total
FROM feature
WHERE kind IN ('named_place', 'settlement');
```

Table/column names (`feature`, `tags_json`) confirmed against `world-model/src/store/schema.py`'s
actual `CREATE TABLE`, not guessed from `StoredFeature`'s field names. Predicted: `via_name_en` near
12,926, `via_int_name` near 864 (summing near the 13,073-row yield). `name_source = 'name'` covers
both already-Latin-1 names that never needed romanising *and* the 6,480 still-broken rows, so
isolating the "gained nothing" count needs a follow-up Python pass over those rows checking
`name.encode("latin-1")` directly (same predicate `_is_latin1_renderable` uses) — expect roughly
6,480 failures there. A result far off any of these numbers means the fix did not take effect as
expected on the real extract and needs a debugger pass before `WM-B1` can be called verified rather
than merely merged.

### Milestone Completion question

Answered inline in `world-model/ROADMAP.md`'s `WM-B1` entry: this does not change what the next
milestone should be or invalidate a downstream assumption — a localized ingest-time data-quality
improvement, `WM-B6` is unaffected in either direction, and nothing else depended on `name`/
`name_source`'s prior shape.

### NOTES.md harvest

Added one entry: the module-independence rule (`body-layer` → `world-model` only) forces this fix's
Latin-1 check to be duplicated by hand rather than imported, and the specific failure mode of that
duplication drifting — presenting as "the upstream fix didn't work" rather than as a visible
sync bug — is durable and non-obvious enough to keep (judged against existing NOTES.md entries;
no duplicate found).

### Recurring-fix pattern check

Reviewer's `review.md` had zero required fixes, so there is nothing to check against
`.claude/agent-memory/dod/MEMORY.md`'s prior "recurring fix" categories — no pattern to log from
this feature.
