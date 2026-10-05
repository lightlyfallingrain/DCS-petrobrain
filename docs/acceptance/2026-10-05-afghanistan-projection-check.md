# Afghanistan projection check — acceptance card

**Artifact card (cockpit-readable version of this document):**
https://claude.ai/artifact/YBRPNY1LcAb37u6GMBB1Vu

**Branch:** `feature/multi-theatre-afghanistan`. **Before you check it out**, confirm it actually
holds this work — `git log --oneline -3` should show `Reviewer: re-review tests-only fix
(91fd8a1) on multi-theatre-afghanistan` at the tip (short sha `0690a74`). If it instead shows
`implementer agent-memory: multi-theatre-afghanistan findings` (`381f828`), the branch has not
been fast-forwarded past the implementer's own commit yet — the review, security fix, and test
tightening exist but are not reachable from this branch name. Ask for that to be fixed before
testing; this card assumes it has been.

```sh
git checkout feature/multi-theatre-afghanistan && git log --oneline -3
```

**No DCS, no flight, for Block 1.** Block 1 is a desk/Mission-Editor task on your Windows DCS box.
Block 2 is an actual sortie, and is optional — flagged as such below.

## What this closes

`THEATRE_PROJECTIONS["Afghanistan"]` (the DCS x/z ↔ lat/lon transform) is `confidence=
"provisional"` — fitted from `beacons.lua`, never checked against DCS's own live `coord.LOtoLL`.
Everything downstream (every position Petrovich reports, the whole `afghanistan-full.sqlite`
build) rests on it. Block 1 is the one check that turns "provisional" into "confirmed" — the same
procedure that already validated Syria's own projection to 0.00–0.03 m in M1.

## Block 1 — live `coord.LOtoLL` projection check (desk task, Windows DCS box)

### Setup

1. In the DCS Mission Editor, create a throwaway mission **on the Afghanistan terrain** — any
   aircraft, any airfield start, the content doesn't matter, only that it loads Afghanistan.
2. Add a trigger: type **ONCE**, condition **TIME MORE 5**, action **DO SCRIPT FILE**, pointing at
   `world-model/tools/dcs-mission-probe/coord_probe.lua` (copy it somewhere DCS can read it, or
   paste its contents directly into a DO SCRIPT action). This script is unmodified from the one
   Syria's own M1 verification used — it calls only `coord.LOtoLL` and `world.getAirbases()`,
   nothing Syria-specific.
3. **Before running: check whether DCS's `Scripts/MissionScripting.lua` still has `io`/`lfs`
   re-exposed.** The script writes its output via `io.open`/`lfs.writedir()` directly (read its
   own header comment if you want the exact caveat) — if that sandbox edit from the M1/M4 probes
   has since been reverted, either redo that one-time edit, or skip straight to the script's own
   documented fallback: change the last few lines to `trigger.action.outText(text, 60)` instead of
   writing a file, and transcribe the JSON from the in-game message log by hand.
4. Save, start the mission, let it run ~10 seconds, then exit.
5. Output lands at `Saved Games/DCS/Logs/coord_probe_output.json`. Copy it back via your usual
   win-mac-sync path (or straight into this repo if you're running Claude Code on the same
   Windows box) into `world-model/data/raw/dcs/<today's date>/coord_probe_output.json`.

### Check the residual

From `world-model/`, with its `.venv` active:

```sh
cd world-model
.venv/bin/python -c "
import json, math, sys
sys.path.insert(0, 'src')
from coordinates import dcs_to_wgs84

def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlmb/2)**2
    return 2 * r * math.asin(math.sqrt(a))

data = json.load(open('data/raw/dcs/<today date>/coord_probe_output.json'))
points = [{'name': 'origin', **data['origin']}, *data['airbases']]
worst = 0.0
for p in points:
    pred_lat, pred_lon = dcs_to_wgs84('Afghanistan', p['x'], p['z'])
    residual = haversine_m(p['lat'], p['lon'], pred_lat, pred_lon)
    worst = max(worst, residual)
    print(f\"{p['name']:30s} residual_m={residual:.3f}\")
print(f'worst residual across {len(points)} points: {worst:.3f} m')
"
```

(Replace `<today date>` with the folder you actually copied the file into.) This script's shape —
import path, `dcs_to_wgs84`, haversine against the live-reported lat/lon — was run in this session
against a synthetic stand-in file with the exact JSON shape `coord_probe.lua` writes, to confirm
it executes correctly end to end; the only thing that can't be verified from here is the real
live-DCS numbers, which only exist once you've run Block 1's mission.

