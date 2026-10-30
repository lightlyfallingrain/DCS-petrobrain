---
name: contact-last-alt-m-flat-projection-trap
description: Contact.last_alt_m is the ownship's own altitude at a contact's last look, not the target's -- any new precision-pointing consumer that reads it directly (not through attack_run.py's remembered-altitude fix) reintroduces an already-fixed bug.
metadata:
  type: project
---

Found 2026-10-30 debugging the ATGM-run sight-tracking bug (`plans/atgm-run-sight-tracking/debug.md`,
branch `fix/atgm-run-sight-tracking`): the 9K113 sight's "belief" aim-source elevation ran away to
+72° on a stationary ground target because `body._look_targets` built every `LookTarget` straight
from `Contact.last_position`, whose altitude (`Contact.last_alt_m`) is documented as *"the most
recent look's own flat-projection altitude"* — concretely `perception.geometry.
project_from_bearing_range` assumes the target sits at **the observer's own altitude at the moment
of that look**, never the target's. Harmless while a contact is re-observed often (ownship altitude
barely changes between consecutive looks); seriously wrong once a contact is seen once and then not
re-observed while the aircraft's own altitude changes a lot in the gap — exactly an ATGM run's own
shape (pick a target high, then fly the descending approach).

**This bug class was already found and fixed once**, for a different consumer:
`belief/attack_run.py`'s own module docstring states *"never `Contact.last_alt_m`, which is the
ownship's own altitude at the last look, not the target's"* (Decision 4 REVISED) and ships
`remembered_target_alt_m` (was `_remembered_target_alt_m`, made public by this fix) — reconstructs
the target's real MSL altitude from the last tier-1 look as `ownship_at_observation.alt_m +
relative_direction.up_m`, which stays correct as the aircraft's *own* altitude later moves, because
it's an absolute number, not a relative snapshot. The 9K113 sight-pointing path (`body.
_look_targets` → `optic_policy.look_target_for`) was built independently (`[[BL-B80]]`, well after
`attack_run.py`'s own fix) and never adopted it — a second, independent occurrence of the identical
documented defect, in a different file, that went uncaught through Stage-1/2 review because nobody
checked whether `_look_targets`' existing (long-standing, pre-BL-B80) altitude handling was safe for
a *new*, precision-pointing consumer.

**How to apply:** before trusting `Contact.last_position`/`Contact.last_alt_m` for anything that
needs a real target altitude (not just gating/search-sweep tolerance), check whether
`belief.attack_run.remembered_target_alt_m(contact)` gives a better number (it does whenever the
contact has ever had a tier-1 look with a `relative_direction`) and prefer it, falling back to
`contact.last_position` unchanged only when it returns `None`. This is now `body.
_look_target_position`'s own pattern — reuse it rather than re-deriving a third copy. Also check
anywhere else a *new* consumer reads `Contact.last_position.alt_m`/`last_alt_m` directly: it is a
plausible site for the exact same latent bug, especially for short-range/precision use, and a grep
for `last_position` or `last_alt_m` outside `attack_run.py`/`body.py`'s now-fixed call site is the
fast way to check.

See also `.claude/agent-memory/dod/project_recurring_stale_state_on_transition.md` for this
project's broader pattern of a fix landing once and a second, independent code path reintroducing
the identical defect it was already written to prevent.
