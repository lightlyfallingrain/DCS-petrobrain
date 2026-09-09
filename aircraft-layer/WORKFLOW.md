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

## Deploy the overlay Hook script (Windows box, once per change)

**UNVERIFIED against a live DCS session** (`plans/dcs-text-panel-output/plan.md`
Stage 2) — authored from `aircraft-layer/research/2026-09-09-dcs-text-panel-output-channel.md`
and modeled directly on DCS-SRS's own installed, working overlay
(`Mods\Services\DCS-SRS\Scripts\DCS-SRS-OverlayGameGUI.lua` +
`Mods\Services\DCS-SRS\UI\DCS-SRS-Overlay.dlg`), but not run against a real DCS
process. Copy both files to `Saved Games\DCS\Scripts\Hooks\`:

- `aircraft-layer/dcs-export/petrobrain-overlay-hook.lua` ->
  `Saved Games\DCS\Scripts\Hooks\petrobrain-overlay.lua`
- `aircraft-layer/dcs-export/petrobrain-overlay.dlg` ->
  `Saved Games\DCS\Scripts\Hooks\petrobrain-overlay.dlg`

Same discipline as `Export.lua`: the repo copy is canonical, never edit the
deployed copy in place. Unlike `Export.lua`, Hook scripts load once into the
GUI Lua state at DCS **application** startup, not per-mission — restart DCS
(not just the mission) after copying either file for a change to take effect.

This opens a second window (420x200px by default, top-left corner of the
screen, draggable) showing the last few lines body-layer's `--overlay` mode
pushes, expiring each line after 20s. It listens on loopback UDP port 7792 —
distinct from Export.lua's own port (7790) and the LAN API port (7791) — fed
by the collector's `POST /text/push` (see "Query from the Mac" below). If the
window never appears, or `dcs.log` shows a Lua error tagged
`PetrobrainOverlay`, that is exactly what Stage 2's live check is for; this
deploy step alone does not confirm the script actually works.

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

The collector also opens a `TextOverlaySender` on loopback UDP port 7792 by
default (`--text-overlay-host`/`--text-overlay-port` to override) — the other
end of the "Deploy the overlay Hook script" section above. This is
fire-and-forget: the collector starts this sender unconditionally, whether or
not the overlay Hook script is actually loaded in DCS, since a missing
listener is an expected state (DCS not running yet, or running without the
overlay script) rather than an error.

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
`plans/pb1-perception-logger/plan.md` stage 3. Each object also carries
`is_ownship` (`true`/`false`/`null` — see
`aircraft-layer/src/schema/world_objects.py`'s docstring for the tri-state
meaning), added by the `todo/todo.md` backlog item replacing body-layer's
50 m proximity-based ownship exclusion with an identity flag set from
`LoGetPlayerPlaneId()`. The player's own aircraft is still included in the
snapshot, flagged rather than dropped. See
`aircraft-layer/src/schema/world_objects.py` for the field list/units.

```
curl -X POST http://<windows-box-lan-ip>:7791/text/push -d '{"text":"hello Petrovich"}'
```

Pushes one line to the in-cockpit overlay (see "Deploy the overlay Hook
script" above) — `200 {"ok": true}` on success (meaning only "the collector
attempted the UDP send," not "the line appeared on screen" — delivery is
fire-and-forget, by design), `400` on a missing/empty/non-string `text`
field, `503` if the collector wasn't built with a `text_sender` (should not
happen via `python -m collector`, which always constructs one). This is the
aircraft layer's only inbound/write path — everything else on this API is
read-only.

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

**Flight protocol** — the discipline matters more than the flying.

The point is to catch a contact callout that cannot have come from the sight. An earlier draft of
this section said "never slew the ASP-17," which was wrong: Petrovich drives the sight, not the
pilot, so if you tell him to scan he *will* slew it. **`OBSERV OFF` is the real control** — sight
off, so any contact report has to come from the other channel.

The Session 2 screenshot already hints at the answer: `OBSERV OFF` → `9 CONTACTS, 1 O'CLOCK` →
`OBSERV ON` → `CAN'T MOVE SIGHT YET`. The callout fired with the sight off. This sortie is to
capture that moment with the log running.

Fly it as an A/B, both segments over the same targets:

- **Setup.** Place ground targets — trucks or armour give the easiest callouts — at varied ranges
  out to ~5 km, spread across bearings so a clock position is meaningful.
- **Segment A — `OBSERV OFF`.** Fly passes bringing targets into view. This is the segment that
  matters: any `"N CONTACTS, H O'CLOCK"` here is naked-eye by construction.
- **Segment B — `OBSERV ON`.** Same targets, same passes, sight active. This is the control: it
  shows what the log looks like when the callout *is* sight-driven, so the two can be compared.

**Capture every callout.** The callout is **text in the radio-message pop-up**, not a voice line,
so it persists on screen for a few seconds and can be read verbatim. For each one:

1. Flip one distinctive cockpit switch that you touch at no other time. It lands in the log as a
   changed param and timestamps the event inside the log itself — far more reliable than
   correlating wall-clock across two machines. Say which switch you used when handing the log over.
2. **Write down the exact text** (e.g. `9 CONTACTS, 1 O'CLOCK`). The count bucket and clock bearing
   can then be checked directly against the `LoGetWorldObjects` ground truth captured in the same
   log — which is far stronger evidence than "something changed near this timestamp." A screenshot
   works too.

You do not need to track the OBSERV transitions by hand: the probe logs `list_indication(2)`
(the ASP-17) on change, so the sight's state is recorded in-band and each callout can be
attributed to a segment after the fact.

**What the result will mean**

- Callouts in segment A, and something in the log changes at the marker → a real ambient signal
  exists and is Lua-readable. That is the strong outcome: it becomes the detection gate, replacing
  PB-1.5's filter as a source swap.
- Callouts in segment A, but nothing in the log changes → naked-eye detection is real but has no
  exported companion. PB-1.5's filter stands as the only option, and the question is closed.
- No callouts at all in segment A → the ambient callout is sight-gated after all, and the Session 2
  screenshot was a lagging callout from a prior scan. Worth knowing, and it would strengthen the
  case for the synthetic filter.

**Restore afterwards**: copy `aircraft-layer/dcs-export/Export.lua` back over
`Saved Games\DCS\Scripts\Export.lua` and delete `pb15_probe.flag`.
