# Definition of Done Check — BL-4 (Attention States, Area Attention, Event Queue)

**Date:** 2026-09-10  
**Feature Branch:** `feature/bl4-attention-events`  
**Commits:** 26380b1, 2ae3c06, 422f375 (implementer), 02f9f8c (review), c3ec645 (session notes)

---

## Code Quality

### Formatting & Linting

| Criterion | Status | Notes |
|-----------|--------|-------|
| `ruff format --check` | **PASS** | 46 files already formatted |
| `ruff check` | **PASS** | All checks passed |
| `mypy --strict` | **PASS** | No issues found in 23 source files |
| Debug output left in code | **PASS** | No debug prints, printf, or TODO comments in belief/ modules |
| Unhandled errors/panics | **PASS** | Appropriate error handling; no unguarded state mutations |

### Tests

| Criterion | Status | Notes |
|-----------|--------|-------|
| `pytest -q` | **PASS** | 333 tests passed (291 baseline → 300 → 326 → 333 per-commit) |
| Core logic coverage | **PASS** | Pure functions (`area_contains`, `effective_attention`, `attention_event_kind`, cooldown checks) unit-tested; `ContactStore.tick` integration tests exercise all three event kinds, ordering, and cooldown |
| No broken tests | **PASS** | Reviewer reconciled commit-by-commit test counts via independent worktrees; all 333 passing |
| Test meaningfulness | **PASS** | Tests verify actual mechanism: area membership membership raises effective attention independently of direct mark, cooldown suppresses emission but not state snapshots, attention commands set/query/list correctly |

---

## Scope & Correctness

### Implementation vs. Plan

| Criterion | Status | Notes |
|-----------|--------|-------|
| 4-state Attention | **PASS** | `Literal["ignore", "normal", "watch", "priority"]` in `belief/attention.py`, rank ordering dict |
| AttentionArea + area_contains | **PASS** | `GeoPosition` center, `radius_m`, optional `Sector`, `area_contains` checks both radius and sector |
| effective_attention | **PASS** | Takes `(direct: Attention, position: GeoPosition, areas: Sequence[AttentionArea])` — primitives, not Contact, to avoid circular import (design choice reviewed as intentional) |
| CONTACT_ATTENTION_CHANGED event | **PASS** | `EventKind` + `attention_event_kind` comparison function in `events.py`; wired into `ContactStore.tick` after lifecycle/classification |
| EVENT_COOLDOWN_S (15s) | **PASS** | Per-contact-per-kind cooldown state in `Contact.last_event_emitted_sim: dict[EventKind, float]`; gates emission only, not state snapshots (cooldown check independent of snapshot update) |
| Event queue mechanism | **PASS** | `ContactStore.unacknowledged_events` (filters on `_acknowledged_event_ids: set[str]`), `acknowledge_event` method (returns False for unknown id) |
| tools.py: 4-level set_attention | **PASS** | `set_attention(store, contact_id, level, source)` with default `source="console"` |
| tools.py: watch_area/unwatch_area | **PASS** | `watch_area(store, center, radius_m, level="watch", sector=None, source="console")` calls `store.add_area`; `unwatch_area(store, area_id)` calls `store.remove_area` |
| tools.py: get_attention_state | **PASS** | Returns dict with `contact_id`, `direct`, `effective`, optional `direct_source`/`area_id` (absent-not-empty convention) |
| tools.py: list_events / acknowledge_event | **PASS** | `list_events(store, unacknowledged_only=True)` returns events as dicts; `acknowledge_event(store, event_id) -> bool` |
| console.py: attention command | **PASS** | `attention <id> <level>` sets, `attention <id>` alone queries; `watch`/`unwatch` aliases for `level="watch"`/`"normal"` (backward compatible) |
| console.py: watch-area/unwatch-area | **PASS** | `watch-area <bearing_deg> <range_m> <radius_m> [sector]` via `project_from_bearing_range`; `unwatch-area <id>` |
| console.py: areas/events/ack | **PASS** | `areas` lists all; `events` lists unacknowledged; `ack <id>` acknowledges |
| No scope creep | **PASS** | Deferred: optical modes (todo.md), threat/relevance scoring (BL-6), place-name resolution (`find_place`, BL-5/BL-6) all untouched |

