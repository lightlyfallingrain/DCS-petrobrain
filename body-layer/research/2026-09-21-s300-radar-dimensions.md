# S-300PS 40B6M / 64H6E real-world dimensions -- sourcing

Implementer research for `plans/aspect-aware-profiles/plan.md`'s "S-300 dimensions" section:
real, published physical dimensions for the two `object_model.py` rows this pass gives measured
`length_m`/`width_m`/`height_m` (`"S-300PS 40B6M tr"`, `"S-300PS 64H6E sr"` -- confirmed as the
exact real DCS `object_type` strings via `body-layer/src/perception/data/
dcs_type_to_reporting_name.tsv` lines 377/384, resolving to `"SA-10 Flap Lid radar"`/`"SA-10 Big
Bird radar"`). Per the plan's own discipline ("cite, don't guess"), every figure below is either a
published source or explicitly flagged as a rough estimate -- none are silently invented.

## S-300PS 40B6M tr (SA-10 Flap Lid radar, "tall mast")

The 40B6M is the universal mobile mast (Russian: 40V6M) that lifts the 30N6/Flap Lid engagement
radar above the local skyline/clutter.

- **Height: 24 m.** [Air Power Australia, "40V6M/40V6MD Universal Mobile Mast"](https://www.ausairpower.net/APA-40V6M-Mast-System.html)
  states the cited Russian-literature mast heights are 24 m (40V6M) and 40 m (40V6MD, the taller
  extension variant) -- specifically the antenna phase-centre elevation, not just a nominal
  figure. Independently corroborated by an Armorama modelling-community citation of "23.8 Mtr" for
  the same mast (search result title, "Armorama :: 30N6E./.23.8 Mtr 40V6M SEMIMOBILE MAST") --
  close enough to the Air Power Australia figure to treat 24 m as solid, not a single-source guess.
- **Length/width: no published figure found for the mast trailer's own footprint** (distinct from
  the erected mast height above). Estimated at **10 m x 3 m**, a typical towed Soviet/Russian
  military semi-trailer footprint (broadly consistent with the MAZ-74106 transporter's own
  10.18 m x 3.05 m chassis footprint, [Trucksplanet](https://www.trucksplanet.com/catalog/model.php?id=2402),
  though that specific chassis carries the 64H6E, not the 40B6M) -- **flagged explicitly as a
  rough estimate, not sourced for this specific mast trailer.** Height dominates this row's
  `apparent_extent_m` at every realistic aspect regardless (24 m vs. a single-digit-metre
  footprint), so this estimate's imprecision has no practical effect on the formula's output.

`length_m=10.0, width_m=3.0, height_m=24.0` -> `size_m=24.0` (`max` of the three, hand-set per the
plan's "S-300 dimensions" section).

## S-300PS 64H6E sr (SA-10 Big Bird radar, "low trailer")

The 64N6 ("Big Bird", DCS/Cyrillic-transliterated designation 64H6E) is the S-band long-range
surveillance/battle-management radar, mounted on a MAZ-74106 semi-trailer tractor.

- **Length: 13.2 m, width: 3.0 m.** [Army Recognition, "64N6 Tombstone - 64N6E - 64N6E2
  radar"](https://www.armyrecognition.com/military-products/army/radars/air-defense-radars/64n6-tombstone-64n6e-64n6e2)
  gives the system's overall dimensions as length 13.2 m, width (+/-) 3.0 m, height (+/-) 4.0 m.
- **Height: 10.0 m -- not from the Army Recognition figure above.** That page's height figure
  (~4 m) reads as the stowed/travel height (antenna folded for road transport), not the erected,
  hydraulically-raised operating height a hovering/approaching aircrew would actually see -- no
  published figure for the erected antenna height was found despite several targeted searches
  (Army Recognition, GlobalSecurity, Wikipedia, Military Periscope, cmano-db all describe the
  system functionally without an erected-height number). Using the **2026-09-21 sortie's own
  documented visual estimate instead** (`body-layer/research/2026-09-21-first-cones-sortie-
  results.md`: "A 64H6E mast is a roughly 10 m vertical structure standing clear of the skyline"),
  per the plan's explicit fallback ("mast height clearly ~10 m per the sortie's own visual
  description") -- **flagged as a rough estimate, sourced from in-game observation of the DCS
  asset rather than real-world literature.** Arguably more directly relevant than a real-world
  figure would be here, since `apparent_extent_m` governs detectability of the DCS-rendered model,
  not the physical article.

`length_m=13.2, width_m=3.0, height_m=10.0` -> `size_m=13.2` (`max` of the three, hand-set per the
plan's "S-300 dimensions" section).

## Not found, not fabricated

No published figure was located for either the 40B6M mast trailer's stowed footprint or the 64H6E
antenna's erected height -- both are explicitly flagged above as rough estimates rather than
presented as sourced fact, per the plan's own instruction not to invent a number silently.
