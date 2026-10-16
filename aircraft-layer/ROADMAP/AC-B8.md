# AC-B8 — A production firing-event channel over the mission-scripting bridge

- [ ] **AC-B8 — Productionise the firing-event probe: a Hook that registers `world.addEventHandler`
  in the `"scripting"` state, accumulates `S_EVENT_SHOOTING_START`/`_END` and `S_EVENT_SHOT`
  in-state, drains them per 1 Hz poll, and publishes a pollable emitter snapshot.** #status/open
  Filed at Architect stage, 2026-10-15, as the transport half of `[[BL-B73]]` and `[[BL-B74]]` —
  `plans/emitter-visibility/plan.md` Stage B.

  **Feasibility is closed, not open.** The 2026-09-25 probe
  (`docs/acceptance/2026-09-24-damage-and-firing-probes.md`, *"do not re-fly it"*) logged
  `register: ok=true` and a ground gun unit's `SHOOTING_START` naming the player as its target.
  Desk research behind it:
  `aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`.
  **Gun rounds are not objects in `LoGetWorldObjects`** (rockets are), so the event is the only
  possible channel — there is no world-object fallback to degrade to.

  **The hard part is not the Hook, it is the state the collector has to hold.** The channel
  publishes a *polled snapshot* of which units are currently emitting, so body-layer stays
  poll-shaped and replay-deterministic. That means the collector owns:

  - a **latch**, because `START` and `END` can arrive in the same drained batch and a sub-poll burst
    must survive at least one body-layer poll (`FIRING_MIN_VISIBLE_S`);
  - a **watchdog**, because a `START` whose `END` never arrives must not leave a unit firing forever
    (`FIRING_WATCHDOG_S`). **Corrected 2026-10-16, Stage B review**: this used to name "a unit
    destroyed mid-burst" as the case, which conflates two different ones. Destruction is already
    owned, immediately, by the `S_EVENT_DEAD`/`_CRASH` removal path; the watchdog's only remaining
    case is a dropped `END` for a unit that is still alive. Since firing events are paired and units
    fire bursts rather than for tens of seconds (user direction, 2026-10-16), that case does not
    occur in practice, so `FIRING_WATCHDOG_S = 180.0` is a pure backstop — **do not tune it down for
    looking long**, a short value there was the Stage B review's actual finding;
  - **per-kind death semantics**: a dead unit's gun-fire entry is removed, a launch-smoke entry is
    kept, because smoke outlives the launcher;
  - **a clean slate on `onSimulationStart`** and on bridge reconnect.

  The full transition/field matrix is in the plan's Co-moving Fields table and should be read before
  implementing, not after.

  **Ship it as a production Hook, not by promoting the probe** — `[[AC-B5]]` records that a probe
  Hook left deployed taxes every sortie.

  **Adjacent risk this channel inherits**, flagged in the plan: `petrobrain-line-of-sight-hook.lua`
  caps at `MAX_SIGHTLINES_PER_CALL = 128` **nearest-first**, so truncation drops the *far*
  candidates — exactly the distant emitters this whole feature exists to admit, and gate 4 is
  fail-closed. Splicing the current emitter ids into that call's sort key belongs with this work.

  Related: `[[BL-B73]]`, `[[BL-B74]]`, `[[AC-B7]]`, `[[AC-B5]]`, `[[AC-B3]]`.
