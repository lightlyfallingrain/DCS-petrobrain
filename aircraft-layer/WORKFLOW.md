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
python -m collector
```

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
curl http://<windows-box-lan-ip>:7791/telemetry/since/<wall_clock_timestamp>
```

- `latest` returns the most recent sample as a JSON object, or JSON `null`
  if nothing has been received yet (not an error — Export.lua may not have
  connected, or DCS may not be running a mission).
- `since/<timestamp>` returns a JSON array of samples received strictly
  after that wall-clock (`received_wall_clock_s`) timestamp, oldest first.
  An empty array is the normal "nothing changed since your last poll"
  result. A timestamp older than the retained ring buffer (default 100
  samples, ~20s at the 5 Hz export rate) silently misses evicted samples —
  poll more often than that window if you need every sample.

See `aircraft-layer/src/schema/__init__.py` for the full field list/units in
each sample.