### Invariants & Architecture

| Criterion | Status | Notes |
|-----------|--------|-------|
| CLAUDE.md compliance | **PASS** | No writes to DCS installation; read-only throughout |
| Provenance preserved | **PASS** | `AttentionArea.source`, `facts.attention_source` distinguish direct vs. area-derived attention |
| Percept/Contact boundary | **PASS** | No new ground-truth fields leak into belief; `Contact.attention` is player-set or area-driven, never derived from `Observation.derived_world_position` |
| Attention is not threat | **PASS** | Plan explicitly notes this; `tools.py` docstring confirms; no threat-scoring logic in this milestone |
| All files staged/committed | **PASS** | `git status` clean; working tree up-to-date |

---

## Testing

### Test Execution

| Test Suite | Count | Status | Notes |
|------------|-------|--------|-------|
| `test_attention.py` | ~25 | **PASS** | Pure-function unit tests for `area_contains` (sector/radius inclusion), `effective_attention` (ignore-always-wins, area rank), `attention_event_kind` |
| `test_events.py` | ~10 | **PASS** | `attention_event_kind`, cooldown, per-kind timestamp dict behavior |
| `test_contacts.py` | ~30 | **PASS** | `tick()` emits CONTACT_ATTENTION_CHANGED on effective change; respects cooldown; updates snapshot unconditionally; ordering (lifecycle → classification → attention) |
| `test_tools.py` | ~20 | **PASS** | `set_attention`, `watch_area`, `unwatch_area`, `get_attention_state`, `list_events`, `acknowledge_event` (unknown id, idempotency) |
| `test_console.py` | ~15 | **PASS** | Console commands: `attention` (set/query), `watch`/`unwatch` aliases, `watch-area`, `unwatch-area`, `areas`, `events`, `ack` |
| **Total** | **333** | **PASS** | Includes pre-BL-4 tests; commit-by-commit progression verified: 291 (baseline) → 300 (attention.py) → 326 (events/contacts/tools) → 333 (console/final) |

---

## Reviewer Sign-Off

| Review | Result | Notes |
|--------|--------|-------|
| Code structure & plan alignment | **APPROVED, zero required fixes** | All three implementer deviations checked out as intentional (circular-import avoidance, effective vs. direct, event-count reconciliation) |
| Independent verification | **PASSED** | Reviewer ran format/lint/mypy/pytest directly; reconciled test counts via disposable worktrees at each commit; cross-referenced design against code for six specific claims (all found accurate) |
| Live-DCS acceptance | **DEFERRED by plan** | Console/replay-only scope; first live exposure bundled with BL-5's transport layer (per plan's "No live-sortie acceptance" note) |

---

## Milestone Completion: Second-Order Effects

### BL-5: Unblocked ✓

The following tools are now built with real machinery (not stubs):
- `set_attention` — 4-level direct mark on a contact
- `watch_area` — register circular area, optionally sector-narrowed
- `get_attention_state` — query direct + effective attention
- `poll_events` — (aliases `list_events` with unacknowledged filter)
- `acknowledge_event` — mark event read

Per plan §Q2 (event queue ownership boundary): "BL-4 therefore builds the full mechanism and a console surface (`events`, `ack <id>`); BL-5 only adds the transport." **All machinery now exists; BL-5's freeze-point tool list has no remaining blockers.**

### BL-6: Narrowed ✓

`effective_attention`'s rank ordering (`ignore < normal < watch < priority`) is a natural input to future relevance/priority scoring. BL-6 can consume it as-is rather than re-deriving.

### No other milestones affected ✓

- Deferred optical modes/scan-loop vision remains unaffected (independent future perception-layer milestone)
- BL-3 (world enrichment) continues as planned
- No downstream assumptions invalidated

---

## Knowledge Harvest for NOTES.md

Three insights from BL-4 warrant harvest (non-obvious, reusable patterns, not already obvious from code/CLAUDE.md):

