### Implementation Summary

Stages 1, 2 and 3 of `plans/bl8-mission-memory/plan.md`, implemented and committed as three
separate commits on `feature/bl8-mission-memory` (plus one follow-up strengthening a Stage 1
test). Stage 4 (attack runs), Stage 5 (query surface / `TOOL_SET`), and Stage 6 ("safe from"
re-enablement) are **not** implemented — out of scope per the orchestrator's instruction.

### Files Changed

**Stage 1 — schema, store, sink (new package `body-layer/src/mission_memory/`)**
- `src/mission_memory/__init__.py` — package docstring stating the import-direction invariant.
- `src/mission_memory/entries.py` — the frozen `Entry` dataclass tree (`PhaseInfo`, `EntryPosition`,
  `SeenHow`, `CompositionItem`, `MotionInfo`, `ThreatInfo`, and the five payload types), plus
  `encode_entry`/`decode_entry`. Zero imports from `belief/`; `Certainty`/`MotionState` are
  duplicated literal types rather than imported, per the module's own stated reason.
- `src/mission_memory/store.py` — `MissionMemory`: `append()` is the single construction site for a
  *live* `Entry` (enforced by a grep test), under one lock; derived `struck_by`/`_latest_live`
  indices; `latest_entry()` added in Stage 2 for the material-change check; `rebuild_struck_by()`
  for a from-the-file-alone replay.
- `src/mission_memory/log.py` — `MissionMemoryLogWriter`, mirroring `speech_log.SpeechLogWriter`'s
  disable-once-and-report policy.
- `body-layer/pyproject.toml` — added `mission_memory` to `known-first-party` (isort).

**Stage 2 — observed entries + wiring**
- `src/mission_memory/admission.py` (new) — the `group`/`air_defence` admission rules (Decision 3),
  holding `RESIGHT_MOVE_M`, `RESIGHT_MIN_INTERVAL_S`, `GROUP_ENTRY_CONFIDENCE_FLOOR` (all via
  `tuning.py`).
- `src/belief/speech.py` — `_cardinality_phrase` renamed to public `cardinality_phrase`; a private
  `_cardinality_phrase = cardinality_phrase` alias keeps every existing in-module and test call site
  working unchanged.
- `src/logger.py` — `--mission-memory PATH`; `_resolve_mission_memory_log_path` (a sibling of
  `_resolve_group_trace_log_path`, not a fifth parameter on `_per_run_log_paths`); `_mission_memory_step`
  called from both poll loops after `run_once()` and (in `--crew-text`) before `drain_events`.
- `src/mission_memory/store.py` — `MissionMemory.latest_entry`.
- `body-layer/config/defaults.toml` — regenerated.

**Stage 3 — commanded marks and `fired_on`**
- `src/mission_memory/marks.py` (new) — `mark_here`/`mark_target`.
- `src/mission_memory/admission.py` — `FIRED_ON_FOLD_WINDOW_S`; `FiredOnTracker` (poll-loop-owned
  per-shooter suppression state, *not* on `MissionMemory`); `_write_fired_on_entries`; `step()`
  gained a `fired_on_tracker` parameter.
- `src/belief/crew_console.py` — `mark_here_fn`/`mark_target_fn` injected-closure fields (see
  "Notable Discoveries" below); `DISPATCHED_COMMAND_TOKENS` gained `"mark_here"`/`"mark_target"`;
  `_handle_mark_here`/`_handle_mark_target`.
- `src/logger.py` — `_mark_here_fn`/`_mark_target_fn` closure builders, wired into `crew_console` in
  the `--crew-text` branch; one `FiredOnTracker` per poll-loop run.
- `body-layer/config/defaults.toml` — regenerated again.

**Tests added** (one file per concern, new):
- `tests/test_mission_memory_entries.py` — JSON round-trip, every kind, plus an all-nullable entry
  and `math.inf` cardinality.
- `tests/test_mission_memory_store.py` — strike chain, two replay tests (in-memory, and now a real
  JSONL round trip), Co-moving Fields assertions, single-construction-site grep tests.
- `tests/test_mission_memory_log.py` — write round trip, disable-once-and-report (via a directory
  path, no monkeypatching needed).
- `tests/test_mission_memory_import_direction.py` — the Decision 1 grep test.
- `tests/test_mission_memory_admission.py` — group/air-defence/fired_on rules against a real
  `ContactStore` with contacts/events injected directly (this codebase's established fake-store
  pattern).
- `tests/test_mission_memory_marks.py` — `mark_here`/`mark_target`.
- `tests/test_crew_console_mission_memory.py` — the `CrewConsole` dispatch layer, using fake
  injected closures rather than a real store.
- `tests/test_run_log_paths.py` — extended with `_resolve_mission_memory_log_path` tests, mirroring
  the existing `_resolve_group_trace_log_path` ones.

### Non-obvious choices

