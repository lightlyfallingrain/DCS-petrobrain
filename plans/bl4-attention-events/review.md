### Review Summary

BL-4 (attention states, area attention, event queue) reviewed against `plans/bl4-attention-events/plan.md`
and `plans/bl4-attention-events/implementation.md` across commits `26380b1`, `2ae3c06`, `422f375`
on `feature/bl4-attention-events`. Scope matches the plan closely — four-state `Attention`,
`AttentionArea`/`area_contains`/`effective_attention`, `CONTACT_ATTENTION_CHANGED` wired into
`tick`, a per-kind emission cooldown, and the full event-queue mechanism (`unacknowledged_events`/
`acknowledge_event`, console `events`/`ack`). No scope creep found into optical modes/scan-loop
(still untouched in `todo/todo.md`'s deferred entry) or threat/relevance scoring (BL-6) — `tools.py`
and `attention.py` both explicitly note attention is not threat.

**All three implementer-flagged deviations checked out as reasonable:**

1. **`effective_attention` takes primitives, not a `Contact`.** Confirmed real: `contacts.py`
   imports `belief.attention` (`from belief.attention import Attention, AttentionArea, Sector,
   effective_attention`), so `attention.py` importing `Contact` back would be circular. The
   primitive signature (`Attention`, `GeoPosition`, `Sequence[AttentionArea]`) leaks nothing a
   `Contact`-based signature wouldn't have — it's a strict narrowing of what the function can see,
   not a widening.
2. **`Contact.last_emitted_attention` stores *effective*, not raw direct, attention.** Confirmed
   intentional per the plan (Implementation Plan step 3, "attention-change events" section) and
   directly exercised by `test_area_membership_raises_effective_attention_without_a_direct_mark`
   (`body-layer/tests/test_contacts.py:383`), which fires `CONTACT_ATTENTION_CHANGED` purely from
   area membership with `contact.attention` unchanged (`"normal"` throughout). This is a real,
   deliberate design choice with event-volume consequences the plan itself flags under Risks &
   Unknowns — worth watching in live use, not a defect.
3. **BL-2 acceptance test's event count 2 → 3.** Traced the actual mechanism in
   `test_scripted_console_session_over_a_replayed_stream`
   (`body-layer/tests/test_console.py:128`): the third event comes from the `watch <id>` command
   changing the contact's *direct* mark between the first and second `tick()` call (not an
   area-membership case) — `CONTACT_DETECTED` + `CONTACT_LOST` + `CONTACT_ATTENTION_CHANGED` = 3.
   Correct given BL-4's machinery existing at all, independent of deviation #2's area-derived case.

**Independent checks, all passed:**

- `EVENT_COOLDOWN_S` (15s, `events.py`) and `CLASSIFICATION_CONTRADICTION_LOCKOUT_S` (30s,
  `classification.py`) are separately named constants operating on disjoint state
  (`Contact.last_event_emitted_sim: dict[EventKind, float]` vs.
  `Contact.classification_lockout_until_sim: float | None`) — no shared logic, and `events.py`'s
  module docstring carries an explicit cross-reference note per the plan's own risk callout.
- Cooldown gates emission only. Traced in `ContactStore.tick`: `contact.last_emitted_*` snapshots
  are written unconditionally after each kind's cooldown-gated emission block, and
  `test_event_cooldown_suppresses_rapid_reemission_but_not_after_it_elapses`
  (`test_contacts.py:433`) explicitly asserts `last_emitted_attention` updates during a suppressed
  window and that a later real change still emits correctly against the true (not stale) state.
- `set_attention` replaces `watch_contact`/`unwatch_contact`; console `watch`/`unwatch` are thin
  aliases (`level="watch"`/`"normal"`) verified byte-identical via
  `test_scripted_console_session_over_a_replayed_stream`'s literal string assertions on
  `watch`/`unwatch`/`contacts watched` output, unchanged from pre-BL-4 shape.
- `attention <id> [<level>]` overload: parsed via `rest.split(maxsplit=1)`, purely positional
  (arg count decides query vs. set), no risk of a level name colliding with anything else. Both
  paths reachable and tested (`test_attention_command_sets_and_queries_a_contacts_level`,
  `test_attention_command_rejects_an_unknown_level`, `test_attention_command_reports_unknown_contact`
  — all in `test_console.py`).
- Event queue: `_acknowledged_event_ids: set[str]` on `ContactStore`, `Event` dataclass untouched.
  `unacknowledged_events` filters correctly; `acknowledge_event` returns `False` sanely for an
  unknown id (`test_acknowledge_event_returns_false_for_unknown_id`, both `test_contacts.py` and
  `test_tools.py`) and re-acknowledging is implicitly idempotent (`set.add`).
- `AttentionArea`/`Sector`/`area_contains` hand-traced: sector-boundary inclusivity (45° exactly on
  the N/NE edge counts as N), inside-radius-but-outside-sector (south point excluded from an
  N-sectored area), inside-both (north point included) — all covered in `test_attention.py`.
  `bearing_deg`'s north-is-+x convention (`atan2(delta_z, delta_x)`) is consistent between
  `area_contains` and the test fixtures.
- Coordinate math stays in `perception.geometry` (`bearing_deg`/`range_m`/
  `project_from_bearing_range`) — `attention.py`/`console.py` call into it rather than
  reimplementing.
- No writes to the DCS installation; nothing in this milestone touches extraction paths.
- No provenance/confidence collapse — `AttentionArea.source`/`facts.attention_source` distinguish
  direct vs. area-derived attention throughout.

**Verification run directly (not trusted from the implementer's log):**

- `ruff format --check body-layer/src body-layer/tests` — pass
- `ruff check body-layer/src body-layer/tests` — pass
- `cd body-layer && mypy src --strict` — pass, no errors
- `pytest body-layer/tests -q` — **333 passed**
- Reconciled the commit-by-commit test count delta myself via a disposable git worktree at each of
  the four commits (`4ef08bd` baseline, `26380b1`, `2ae3c06`, `422f375`): **291 → 300 → 326 → 333**,
  exactly matching the implementation log's claim.

No live-DCS acceptance stage was in this milestone's scope (console/replay-only, per the plan's
explicit "No live-sortie acceptance is planned for this milestone" note) — review proceeds without
one, consistent with that scoping.

### Required Fixes

None.

### Optional Refinements

- `attention.py`'s `Sector` test coverage doesn't include an explicit "inside sector, outside
  radius" case (only "inside radius, outside sector" and "inside both" are directly tested) —
  low risk since the radius check short-circuits first and is independently tested without a
  sector, but a combined case would close the gap fully (optional).
- `_handle_attention`'s error message on an unrecognized level echoes back only the levels, not a
  hint that `attention <id>` alone queries — minor console UX polish, not a correctness issue
  (optional).

### Verdict
APPROVED

### Review Confidence
Full read — plan, implementation log, all touched source files (`attention.py`, `events.py`,
`contacts.py`, `tools.py`, `console.py`) read in full; test files spot-checked against each of the
six specific claims under review (all found accurate) plus a general scope/staging pass. Full
verification suite run directly, including an independent per-commit test-count reconciliation via
a disposable worktree rather than trusting the implementer's arithmetic.
