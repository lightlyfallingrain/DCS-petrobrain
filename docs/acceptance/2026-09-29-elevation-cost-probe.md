# Elevation cost probe — flight card

**Nothing to check out.** This flight tests a Hook script already deployed on the Windows box by
the Windows-box Claude session. Its source lives on branch `investigate/terrain-elevation-source`
(commit `dbbbbd6`), **unpushed**, so nothing about it is readable from the Mac repo — every claim
below about what the hook does is relayed from that session, not verified here.

**This is not the group-reporting acceptance sortie.** Fly them separately. The probe may hitch the
frame by design, which is exactly what would contaminate a judgement about whether Petrovich's
callouts feel right — and vice versa.

## What this flight settles

The bridge cost question is already answered for `getVelocity`: 0.5 ms fixed + ~2.6 µs per item,
p99 of 8 ms at 568 units, read out of a sortie that was already in `dcs.log`. Two things that
figure cannot tell us:

1. **Does `land.getHeight` work through the mission bridge at all?** High confidence, never
   demonstrated — every prior elevation probe ran offline through mission-editor triggers.
2. **What does it cost, and does it block DCS's own frame?** A different engine call from
   `getVelocity`, and the 20 ms outliers in the existing data are the hint that a `dostring_in`
   payload might stall the renderer rather than merely taking time.

The second is the prize, and **half of it can only be answered by you** — the log can record
milliseconds, it cannot record whether the aircraft stuttered.

## Setup

Minimal: **DCS alone**. No collector, no body-layer, no brain, no audio adapter. The hook writes
straight to `dcs.log`.

1. Start DCS on the Windows box.
2. Load **any Syria mission** — the probe's eight reference coordinates are Syria-specific.
3. Let it run. The hook fires ~10 s after mission start on its own.

*(UNVERIFIED — the hook's trigger timing, its Syria dependency and its output format are all as
relayed by the Windows session. None of it could be run or read from the Mac.)*

## Block A — did it run, and did it return real heights?

**Do:** nothing. The hook checks `land.getHeight` through the bridge against 8 coordinates whose
true heights are already on record.

**Expect:** eight comparisons in `dcs.log`, matching the recorded values. A mismatch is as
interesting as a match — it would mean the bridge reaches the function but returns a different
surface from the one the earlier mission-editor probes read.

**Record:** nothing by hand. It is in the log.

## Block B — THE PRIZE: did the aircraft stutter?

**Do:** fly normally for the first minute after mission start, and pay attention at the ~10 s mark
and for the few seconds after. The hook times batches of 1, 100, 500 and 2601 points against a
zero-work null call, 20 repeats each.

**Expect:** by extrapolation from `getVelocity`, a 2601-point batch is ~7 ms of bridge time — below
one frame at 60 fps. If that extrapolation holds you should feel nothing at all.

**Record, in your own words:**

- Did you feel a stutter, hitch or freeze? Roughly how long?
- Did it happen once, or several times in a row (the batches run in sequence, so several hitches
  of growing length would point straight at batch size)?
- Anything on screen that looked like a dropped frame rather than a pause?

**A clean "felt nothing" is a real result**, not a non-answer — it is what clears live probing to
be designed around.

## Block C — a second bridge data point (optional, costs nothing)

**Do:** stay airborne two or three minutes with whatever units the mission contains.

**Expect:** the existing telemetry hook keeps logging `bridge_call_ms` at 1 Hz throughout.

**Record:** nothing by hand — it is another sample of the same figure at a different unit count.

## Not testable on this flight

- **The `.surface5` file route.** Confirmed to hold elevation (129/129 known heights fell inside
  the right tile's band, against 71/129 for a shuffled null control) but only the envelope decoded;
  per-node heights are still unread. Nothing about it is exercised here.
- **Grouping, the confirm band, the LOS tolerance.** Different flight, different card
  (`docs/acceptance/2026-09-29-group-reporting-sortie.md`).

## Bring back

1. **`dcs.log`** — or the probe's lines out of it. Everything numeric lives there.
2. **Did it stutter, and for how long?** The one thing the log cannot answer.
3. Whether the eight height comparisons matched.
4. **Anything that surprised you is worth more than anything on this list.**
