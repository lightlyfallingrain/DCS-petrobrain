# SPU-8 intercom read/write probe

**Branch: none yet** — this is reconnaissance for Audio-adapter Slice 2
(`audio-adapter/ROADMAP.md`), not a feature branch. There is nothing to check out; this probe runs
against your current DCS install directly, no code changes deployed. Findings:
`aircraft-layer/research/2026-10-05-spu8-intercom-write-path-recon.md`.

**Batches with the Afghanistan projection check** — `docs/acceptance/2026-10-05-afghanistan-
projection-check.md` on branch `feature/multi-theatre-afghanistan` — same session at the DCS box,
different question. Do that one too while you're there.

## Why this card exists

Slice 2 wants Petrovich's audio gated by the real intercom switches: pilot's own Radio/ICS switch
(arg 456) and the co-pilot/operator's intercom power switch (arg 664) — the second one sits on the
**operator's** panel, which you can't reach by clicking from the pilot's seat. Static file reading
confirms the command mechanism exists and is already shipping (BL-6's AI-wheel trigger uses the
same `GetDevice():performClickableAction()` call), but nothing has ever tested whether a write to
an **operator-panel** control succeeds while you're sitting in the **pilot's** seat. That's a
one-flight test, and it decides whether Slice 2 can set arg 664 automatically or has to ask you to
flip it by hand.

## Setup

1. Back up your deployed `Saved Games\DCS\Scripts\Export.lua` (copy it somewhere safe).
2. You'll be adding a few lines to a copy of `Export.lua` — see "The probe" below for exactly what
   to add. This runs standalone; the collector does not need to be running.
3. Fly any Mi-24P mission, in the **pilot** seat.

## The probe

Add this inside your `Export.lua`'s `LuaExportAfterNextFrame` (or any function that already runs
every frame/second — the existing throttle in that function is fine, this doesn't need to run at
5 Hz):

```lua
local function probe_spu8()
    local dev0 = GetDevice(0)
    local function read(arg)
        local ok, v = pcall(function() return dev0:get_argument_value(arg) end)
        return ok and tostring(v) or "ERROR:" .. tostring(v)
    end

    log.write("SPU8_PROBE", log.INFO, string.format(
        "456(P-ICS)=%s 457(P-VOL)=%s 376(NET2)=%s 377(NET1)=%s 664(OP-ICS)=%s",
        read(456), read(457), read(376), read(377), read(664)))
end
```

Call `probe_spu8()` once per second from your export loop and let it log for ~15 seconds while you:

- **Move the pilot's own ICS switch (physically click it in the cockpit)** and the volume knob —
  confirms 456/457 read sensibly and that you've found the right controls before trusting 664.
- Leave 664 alone for this pass — just read it.

Then, **once**, add this write attempt (fire it once, e.g. gated on a frame-count check, not every
frame):

```lua
local ok, err = pcall(function()
    GetDevice(55):performClickableAction(3015, 1)   -- CMD_SPU8_O_ICS, arg 664
end)
log.write("SPU8_PROBE", log.INFO, "write attempt ok=" .. tostring(ok) .. " err=" .. tostring(err))
```

Then keep logging the five reads above for another ~10 seconds to see if 664 changed and held.

4. Read `Saved Games\DCS\Logs\dcs.log`, search for `SPU8_PROBE`.
5. Restore your real `Export.lua` afterward.

## Pass criteria

There's no pass/fail here — it's a measurement, either answer is useful. What decides Slice 2's
design is simply: did 664 change value after the write attempt, and did it hold (not get reset by
some other system)?

## Bring back

1. **The five `get_argument_value` readings** — 456, 457, 376, 377, 664 — before any write, in
   whatever position each switch happened to be in (and note what position, if you remember moving
   one).
2. **456 and 457 across knob/switch travel** — flip 456, turn 457 through its range, read back
   between moves. Confirms the read channel works at all before trusting a negative result on 664.
3. **A single yes/no: did `GetDevice(55):performClickableAction(3015, 1)` move arg 664?** Quote the
   `before`/`after` values from the log, and whether it held for the following ~10 s rather than
   snapping back.
4. If the write failed (`ok=false`) rather than just not-moving: the `err` value from the log.
5. Anything that surprised you — including if the pilot's own 456/457 behaved unexpectedly, since
   that would undercut the whole premise of this probe.
