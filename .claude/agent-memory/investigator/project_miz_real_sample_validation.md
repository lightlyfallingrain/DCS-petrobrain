---
name: miz-real-sample-validation
description: What a real .miz sample confirmed/corrected vs the secondhand pydcs/Hoggit-only prior note; use before re-investigating .miz structure.
metadata:
  type: project
---

Session 2026-09-12 validated `mission-interpreter/research/2026-09-12-miz-file-structure.md`
(pydcs-source-only, no real bytes) against a real sample at
`mission-interpreter/research/samples/Mission 02-Bagram.miz` (gitignored, never quote it at length).
Full detail: `mission-interpreter/research/2026-09-12-miz-validation-against-real-sample.md`.

Key corrections/additions to carry forward, don't re-derive:
- `mapResource` lives at `l10n/DEFAULT/mapResource`, not zip-root. Zip root also has a bare
  `theatre` text file (e.g. "Afghanistan") separate from `mission["theatre"]`.
- KNEEBOARD path in the wild was flat `KNEEBOARD/IMAGES/`, not `KNEEBOARD/<aircraft>/IMAGES/` —
  don't assume the aircraft-scoped path is the only real layout.
- DictKey_* externalization is tree-wide (trigger action text/radio/comments too, not just the
  4 briefing fields) — resolve it as a whole-tree substitution pass, not a fixed field list.
- trigger zone `type=0` circle (radius+x/y), `type=2` polygon with vertices in a **misspelled**
  key `["verticies"]` (not "vertices") — real DCS typo, will bite a hand-typed schema.
- trigrules real schema is `predicate`-string based and cleanly namespaced: `a_*` = action,
  `c_*` = condition, `trigger*` = rule kind (triggerStart/triggerOnce/triggerContinious[sic]/
  triggerFront), `"or"` = boolean combinator. This vocabulary IS closed/greppable per file (39
  unique values seen in one real mission) — pydcs's TriggerRule/action/condition Python classes
  are a lossy abstraction over this, not a 1:1 mirror; prefer reading the raw predicate strings
  as ground truth over pydcs's wrapper when precision matters.
- Previously unknown: `mission["trig"]` — a third trigger-adjacent top-level table holding
  literal generated Lua source strings (compiled/flattened form of trigrules, same a_*/c_*
  predicates as real Lua calls with concrete args). Not documented anywhere (ED/Hoggit/pydcs).
  Useful for recovering exact predicate call signatures. Whether trig or trigrules is what DCS
  actually executes at runtime is UNRESOLVED — check a second sample or ask ED forum if it matters.
- Groups live at `mission.coalition.<blue|red|neutrals>.country[N].<category>.group[]`
  (category = unit type like helicopter/plane/vehicle) — this path was never stated in any
  secondhand source consulted before this session.
- `route.points[]` and `weather` sub-schemas are now directly bytes-confirmed (see the dated
  note for full field lists) — no need to re-derive from Hoggit prose again.
- pydcs was NOT installed in this repo's Python env this session (`pip3 show dcs` → not found) —
  don't assume it's available; check first if a future task wants to cross-validate with it.

Follow-up session 2026-09-12 (same sample): confirmed the player-slot marker is
`unit["skill"] = "Player"` (or community-claimed `"Client"` in MP, unverified — this SP sample
only had `"Player"`, count exactly 1, zero `"Client"`). No other field is reliable: `callsign`,
`onboard_num`, `AddPropAircraft`, group-level `uncontrolled` are all present on AI units too, and
unit/group `name` containing the string "Player" was coincidental mission-author text, not a
schema guarantee. Full detail: `mission-interpreter/research/2026-09-12-player-slot-skill-field.md`.
`Unit` dataclass in `tree.py` needs a `skill: str` field added for MI-3 ownship passthrough.
