"""Plain-text DCS gazetteer parsers.

`towns.py` and `beacons.py` both read unencrypted Lua data files shipped
inside the installed terrain module (`Mods/terrains/<Terrain>/map/*.lua`) --
DCS-authoritative named-place and navaid/airfield data with no live mission,
no scripting sandbox, and no Windows round-trip required. Neither module
uses a Lua interpreter; both are strict, fully-anchored regex parsers that
raise on any entry-shaped text they cannot parse rather than silently
skipping it, per the project invariant that a format change must be a loud
exception, not plausible-looking wrong geography. See
`plans/m5-first-persistent-model/plan.md` Findings A and the "Airfield
layer" section for the research this rests on.
"""
