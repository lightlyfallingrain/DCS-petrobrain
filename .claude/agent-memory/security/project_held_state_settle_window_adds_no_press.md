---
name: held-state-settle-window-adds-no-press
description: how to verify a settle/debounce window that holds a derived boolean cannot itself cause a wrong cockpit write — check it only reassigns the boolean, never calls the write primitive
metadata:
  type: project
---

`fix/apw-seat-swap-settle` (2026-11-18, `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`):
a settle window added to absorb a sensor-lag false edge (`ai_pilot_parked_active` briefly `true` on
a pilot->operator seat swap, arg 852 unstow lag) holds a derived boolean at its pre-switch value for
a fixed delay instead of recomputing it immediately.

**Why this is a security question at all, briefly**: the project's actual cockpit-write primitive
is `GetDevice(30):performClickableAction` (the one "write access to the computer"-shaped surface in
this DCS-Lua layer per root `CLAUDE.md`'s "Access to the computer" scope item), so any new state-hold
logic near it is worth a quick check that it cannot itself fire a write or get stuck.

**How to verify quickly**: grep the settle/hold branch itself (not the whole function) for the
write primitive's call sites. If the branch only reassigns local booleans and the write calls live
entirely in the pre-existing code that reads those booleans *afterward*, the window changes which
branch fires later, never adds a write. Separately confirm the window's own close condition
(`t >= until_t`) is checked unconditionally every frame (not gated on the same condition that could
re-arm it), and that leaving the triggering state (here: `in_operator_seat` going false) always
short-circuits the hold regardless of a still-open timer — both guarantee no path can hold a stale
value indefinitely even under rapid toggling of the triggering condition.

**How to apply**: the next time a plan/fix adds a debounce or settle window near any
`performClickableAction` (or an equivalent direct-write cockpit primitive), do this same two-part
check (no write inside the hold branch; the hold always has an unconditional close path) before
treating it as in-scope for Security at all — if both hold, it is very likely a correctness
question (Reviewer's, per root `CLAUDE.md` "Scope" in this role's own file) rather than a security
one, since nothing about reachability or write-surface changed.
