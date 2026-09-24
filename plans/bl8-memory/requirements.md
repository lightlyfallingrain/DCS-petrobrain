# BL-8 memory layer — what it must hold, and what it can actually get

BL-8 has been deferred since 2026-09-10 on one condition: *"the shape of what's worth remembering
is only knowable after BL-2 through BL-7 have run for real."* That condition is now met — the user
has flown the belief layer, the voice loop and the optics, and has stated what memory is for.

**This document is the requirement, plus an availability audit.** It is not a plan. Roughly half of
what is wanted needs data that does not exist anywhere in the project yet, and saying which half is
the useful part.

---

## The model: a kneeboard

The user's framing, and it is a good one because it bounds the problem:

> the kneeboard notes is a perfect example of how it should work

A crew member writes down what matters, in pen, and uses it later. That implies four properties
worth stating, because each rules something out:

- **Selective.** A kneeboard holds what was worth the effort of writing. Not everything observed.
- **Durable.** It survives losing sight of the thing. Belief decays; a written note does not.
- **Stale by nature.** A written position is where it *was*. The note does not update itself, and a
  crew member knows that when reading it back.
- **Hand-writable.** The crew can add an entry deliberately — the user asks for exactly this below.

---

## What it should hold

### Pre-mission, from the Mission Interpreter

| wanted | available today? |
|---|---|
| flight plan | **yes** — `route`/`phases`, already consumed by BL-7 |
| expected enemy locations | **partly** — `expected_threats` exists as *strings only*, no positions |
| known enemy units | **no** — not in the compact runtime output |
| known friendly units and positions | **no** — not in the compact runtime output |
| frontline / which coalition holds what terrain | **no** — does not exist anywhere in the project |
| aircraft loadout: fuel, ammo, weapons | **no** — aircraft-layer exports none of it |
| weather | **no** — not exported; reachable only via the mission-scripting bridge |
| radio frequencies | **no** — not exported |

**Two fields are already produced and thrown away.** `runtime.compact.RuntimeMissionUnderstanding`
carries `key_locations` and `expected_threats`; body-layer's `MissionUnderstandingData` parses only
`phases` and `route`. Same shape as the numeric bearing being computed and dropped at the transcript
wire — the fix is wiring, not new capability.

**But `key_locations` has no position field** (`id`, `kind`, `place_name` only), and
`expected_threats` is a tuple of strings. So "expected enemy locations" cannot be *placed* on a map
today even once wired. That is an upstream gap in the Mission Interpreter, already recorded in
`body-layer/ROADMAP.md`'s BL-7 entry as a known limitation.

### Observed during the mission

| wanted | available today? |
|---|---|
| significant enemy location and type | **yes** — this is what `ContactStore` holds |
| high-threat auto-entry ("threat classification guide") | **yes** — `docs/concept/threat-levels.md` plus `body-layer/data/threat_envelopes.json` |
| mission target units | **blocked** — needs `key_locations` to carry positions |
| updates to known unit positions | **yes**, and improving — see `plans/precise-position-belief/` |
| damaged and destroyed units | **no** — nothing detects destruction |
| smoke / signal smoke / signal flare | **deferred by the user** — no detection logic exists |

### Crew-directed

> crew can set (player command) to remember certain units or locations (landmarks even)

**Buildable.** The command surface exists and every recognised command now dispatches
(`plans/voice-command-completeness/`). Landmarks specifically compose with world-model's named
places, which `belief.enrichment` already queries.

---

## What this changes about sequencing

**The cheapest real capability is the crew-directed one**, and it is also the one that proves the
kneeboard model end to end: a player command writes an entry, the entry survives the contact
decaying to `lost`, and a later report reads it back. Nothing upstream blocks it.

**The most valuable blocked one is terrain control.** It gates believed coalition, which gates
threat banding (`docs/concept/threat-levels.md`), which is the longest unbuilt chain in the project
— and it now also gates "which coalition holds what areas". It is a world-model milestone, not a
body-layer one.

**Three items need an aircraft-layer export that does not exist**: loadout/fuel/ammo, weather, and
radio frequencies. Weather is the interesting one — it is reachable through the same
mission-scripting bridge that already carries unit velocity in production
(`petrobrain-mission-telemetry-hook.lua`), so it is an extension of a working mechanism rather than
a new one.

---

## The property that must not be lost

A kneeboard entry is **a record of a belief, not a fact**. It inherits whatever uncertainty the
belief had when it was written, and it goes stale in a way the crew member understands. The memory
layer must not become a back door through which a decayed or never-observed truth re-enters belief
as certainty — which is the same boundary `belief/percept.py` defends at the perception end, and
the same failure `plans/precise-position-belief/` exists to prevent at the position end.
