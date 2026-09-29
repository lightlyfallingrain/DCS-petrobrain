# Windows-box session handoff — what to do with DCS access

> **CLOSED 2026-09-29 on the Windows box. All four tasks done, plus a fifth the user added.**
> Ten flights. Branch `investigate/terrain-elevation-source`. Read the results in
> `aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md` (the main one, 21 findings),
> `2026-09-29-bridge-call-cost-at-scale.md`, and
> `world-model/research/2026-09-29-surface5-elevation-confirmed.md`.
>
> | task | outcome |
> |---|---|
> | 1. `bridge_call_ms` at scale | **Done.** A 568-unit sortie was already in `dcs.log`, unread: mean 1.99 ms, p99 8 ms at 1 Hz, ~2.6 us/item. |
> | 2. `land.getHeight` through the bridge | **Done.** Works, and matches the M4 mission-editor probe on all 8 points to 4.6e-05 m. Costs **0.9 us/point** — a full 2,601-point M8 chunk is 2.0 ms. |
> | 3. `.surface5` decode spike | **Done, and it did not disprove.** The file does encode elevation: 129/129 ground-truth points fall strictly inside their tile's y-range against a 71/129 null control. But only a per-tile envelope decoded; per-node values need the `Pbase` payload located inside 30 GB. **Recommendation: park it.** |
> | 4. Does the format generalise? | **Not run, deliberately** — conditional on pursuing task 3, which is not recommended. The walker is theatre-agnostic, so it is one command whenever wanted. Kola remains the right second target. |
> | 5. *(added by the user)* Trees and buildings for LOS | **Answered, and positively — on a call nobody had tried.** See below. |
>
> **The headline the Mac session most needs:** `land.isVisible` is **terrain-only** — 40 rays fired
> deliberately through 40 buildings, 0 blocked. But `world.searchObjects` with
> `world.VolumeType.SEGMENT` **does** return the buildings on a sightline, as a **true 3D test**
> (6 hits at 2 m AGL, 0 at 15 m and above), for **8.7 us/sightline** — *cheaper* than
> `land.isVisible`'s 10.6 us. Trees have **no DCS route at all**; OSM landcover is the only source.
> Remaining build work is filed as **X-B28** (not started); **X-B4 is closed**.
>
> **Also found, unasked:** `line_of_sight_clear` reads the **base grid only** and body-layer never
> ATTACHes the probe store — so finer probe data will not reach the missed-AAA defect until that is
> wired. And SRTM's 1000 m grid is *our resampling choice*, not SRTM's resolution (it ships at
> 30-90 m); the whole elevation grid is 12 MB of a 589 MB store, so rebuilding finer is cheap.
> That discussion is **open and continues on the Mac** — see `X-B26`.
>
> **Still outstanding, still needs this box:** the acceptance sortie
> (`docs/acceptance/2026-09-29-group-reporting-sortie.md`). Unaffected by any of the above.


Written 2026-09-29 on the Mac, for a Claude Code session running on the Windows box where DCS is
installed. Everything here needs either the DCS install or a running mission; none of it can be
done from the Mac, which is why it has been queued rather than attempted.

**Read first, in this order** — all three are on `main`:

1. `plans/missed-aaa-detection/debug.md` — why this matters. A real sortie flew past insurgent AAA,
   attacked it, and Petrovich never saw it. Root cause: world-model's SRTM elevation grid
   (1000 m spacing, **measured 11.52 m stddev** against DCS ground truth) can place a unit *below*
   the modelled terrain at its own position, permanently blocking line-of-sight from every angle.
2. `world-model/research/2026-09-29-x-b26-terrain-file-vs-live-probe.md` — the current state of the
   file-versus-probe question, including two ED forum threads now read and found to contain no
   prior art.
3. `aircraft-layer/research/2026-09-28-live-terrain-probing-feasibility.md` — the probing route's
   recon: the mission-scripting bridge, what is proven and what is unmeasured.

**Standing rule that still applies:** do not run a full theatre build. Hand the user the command.

---

## Task 1 — `bridge_call_ms` under a realistic unit count (highest value, lowest effort)

**This is the measurement that decides the whole terrain design**, and the mechanism to produce it
already exists and has simply never been read.

`aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua` already self-measures its own
bridge cost (`bridge_call_ms`, alongside `unit_count`) and writes it to `dcs.log`. The only flown
sortie had **12 units**, which tells us nothing about scale.

