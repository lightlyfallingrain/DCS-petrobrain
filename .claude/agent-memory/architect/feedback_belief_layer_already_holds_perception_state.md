---
name: belief-layer-already-holds-perception-state
description: Before planning a perception->belief seam for FOV/mask/visibility, check Contact's own observability fields — ContactStore.tick already stamps them once per tick and callout_observable is the sanctioned read
metadata:
  type: feedback
---

**Before designing any perception→belief coupling for visibility, FOV or cockpit masking, check what
`Contact` already carries.** It carries `last_observable_sim`, `los_masked_since_sim`,
`live_los_clear`, `last_seen_sim`, `first_seen_sim`.

**Why:** `ContactStore.tick(ownship=...)` already evaluates `perception.cockpit_mask.is_visible`
against every contact once per tick and stamps `last_observable_sim` (`_callout_may_speak`).
`ContactStore.callout_observable` is explicitly documented as *"a read of bookkeeping, not a second
mask computation"* — recomputing the geometry elsewhere would let two copies drift. So the seam is
**already crossed, once per tick, in the sanctioned place**, and a plan that proposes a new one is
proposing a duplicate.

Two details that decide designs:

- **It tests the cockpit mask, not the gaze cone.** Deliberate: Decision 1 of
  `plans/sortie-2026-09-26-fixes` is explicit that a contact merely out of current gaze must still
  get its tracking update — only *physically unseeable from any gaze direction* may be gated.
- **It is a remembered test with a grace window**, `now_sim - last_observable_sim <
  CALLOUT_OBSERVABILITY_GRACE_S` (10 s), and its docstring says the window *must* be measured from
  the last confirmed sighting rather than the first failed check. A raw current-mask test churns on
  every yaw.

**How to apply:** when a direction says "ignore what Petrovich cannot see", separate **cost pruning**
(the cheap test decides *whether* expensive work runs) from **content filtering** (unseen things are
omitted from the answer). In the belief layer these are not the same operation, because a belief
contact is there *because* it was seen — it is remembered, not undetected, and the decay ladder
(`OBSERVED_WINDOW_S` 16 → `POSITION_HALF_LIFE_S` 30 → `LOST_THRESHOLD_S` 120) is what retires it.
Content filtering on current visibility makes an answer change as the pilot's head turns, and
because the member set is also `GroupStore.reconcile`'s input, a filter upstream of clustering makes
a yaw look like a split/merge and churns the group identity `BL-12` exists to stabilise.

**Settled by the user, 2026-10-13: cost pruning, not content filtering** — *"Yes, I mean 1, not 2"*.
Put the gate on the caller (does this run at all), not inside the derivation (what does it return).
`callouts.py`'s push loop is the precedent: it tests `callout_observable` with **`any` member
observable, not `all`**, because *"a group straddling the cutoff is a group Petrovich can genuinely
see"*. Reuse that predicate rather than writing a second one.

Recorded because the literal reading of the direction was the wrong one, and a later pass reading
only the sentence would re-derive it. Full account: `plans/group-collapse/plan.md` Decision 6/6a and
`plans/group-collapse/scratchpad/probe_fov_pruning.py`.
