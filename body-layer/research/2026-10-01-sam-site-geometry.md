# Real-world SAM site emplacement geometry, for the group-cohesion installation cap

**Date:** 2026-10-01
**DCS version:** not applicable — this is a real-world/doctrine research question, not a DCS-internals
one. DCS's own unit-placement behaviour (what mission authors actually do) is covered in §3 below.
**Theatre:** Syria, as flown by the Mi-24P sorties this project uses as ground truth.

### Question

`plans/group-cohesion-redesign/plan.md` §3 proposed a flat 1000 m cap on inter-component spacing for
an "air-defence installation" group, justified by the **only measurement on hand** — 236–838 m
spacing between four S-300 components in one DCS sortie's detection trace. The user has since said
that measurement is worthless: *"the SAM battery placement was not realistic, rather that units put
on map for testing. Search internet for realistic SAM site patterns."* Both the number and its
justification need replacing with something grounded in real emplacement geometry, covering the SAM
families DCS actually models over Syria, and distinguishing real doctrine from what DCS mission
authors typically place.

### Findings

**S-75/SA-2 (classic "flower"/star site)**
- Six single-rail launchers in a hexagonal "flower" pattern around a central Fan Song radar and
  control van. — **evidence:** documented — **source:** [geimint.blogspot.com S-75 site analysis](http://geimint.blogspot.com/2007/07/s-75-sam-system-site-analysis.html); [Air Power Australia, SAM Site Configs Part 1](https://www.ausairpower.net/APA-Rus-SAM-Site-Configs-A.html)
- Launcher-to-launcher spacing **≈ 60–100 m**. — **evidence:** documented (multiple independent
  secondary sources cite this figure for the hexagon arrangement) — **source:** aggregated from the
  above plus general open-source SA-2 site descriptions; no single primary cite gives a tighter
  error bar than this range.
- Overall site diameter **≈ 160–230 m** (0.16–0.23 km), with ~200 m as the typical figure.
  — **evidence:** documented (satellite-imagery-based site analysis) — **source:** geimint
  blogspot (explicit Google Earth measurement, author flags it as approximate); ausairpower
  corroborates the same range independently.
- Individual launcher revetments 20–25 m across (30 m for Chinese HQ-2 copies). — **evidence:**
  documented — **source:** ausairpower.

**S-125/SA-3 (low-altitude complement to SA-2)**
- Three or four launch positions (two-rail 5P71 or four-rail 5P73) arranged around a central
  LOW BLOW radar, in triangular, parallelogram, trapezoidal, or square patterns depending on
  terrain/site. — **evidence:** documented — **source:** ausairpower; geimint S-125 site analysis.
- Launcher spacing **≈ 60 m**, cited via the commonly repeated "hand-shaped" (finger-spread)
  description of the launcher arrangement. — **evidence:** forum-claim/secondary-source,
  moderately corroborated (repeated across independent summaries but no primary imagery
  measurement found with a stated error bar) — **source:** aggregated secondary descriptions;
  primary ausairpower/geimint material gives the *shape* but not a numeric spacing.

**S-200/SA-5 (strategic, long-range — unlikely Mi-24P-relevant but DCS models it)**
- Two to five launch areas, each with six launch rails; "large expansive footprint," radars and
  control bunkers near but behind revetments from the rails. No numeric spacing found in any
  source consulted. — **evidence:** documented (shape/composition only) — **source:**
  ausairpower. **Site diameter not established** — flagged unresolved below. Low relevance to a
  Mi-24P sortie profile (strategic, rear-area system); included for completeness only.

**SA-6/2K12 Kub**
- Battery = one 1S91 "Straight Flush" radar + typically four 2P25 TELs (triple-rail), arranged in
  the "Kvadrat" (square) pattern with the radar at centre. — **evidence:** documented — **source:**
  Wikipedia/weaponsystems.net cross-checked, consistent with Falcon-Lounge BMS threat guide.
- **No numeric spacing figure was found in any source consulted** for TEL-to-TEL or TEL-to-radar
  distance. This is the real evidentiary gap for the single most Syria-relevant mobile SAM.
  Flagged unresolved below.

**SA-8/Osa, SA-15/Tor, SA-19/Tunguska — single-vehicle systems**
- Each of these is one vehicle carrying its own search/track radar **and** launchers/guns — there
  is no "site" to measure, because the engagement unit and the sensor are the same platform.
  — **evidence:** documented (basic system composition, uncontested) — **source:** Wikipedia/
  armyrecognition entries for 9K33 Osa, 9K330/Tor, 2K22 Tunguska.
- A **battery** of these (e.g. a Tunguska battery = six 2S6 vehicles + a PU-12M/Ranzhir command
  post) *does* disperse multiple same-type vehicles for survivability, but **no numeric
  vehicle-to-vehicle spacing figure was found** in any source consulted (several searches
  targeted this specifically). — **evidence:** inferred from general dispersion doctrine
  (see RUSI/Bronk reference below), **not** a measured figure — **source:** none found with a
  number; flagged unresolved below.

**SA-11/Buk**
- Battalion = command vehicle + target-acquisition radar (TAR) + up to six TELARs (self-contained
  radar+launcher vehicles) + reload TELs; a battery-level sub-unit has 1–2 TELARs. — **evidence:**
  documented (composition) — **source:** Wikipedia/armyrecognition. Each TELAR is itself a
  self-contained radar+launcher (like Osa/Tor), so a Buk "group" is closer to several
  semi-independent nodes than to a single fixed star-pattern site.
- **No numeric inter-vehicle spacing found.** — unresolved.

**S-300 family (SA-10/SA-20)**
- Battalion: acquisition radar, engagement radar, 8–12 TELs, command post, loader — launchers
  placed on concrete pads, levelled by hydraulic jacks; engagement radar occasionally tower-mounted
  (24.4 m) in forested/rugged terrain to clear line of sight. — **evidence:** documented
  (composition/mounting detail) — **source:** FAS/nuke.fas.org SA-10 Grumble page,
  mitchellaerospacepower.org. **No numeric spacing figure found.**
- The one number this project already had — 236–838 m from the 2026-10-01 DCS sortie — is
  **ruled out by the user as not reflecting real emplacement**, confirmed by the absence of any
  real-world source giving a comparably tight number; real S-300 spacing was not independently
  established by this research (unresolved).

**AAA: ZSU-23-4 Shilka, ZU-23 towed**
- No numeric emplacement-spacing figure was found for either, in airfield point-defence or battery
  configuration. — unresolved. The one tangential figure found (ammo-truck resupply radius ~200 m,
  from the DCS-specific airgoons source below) is a DCS gameplay mechanic, not a real-world
  emplacement fact, and is reported separately.

**General Soviet/Russian dispersion doctrine (cross-cutting, not family-specific)**
- Doctrine explicitly favours dispersing battery components (pre-surveyed alternate positions,
  camouflage, EMCON "hide, shoot, scoot") specifically so a single strike cannot kill a whole
  battery — the same reasoning the user gave. — **evidence:** documented (doctrine description,
  not geometry) — **source:** [Air Power Australia, SAM System Mobility](https://www.ausairpower.net/SP/DT-SAM-Mobility-Sept-2009.pdf);
  general open-source IADS doctrine summaries. **No numeric distance accompanies this doctrine
  statement in any source found** — it establishes *why* sites are spread, not *how far*.
- I attempted to fetch RUSI's Bronk IADS report (`static.rusi.org/20191118_iads_bronk_web_final.pdf`),
  a credible primary analytical source on this exact doctrine question — the fetch tool returned
  the PDF as unreadable binary rather than extracted text. **This is a genuine unread source, not a
  403** — flagged for the user to open directly if more precision is wanted (it is a long,
  citable RUSI monograph specifically on Russian/Chinese IADS employment and would very likely
  contain the dispersion-distance doctrine this research wants).

**What DCS mission authors/community guides actually recommend (distinct from doctrine)**
- A DCS-specific mission-building tutorial gives: *"Disperse components: 200–800 m spacing keeps
  one JDAM from deleting an entire battery,"* *"Spread units 200–600 m for survivability; keep LOS
  to the radar"* (for an SA-6-type battery specifically), short-range point-defence systems (Tor/
  Osa) offset **1–2 km** from the high-value asset they protect, and AAA/MANPADS ringing a site at
  **0.5–1 km**. — **evidence:** forum-claim-unverified (a community tutorial, not doctrine or
  measured imagery; no citation of its own given) — **source:** [letsflyvfr.com DCS mission
  editor tutorial](https://letsflyvfr.com/dcs-world-mission-editor-tutorial-how-to-build-air-defences-sam-aaa-for-beginners/).
  This is exactly "what mission authors are told to do," not "what real sites look like" — useful
  as the *other* data point the plan asked for, not as ground truth.
- A second DCS reference page notes mechanically that "most multi-unit SAMs are able to spread
  units as far as 25 nm from each other" in the engine (a game-engine group-radius limit, not a
  realism claim) and that all SAM components must share one Mission Editor group to function.
  — **evidence:** documented (DCS mechanic) — **source:** [airgoons.com DCS Reference: Air
  Defences](https://www.airgoons.com/w/DCS_Reference/Air_Defences). This confirms the earlier
  finding (236–838 m) was well inside what the engine *permits*, saying nothing about what is
  realistic — consistent with the user's "placed for testing" read.

### Reproducible Test

Not applicable in the probe-script sense — this is desk research, not a DCS probe. The check that
*is* reproducible: re-run the web searches/fetches above; the geimint and ausairpower pages are
static long-form analyses unlikely to change, and both explicitly flag their own measurement
methodology (Google Earth, stated as approximate) rather than claiming precision.

### Possible Approaches

The plan's §5 question — can one flat metre value serve all these families — has a clear answer
from this research: **no, and more importantly, the *kind of number* needed differs by case, not
just its value.**

1. **Fixed-radar star/flower sites (S-75, S-125, and by analogy S-200, S-300, SA-6 Kvadrat)** —
   genuinely one emplacement, components doctrinally bounded to roughly **60–230 m** of each other
   (tightest, best-sourced figures: S-75 ≈ 60–100 m launcher spacing / ~200 m site diameter; S-125
   ≈ 60 m). No source found puts any of these families' real spacing anywhere near 800+ m. A flat
   cap in the **200–300 m range** is defensible for this group, with real-doctrine support; it
   would also have correctly rejected the DCS test-sortie's 838 m outlier as too wide for a single
   installation — which is itself evidence the flat-cap design direction is right, only the number
   was wrong.
2. **TELAR-based mobile batteries (Buk, and S-300/SA-6 in their mobile dispersed mode)** — no
   measured figure exists anywhere consulted. The DCS community's own practical number (200–800 m)
   is the best available anchor *for this subfamily specifically*, precisely because these systems
   are the ones doctrine explicitly tells to disperse for survivability (unlike the fixed star
   sites, whose components are cabled/RF-linked and can't be far apart). Recommend scoping a wider
   cap — **≈ 500–800 m** — for recognized multi-TELAR/multi-TEL batteries (Buk, S-300 mobile, SA-6),
   separate from the tighter fixed-site cap in (1), if the `op_class` vocabulary can distinguish
   them; otherwise one shared cap at the upper end of (1)'s range understates Buk/S-300 and one
   shared cap at this range overstates S-75/S-125.
3. **Single-vehicle systems (Osa, Tor, Tunguska, Shilka)** — these are not candidates for an
   "installation cap" at all; each one *is* its own radar+launcher. The line the plan asks about
   (§4) falls exactly here: **a lone Osa/Tor/Tunguska/Shilka is never a multi-component
   installation, and the kind-coherence rule should not be the mechanism that merges two of them.**
   If two Tor vehicles from the same battery sit within a few hundred metres to a couple of
   kilometres of each other (the DCS-community figure for SHORAD offset from a protected asset is
   1–2 km, and Tunguska/Pantsir battery dispersion for survivability is plausibly similar, though
   unmeasured), that is **battery-mate cohesion among same-class single-vehicle systems**, which is
   a different and looser question from "radar+launcher that belong to one fixed site." The
   relative/density test the plan already keeps as the outer gate is the right tool for this case,
   not a flat kind-coherence cap — a flat cap wide enough to catch real Tor-battery dispersion
   (≥1 km) would, as the plan itself worried, risk merging two genuinely unrelated single-vehicle
   SAMs a kilometre apart.
4. **Given the evidentiary gaps above, the single most defensible concrete number to replace 1000 m
   with, if the plan wants to keep one flat constant for the whole `AIR_DEFENSE_INSTALLATION_CLASSES`
   set:** something in the **300–500 m** range — above the best-documented fixed-site figures
   (covers S-75/S-125/Kvadrat-pattern SA-6 comfortably with margin), below the DCS-community's own
   800 m outer bound for "disperse components" and far below the discredited 838 m single data
   point, and explicitly **not** large enough to cover genuine multi-TELAR Buk/S-300 dispersed
   deployments or SHORAD-vehicle battery spacing — which is honest, because no source found
   supports a tighter number for those without either accepting the DCS-community heuristic or
   flying more sorties against real mission-author placements to re-derive the next 236–838-style
   measurement, this time against a mission built to realistic doctrine rather than a test map.

### Unresolved

- **No numeric real-world spacing figure exists in any source consulted for SA-6/Kub TEL-to-radar
  distance, Buk TELAR-to-TELAR/TAR distance, S-300 TEL-to-radar distance, or Tunguska/Pantsir
  battery vehicle dispersion.** These are exactly the Syria-relevant mobile systems the plan most
  needs a number for, and the gap is real, not a search failure — multiple distinct queries were
  run per system. Satellite-imagery analyses of real deployments (Oryx/Bellingcat-style
  Ukraine-war imagery geolocation work) were not located in this session but are a plausible next
  source — they post-date most of the classic Cold-War-era site-analysis blogs cited above and
  may have measured exactly these systems in the field from the 2022+ war; worth a follow-up
  search specifically against Oryx/Bellingcat/OSINT-Twitter archives if the user wants tighter
  numbers before the next sortie.
- **RUSI's Bronk IADS monograph** (`static.rusi.org/20191118_iads_bronk_web_final.pdf`) — a strong
  candidate primary source for the dispersion-doctrine distance question — could not be read by
  the fetch tool (returned as unreadable binary, not a 403). If the user can open it directly and
  paste the relevant section (search for "dispersion," "survivability," or "single-shot kill
  probability"), that would likely resolve several of the gaps above.
- **S-200/SA-5 site diameter** — composition and shape are documented, no numeric spacing found;
  low priority given its rear-area/strategic role makes it unlikely to appear in a Mi-24P-relevant
  Syria scenario.
- **AAA (Shilka/ZU-23) real-world emplacement spacing** — not found in any form (doctrinal or
  measured); the only figure encountered was a DCS gameplay mechanic (ammo-resupply radius), which
  is explicitly not a geometry fact and should not be used as one.
- No search specifically targeted post-2022 Ukraine-war OSINT imagery geolocation (Oryx, Bellingcat
  threads, Covert Shores, etc.), which is the most likely place to find recently-measured real
  figures for Buk/S-300/Tor since those systems have been destroyed and geolocated in the field
  repeatedly during that war — flagged as the clearest next step rather than closed out as a dead
  end.
