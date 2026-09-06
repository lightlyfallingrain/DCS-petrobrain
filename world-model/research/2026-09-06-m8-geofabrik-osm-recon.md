# M8 — Geofabrik OSM extracts (formats, coverage, parsing options)

**Date:** 2026-09-06
**DCS version:** not applicable — this investigation concerns OpenStreetMap/Geofabrik, not DCS internals
**Theatre:** Syria (envelope from `2026-09-05-m7-syria-theatre-extent.md`: lat 31.2–39.0 N, lon 32.3–40.2 E)

### Question

M8 re-introduces OSM as an augmentation layer via manually-downloaded Geofabrik per-country
extracts instead of M3's live Overpass API. Open questions: (1) does Geofabrik still offer a
stdlib-parseable format (`.osm.bz2` XML) or is `.osm.pbf` the only full-data option; (2) which
extracts cover the theatre envelope and how large is the covering set; (3) if `.pbf` is
mandatory, what's actually involved in parsing it and what are the library alternatives; (4) is
there a manual CLI clip/filter step that should happen before Python ever sees the data; (5)
rough feature-count order of magnitude for the M7 store-growth question.

### Important caveat on evidence quality for this session

`WebFetch` against `download.geofabrik.de` failed on every attempt this session — two 502s,
one 503, two 60s timeouts, across `asia.html`, `asia/syria.html`, and `europe.html`. Direct
`curl` from this environment's Bash tool is sandboxed/denied (no outbound network permission
for the coordinator process). The user offered mid-session to download files directly, but no
page content was pasted back before this report was written. **Everything below about Geofabrik
page contents (formats, sizes, region names) is therefore sourced from `WebSearch` result
snippets (search-engine cache of Geofabrik pages, and third-party pages quoting them), not a
direct read of the live page** — one step weaker than this investigator's usual "installed
software" or "reproduced locally" tiers. It should be treated as **forum-claim-unverified**
even though the source domain is Geofabrik itself, until someone opens the URLs below directly
and confirms. The PBF format facts (byte structure) and library license/dependency facts *are*
independently corroborated (OSM wiki, GitHub READMEs, PyPI) and are more reliable.

### Findings

