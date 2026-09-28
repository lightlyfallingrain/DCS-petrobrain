# LOS elevation-tolerance sortie

**Branch: `fix/los-elevation-tolerance`** (will be `main` once merged — check `git log --oneline -3`
after checkout to confirm you're on the fix, not an older `main`).

```sh
git checkout fix/los-elevation-tolerance && git pull
```

**Not a standalone sortie.** This rides along with whatever flight you fly for
`feature/group-reporting`'s own acceptance — nothing here needs its own dedicated sortie, and there
is no conflict between the two: group-reporting is a callout-scheduling change, this is a terrain-
LOS constant. Fly one flight, cover both.

## Why this card exists

2026-09-28: you flew close past an insurgent AAA position, boresight, on an attack run, attacked
it, and Petrovich never called it out — not once, across the whole pass. Diagnosed offline
(`plans/missed-aaa-detection/debug.md`): world-model's elevation grid (SRTM, 1000 m spacing,
measured 11.52 m stddev against DCS ground truth) can place a real unit *below* the modelled
terrain at its own position — permanently blocking terrain line-of-sight to it from every angle,
not a one-off miss. Fixed with a 12 m tolerance on the terrain-LOS check
(`_TERRAIN_TOLERANCE_M = 12.0`, `world-model/src/query/line_of_sight.py`): terrain only blocks when
it exceeds the sightline by more than that margin.

**Reviewed and security-approved on fixtures alone.** Every test in the suite monkeypatches the
elevation grid — that proves the arithmetic is right, it cannot prove Petrovich now calls out the
real AAA position over the real store, and it cannot show whether the accepted cost (see below)
is mild or not in practice. Only this flight settles either.

## Setup

Same collector/brain/crew-text stack as your other current-branch sorties:

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text.sh --detection-trace ~/dcs-detection-trace.jsonl
```

**Fly with `--detection-trace` enabled** (added above, additive, no other behaviour change —
confirmed via `logger --help` on this branch). Without it, a miss on this flight would be exactly
as unevidenced as the one that started this fix: `~/dcs-belief-truth.jsonl` structurally cannot
record a rejected candidate, only an admitted one, so a "no callout" result gives you nothing to
diagnose. `--detection-trace` records every gate's verdict per object per poll, including
rejections.

## The one test that matters

### 1 — Fly the same kind of pass that missed it

**Do.** In mountainous terrain (Syria — the same region as 2026-09-28's flight if you can place
it, otherwise any similarly hilly area with a known ground unit), fly a boresight attack pass —
diving, target dead ahead — close enough that you'd naturally have called it yourself.

**Expect.** Petrovich calls it out this time. This is the headline and the only thing that
actually needs to work for this fix to be worth keeping.

**Record.**
- [ ] Did Petrovich call the target out on this pass?
- [ ] If not: roughly when in the pass would you have expected the call (range/angle), so the
  trace can be checked against that window?

### 2 — Listen for the cost, not just the fix

**The 12 m tolerance necessarily reveals some units it shouldn't** — anything genuinely masked by
a ridge/treeline clearing the sightline by less than 12 m now reads as visible. You accepted this
(2026-09-28) on the grounds that the Mi-24P attacks in a run rather than hiding-and-popping-up like
a Ka-50 or Apache — a tactic where this margin would matter far more.

**Do.** Over the rest of the flight, notice any moment Petrovich calls a contact that is plainly,
visibly masked by terrain from your seat — not "I didn't expect that call" but "that unit is
obviously behind a ridge and he named it anyway."

**Expect.** Nothing, ideally — the accepted cost is meant to be small and rare at Mi-24P attack
geometries. Any real instance is worth knowing about even if it doesn't change the verdict today.

**Record.**
- [ ] Any call that felt like Petrovich saw through terrain that was plainly hiding the target?
  If yes: rough geometry (your altitude/range, roughly how much ridge you'd guess was between you).

## Optional — riding along on the same flight, not required for this fix

Two small, separate checks from `aircraft-layer/research/2026-09-28-live-terrain-probing-
feasibility.md`, gating a *future* incremental-elevation design (not this fix). Do them only if
convenient; neither blocks accepting the fix above.

- **(a) `land.getHeight` returns a real number through the live mission-scripting bridge —
  UNVERIFIED, needs a manual edit on the Windows box.** No prior sortie has actually called
  `land.getHeight` through the Hook bridge and read a number back (every earlier probe ran as an
  offline mission-editor script). The research note's suggested one-liner, added temporarily to
  `aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua`'s `VELOCITY_CODE` string (or a
  throwaway sibling snippet) and removed afterwards — **not** something this DoD pass has added to
  the codebase, since it's unrelated to this fix's scope:
  ```lua
  return tostring(land.getHeight({x = 0, y = 0}))
  ```
  (replace `{x=0, y=0}` with a real ownship position if you want a meaningful number, not just "it
  didn't error"). This is entirely your call whether to try it this flight.
- **(b) `bridge_call_ms` at a realistic unit count — no setup needed, already logging.** The
  velocity-telemetry hook already self-measures and logs `bridge_call_ms`/`unit_count` to `dcs.log`
  on every poll (`petrobrain-mission-telemetry-hook.lua` lines ~164-179) — nothing to enable. If
  this flight happens to have 50-200 units present (a busy mission), grep `dcs.log` for
  `"velocity poll: unit_count="` afterwards and note the `bridge_call_ms` range. The only flown
  sortie so far had 12 units, "well below the range that would stress this" — any busier flight is
  new data for free.

## Bring back

- Did the AAA-style pass get called out this time?
- Any terrain call that looked like it saw through a ridge?
- (if tried) did `land.getHeight` return a number, and what was it?
- (if the mission was busy) what `bridge_call_ms` range did `dcs.log` show?
- Anything that surprised you is worth more than anything on this list.
