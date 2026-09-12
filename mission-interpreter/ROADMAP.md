# Mission Interpreter — Roadmap

Decisions locked in for this phase (`plans/mission-interpreter/plan.md`):

- **`.miz`/Lua parsing**: vendored pydcs `dcs.lua` parse/serialize subpackage (Decision 1), not the
  full `pydcs` package.
- **`trigrules`**: parsed as a raw `predicate`-string tree directly, not through pydcs's wrapper
  classes (Decision 1a).
- **World-model transport**: HTTP, not in-process import (Decision 2) -- `mission-interpreter` <->
  `world-model` is a network call, mirroring `aircraft-layer` <-> `body-layer`'s existing seam, not
  `body-layer` <-> `world-model`'s deliberate single in-process exception.
- **Player-intent input**: text console for MVP (MI-5), a web form later (MI-5b) (Decision 4).
- **`mission["trig"]` vs. `trigrules` runtime authority**: open, not blocking (Decision 5) --
  `trig` is treated as an explicitly documented out-of-scope gap through MI-1.5.
- **MI-4's capable-model choice/hosting**: still open (Decision 3) -- gates only MI-4; MI-0 through
  MI-3 do not need it.

Milestones below are from `plans/mission-interpreter/plan.md`'s Implementation Plan.

- [x] **MI-0 — Get a real `.miz` and lock the schema shape.** Completed 2026-09-12:
  `mission-interpreter/research/samples/Mission 02-Bagram.miz` obtained (gitignored, third-party
  campaign content) and validated against a first secondhand research pass, producing
  `research/2026-09-12-miz-file-structure.md` (Hoggit/forum/pydcs-source only, no real bytes) and
  `research/2026-09-12-miz-validation-against-real-sample.md` (real-bytes corrections/confirmations
  -- load-bearing wherever the two disagree). Only one sample/author/DCS mission-format version has
  been examined; treat every finding as "true in this file," not yet "true in general."
- [x] **MI-1 — Structured `.miz` parser (minimal working version).** Done: `src/miz/` reads the zip
  (`reader.py`), parses `mission` + `l10n/DEFAULT/dictionary` via the vendored Lua parser
  (`src/_vendor/dcs_lua/`), and resolves every `DictKey_*` reference tree-wide
  (`dictionary.resolve_dict_keys` -- a generic recursive substitution pass, not a fixed field list,
  per the plan's corrected MI-1 scope) into the typed `RawMission` intermediate representation
  (`tree.py`): theatre, date, weather (raw passthrough), coalition/country/group/unit structure,
  routes, trigger zones (including the literal misspelled `"verticies"` key), `trigrules` (parsed
  structurally, predicate tree left raw), briefing text, kneeboard image paths (opaque, no
  OCR/VLM). `mission["trig"]` is carried through verbatim, unparsed (`RawMission.trig_raw`).
- [x] **MI-1.5 — Author-only-knowledge filter.** Done: `src/filter/crew_available.py` produces
  `CrewAvailableMission` from a `RawMission`, dropping every `hidden`/`hiddenOnPlanner`/
  `hiddenOnMFD`/`lateActivation` group entirely -- `CrewAvailableMission` has no raw-passthrough
  field, so a hidden group's existence cannot leak back in through an unfiltered catch-all.
  `trigrules`/`mission["trig"]` are never surfaced on `CrewAvailableMission` (kept as raw
  research/debugging data on `RawMission` only); `src/filter/trigrules.py` parses `trigrules`' raw
  `predicate`-string schema (Decision 1a) for that research/debugging use. Tests
  (`tests/test_filter.py`) prove the invariant against both the committed synthetic fixture (must
  pass in every checkout) and the real sample mission (skipped if absent).
- [x] **MI-2 — World enrichment.** Done (`plans/mi2-world-enrichment/plan.md`): world-model's
  `src/api/server.py` (`WorldModelAPIServer`, three read-only `GET` routes wrapping
  `describe_position`/`find_place_by_name`/`line_of_sight_clear`, theatre-mismatch validated as a
  `400` to prevent silently-wrong-projection results) is this project's first HTTP seam, called by
  `mission-interpreter/src/world_enrich/world_model_client.py` (`WorldModelClient`, raises on every
  failure -- no "not built yet" expected-empty state). `src/world_enrich/enrich.py`'s
  `enrich_mission` walks a `CrewAvailableMission` (route waypoints, one representative position per
  group, every trigger zone) into a parallel `EnrichedMission` tree (`schema.py`), mirroring
  `belief.enrichment`'s "zero shared surface" precedent rather than mutating MI-1/MI-1.5's frozen
  dataclasses. Per-unit enrichment and free-text briefing-prose place extraction are explicitly out
  of scope this stage (deferred to MI-4). Does not change what MI-3 should be -- MI-3 still needs a
  first Mission Understanding schema, now with `EnrichedMission` as an available input alongside
  `CrewAvailableMission`.
- [x] **MI-3 — First Mission Understanding schema (no model synthesis).** Done
  (`plans/mi3-mission-understanding-schema/plan.md`): `src/schema/` hand-maps MI-1.5's
  crew-available tree + MI-2's `EnrichedMission` into a new, versioned `MissionUnderstanding`
  dataclass tree (`SCHEMA_VERSION = 1`), populating only `theatre`/`ownship`/`route`/a mechanical
  `mission_phases` skeleton (`TakeOff*` -> DEPARTURE, `Land` -> RETURN, everything else left
  unpopulated rather than guessed)/`important_locations` (named `Group`/`TriggerZone` entities whose
  `world_ref.name_matches` is non-empty -- not route waypoints, which the pipeline doesn't resolve
  names for). Every populated field is tagged `FACT` or `OBSERVATION` via the new `Tagged[T]`
  epistemic-tagging mechanism (`src/schema/tags.py`), never `INFERENCE`/`ASSUMPTION` -- proven by a
  dedicated invariant test. Required adding `Unit.skill` to `miz/tree.py` (real-bytes-confirmed
  field, per the investigator's `research/2026-09-12-player-slot-skill-field.md`) so ownship
  resolution can scan for `skill in ("Player", "Client")`; 0 or >=2 matches resolve to `UNKNOWN`
  rather than guessing. `purpose`/`task`/`known_threats`/`player_intent` are declared on the schema
  but deliberately left unpopulated -- MI-4's job once a capable model exists. Does not change what
  MI-4 should be, but confirms `Tagged[T]` as the one epistemic-tagging convention MI-4/5/6 should
  reuse rather than reinvent.
- [ ] **MI-4 — Capable-model synthesis.** Not started; gated on Decision 3 (model choice/hosting).
- [ ] **MI-5 — Player questions (text console MVP).** Not started.
- [ ] **MI-5b — Player questions, web form.** Future; not started, no design work until MI-5 proves
  out.
- [ ] **MI-6 — Runtime compilation.** Not started.

## Keeping this current

See root `ROADMAP.md`'s "Keeping this current" note -- this file is the source of truth for Mission
Interpreter's own milestone status; the root file only tracks the cross-subproject picture.
