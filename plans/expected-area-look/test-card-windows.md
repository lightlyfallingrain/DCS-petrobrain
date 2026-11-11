# Test card — expected-area look, Stage 1 (Windows, no body-layer needed)

**Branch to check out: `main`, after this feature merges.** This card confirms the aircraft-layer
side only (the `probe_points` inbound op on the line-of-sight Hook) — no body-layer process needs
to be running.

## What this proves

`plans/expected-area-look/plan.md` Stage 1 added a second inbound op, `probe_points`, to the
existing `petrobrain-line-of-sight-hook.lua` 7797 listener: a point line-of-sight query (terrain
clear/blocked at an arbitrary ground point, +2 m), distinct from the existing per-unit
`look_direction` op. This has not been confirmed against a live DCS session. The plan's own
words: *"The Windows card in Stage 1 confirms it live, and that is a verification step, not an
open question."*

## Setup

1. Deploy the Hook (if not already): copy
   `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` to
   `Saved Games\DCS\Scripts\Hooks\petrobrain-line-of-sight-hook.lua`, and confirm
   `Saved Games\DCS\Config\autoexec.cfg` has `net.allow_dostring_in = { "scripting" }`. **Restart
   DCS (not just the mission)** for the Hook to load — see `aircraft-layer/WORKFLOW.md`'s "Deploy
   the line-of-sight Hook script" section for the full procedure.
2. Start the collector on the Windows box (`aircraft-layer/WORKFLOW.md`, "Run the collector").
3. Start any mission with an **air start near a ridge or hill**, straight and level — the ridge
   is what makes the three probe points land on genuinely different terrain.
4. From the Mac (or WSL), confirm the collector answers at all:
   ```sh
   curl -s http://<collector-host>:7791/telemetry/latest
   ```

## Step 1 — push three probe points by hand

Read ownship's `x`/`z` off `GET /telemetry/latest`, then pick three points along the direction
you are facing the ridge:

- one on the **near slope** (should read terrain-clear from a reasonable altitude),
- one **behind the crest** (should read terrain-blocked),
- one in **open ground** beyond the ridge (should read terrain-clear).

```sh
curl -s -X POST http://<collector-host>:7791/command/probe_points \
  -H 'Content-Type: application/json' \
  -d '{"seq": 1, "points": [[<near-slope-x>, <near-slope-z>], [<behind-crest-x>, <behind-crest-z>], [<open-ground-x>, <open-ground-z>]]}'
```

**Check:**
- `dcs.log` shows new `PetrobrainLineOfSight` lines (no errors/exceptions from the Hook).
- `curl -s http://<collector-host>:7791/line_of_sight/latest` carries a `"probes"` field with
  three entries matching `seq: 1`. Expected pattern: `1` (clear), `0` (blocked), `1` (clear) for
  near-slope/behind-crest/open-ground respectively.

## Step 2 — fly closer and confirm the near-slope point flips

Climb or close the distance until the near-slope point should newly clear the ridge line (or the
reverse — descend until a previously-clear point goes behind a rise). Push the **same** three
points again with a new `seq`:

```sh
curl -s -X POST http://<collector-host>:7791/command/probe_points \
  -H 'Content-Type: application/json' \
  -d '{"seq": 2, "points": [[<near-slope-x>, <near-slope-z>], [<behind-crest-x>, <behind-crest-z>], [<open-ground-x>, <open-ground-z>]]}'
```

**Check:** the near-slope point's own `clear` value changes between the two pushes, tracking your
altitude/position relative to the ridge — this is the live confirmation that `land.isVisible` is
actually being evaluated against the pushed terrain point, not a cached or default answer.

## Step 3 — paused-state check

**Pause the mission**, then repeat Step 1's `curl` with a new `seq`.

**Check:** the Hook still answers (or, per its own fail-closed contract, the field is absent/
`null` rather than a stale `1`) — it must not crash or freeze while paused. `dcs_model_time_s` in
the response should stop advancing while paused (DCS's own sim clock behaviour, not a bug).

## Step 4 — clear the probes and confirm `bridge_call_ms` is unaffected

```sh
curl -s -X POST http://<collector-host>:7791/command/probe_points \
  -H 'Content-Type: application/json' \
  -d '{"seq": 3, "points": []}'
```

**Check:**
- `GET /line_of_sight/latest`'s `"probes"` field clears (empty or absent).
- `bridge_call_ms` in the same payload does not move measurably from its baseline before any
  probes were pushed — the plan's own measured cost is "~25 µs peak" per sightline
  (`aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md`), well under anything
  `bridge_call_ms` would show.

## If something looks wrong

- No `"probes"` field at all: confirm the Hook actually reloaded (restart DCS, not just the
  mission) and that the collector's own schema has the optional `probes` key (it should, on
  `main`).
- Every point reads blocked, or every point reads clear regardless of terrain: report this —
  it means the fail-closed contract or the terrain-height lookup is not working as designed, not
  a tuning question.