**Pass criterion:** worst residual ≤ ~0.1 m (the same float-rounding-noise floor Syria's own M1
measured, 0.00–0.03 m, and the investigator's beacon-fit validation, ~0.03 m). If every point
clears that, flip `THEATRE_PROJECTIONS["Afghanistan"]`'s `confidence` from `"provisional"` to
`"confirmed"` in `world-model/src/coordinates/projections.py` and update its `source` string to
cite the new dated research note. **A residual in the metres, not sub-metre, at any point means
the provisional fit is wrong** — do not flip confidence; write a dated research note with the
actual numbers instead and flag it back.

### Keep the output file — it's the seed for the full airfield list

**Do not discard `coord_probe_output.json` after this check.** `world.getAirbases()` enumerates
DCS's real airbase registry — the same thing that drives in-game ATC/parking — independent of
`beacons.lua`. Right now `world-model`'s own airfield data only knows about **7 of Afghanistan's
~26 airfields** (the ones with navaids; see `plans/multi-theatre-afghanistan/review.md`'s
"Airfields" finding) — this file's `airbases` array is an independently-sourced, already-dated
list of all ~26 names and positions, a ready-made seed for widening that coverage in a later
milestone. It costs nothing to keep and would have to be re-flown to reproduce.

### While the mission is open: re-confirm the theatre string (optional, already checked once)

`mission["theatre"] = "Afghanistan"` has already been independently confirmed against a real
campaign `.miz` (`world-model/research/2026-10-05-afghanistan-theatre-build.md`) — no need to
redo this unless you're curious. If you do: `mission["theatre"]` should read exactly
`"Afghanistan"` (case included) — open the mission file as a zip and look at the `mission` entry,
or just trust the prior check.

## Block 2 (optional) — a real sortie against the built `afghanistan-full` store

**This block is honestly a smaller ask than it looks — it reuses your normal sortie startup, with
one flag swap.** Not required for Block 1's pass/fail; flown only if you want to see Petrovich
actually fly Afghanistan.

Mission: **"Mi-24P – The Dawn of the Soviet Afghan War", Mission 02-Bagram** (confirmed present at
your `Saved Games/DCS/Missions/Campaigns/en/...` path in this session).

Your usual `run-scripts/run-crew-text.sh` is hardcoded to Syria. Don't edit it in place — either
copy it, or run the equivalent command directly from `body-layer/`, swapping only the theatre and
store:

```sh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
    --aircraft-layer-url http://<your-collector-ip>:7791 \
    --theatre Afghanistan \
    --world-model-db ../world-model/data/world-model/afghanistan-full.sqlite \
    --speech-audio --speech-input --crew-text --f10-commands \
    --audio-adapter-url http://127.0.0.1:7795 \
    --brain-client http --brain-url http://127.0.0.1:7796 \
    --speech-log ~/dcs-speech.jsonl
```

**Verified this session** (without a live DCS/aircraft-layer connection, which this environment
doesn't have): the `--theatre Afghanistan --world-model-db .../afghanistan-full.sqlite` pair
resolves and passes the mismatch guard cleanly against the real built store — confirmed by running
this exact command with a deliberately-unreachable `--aircraft-layer-url` and watching it fail
only once it tries to poll aircraft-layer, never on theatre/store resolution. Also confirmed the
mismatch guard actually rejects a wrong pairing (`--theatre Syria` against the Afghanistan store
errors immediately, before any poll). **UNVERIFIED**: the rest of the pipeline against a live DCS
session on Mission 02-Bagram specifically — that needs your hands and a running mission.

The newer `--mission-understanding <artifact> --world-model-dir <dir>` derivation path (Stage 5's
other route — theatre comes from the mission file instead of a typed flag) is not exercised by
this block: producing that artifact for Mission 02-Bagram would mean running mission-interpreter's
own LLM pipeline against it first, which hasn't happened and is a separate piece of work. The
explicit `--theatre`/`--world-model-db` pair above is the simpler, already-proven path and is
exactly as correct for this sortie.

**What to observe:** Bagram airfield itself (DCS x=125892.4, z=272874.7) resolves to SRTM
elevation ≈1478 m in the built store — real Bagram sits around 1497 m, so this is in the right
range but not pinned to the metre (expected: SRTM vs. DCS terrain art, same ~tens-of-metres-class
agreement Syria's own spot-checks show). Petrovich's terrain line-of-sight gate
(`NakedEyePerceptionSource`) uses this elevation data for every contact near Bagram/Kabul — if
contacts in mountainous terrain near either city get masked/revealed in a way that looks
geographically sensible (a ridge blocking view into a valley, not a flat-earth guess), that's the
thing this plan's world-model data is actually feeding.

**Don't expect:** any Afghanistan-specific wording change in what Petrovich says — nothing in this
plan touches speech/callout text. Don't expect airfield call-outs for anything other than the 7
beacon-derived airfields (see Block 1's note above) — Bagram and Kabul are both in that 7, so this
specific sortie isn't actually blocked by the gap, but a different Afghanistan mission easily could
be.

## What is NOT yet true — say this plainly before you fly anything else on Afghanistan

- **The projection is provisional until Block 1 passes.** Every position Petrovich reports on
  Afghanistan terrain rests on it. If Block 1 hasn't been flown yet, treat any Afghanistan position
  as "plausible, not confirmed" — which is exactly what the research note and the code's own
  `confidence` field already say.
- **Raster chart (F10 map) registration is out of scope for this plan** — nothing a pilot would
  notice changes there; it only affects two diagnostic tools nobody runs mid-sortie.
- **Road junctions are real but sparse** (196 in the whole Afghanistan store vs. Syria's 8,732) —
  a known detector/data-authoring limitation (`review.md`'s finding), not something this sortie
  will surface as a defect; just don't expect Afghanistan's road network to feel as richly
  junction-dense as Syria's.

## Bring back

1. **Block 1's worst residual, in metres, and whether confidence got flipped to `"confirmed"`.**
   This is the one thing this card exists to answer.
2. If you kept `coord_probe_output.json` — confirm you have it somewhere findable; it's the
   26-airfield seed, not disposable.
3. Block 2, if flown: did Bagram/Kabul-area terrain masking look geographically sensible to you.
4. Anything that surprised you is worth more than anything on this list.
