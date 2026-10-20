---
name: project-emitter-tracker-watchdog-staleness
description: REFUTED as the explanation for the 2026-10-20 Vulcan-2 false reading -- the live entry's own since_sim showed a fresh (0.2s-old) SHOOTING_START, not a stale latch. The watchdog mechanism itself is still real (direct code read); the transferable lesson is to check an entry's own freshness before reaching for a staleness explanation
metadata:
  type: project
---

Session 2026-10-20, investigating why a visibly-player-targeting M163 Vulcan read
`targets_ownship: false` in `/firing/latest` (`docs/acceptance/2026-10-20-sortie-feedback.md` F6).
**This session's first-pass hypothesis here was wrong, corrected by the coordinator from evidence
already in hand — kept as the correction, not the original guess**, per this role's "label an
inference as one all the way to its destination" discipline.

**The mechanism is real (direct code read, not in question)**: `collector/firing_receiver.py`'s
`EmitterTracker._apply` **fully replaces** the `ActiveEmitter` entry for a unit's name on every new
`S_EVENT_SHOOTING_START` — `targets_ownship` included, not merged or left over from a prior entry.
A `SHOOTING_END` only tightens `expires_at_sim`; it never itself produces a stale `targets_ownship`.
Without a received `SHOOTING_END` (unit still alive), an entry *can* in principle survive
`FIRING_WATCHDOG_S` (180s) past its `since_sim` with a frozen value from one old engagement — **but
only if no newer `SHOOTING_START` has arrived for that name since.** A fresh `SHOOTING_START`
always resets it, `since_sim` included.

**Why this session's original hypothesis was wrong**: it cross-referenced a stale t≈289s engagement
from the **wrong mission's** `debrief.log` (a mission-restart mtime coincidence — see
[[reference_debrief_log_for_firing_event_ground_truth]]'s mission-attribution-pitfall caveat)
against the F6 sortie's t=335.7s query, without first checking the live entry's own freshness. The
coordinator already had that check: `since_sim: 335.461` at query time `335.692` — a
`SHOOTING_START` **0.2 seconds old**. A 0.2s-old entry cannot be a 45-second-stale watchdog latch;
the hypothesis was refuted by data that was already available, not by anything newly probed this
session.

**The transferable lesson**: *before* reaching for a staleness/latch explanation for an unexpected
live value, check the entry's own freshness indicator (`since_sim` here, or the equivalent in
whatever system is being diagnosed) first. A plausible, code-confirmed mechanism being *possible* is
not evidence it is *this* reading's cause — verify it against the specific instance's own
timestamp before building a timing argument on top of it, not after.

**What the fresh-`false` reading's real cause turned out to be**: confirmed genuine mismatch, not a
code defect — the specific `SHOOTING_START` the collector read really did target the player's
wingman, not the player, per this sortie's own `debrief.log` once the mission ended. Full account:
`aircraft-layer/research/2026-10-20-aaa-firing-target-recon.md`'s "Final confirmation" section. Not
this memory's subject beyond that pointer — this memory is about the staleness-mechanism lesson
above, which stands on its own regardless of what the eventual real cause was.