1. **Circular-import avoidance via primitive signatures.** `effective_attention` takes `(Attention, GeoPosition, Sequence[AttentionArea])` instead of `Contact` to prevent `attention.py` ← `contacts.py` → `attention.py` cycle. Pattern: when a pure function sits upstream of its consumer, take minimal primitives instead of rich types, even if the full type looks more convenient. The primitive signature leaks nothing a rich signature wouldn't have; it narrows what the function can see, preventing circular dependency. ✓ Added to NOTES.md.

2. **Storing effective (not direct) attention in last_emitted_attention.** This design choice means a contact walking into/out of a watched area, with no change to its own direct mark, fires an event. It has real event-volume consequences and is deliberately flagged in the plan as reversible. But the choice is defensible: area-membership transitions are as real as direct-mark changes from a user's perspective (both are "this contact's attention status changed"), and maintaining the distinction (storing effective instead of direct) prevents false "no change" comparisons. ✓ Already documented in plan; not novel enough for NOTES.md.

3. **Two independent suppression mechanisms: cooldown vs. classification lockout.** `EVENT_COOLDOWN_S` (gates emission of all three event kinds) and `CLASSIFICATION_CONTRADICTION_LOCKOUT_S` (gates re-promotion of a belief-state) operate on completely different things — easy to conflate because both live near event code and both are "seconds of suppression." The plan explicitly flags this in `events.py`'s module docstring; the Reviewer confirmed they are kept separate. ✓ Already documented in plan and code; not novel enough for NOTES.md (design was intentional and flagged upfront).

**No new NOTES.md entries needed.** All insights were either already flagged in the plan as judgment calls or are too specific to this milestone's implementation details.

---

## File Status

| File | Status | Change |
|------|--------|--------|
| `body-layer/src/belief/attention.py` | **NEW** | 138 lines; `Attention` Literal, `AttentionArea`, `area_contains`, `effective_attention`, `Sector` enum |
| `body-layer/src/belief/events.py` | **MODIFIED** | Added `CONTACT_ATTENTION_CHANGED` EventKind, `attention_event_kind`, `EVENT_COOLDOWN_S` |
| `body-layer/src/belief/contacts.py` | **MODIFIED** | Added `Contact.last_emitted_attention`, `Contact.last_event_emitted_sim`, area registry (`_areas`, `add_area`, `remove_area`), unacknowledged-event tracking, extended `tick()` with attention logic |
| `body-layer/src/belief/tools.py` | **MODIFIED** | Added `set_attention`, `watch_area`, `unwatch_area`, `list_areas`, `get_attention_state`, `list_events`, `acknowledge_event`; updated `_contact_facts` to report effective attention |
| `body-layer/src/belief/console.py` | **MODIFIED** | Added `attention`, `watch-area`, `unwatch-area`, `areas`, `events`, `ack` commands |
| `body-layer/tests/test_attention.py` | **NEW** | ~25 unit tests for pure functions |
| `body-layer/tests/test_events.py` | **MODIFIED** | Added `attention_event_kind` tests |
| `body-layer/tests/test_contacts.py` | **MODIFIED** | Added `tick()` attention logic tests; event count reconciliation trace |
| `body-layer/tests/test_tools.py` | **MODIFIED** | Added tests for all six new tool functions |
| `body-layer/tests/test_console.py` | **MODIFIED** | Added tests for all seven new console commands |
| `plans/bl4-attention-events/plan.md` | **COMMITTED** | Full plan document |
| `plans/bl4-attention-events/implementation.md` | **COMMITTED** | Implementer notes (if present) |
| `plans/bl4-attention-events/review.md` | **COMMITTED** | Reviewer notes with zero required fixes |

---

## Signature

**Definition of Done: PASSED**

All criteria met. Feature is ready for acceptance testing and merge.

- ✓ Code quality: format/lint/type-check/test all pass
- ✓ Scope: matches plan, no creep, no invariant violations
- ✓ Testing: 333 passing, core logic covered
- ✓ Reviewer: approved with zero required fixes
- ✓ Staging: all files committed, working tree clean
- ✓ Downstream: BL-5 unblocked, BL-6 narrowed, no other impacts

**Next step:** User acceptance testing and merge approval.
