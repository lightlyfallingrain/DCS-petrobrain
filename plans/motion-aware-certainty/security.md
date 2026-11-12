## Security Deep Analysis: motion-aware-certainty (BL-B112)

Scope: body-layer only, diff `e6a43148..9228a080` (branch `feature/motion-aware-certainty`, after
main was merged in to resolve a worktree divergence; this analysis was run at that final tip).
Inputs read: `plan.md`, `implementation.md`, `review.md` (APPROVED WITH MINOR FIXES — both required
fixes were test-card wording/scope issues, not code; `3c055ea7` applied the fix).

### Dependency Status

No dependency change. `body-layer/pyproject.toml` has no diff in this range — confirmed by `git
diff e6a43148..9228a080 -- body-layer/pyproject.toml` (empty). Declared surface stays `pyproj`,
`numpy`.

### Code Findings

Changed files: `belief/association_over_time.py`, `belief/contacts.py`, `belief/crew_console.py`,
`belief/decay.py`, `belief/motion.py`, `belief/speech.py`, `body.py`,
`mission_memory/admission.py`, `mission_memory/entries.py`, `perception/object_model.py`,
`tuning.py`, plus tests/fixtures/docs/config.

This feature is entirely in-process belief-state arithmetic and a new mission-memory write path —
no new network surface, no new file path construction, no new external-input parsing, no new
subprocess/eval/exec.

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `mission_memory/admission.py` — new `LostContactTracker`, `_write_lost_entry`/`_write_lost_entries` | New write path into the mission-memory JSONL store | Writes go through the existing `MissionMemory.append` → `MissionMemoryLogWriter` machinery (unchanged by this diff); the new code only builds `GroupPayload`/`AirDefencePayload`/`ThreatInfo` dataclasses from in-memory `Contact` state (DCS game-object fields: class, position, cardinality). No externally-reachable input (network, mission briefing text, file content) flows into a file path or into dynamic code. The target path/filename is not touched by this change. | None |
| `mission_memory/entries.py` — `CompositionItem.immobile`, `_decode_composition` | New schema-2 field decoded with `item.get("immobile", False)` | Defensive default for old (schema-1) on-disk entries, consistent with the module's stated exception to its own "missing key is corrupt" rule. This is a resilience improvement (fewer crash-on-load paths from a malformed/old file), not a new trust boundary — the mission-memory JSONL is locally written by this same process, not attacker-supplied. | None |
| `mission_memory/admission.py:481,542`, `belief/contacts.py:976`, `body.py:719` — `self.__init__()  # type: ignore[misc]` | Pre-existing reset pattern, `LostContactTracker.reset_for_new_mission` is a new instance of an existing pattern (`FiredOnTracker`'s own sibling) | Same shape as the pre-existing `FiredOnTracker.reset_for_new_mission`; not a new risk category, `type: ignore` is for mypy's `__init__` re-call restriction, not a safety bypass. | None |
| `belief/decay.py` — `certainty_of`, `distance_since_last_seen_m`, `LAST_I_SAW_GROWTH_THRESHOLD_M` | Pure arithmetic over in-memory contact fields | No I/O, no external input parsing, no injection surface. Behavioural correctness of the tracked/estimated/lost boundary is Reviewer's domain (already reviewed, approved). | None |
| `perception/object_model.py` — new `immobile` field, new SA-2 keyword rows | Static data table (DCS object-type keyword → profile), no runtime input | Not attacker-influenceable; keyword strings are from this project's own `data/dcs_type_to_reporting_name.tsv` reference data, not from any network or mission-file-derived string matched against untrusted content in a way that could be abused (the matching itself is pre-existing `belief.association`/`object_model` code, unchanged by this diff). | None |
| `body.py` — `_mission_memory_step`, `_reset_mission_state`, `_check_for_new_mission` plumbing for the new tracker | Threading a second tracker object through existing call sites | `_mission_memory_step`'s existing `except Exception: logger.exception(...)` (Decision 8: a memory write must never kill the poll loop) still wraps the new `_write_lost_entries` call — confirmed unchanged in the diff, so a crash in the new write path cannot take down the poll loop, same guarantee as before. | None |

**LAN/port-scanner surface**: this feature adds no new listening socket, no new HTTP endpoint, and
no new deserialization of anything arriving over the network. It is pure belief-state logic plus a
local file write that was already a feature of this codebase (schema extended, not newly added).

**LLM prompt injection**: no new text that an LLM reads flows through this change. `op_class`,
`count_word`, DCS type-name keywords and the new `immobile` flag are all structured/enum-like
values produced by this project's own code, not freeform text handed to a model.

**Secrets**: none found; grep for credential-like patterns on the changed files returned only false
positives (`token` as in voice-command dispatch token, not an auth/API token).

### Verdict

APPROVED

### Required Fixes (if any)

None.

### Findings filed / not filed

No security findings were produced by this analysis, so there is nothing to file as a backlog item.
(Closing-step check per this role's own memory/instructions: report grepped for any `Options:
(A)/(B)/(C)/(D)` or risk-matrix block before writing this verdict — none exists in this report.)

### Passed to Reviewer

None beyond what `review.md` already covers (both its required fixes are test-card wording/scope
issues already resolved in `3c055ea7`). No new player-facing correctness observation surfaced
during this pass.