**1. `.osm.bz2` XML — deprecated, do not plan around it.**
- Geofabrik officially discontinued `.osm.bz2` (bzip2'd raw OSM XML) extracts because nearly
  all downstream tools now support `.osm.pbf` — **evidence: forum-claim-unverified (WebSearch
  snippet of Geofabrik's own documentation/technical page), consistent across multiple
  independent search results** — **source:** WebSearch summary of `download.geofabrik.de`
  content, corroborated by community discussion (GitHub `download-geofabrik` tool docs).
- Geofabrik reportedly still generates `.osm.bz2` in the background "with a low-priority
  process" for legacy consumers, but these are described as larger and slower than the `.pbf`
  they're derived from, and not advertised as a first-class product — **evidence:
  forum-claim-unverified**.
- Practical implication: **plan on `.osm.pbf` being the only realistically available full-data
  format** for these extracts. Do not design the pipeline around a bz2/XML stdlib parse path
  as primary; treat it as unavailable unless someone confirms otherwise by opening a Geofabrik
  page directly.
- `.shp.zip` (Geofabrik's own shapefile product) is still offered but is **explicitly a
  filtered subset of features/attributes, not a complete extract** — Geofabrik's own
  documentation says so — **evidence: forum-claim-unverified, but directly quotes Geofabrik's
  technical page**. This rules `.shp.zip` out for anything wanting full tag fidelity (e.g.
  `place=hamlet` vs `place=village` distinctions, `natural=water` subtypes), though it could be
  a fallback for a narrower feature set (e.g. just settlement polygons) if `.pbf` parsing is
  rejected as a dependency. Also newer Geofabrik pages appear to additionally offer a
  `.gpkg.zip` (GeoPackage) product for at least some countries (seen on the Turkey page) — same
  "filtered subset" caveat likely applies; not independently confirmed either way for whether
  it's complete.

**2. Coverage set and sizes for the theatre envelope (31.2–39.0 N, 32.3–40.2 E).**

Geofabrik's continent-level groupings do not include a "Middle East" bucket — the top-level
split is by continent (africa, asia, australia-oceania, central-america, europe,
north-america, south-america, russia, antarctica) and **Turkey is filed under `europe/`, not
`asia/`** (`europe/turkey.html`), which is easy to get wrong when guessing URLs —
**evidence: forum-claim-unverified (WebSearch), but corroborated by an independently-returned
literal URL `download.geofabrik.de/europe/turkey.html`**. The needed set and reported
`.osm.pbf` sizes (all sizes from WebSearch snippets, **not independently verified — treat as
approximate until confirmed**):

| Extract | Geofabrik path | Reported `.osm.pbf` size |
|---|---|---|
| Syria | `asia/syria.html` | ~77 MB |
| Lebanon | `asia/lebanon.html` | ~49.2 MB |
| Israel and Palestine | `asia/israel-and-palestine.html` | ~114 MB |
| Jordan | `asia/jordan.html` | ~29.1 MB |
| Iraq | `asia/iraq.html` | ~86 MB |
| Turkey (whole country) | `europe/turkey.html` | ~612 MB |
| Cyprus | `europe/cyprus.html` | ~34.9 MB |

**Total minimal covering set ≈ 1.0 GB** in `.osm.pbf`, overwhelmingly dominated by Turkey
(612 MB of ~1002 MB total) even though the envelope only needs Turkey roughly down to the
Konya/Adana line, a fraction of the country. Geofabrik does not appear to publish an official
sub-national split for Turkey the way it does for large countries like Germany (states) or
India (zones) — no `europe/turkey/<region>.html` pages turned up in search. If that's
confirmed correct, **there is no smaller server-side Turkey extract to substitute** — the
options are (a) download the full 612 MB and clip client-side, or (b) accept the larger
download. This is the single biggest open question for sizing M8's manual-download step and
should be confirmed by opening `europe/turkey.html` directly (the user's offer to download is
the fastest way to settle it — see "what I need from you" below).

No page for a `.pbf` covering NE Egypt/Sinai was checked; the envelope only marginally clips
that corner and it is likely negligible — not investigated further given time budget.

**3. `.osm.pbf` structure and hand-rolled parsing feasibility.**

- Confirmed against the actual spec (`wiki.openstreetmap.org/wiki/PBF_Format`) —
  **evidence: documented**. Structure: repeating `[4-byte BE length][BlobHeader][Blob]` frames.
  `BlobHeader` (field 1 type string "OSMHeader"/"OSMData", field 3 datasize) is a tiny
  protobuf message. `Blob` carries either raw bytes or `zlib_data` (field 3) + `raw_size`
  (field 2) — decompress with stdlib `zlib`. Decompressed bytes are a `HeaderBlock` (for
  "OSMHeader" blobs) or `PrimitiveBlock` (for "OSMData" blobs).
- `PrimitiveBlock`: field 1 = `StringTable` (all keys/values as opaque byte strings, index
  0 reserved), field 2 = repeated `PrimitiveGroup`, field 17 = `granularity` (nanodegrees,
  default 100), fields 19/20 = `lat_offset`/`lon_offset`. Coordinate decode is
  `lat = 1e-9 * (lat_offset + granularity * lat_delta_accum)`, same for lon — deltas are
  packed/delta-encoded varints inside `DenseNodes` (field 2 of `PrimitiveGroup`, the form
  virtually all real-world extracts use for nodes rather than individual `Node` messages).
  Ways/relations are simpler (plain repeated fields, delta-encoded member/node-ref ids).
- Everything needed — varint decoding (7-bits-per-byte + continuation bit, a ~15-line
  function), protobuf wire-type/field-number dispatch (a `while pos < len: tag = varint();
  field_no, wire_type = tag>>3, tag&7; ...` loop), zlib inflate, and the delta/granularity
  math — **is achievable with stdlib `zlib` + `struct` + a hand-written varint reader, no
  protobuf compiler or `protobuf` pip package required**, *provided* the parser only needs to
  handle the small, fixed set of message types/field numbers actually used by real Geofabrik
  extracts (`HeaderBlock`, `PrimitiveBlock`, `StringTable`, `DenseNodes`, `Way`, `Relation`).
  Rough size estimate for a purpose-built reader emitting `place` nodes, `highway`/`natural`/
  `waterway` ways with their tags and lat/lon: **200–400 lines of Python**, comparable in
  complexity to the `.rn4`/`.routes` manual binary scan-forward parser already written for M5
  (`world-model/research/2026-09-04-m5-roadnet-byte-decode.md`) — i.e. within this project's
  established "we hand-roll undocumented/binary formats" pattern. Caveat: ways referencing
  node IDs need a node-id → (lat,lon) lookup pass either held fully in memory (fine at
  country-extract scale — tens of millions of nodes at ~16-24 bytes packed is a few hundred MB,
  Turkey being the outlier) or via a two-pass streaming approach, which is real added
  complexity beyond the `.routes`/`.rn4` precedent (those were single-pass over comparatively
  tiny files). **Evidence: inferred** from the documented format — no probe was written or run
  this session (no sample `.pbf` file is available locally to test against); this should be
  verified against an actual downloaded extract once the user has one.

**4. Library options.**

| Library | License | Install | Native build? | Notes |
|---|---|---|---|---|
| `pyosmium` (Python bindings for libosmium) | BSD-2-Clause | pip, prebuilt wheels for Linux/macOS/Windows x64 for maintained Python versions | No wheel needed on supported platforms; building from source needs cmake, expat, zlib, bz2 dev headers | Fastest, most complete, most widely used; but a compiled C++ extension dependency, not pure Python — same category of dependency this project has been avoiding (GDAL/rasterio-class) |
| `osmium-tool` (CLI, not a Python library) | GPLv3 | `brew install osmium-tool` on macOS | N/A — it's a compiled CLI binary, not a Python import | See item 4 below — this is a manual preprocessing tool, not a pipeline dependency |
| `pyrosm` | MIT | pip | Needs GeoPandas, Shapely, Cython, Protobuf, Cykhash — **pulls in GeoPandas**, exactly the dependency class `world-model/CLAUDE.md` has repeatedly avoided | Rules this out per existing project policy without a new escalation |
| `osmread` (dezhin) | MIT | pip, pure Python | No | Uses a pure-Python protobuf implementation, described by its own docs as slow; fine for country-sized extracts, likely too slow for full Turkey at scale; low/no recent maintenance activity observed |
| `osmiter` (MKuranowski) | MIT | pip, pure Python | No | Same pure-Python-protobuf performance caveat as osmread; reads XML/GZ/BZ2/PBF uniformly, which is convenient but not a meaningful advantage now that bz2 is deprecated |
| Hand-rolled stdlib parser (per item 3) | N/A (project code) | none | No new dependency at all | Only option that adds **zero** new dependencies; higher one-time implementation cost, matches the project's established `.rn4`/DDS/`.hgt` precedent of hand-rolling undocumented/binary formats with stdlib only |

None of these were installed or run this session (no probe was written per the "do not write
pipeline code" boundary for this investigation) — license and dependency claims are sourced
from each project's own README/PyPI page, which is reasonably strong secondary evidence but
**evidence: forum-claim-unverified** in the strict sense that this session did not run
`pip install` and inspect the actual dependency tree.

**5. Manual CLI preprocessing (osmium-tool / osmconvert).**

`osmium extract --bbox=LEFT,BOTTOM,RIGHT,TOP input.osm.pbf -o output.osm.pbf` (from
`osmium-tool`, GPLv3, `brew install osmium-tool` on macOS) clips a `.pbf` to a bounding box
before anything touches Python — **evidence: documented** (osmcode.org manual page, GitHub
README). This is the same execution-boundary pattern as `world-model/docs/M7_RUN_INSTRUCTIONS.md`:
a CLI the user runs once, manually, outside the Python pipeline. Because it's a locally-run
binary rather than a Python import, it is a materially lighter dependency decision than
`pyosmium`/`pyrosm` even though `osmium-tool` and `pyosmium` share the same underlying
libosmium C++ library and GPLv3-family licensing — the distinction the user asked to keep
explicit: **a manually-run CLI tool is not a pipeline runtime dependency**, it never ships in
`world-model/src/`'s dependency graph or gets imported by pipeline code. `osmconvert` is a
lighter-weight, older alternative CLI (single C file, easier to build, less actively
maintained) that supports the same `-b=` bbox clipping; not independently checked for its
current license this session.

Recommended manual step if the hand-rolled parser is chosen: run `osmium merge` (combine the
7 country extracts) then `osmium extract --bbox` (clip to the theatre envelope, ideally with
some padding) once per Geofabrik refresh, producing a single small clipped `.pbf` that the
Python pipeline then parses — turning "hand-roll a parser for a 1 GB multi-country input" into
"hand-roll a parser for a much smaller, already-bounded input," which meaningfully changes the
calculus in item 3's favor.

**6. Feature-count order of magnitude.**

No taginfo-style authoritative count was found for this specific envelope this session — the
searches returned only tangential humanitarian-mapping stats (e.g. "~173,400 km of roads in
Syria" from a HDX/HOTOSM export, itself dated/uncertain provenance). **Evidence: inferred**,
order-of-magnitude only, reasoning from country population/mapping-density priors rather than
a direct count: a covering set spanning all of Syria, Lebanon, Israel/Palestine, Jordan, Iraq,
and a large slice of Turkey plus Cyprus is a densely-mapped, high-population-density region
(unlike, e.g., a similarly-sized area of Siberia). Expect **highway ways in the high
hundreds-of-thousands to low millions**, **place nodes in the tens of thousands**, and
**natural=water/waterway features in the low-to-mid thousands** for the full covering set
before any bbox clip — i.e. **two to three orders of magnitude larger** than M7's existing
store (14,833 roads, 1,182 named places). After clipping to the actual theatre envelope
(a fraction of Turkey's area), the multiplier shrinks but is still very likely **10x+ on roads
alone**, given OSM's much denser road-network sampling than DCS's native `.rn4`/`.routes` mesh
which only encodes drivable/AI-usable roads, not every mapped path, track, and residential
street. **This is a real signal that the OSM layer will need its own filtering/decimation
design** (e.g. only `highway` values above `residential`/`track` for the "roads" layer; some
`place` rank cutoff) rather than being ingested wholesale as an equal-weight addition to the
existing store — but the exact cutoffs need real numbers from an actual downloaded extract to
set correctly, not this session's guesswork.

### Reproducible Test

None executed this session — no `.pbf` file was available locally, and direct `WebFetch` /
`curl` access to `download.geofabrik.de` was unavailable from this environment (see caveat
above). Once an extract is downloaded (see "what's needed from you" below), a natural first
probe: `python3 -c "import zlib,struct; ..."` reading the first BlobHeader+Blob pair and
confirming it decompresses to a valid HeaderBlock with the theatre's bbox inside it — this
would validate finding #3 without needing the full parser built yet.

### Possible Approaches

- **If zero new dependencies is the hard constraint**: hand-roll the `.pbf` reader per item 3,
  and require the user to run `osmium-tool` (a manually-invoked CLI, not a Python dependency)
  once to merge+clip the 7 extracts before the pipeline ever runs. This mirrors the M5/M2
  precedent of hand-rolling undocumented binary formats and keeps the "no new runtime
  dependency" invariant intact, at the cost of ~200-400 lines of new parsing code and an
  unverified performance/complexity profile at 1 GB input scale (mitigated by clipping first).
- **If a compiled dependency is acceptable with escalation**: `pyosmium` (BSD-2, prebuilt
  wheels, no compiler needed on macOS/Linux/Windows x64) is the standard, well-maintained
  choice and avoids writing/maintaining a PBF parser at all. This is a genuine new-dependency
  escalation per `docs/PROCESS.md` and should go to the user explicitly, not be decided here.
- **If bz2/XML were still available it would trivially win** (zero new deps, stdlib-only,
  already-proven `iterparse` pattern) but per item 1, plan as if it is not — confirm via the
  Geofabrik page directly before ruling it out completely, since this session's evidence is
  search-derived, not a direct page read.
- **Filtering/decimation for the OSM layer** (per item 6) should be scoped as part of M8's
  design, not deferred — unlike M3's Overpass path (which asked for exactly the features
  wanted via query), a full extract needs a client-side feature-type/tag filter regardless of
  which parser is chosen.

### Unresolved

- **Exact Geofabrik page contents (formats/sizes/region names) were never directly read this
  session** — `WebFetch` failed 5/5 times against `download.geofabrik.de` (502, 503, two
  timeouts) and outbound `curl` from the Bash tool is denied in this environment. All figures
  above are WebSearch-snippet-derived. **Action needed:** the user offered mid-session to
  download directly — the most useful thing they can check by hand is (a) whether
  `europe/turkey.html` truly has no sub-national split, since that extract dominates total
  download size, and (b) whether `.osm.bz2` links are genuinely absent from the page (not just
  unmentioned in search snippets) for at least `asia/syria.html` and `europe/turkey.html`.
- Whether `.gpkg.zip` (seen mentioned for Turkey) is a complete extract or, like `.shp.zip`, a
  filtered subset — not checked.
- No real `.pbf` sample was parsed; the ~200-400 line hand-rolled-parser estimate and the
  in-memory node-lookup sizing are inferred from the documented format, not measured.
- Real feature counts (item 6) are order-of-magnitude guesses; should be replaced with actual
  counts from a downloaded extract (e.g. `osmium fileinfo -e` gives per-type counts cheaply)
  before Architect finalizes any decimation thresholds.
- NE Egypt/Sinai corner of the envelope not checked for coverage — likely negligible, not
  confirmed.

### What's needed from the user (given the offer to download)

To resolve the biggest open item cheaply: open these two pages in a browser and report what
download links (format + size) actually appear:
1. `https://download.geofabrik.de/europe/turkey.html` — full list of formats/sizes, and
   whether there's a link to any sub-national Turkey split (there usually is a "sub regions"
   table near the bottom of a Geofabrik country page if one exists).
2. `https://download.geofabrik.de/asia/syria.html` — to confirm whether `.osm.bz2` is truly
   absent (not just absent from this session's search snippets).

If the user wants to proceed with downloading the full covering set now, the 7 files are listed
in the coverage table in section 2 above (`asia/syria.html`, `asia/lebanon.html`,
`asia/israel-and-palestine.html`, `asia/jordan.html`, `asia/iraq.html`, `europe/turkey.html`,
`europe/cyprus.html` → each page's `.osm.pbf` download link).
