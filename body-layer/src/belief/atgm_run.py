"""The ATGM run's own per-poll state (`[[BL-B67]]`, `plans/bl-b67-atgm-run/
plan.md`). **Stage 1 only** -- the run skeleton that ties the run's
lifecycle to `belief.attack_run.AttackRunState` (`body.py`'s one
construction site, the engage-apply block) and the run's own target
contact id. The full "when" -- `decide`, the state machine (Preparing ->
Tracking -> InFlight -> Resetting -> Selecting -> Tracking/Empty, plus
Refused), the range latches, the tracked missile -- is Stage 3, not built
here.

A companion state beside `runner.attack_run_state`, never a replacement
and never a field on `AttackRunState`: that state is reset wholesale on
every re-point (`attack_run.py`'s `decide`, "Resets `state` to fresh the
moment `contact.id` differs from `state.last_contact_id`"), which would
silently drop a weapon field -- the recurring stale-state shape,
`.claude/agent-memory/dod/project_recurring_stale_state_on_transition.md`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AtgmRunState:
    """The ATGM run's own state, carried on `body.ConsolePerceptionRunner`
    beside `attack_run_state` -- replaced wholesale each poll, never
    mutated, the same replay-determinism discipline every other state on
    that class already follows. `None` on the runner means "no ATGM run
    engaged" -- the same convention `attack_run_state` itself uses.

    Stage 1 carries only `contact_id`, the run's own target -- the one
    thing both the "Observ on, wait." dispatch (`belief.crew_console.
    drain_atgm_engage`) and the sight lock/single-unit aim threading
    (`body.py`'s poll loop) need to exist at all. The phase/in-flight/
    selection fields the full plan describes are Stage 3's own addition,
    not built here; every `AtgmRunState(` construction site this stage
    adds is a fresh instance on `engage ... missiles`, never a `replace()`
    carrying anything forward -- there is nothing yet to carry."""

    contact_id: str
