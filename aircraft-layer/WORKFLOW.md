# Aircraft Layer — Cross-Machine Workflow

Live-process workflow: nothing here is a one-off file copy like
`world-model/WORKFLOW.md`'s Dropbox-symlink flow — the collector is a
long-running process on the Windows box, polled live over LAN. See
`plans/aircraft-layer/plan.md` for the design this implements.

## Deploy Export.lua (Windows box, once per change)

Copy `aircraft-layer/dcs-export/Export.lua` to
`Saved Games\DCS\Scripts\Export.lua`. Canonical source lives in this repo;
never edit the deployed copy in place — same convention as
`world-model/tools/wsl/` -> `win-mac-sync/run-wsl/`. A synced copy is kept at
`win-mac-sync/to-windows/aircraft-layer/Export.lua` for machines pulling via
that sync folder instead of a direct repo checkout.

Optional: create `Saved Games\DCS\Scripts\aircraft_layer_debug.flag` (any
content, even empty) to turn on verbose logging to
`Saved Games\DCS\Logs\aircraft_layer_debug.log`.

## Run the collector (Windows box)

```
cd aircraft-layer
set PYTHONPATH=src
python -m collector
```

(PowerShell: `$env:PYTHONPATH="src"`; macOS/Linux: `PYTHONPATH=src python -m collector`.)
`src` isn't installed as a package — `PYTHONPATH` is required, not optional; `python -m collector`
alone fails with `No module named collector`.

This starts two servers in one process, sharing one in-memory cache:

- **Export.lua listener** — loopback-only (`127.0.0.1:7790` by default,
  `--host`/`--port` to override). Never exposed off-box; Export.lua connects
  to it directly, same machine.
- **Telemetry API** — LAN-facing (`0.0.0.0:7791` by default, `--api-host`/
  `--api-port` to override). This is the port the Mac (or any LAN client)
  reaches.

Add `--debug` for per-line DEBUG logging (received/parsed telemetry), or
`--dump-interval N` to change how often the latest sample prints to stdout
(default 1s; this stdout dump is separate from the LAN API and useful for
watching the pipeline without a separate HTTP client).

## Firewall (Windows box, one-time)

Windows Firewall blocks inbound connections to a Python process by default.
Allow inbound TCP on the API port (7791, or your `--api-port` value):

```
netsh advfirewall firewall add rule name="aircraft-layer-api" dir=in action=allow protocol=TCP localport=7791
```

Scope this to your LAN profile, not Public, if prompted. The Export.lua
listener port (7790) needs no firewall rule — it's loopback-only and never
receives connections from off-box.

## Query from the Mac

```
curl http://<windows-box-lan-ip>:7791/telemetry/latest
```

Returns the most recent sample as a JSON object, or JSON `null` if nothing
has been received yet (not an error — Export.lua may not have connected, or
DCS may not be running a mission). Poll as often as your consumer needs;
there's no separate delta/since endpoint — one was implemented and then
dropped (stage 5) once live pause testing showed its receipt-time cursor
returned every motionless sample as "new," which wasn't a useful signal,
and the consumer side doesn't need gap-free history anyway.

See `aircraft-layer/src/schema/__init__.py` for the full field list/units in
each sample.

```
curl http://<windows-box-lan-ip>:7791/world_objects/latest
```

Returns the most recent `LoGetWorldObjects` ground-truth snapshot (raw
position/type/coalition/heading only, no detection filtering — that's
body-layer's job) as a JSON object, or JSON `null` on the same "not an
error" basis as `/telemetry/latest`. Added by
`plans/pb1-perception-logger/plan.md` stage 3. See
`aircraft-layer/src/schema/world_objects.py` for the field list/units.

## PB-1.5 ambient-detection probe (spike, temporary)

`aircraft-layer/dcs-export/Export.probe-pb15.lua` is the production
`Export.lua` plus one extra instrumentation block. It exists to answer the
last question left open by
`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`:

> During a naked-eye-only pass, does **any** exported Lua value change at the
> moment Petrovich's ambient `"N CONTACTS, H O'CLOCK"` callout fires?

Delete the file once that is settled — it must not drift into a second
production script.

**What it logs** (to `Saved Games\DCS\Logs\pb15_probe.log`, separate from
`aircraft_layer_debug.log`):

- The full `list_indication(6)` tree, **only when it changes**. No named-leaf
  targeting: Session 5 retired `upper_list_text`/`upper_upper_list_text` as
  candidates, so the whole tree is the subject.
- A `list_cockpit_params()` sweep, **only the params that changed**. Params
  that change more than 8 times are retired permanently as volatile (rotor
  RPM, needles, gauges) and logged once as `RETIRED (volatile)`. What survives
  is the set of rarely-changing params — the shape a detection-state flip has.

**Setup**

1. Copy `aircraft-layer/dcs-export/Export.probe-pb15.lua` to
   `Saved Games\DCS\Scripts\Export.lua` (overwriting the production copy —
   this file is a superset, so the collector keeps working unchanged).
2. Create `Saved Games\DCS\Scripts\pb15_probe.flag` (empty file). Without it
   the probe block is a no-op.
3. Delete any stale `Saved Games\DCS\Logs\pb15_probe.log` so the run is clean.

**Flight protocol** — the discipline matters more than the flying:

- Place a handful of ground targets (trucks/armour are the easiest classes to
  get a callout on) at varied ranges out to ~5 km.
- **Never slew the ASP-17.** The whole point is to isolate ambient spotting
  from the scope channel; one slew contaminates the sortie.
- Turn Petrovich's observation mode on and fly passes that bring the targets
  into view.
- **Mark every callout in-band.** When you hear `"N CONTACTS, H O'CLOCK"`,
  immediately flip one distinctive cockpit switch that you touch at no other
  time. It shows up in the log as a changed param and timestamps the event
  inside the log itself — far more reliable than correlating wall-clock
  across two machines. Say which switch you used when handing the log over.

**Restore afterwards**: copy `aircraft-layer/dcs-export/Export.lua` back over
`Saved Games\DCS\Scripts\Export.lua` and delete `pb15_probe.flag`.
