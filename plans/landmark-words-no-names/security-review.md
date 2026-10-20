## Security Deep Analysis: landmark-words-no-names

Reviewed at tip `4ea0fb64` (`git diff f60f99da..4ea0fb64`), against `plans/landmark-words-no-names/
plan.md`, `implementation.md`, `review.md` (verdict: APPROVED WITH MINOR FIXES, all three required
fixes addressed in the implementation pass), and `docs/acceptance/2026-10-20-sortie-feedback.md`
F7 ("settled").

### Dependency Status

No dependency change. The only new import is `tuning` (`body-layer/src/tuning.py`, the project's
own existing constants loader, already used by every other `belief/enrichment.py` constant). No new
third-party package, no new `pyproject.toml` entry in either touched subproject.

### Scope confirmed by reading the diff, not assuming the plan's claims

- **`TOOL_SET` / brain-facing surface**: untouched. `git diff --name-only` shows no change to
  `body-layer/src/belief/tools.py` or `mission_memory/*.py`; the only changes in
  `test_console.py`/`test_tools.py` are `area_m2: float | None = None` added to each file's own
  `_FakeInfo` stand-in (required because `semantic_facts_for` now reads that field
  unconditionally — a fixture-fanout issue, not a production change). Confirmed no `Entry(` /
  `admission.py` / `marks.py` edits anywhere in the diff.
- **Mission memory**: unaffected for the same reason — it reads `SemanticFact.text`/`feature_id`
  directly (`admission.py`, `marks.py`), both of which keep the full name; this feature only adds a
  new *speech-side* rendering function that neither of those call.