1. **Decision 1's import direction forced `mark_here_fn`/`mark_target_fn` to be plain closures,
   not a `MissionMemory` field on `CrewConsole`.** The plan's Affected Modules section lists
   `crew_console.py` as gaining the two handlers, but `belief/crew_console.py` may not import
   `mission_memory` at all (only `belief/tool_api.py` may, and that module doesn't exist yet).
   `logger.py` sits outside `belief/` and may import both, so it builds `Callable[[float], str]`/
   `Callable[[str, float], str]` closures over the live `MissionMemory` and injects them — the same
   shape `transcript_log`/`speech_log_sink` already use for the identical reason. This is a
   mechanical consequence of Decision 1, not a deviation from Decision 6's substance: the player
   still gets `mark here`/`mark target`, dispatched the same way every other command is.

2. **`SeenHow.optic`/`range_m` do not read `Contact.last_percept`.** That field's own docstring
   (`belief/contacts.py`) names `belief.attack_run` as its one sanctioned reader outside the fields
   already pulled onto `Contact`; `mission_memory` lives outside `belief/` entirely with no standing
   exception. `optic` is read from `Contact.sighting_spans[-1].source` instead (the same channel
   string); `range_m` stays `None` — a real fact genuinely unavailable without that field, and the
   schema's own nullable slot for exactly this case.

3. **`ad_link`/`group_link` are one-directional at write time.** Decision 4 forbids mutating a past
   entry, so when two contacts share a `belief.groups.Group`, whichever entry is written *second*
   can link to the first (via `MissionMemory.latest_live_seq`), but the first cannot be retroactively
   updated. It only gains the link back the next time *it itself* is re-written (a resight/material
   change). Tested end to end in `test_air_defence_and_group_entries_link_both_ways_eventually`.
   This is the plan's own Decision 4 applied to a case the plan doesn't spell out explicitly —
   flagging it here rather than treating it as self-evident.

4. **`GROUP_ENTRY_CONFIDENCE_FLOOR`: no existing threshold found to reuse.** Per the plan's explicit
   instruction, searched (`grep -rn "confidence >=\|CONFIDENCE_FLOOR" src/belief/`) before declaring
   a new tuning key. Nothing on the describe/callout path gates disclosure on a confidence number —
   `classification.py`'s per-level defaults are fold-starting values, not a threshold anything
   checks before speaking. Declared as a new `tuning.fraction` key.

5. **Marks' position-building duplicates a small amount of `admission._build_entry_position`'s
   logic rather than sharing it.** `admission`'s version is keyed on a `Contact` (it reuses
   `EnrichmentContext.cache.get_or_compute`'s per-contact cache and terrain-aware lookup); a mark's
   subject is sometimes ownship itself, which has no `Contact`. Forcing one shape onto both call
   sites looked like the wrong kind of DRY, so `marks._mark_position` is its own small function —
   `dcs_to_wgs84` plus a direct `semantic_facts_for` call, no caching. Noted in both modules'
   docstrings.

6. **Marks always write `phase=None`.** `CrewConsole` has no `MissionPhaseTracker` of its own
   (unlike the poll loop's observed-entry writes, which resolve a live phase every poll). Threading
   one through would mean a third wiring path into `CrewConsole` for a nullable field whose `None`
   case is already the schema's honest default. Documented in `logger.py`'s wiring comment rather
   than silently defaulted.

7. **`FiredOnTracker` is owned by the poll loop, not by `MissionMemory`.** It is this one admission
   rule's own bookkeeping (which events have been scanned, per-shooter suppression timestamps), not
   a property of the store itself — keeping `MissionMemory` free of rule-specific state, consistent
   with the plan's "the store never decides anything" framing for strikes.

8. **The `--mission-memory` per-run path resolution is a fifth sibling function
   (`_resolve_mission_memory_log_path`), not a widened `_per_run_log_paths`.** Follows the precedent
   `_resolve_group_trace_log_path` already set (and its own stated reasoning): widening
   `_per_run_log_paths`'s 3-tuple return would touch nine existing tests for a mechanical reason
   unrelated to what they test.

### Tests Added

See the file list above — 8 new test files plus one extension of an existing one
(`test_run_log_paths.py`). Every test the plan names by description for Stages 1-3 has a
corresponding test; see the per-stage commit messages for the mapping.

### Checks

(body-layer/ only — no other subproject touched)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (66 source files; this is the canonical check per
  `body-layer/CLAUDE.md` — `mypy` is never run against `tests/` in this subproject, and doing so as
  a batch surfaces ~160 pre-existing, unrelated cross-file inference errors in test files this
  branch never touched. New/changed test files were additionally checked individually, which is
  clean.)
- `pytest body-layer/tests -q`: 2138 passed, 4 xfailed (pre-existing xfails, unrelated)
- `tools/generate_defaults.py --write` run after each stage that added a tuning constant;
  `test_tuning_defaults_toml.py` confirms `config/defaults.toml` is current.

### Notable Discoveries

- **Decision 1 (import direction) and Decision 6 (crew_console gains the handlers) are in real
  tension**, not just in appearance. The plan's Affected Modules section describes
  `belief/crew_console.py` as gaining `_handle_mark_here`/`_handle_mark_target` without noting that
  those handlers' actual logic lives in a package `crew_console.py` is forbidden from importing.
  The closure-injection resolution (point 1 above) is mechanical and matches an existing pattern in
  the same file, but a future stage extending the mark path (e.g. the richer mark forms BL-10
  mentions) should expect the same constraint, not rediscover it.
- **`belief.contacts.Contact.last_percept`'s "one sanctioned reader" restriction extends naturally
  to code outside `belief/` too**, even though its own docstring only names `belief.attack_run`.
  Worth stating explicitly in that docstring the next time it's touched, since a reader working
  purely from grep (as the restriction is currently enforced) would not find this module's
  avoidance of the field documented anywhere near the field itself.
- **No gaps found between the plan's test-impact list and the actual test suite** for Stages 1-3 —
  every test the plan named by description exists; no pre-existing test outside the new files
  needed rework (`cardinality_phrase`'s rename kept a private alias specifically to avoid touching
  `test_speech.py`).
