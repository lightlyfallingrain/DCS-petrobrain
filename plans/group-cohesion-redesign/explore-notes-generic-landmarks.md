# Explore — a landmark does not need its name (user, 2026-10-01)

Resolves the naming-source question the plan's landmark brief left open, and dissolves it rather
than answering it.

> *"'<village>' can also just be 'village' not necessarily the real name of the village. It's not
> like I know them either and not like the map names all of them."*

So *"group 10 o'clock, 2 km, south of the village"* is a complete, useful callout. The name is an
optional refinement, not the point.

## What this kills

The plan's open question was which source names a place — DCS's `towns.lua` gazetteer
(`named_place`, 23 044 Point rows) or OSM's (`settlement`, 26 182 Polygon rows) — since the same
village can appear in both under different names, and "south of \<village\>" needs one name used
consistently. **That question no longer blocks anything.** The generic noun is always available, so
the naming source becomes an enhancement to resolve later, on its own schedule.

Two reasons this is the better default rather than merely the cheaper one, both in the user's own
sentence:

- **The pilot does not know the names either.** A Syrian village name spoken aloud is not a handle
  he can act on; "the village south of you" is. The callout exists to orient him, and a name he
  cannot place does not orient him.
- **The map does not name them all.** Any design that depends on a name has a coverage hole
  wherever the gazetteer is thin, and would need the generic fallback regardless — so the fallback
  is the real mechanism and the name is the special case.

## What this means for the design

- **Generic kind nouns are the primary form**: village, town, city, road, river, valley, ridge,
  mountain, lake, sea. The world model's `subtype` already supplies these directly
  (`settlement.subtype` is village/town/city/built_up; `named_place.subtype` is
  village/town/peak/dam/city).
- **A name is spoken only when it adds something** — and when it does is now a smaller, later
  question. Plausible triggers worth considering rather than deciding here: the pilot used the name
  first, the mission briefing named it, or two same-kind landmarks need telling apart and the name
  is the cheapest discriminator.
- **The local-uniqueness test gets more important, not less.** Without a name, "the village" must
  be unambiguous from where the pilot sits — which is exactly the uniqueness test the landmark
  brief already requires, now carrying more weight because it is the only disambiguator left.
  Combination remains the resolver: *"in the valley, south of the village"*.
- **`built_up`, 94 % of settlement rows and mostly unnamed, becomes usable.** Under a
  name-dependent design those rows were dead weight; an unnamed built-up polygon can still be
  "the village" if it passes the extent and uniqueness tests. Worth re-checking whether `built_up`
  is actually village-shaped before relying on it — it is a landcover class, not a place class.