- **No-omniscience invariant** (`body-layer/CLAUDE.md`, "No omniscience is structural"): this
  feature changes wording only, not the knowledge source. `semantic_facts_for` already derived
  settlement/water facts from the aircraft's own world-model-queried position before this change;
  the size word (`_settlement_size_word`) is computed from the *same* `SettlementInfo` the name
  already came from (`subtype`, and now `area_m2`, both already resolved by `describe_position`
  against ownship's own position). No new knowledge reaches Petrovich that wasn't already reachable
  — if anything, speech now discloses *less* (no name, no distance figure) than before. `belief/
  percept.py`'s `Percept`/`percept_of` boundary, `Contact`, and `ContactStore.ingest` are untouched
  by this diff entirely (`git diff --name-only` confirms no change under `belief/percept.py`,
  `belief/contacts.py`, `belief/association_over_time.py`).

### Input handling of the new `area_m2` tag

- **Where it comes from**: `world-model/src/build/ingest_osm.py:644` always sets
  `tags: dict[str, Any] = {"area_m2": net_area_m2}` where `net_area_m2` is a `float` computed by
  `ring_area_m2` (shoelace formula) at build time — never a value supplied at body-layer runtime,
  never derived from mission (`.miz`) data, never network-received. The feature's only new read is
  `world-model/src/query/describe.py:444`, `area_m2=feature.tags.get("area_m2")` — additive,
  read-only, same tag `_preferred_settlement` (`describe.py:462`/`502`) already reads two functions
  above this change, with the identical un-validated-type trust assumption (`feature.tags` is a
  `dict[str, Any]` deserialized by `json.loads` in `store/reader.py`, with no schema check on any
  key, a pre-existing pattern that predates this feature).
- **Missing**: `feature.tags.get("area_m2")` returns `None` when absent (e.g. an OSM point with
  `place=*` but no polygon, or any feature predating the tag). `_settlement_size_word` and
  `SettlementInfo`'s own type (`area_m2: float | None`) both handle this explicitly — covered by
  tests (`test_settlement_size_word_built_up_no_area_defaults_to_village`,
  `test_settlement_size_word_unrecognised_subtype_uses_area`). Degrades to the documented "safer
  default" (village), consistent with this module's existing absent-data posture.
  `_preferred_settlement`'s tie-break on the same tag independently defaults to `float("inf")` on
  absence — an existing, different convention, unaffected by this change.
- **Non-numeric / negative / NaN**: the ingest pipeline only ever writes a `float` here, so these
  cases would require a hand-corrupted or foreign `.sqlite` store (a local build artifact this
  project's own tooling produces and body-layer reads read-only — not an attacker-reachable input
  in this single-player, LAN-only project; the user is the only one who could substitute a
  different store, per `body-layer/CLAUDE.md`'s own "the user is responsible for copying the built
  file over manually" note). Within that already-narrow scope:
  - **NaN**: `area_m2 < BUILT_UP_VILLAGE_MAX_AREA_M2` evaluates `False` for NaN (IEEE 754), so the
    `if area_m2 is not None` branch below it returns `"town"` — no crash, just a wrong-but-bounded
    word choice.
  - **Negative**: compares as less than the threshold, returns `"village"` — again wrong-but-bounded,
    never a crash. (Also not reachable from the real `ring_area_m2` formula, which subtracts a
    bounded hole area from an outer ring and is itself gated: `ingest_osm.py:606`.)
  - **Non-numeric (e.g. a string)**: `str < float` raises `TypeError` at the comparison in
    `_settlement_size_word`. This is the one path that would crash rather than degrade, but it
    requires a `tags["area_m2"]` value of the wrong Python type in the store's JSON blob — not
    reachable through this feature's own write path (which only ever stores a float) and no more
    exploitable than the dozen other `feature.tags.get(...)` call sites across `describe.py` and
    `enrichment.py` that already carry the same unchecked-JSON-blob trust assumption. See "Findings"
    below — tracked, not blocking.
- **`assert isinstance(text, str)` in `_landmark_speech_text`** (`speech.py:1946`): operates on a
  `fact["text"]` value from `facts["semantic"]`, itself built entirely by `semantic_facts_for`
  (internal belief/world-model data, never player voice input or mission-author data). This is the
  same internal-invariant assert pattern used at ~20 other sites in this file (`speech.py:2020`,
  `2044`, `2047`, `2136`, etc.) — not a new pattern, not on an externally-reachable data path.

### Tunable bounds (`BUILT_UP_VILLAGE_MAX_AREA_M2`)

`lo=100_000.0, hi=5_000_000.0`, default `1_000_000.0`, both AST float literals (not computed),
`status="judgement"`. No cross-key coupling: this key is read by exactly one function
(`_settlement_size_word`) and compared against exactly one other value (`area_m2`, not another
tunable), so the one documented residual-coupling class in this project (two *tunables* compared
against each other, e.g. `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S`) does not apply here. Rendered
`defaults.toml` line checked directly (not just the `#:` source comment) — value renders correctly
as `BUILT_UP_VILLAGE_MAX_AREA_M2 = 1000000.0`; the comment line has a dropped leading backtick,
already identified by `review.md` as a pre-existing generator defect (same defect on two unrelated
entries) — cosmetic, not a behavior or security issue, not this feature's to fix.

### `feature_id` encoding — no injection surface

`feature_id` strings (`f"settlement:{size_word}:{name}"` etc.) are never evaled, never used to
build a file path or SQL query, and never passed to a shell or subprocess — only split with
`str.partition`/`str.split` in `_landmark_speech_text`. A settlement/water name containing a colon
does not break the parse: `word = rest.split(":", 1)[0]` always takes the segment immediately after
`kind:`, regardless of how many further colons the name itself contains. Verified by reading both
construction sites (`enrichment.py`) and the one consumption site (`speech.py`).

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `world-model/src/query/describe.py:444` | `feature.tags.get("area_m2")` — no type/range validation on a value from a `json.loads`-deserialized blob | Extends a pre-existing trust pattern (same tag already read unchecked by `_preferred_settlement`) to a store that is built by this project's own offline pipeline, never attacker-supplied at runtime in this single-player/LAN-only project. Non-numeric would raise `TypeError` in `_settlement_size_word`'s comparison; NaN/negative degrade silently to a wrong-but-bounded word, no crash. | Not filed, intentionally — see below. |
| `body-layer/src/belief/speech.py:1946` | `assert isinstance(text, str)` | Internal-invariant assert on internally-constructed data (never player/mission input), consistent with ~20 existing identical-shape asserts in the same file. | None — false-positive-by-pattern, matches established codebase convention. |
| `body-layer/config/defaults.toml` (generated) | Dropped leading backtick in the `#:` comment render for the new tunable | Cosmetic only (comment text, not the value); pre-existing generator defect confirmed by `review.md` on two other entries. | None — already noted as an Optional Refinement in `review.md`, not this feature's defect to own. |

### Verdict

APPROVED

No exploitable vulnerability, no expansion of the brain-facing (`TOOL_SET`) or mission-memory
surface, no new dependency, no omniscience violation, no injection surface in the new `feature_id`
encoding. The one finding above is a type-confusion robustness gap with no realistic attack path in
this project's single-player/LAN-only context (the only way to trigger it is to hand-corrupt one's
own local build artifact), and it exactly mirrors a trust assumption this codebase already made at
the same call site family before this feature existed.

### Required Fixes

None.

### Low-risk finding disposition (per the "every finding gets an ID or an explicit refusal" rule)

**Finding:** `feature.tags.get("area_m2")` (and the pre-existing sibling reads of the same
`dict[str, Any]` tags blob two functions above it) has no type/range validation; a non-numeric
value would raise `TypeError` inside `_settlement_size_word`'s `<` comparison instead of degrading.
**Location:** `world-model/src/query/describe.py:444` (new read), pattern shared with
`describe.py:462`/`502` (pre-existing).
**Probability:** low — the only write path for this tag (`ingest_osm.py:644`) always stores a
`float`; triggering the bad-type case requires a hand-corrupted or deliberately foreign `.sqlite`
store, which only the store's own owner (the player/developer) could substitute, per
`body-layer/CLAUDE.md`'s own documented manual-copy workflow. No realistic attacker path in a
single-player, LAN-only project.
**Impact:** low — one function raises `TypeError` rather than rendering a wording fallback;
`semantic_facts_for`'s caller chain is `belief` code already running inside the same local process,
so this is a local crash/exception, not a security boundary crossing.
**Recommended action:** none required now; if `query/describe.py`'s info dataclasses ever grow a
shared validation layer (e.g. for a future untrusted-store scenario), fold `area_m2` into it then.

**Not filed, intentionally.** This does not meet the bar for a backlog item: it is a pre-existing
trust pattern (`tags.get(...)` on an unchecked JSON blob) that this feature extends to one more
field rather than introduces, has no realistic attack path given the project's single-player/
LAN-only scope and the store's offline, locally-owned build process, and the two existing sibling
reads of the same tag at the same trust level were never themselves flagged or ticketed. Filing a
backlog item here would be tracking the pattern, not this feature's use of it — if the pattern
itself is ever worth closing, that is a `WM-B*`-scoped item about `query/describe.py`'s tag-reading
convention in general, not something this feature should mint in isolation.
