### Implementation Summary

`BL-B76` Step 1: widen `belief_truth_log._write_attack_run_tripwire` so it can distinguish
"blocked" (`live_los_clear=False`) from "no answer yet" (`live_los_clear=None`) for the
attack-run target specifically, and both from "not evaluated this poll at all." Logging only --
no change to `perception/visibility.py`, admission, `Contact`, or anything the attack run says.

**The hard part named in the task was the join**, and it required designing a new, persistent
cache inside `belief_truth_log.py` rather than reusing anything that already existed:

- `Contact` retains **no ground-truth `object_id` at all** (checked: `grep -n object_id
  body-layer/src/belief/contacts.py` — the only hits are docstring prose about continuity, never
  a field). This is deliberate, the no-omniscience boundary (`belief/percept.py`) — belief must
  not hold a DCS identifier.
- A rejected `DetectionTrace` entry therefore has an `object_id` but never an `observation_id`
  (`observation_id` is only set on an `ADMITTED` row, once clustering/emission have run) -- so
  the existing `observation_id_to_contact_id(store)` join, which is what the original tripwire
  loop used, cannot resolve a rejected entry to any contact.
- `NakedEyePerceptionSource` already keeps exactly this kind of persistent `object_id ->
  last_observation_id` map (`_object_id_to_last_observation_id`, module docstring point 6), but
  it is private perception-layer state with no public accessor, and reaching it from
  `belief_truth_log.py` would mean threading the live `NakedEyePerceptionSource` instance through
  `write_poll` and both `logger.py` call sites -- a bigger change than "logging only," and the
  plan's own scope line says this is a `belief_truth_log.py`-only change.

**Chosen join**: `BeliefTruthLogWriter` now keeps its own `dict[int, str]` (`object_id ->
contact_id`) plus a parallel `dict[int, float]` (`object_id -> last-seen t_sim`), updated every
poll (`_update_object_id_contact_cache`) from that poll's `ADMITTED` entries -- the same
`entry.object_id` plus every id in `entry.cluster_member_object_ids`, mapped to whatever contact
`observation_id_to_contact_id` resolves the entry's `observation_id` to. `_object_ids_for_contact`
reads it back for a given `contact_id`, excluding any entry older than `OBJECT_ID_MEMORY_S`
(reused from `belief.decay`, not a new constant) -- the same window `belief.decay.
object_id_continuity_valid` already uses to decide how long a DCS `object_id` is still trusted to
name the same real vehicle.

**Why this is sound enough to ship, per the task's own bar** ("if the join cannot be made sound,
say so and stop"): a stale or wrong cache entry can only ever cause a **miss** (the poll reads
`"absent"` instead of `"rejected"`), never a wrong contact's rejection being attributed to this
one -- the cache is only ever consulted for `attack_run_target_contact_id` itself, and is only
ever populated from an `ADMITTED` row that already resolved to a real contact that same poll. The
one accepted residual risk is DCS reusing an `object_id` for a different real unit within the
`OBJECT_ID_MEMORY_S` window -- already an accepted risk elsewhere in this codebase
(`object_id_continuity_valid`'s own docstring), not a new one introduced here.

**Cache is warmed every poll, not only when a run is active.** Originally I only updated it
inside `_write_attack_run_tripwire` (called only when `attack_run_target_contact_id is not
None`), which meant a newly-started run's very first poll would always read `"absent"` even if
the target had been continuously observed for the whole sortie before the run began. Moved the
cache update to the top of `write_poll`, unconditional on whether a run is active, so the cache is
already warm the instant a run starts.

### Files Changed

- `body-layer/src/belief_truth_log.py`:
  - New import `belief.decay.OBJECT_ID_MEMORY_S`.
  - `BeliefTruthLogWriter.__init__`: two new instance dicts, `_object_id_to_contact_id` and
    `_object_id_last_seen_sim`.
  - `write_poll`: calls `_update_object_id_contact_cache` unconditionally every poll; passes
    `now_sim=ownship.t_sim` into `_write_attack_run_tripwire`.
  - `_write_attack_run_tripwire`: rewritten. First searches for an `ADMITTED` match (unchanged
    logic, now named `outcome="admitted"`); if none, searches rejected entries whose `object_id`
    is in the cache's set for this contact (`outcome="rejected"`, `gate_outcome` = the
    `GateOutcome.value`); else `outcome="absent"`. `join_skew_s`/`live_los_clear` are read off
    whichever entry was found, admitted or rejected alike -- `annotate_los` runs upstream of the
    gate chain, so a rejected `TERRAIN_LOS` row already carries the real `live_los_clear`
    (`False` or `None`) exactly as an admitted row would.
  - New methods `_update_object_id_contact_cache`, `_object_ids_for_contact`.
