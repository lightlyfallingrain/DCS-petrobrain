# MI-1 — Structured `.miz` parser

- [x] **MI-1 — Structured `.miz` parser (minimal working version).** #status/done Done: `src/miz/` reads the zip
  (`reader.py`), parses `mission` + `l10n/DEFAULT/dictionary` via the vendored Lua parser
  (`src/_vendor/dcs_lua/`), and resolves every `DictKey_*` reference tree-wide
  (`dictionary.resolve_dict_keys` -- a generic recursive substitution pass, not a fixed field list,
  per the plan's corrected MI-1 scope) into the typed `RawMission` intermediate representation
  (`tree.py`): theatre, date, weather (raw passthrough), coalition/country/group/unit structure,
  routes, trigger zones (including the literal misspelled `"verticies"` key), `trigrules` (parsed
  structurally, predicate tree left raw), briefing text, kneeboard image paths (opaque, no
  OCR/VLM). `mission["trig"]` is carried through verbatim, unparsed (`RawMission.trig_raw`).
