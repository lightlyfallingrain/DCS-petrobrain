### Performance Review

BL-B102 ("that"/"it" referent resolution), branch `feature/that-it-referent`, tip `58e66a8e`.
Batch: Stages 1-4 (core mechanism, `where_is_it`/`mark_target`, `follow`/`select_target`/
`engage`/`watch` family, regression) — one pass per `CLAUDE.md`'s "once per batch" rule.

No hard real-time budget applies yet (Petrobrain Runtime work has not started). Assessed against
this phase's actual constraints: no per-request allocations on genuinely hot (per-poll) paths,
precompute/batch over per-item work, async offload for anything heavy. Single-user, LAN-only
project — proportionate review, not an exhaustive audit.

### Findings

#### `resolve_referent` / `_report_scope(restrict_to_ids=...)` full-contact iteration
- **Location:** `belief/crew_console.py:4257` (`_report_scope`), called from
  `_resolve_referent_target` (`crew_console.py:2539`) via `resolve_referent`'s `qualifier_scope`
  callback (`belief/referent.py:150-197`).
- **Risk:** `_report_scope` with `restrict_to_ids` set still calls `get_contacts(self.store,
  now_sim, ...)` and iterates **every current contact** to find the handful whose id is in
  `restrict_to_ids`, rather than looking those ids up directly. This is a full-dataset scan to
  answer a bounded-set query.
- **Action:** MONITOR.
- **Why not NOW:** This is the pre-existing pattern `_report_scope` already used for plain
  `report`/`_resolve_attack_target` (unfiltered case) — `restrict_to_ids` reuses rather than
  worsens it, and the plan explicitly chose this reuse over a second filtering mechanism
  (`plan.md`'s "Facts" section). The call site fires once per voice command (confirmed: every
  `_resolve_referent_target` call site is inside a `_handle_*` command handler, never inside the
  per-poll `tick`/`drain_events`/`CalloutScheduler.tick` path), and contact counts in this
  project's scenarios are bounded by the operating envelope (a handful to low tens of live
  contacts per sortie, not hundreds) — a human-paced voice command scanning tens of contacts is not
  a measurable cost. Flagging because the scan is `O(all contacts)` where `O(len(restrict_to_ids))`
  (typically 1-5, bounded by `REFERENT_WINDOW_S`) would be structurally cheaper, and if a future
  milestone pushes contact counts materially higher (e.g. a much larger battlefield simulation) or
  this method moves onto a genuinely hot path, it should be revisited then — not today's problem.

#### `ReferentMemory.record`/`_prune` — list rebuild per call
- **Location:** `belief/referent.py:73-94`.
- **Risk:** `_prune` rebuilds `self._mentions` with a full list comprehension on every `record`
  and every `recent`/`last` call.
- **Action:** MONITOR (effectively none).
- **Why not NOW:** The list is bounded by `REFERENT_WINDOW_S` (60s default, 15-180s tunable) at
  realistic speech rates (a handful of lines per minute) — a few dozen entries at most. `record`
  only runs from inside `CrewConsole._print`, gated by `if lines and mentions`, so it fires once
  per actual spoken reply, not per poll. No allocation concern at this scale.

#### `_resolve_group_referent_target` — throwaway `ReferentMemory()` per call
- **Location:** `belief/crew_console.py:2605-2634`.
- **Risk:** Allocates a new `ReferentMemory` instance and re-runs `resolve_referent`'s
  group-reduction logic through it, purely to reuse that function's reduction step rather than
  duplicating it inline.
- **Action:** MONITOR (effectively none).
- **Why not NOW:** This is a once-per-voice-command path (same call frequency as the rest of
  `resolve_referent`), one small object, no loop. A deliberate reuse-over-duplication tradeoff
  (explicitly reasoned in the function's own docstring) — the right call at this cost.

#### Mention recording inside `_print` / `CalloutScheduler.tick`
- **Location:** `belief/crew_console.py:5116-5203` (`_print`), `belief/callouts.py:1030-1376`
  (`CalloutScheduler.tick`, `last_spoken_mention` writes).
- **Risk:** None credible. `_print`'s `self._referent_memory.record(...)` is gated on `if lines
  and mentions` — it only runs when something is actually said, not on every poll tick.
  `CalloutScheduler.last_spoken_mention` is a single `Mention` dataclass construction on the
  already-per-poll callout path, only when a callout is actually spoken (same cost class as the
  `text`/`busy_until_sim` work immediately beside it). No new per-poll-always cost was added.
- **Action:** none needed.

### Verdict
APPROVED