- `body-layer/tests/test_belief_truth_log.py`: four tests added/extended (see below).

### Row shape change -- backward compatibility

`present_in_snapshot` is **kept**, but its meaning has widened: it used to be `True` only for
`"admitted"`, and is now also `True` for `"rejected"` (`outcome != "absent"`). Two new keys are
added: `"outcome"` (`"admitted"` / `"rejected"` / `"absent"`) and `"gate_outcome"` (the rejecting
gate's `GateOutcome.value`, `None` for `"admitted"`/`"absent"`). `join_skew_s`/`live_los_clear`
keep their existing names and types.

**This needs a `sortie-log-triage` skill check**, flagged per the task's own instruction: any
reader of `present_in_snapshot` that assumed it meant "admitted" rather than "evaluated at all"
should be re-pointed at `outcome`. I did not audit or change that skill -- out of this logging-only
change's scope, and the skill lives outside `body-layer/`.

### Tests Added

- `test_write_poll_attack_run_tripwire_present_in_snapshot` (extended) — asserts
  `outcome == "admitted"` and `gate_outcome is None` alongside the existing assertions.
- `test_write_poll_attack_run_tripwire_absent_from_snapshot` (extended) — asserts
  `outcome == "absent"` and `gate_outcome is None`.
- `test_write_poll_attack_run_tripwire_rejected_terrain_los_blocked` (new) — seeds the cache with
  an admitted poll, then rejects the same `object_id` at `GateOutcome.TERRAIN_LOS` with
  `live_los_clear=False`; asserts `outcome="rejected"`, `gate_outcome="terrain_los"`,
  `live_los_clear is False`.
- `test_write_poll_attack_run_tripwire_rejected_terrain_los_no_verdict` (new) — same shape, with
  `live_los_clear=None`; asserts the same `outcome`/`gate_outcome` with `live_los_clear is None` --
  pins the `False`-vs-`None` split that is the whole point of this change.
- `test_write_poll_attack_run_tripwire_three_states_are_distinguishable` (new) — one writer across
  three polls (admitted, rejected, absent); asserts the three rows' `outcome` sequence is
  `["admitted", "rejected", "absent"]` and that the rejected and absent rows differ in
  `present_in_snapshot` despite both previously reading `False` under the old code.

**Counterfactual run** (per the project's own "a counterfactual is evidence only if you ran it"
rule): temporarily replaced the rejected-entry lookup with a hardcoded empty `frozenset()` (the
exact bug this change fixes -- "never find a rejected match") and reran the three new/affected
tests; all three failed for the stated reason (`'rejected'` not found, falling through to
`'absent'`). Restored from a file copy taken before the injection (`shasum`-verified identical
before/after), then reran the full suite to confirm no deletions survived.

### Checks

(only `body-layer/` touched)

- `ruff format --check`: pass (`133 files already formatted`)
- `ruff check`: pass (`All checks passed!`)
- `mypy --strict` (`cd body-layer && .venv/bin/mypy src`): pass (`Success: no issues found in 60
  source files`)
- `pytest -q`: pass -- `2060 passed, 4 xfailed` (baseline was `2057 passed, 4 xfailed`). Net +3
  passing tests: 3 new test functions added (the two listed above plus the three-states test);
  the other two listed changes only added assertions to existing test functions, so they add no
  new count. xfailed count unchanged.

### Notable Discoveries

- **The plan's own hint — "look at what `Contact` actually retains about its member object ids" —
  resolves to "nothing."** `Contact` has no object-id field anywhere; the only sound join source
  turned out to be a self-maintained cache inside this already-sanctioned ground-truth-plus-belief
  module, not a field to read off belief.
- **`NakedEyePerceptionSource._object_id_to_last_observation_id` already does a more sophisticated
  version of this same correlation** (majority-overlap voting across cluster splits/merges,
  module docstring point 6), but it is private and perception-layer, and reaching it would have
  been a materially bigger change than this task's "logging only" scope. If a future stage needs
  this join to be as robust as that one (e.g. because the cache's simpler "last admission wins"
  rule starts mis-attributing object_ids across group splits in practice), that existing map is
  the thing to expose a public accessor for, rather than reinventing its voting logic here.
- **No new behaviour-affecting constant was needed** — `OBJECT_ID_MEMORY_S` already exists in
  `belief.decay` for exactly this kind of trust-window question, and reusing it keeps this change
  honest about not introducing a second number to tune for the same concern.
- **This entry's own cross-key-coupling note doesn't apply here**: the only constant touched is
  reused, not new, and it is already tuned/bounded elsewhere.