- Fly (or have the user fly) a mission with **50–200 units** present.
- Pull `bridge_call_ms` and `unit_count` from `dcs.log` — `.claude/skills/dcs-log-recon` exists for
  exactly this kind of extraction.
- Report the distribution, not just a mean: the tail is what would stutter the game.

**Why it decides things:** a terrain-probe batch is two-plus orders of magnitude more per-call work
than the velocity loop. If the bridge is already near its budget at 200 units, live probing at any
useful sample density is not viable and the answer is the file route (or neither). If it has
headroom, the live-probe design in the aircraft-layer note proceeds.

## Task 2 — does `land.getHeight` work through the bridge at all?

High-confidence inference, **never actually demonstrated**. `land.*` is Mission Scripting API and
`net.dostring_in("scripting", ...)` runs in exactly that environment — but no session has ever
called it and read a number back. Every prior elevation probe (M4/M5) ran offline through
mission-editor trigger scripts, before the bridge existed.

- Add a single `land.getHeight` call to the existing bridge snippet, at a known `(x, z)`.
- Confirm it returns a real number, and record it with the coordinates.

**Read `aircraft-layer/research/2026-09-22-mission-bridge-already-shipping.md` before writing any
probe.** A previous probe of this bridge returned a *clean but misleading negative* (`net present:
false`), and that note explains exactly why. Repeating that mistake is the most likely failure here.

## Task 3 — the `.surface5` decode spike, timeboxed

**Timebox this and treat it as a disproof attempt, not a likely success.** Two forum threads were
read on 2026-09-29: no public documentation or community reverse-engineering of this format exists,
and the one person found publicly asking this exact question concluded *"I guess I'll just use a lua
script in game to query the terrain height"* — i.e. gave up on files. The prior probability is low.

Target: `Mods/terrains/Syria/surface/Syria.surface5` (30 GB+, a recursive LOD-quadtree mesh
container; structurally readable TLV grammar, no encryption, payload never decoded).

- Byte offset and float32 layout for a candidate elevation anchor are already identified in
  `world-model/research/2026-09-05-m7-terrain-mesh-elevation-relitigation.md` Finding 5. **Start
  there rather than re-deriving.** That anchor was pattern-matched by magnitude *once*, never
  cross-checked against anything.
- The decisive test is **one comparison**: decode a node's anchor point, then read `land.getHeight`
  at the same `(x, z)` (Task 2's mechanism). Agreement proves both "this is elevation" and "it
  matches the live surface" — the two things the whole question turns on. Disagreement kills the
  file route cleanly.
- If it agrees, the follow-up is resolution: is the mesh denser than SRTM's 1000 m? If it is not,
  the file route is pointless regardless of decodability.

## Task 4 — does the format generalise? (only if Task 3 succeeds)

The `.surface5` file family exists for every installed terrain (Afghanistan, Caucasus, Kola,
Mariana, Syria — confirmed from `DCS-files.txt`), but only Syria's copy has ever been examined at
byte level. Re-run the same head/tail capture against one non-Syria terrain.

**Kola is the right second target**, for two reasons at once: it is already flagged as the next
stress case, and it has an unrelated, genuine elevation-source gap — SRTM does not cover ~68–69°N
at all, so *nothing* currently fills it.

---

## What to bring back

A dated research note in the right module's `research/` directory (`world-model/` for the file
format, `aircraft-layer/` for the bridge), findings with evidence and confidence classes, per
`docs/concept/WORLD_MODEL_BUILDER.md`'s format. **Findings, not pipeline code.**

The single most useful outcome is a clear answer to: **probe, files, or neither** — with the
`bridge_call_ms` number attached, since that is what makes "probe" affordable or not.

---

## Also outstanding on the Windows box, unrelated to terrain

**The acceptance sortie.** Everything merged tonight is unflown and rides one flight from `main`:
group reporting, the confirm band, the LOS elevation tolerance, and the 2026-09-26 fixes. Card:
`docs/acceptance/2026-09-29-group-reporting-sortie.md` (published at
https://claude.ai/artifact/WXTSUmzmQrzpSueEVh4K2B).

Ask the user to fly with **`--detection-trace <path>.jsonl`** enabled. Without it a future "he
didn't see it" is unevidenced — `belief-truth.jsonl` structurally cannot record a *rejected*
candidate, which is precisely why the AAA defect needed an offline reproduction to find.

The number most wanted back from that flight: whether `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS`
(20.0, ≈140 m between neighbouring 7 m vehicles) draws group boundaries where the pilot perceives
them. It is a stated assumption he explicitly asked to refine from flight evidence.
