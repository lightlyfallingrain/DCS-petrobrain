# AC-B7 — Per-unit life on the existing mission-scripting bridge

- [ ] **AC-B7 — Add `getLife()`/`getLife0()` to the mission-telemetry hook's existing in-state
  per-unit loop and carry them on the same feed, so body-layer can tell a burning unit from a
  healthy one.** #status/open Filed at Architect stage, 2026-10-15, as the transport half of
  `[[BL-B72]]`'s burning emitter — `plans/emitter-visibility/plan.md` Stage A.

  **This is a field addition, not a mechanism.** `petrobrain-mission-telemetry-hook.lua` already
  runs an `O(N)` per-unit loop inside the `"scripting"` state calling `getVelocity()`, bridged at
  1 Hz via `net.dostring_in` and joined body-side by `unit_name`. `getLife()`/`getLife0()` were
  confirmed working per unit over that same channel by the closed probe
  (`docs/acceptance/2026-09-24-damage-and-firing-probes.md`, flown 2026-09-25, *"do not re-fly it"*).

  **The visible state is fire, not smoke**, bracketed to a life fraction of **(0.69, 0.84]**. The
  exact value inside that band, and whether it is global or per-type, is a tuning question and lives
  in body-layer's tuning file — not a feasibility question and not a reason to probe again.

  **The one number worth measuring**: this roughly doubles that loop's per-unit work, on DCS's own
  thread — the one place in this project where cost means cockpit stutter rather than service
  latency. The bridge already self-measures `bridge_call_ms` per poll, so the measurement is a log
  read, not a probe. Same standing argument as `[[AC-B4]]`: measure, do not reason.

  Open: whether the loop's existing live-units-only scope (statics carry no velocity API and are
  skipped) leaves burning statics invisible, and whether that matters.

  Decision for the user, carried in the plan: whether these fields ride on the existing
  `/unit_velocity/latest` feed — recommended, since the feed is already "per-unit mission-scripting
  state joined by `unit_name`" and only its *name* says velocity — or get their own endpoint.

  Related: `[[BL-B72]]` (the consumer), `[[AC-B8]]` (the event channel, a genuinely new mechanism),
  `[[AC-B4]]` (the unmeasured-DCS-cost precedent).
