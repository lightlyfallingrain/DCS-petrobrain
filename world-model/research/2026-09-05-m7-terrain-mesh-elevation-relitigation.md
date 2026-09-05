# M7 relitigation — can Syria's terrain-mesh files (`.surface5`/`.ng5`/`.tile`/`.scn5`) supply elevation offline?

**Date:** 2026-09-05
**DCS version:** 2.9.29.27278 (per M0), findings below are read of already-captured live-installation bytes, not a fresh probe run this session
**Theatre:** Syria

### Question

M4 (`2026-09-03-m4-elevation-recon.md`) and a follow-on M5 pass
(`2026-09-03-m5-terrain-file-formats.md`) both concluded no offline heightmap
exists, but the M5 pass explicitly flagged its own "no-go" as resting on
**filename/directory-shape evidence only** — `Scenes/Syria.scn5` and
`surface/Syria.{tile,ng5,surface5,onlay.sup4}` had never actually been opened.
That gap was closed by the `probe_syria_terrain_files_deep.sh` script's
**Part 2**, which *did* run against the real installation
(`2026-09-04-m5-terrain-files-deep-probe-raw-2.txt`, lines 95–618) — but no
one had gone back and read those results specifically for the elevation
question; M5's own note text was written before/without incorporating that
raw output's Part 2 content into its terrain-mesh conclusion. The user has
now rejected coarsening the live `land.getHeight` probe grid and wants this
re-litigated with real byte evidence, not the prior filename-based inference.

**Question: does actual byte-level inspection of these files change the
M4/M5 "no offline path" conclusion?**

### Findings

All findings below are **evidence: reproduced-locally** (read directly from
`2026-09-04-m5-terrain-files-deep-probe-raw-2.txt`, itself a real head/tail
byte capture off the live Syria installation) unless marked otherwise. File
paths are under `Mods/terrains/Syria/`.

1. **`Scenes/Syria.scn5`** (5.52 GB) — header `landscape5::Scene5File`,
   followed immediately by a long length-prefixed **string table of static
   object/prop names**: `townwall`, `fence_wall_crash`, `fanar`,
   `israel_town_house_01`, `toyota_sedan`, `car_crash_01`, `power_generator_01`,
   `village_house_02`, etc. This is a **static-object placement scene graph**
   (buildings, vehicles, clutter — the same kind of catalog a mission's
   static-object placer would draw from), not a heightfield. The tail bytes
   show repeating ~16-byte records with monotonically-increasing pointer-like
   values — consistent with an object-instance index, not elevation samples.
   **Ruled out** as an elevation source.
2. **`surface/Syria.tile`** (4.26 MB, small) — header
   `landscape5::SurfaceTile`, then a recursive named-property block
   containing shader/material definitions: `RunwayOnlay5.1`, `Splatmap5.1`,
   texture filenames (`fabricPalette.tif`, `pointAtlas.Splatmap5.1.blendTexture.tif`),
   and (in the tail) plaintext ASCII fields `maxU`/`maxV`/`minU`/`minV` with
   decimal-string values (`0.499495`, `0.500088`, ...) — **texture-atlas UV
   coordinates**, not world-space geometry. **Ruled out.**
3. **`surface/Syria.ng5`** (3.31 GB) — header string is literally
   **`navGraph5File`** — a navigation graph, not a terrain mesh. This is a
   new finding not previously identified even by name (M5's note only
   guessed "`.ng5` = unclear"). Its body is a dense table of small
   monotonically-increasing pointer/offset values paired with small integers
   (plausibly node degree counts) — structurally an adjacency/offset index,
   not a flat coordinate array (unlike `.routes`, which showed an
   immediately-recognizable float64 triple pattern). This is very likely the
   AI ground-unit pathfinding graph (a superset of the road network, possibly
   including off-road traversability), not elevation. **Ruled out** as a
   *direct* elevation source, though if it does encode node positions
   somewhere in its body those would carry elevation implicitly the same way
   `.routes` does — not established either way this session.
4. **`surface/Syria.onlay.sup4`** (680 MB) — header
   `landscape4::lSuperficialFile` (note: `landscape4`, the same magic family
   as `.routes`/`.rn4`), body contains `RadarPointsOnlay5.1`, `Building`
   labels and float32 fields (`intensity`, `omni`, `materialParamsIndex`) —
   a radar-cross-section / building-overlay data layer, not terrain shape.
   **Ruled out.**
5. **`surface/Syria.surface5`` (30.4 GB — by far the largest file in the
   entire terrain module)** — header `landscape5::Surface5File`. This is the
   one genuinely new, non-ruled-out finding. Its body is a recursive
   named-property tree (same "4-byte namelen + ASCII name, 1-byte type tag,
   4-byte valuelen, value" shape already seen in `.tile`) whose field names
   are exactly the vocabulary of a **LOD-quadtree triangulated terrain mesh**:
   `Land`, `Pbase` / `Nbase` (plausibly "position base" / "normal base" data
   blocks), `nextLodIndex`, `maxEdge`, `depth` (classic quadtree LOD-selection
   parameters), and `TRITYPE` / `TRI` (triangle-type / triangle data blocks,
   each with an explicit byte-length field, e.g. `TRI` block length `0x144c`
   bytes following a record count `0x6c8`=1736). Immediately after the header,
   at byte offsets ~0x80–0xac, three back-to-back float32 triples appear whose
   magnitude classes (`0x47xxxxxx` ≈ 10⁴–10⁵, `0x43xxxxxx` ≈ 10²–10³,
   `0x47xxxxxx` ≈ 10⁴–10⁵) are consistent with an **(x, y-elevation, z)
   anchor/bounding point in DCS's native coordinate scale** (matching the
   x/z magnitude ranges already established for Syria in M1/M5:
   tens-of-thousands to ~250,000 for x, similarly for z, with a distinctly
   smaller "hundreds" value in the middle position matching known Syria
   elevation range) — **evidence: inferred** (float-magnitude class-matching
   from a hex dump, not a confirmed decode; this is the same kind of
   pattern-match that correctly predicted `.routes`' float64 triples in M5,
   but has not been verified against a second sample or cross-checked
   against a known ground-truth elevation for the same x/z).
6. **No file anywhere in the terrain module is a flat, regular height grid.**
   Every candidate is either ruled out (Findings 1–4) or is a recursive,
   variable-length, typed-block container (`Syria.surface5`) whose likely
   payload is per-triangle/per-node mesh geometry inside an adaptive LOD
   quadtree — structurally the opposite of "coarsen a live probe grid": if
   real, elevation would be recoverable at whatever resolution the mesh's
   finest LOD level actually stores triangles, which could be *finer* than
   any practical live-probe grid, not coarser — but only by fully decoding a
   nontrivial recursive binary container, not by reading a header.
7. **No public documentation or community reverse-engineering of
   `landscape5::`/`Surface5File`/`navGraph5File`/`Scene5File` was found**,
   despite a harder search pass than M4's original one (`Surface5File`,
   `navGraph5`, `landscape5`, "DCS EDGE engine terrain quadtree",
   "DCS terrain SDK/export mesh" queries against WebSearch + targeted GitHub
   search) — **evidence: documented-absence** (a real, current negative
   search result, not an assumption). Two ED-forum threads surfaced that are
   directly on-topic by title (`forum.dcs.world/topic/157234-can-i-export-terrain-mesh-for-app/`
   and `.../topic/48556-dcs-terrain-tool-for-3rd-party-developers`) but both
   403'd on automated fetch — **unread, not a confirmed dead end** (see
   Unresolved; per established convention this needs the user to paste
   content manually rather than being treated as a settled absence).
   The one DCS-terrain-focused open-source project found
   (`JonathanTurnock/dcs-global-terrain-database`) confirmed by its own
   README to be a manually-curated GeoJSON database, not a binary-format
   parser, and does not touch elevation extraction at all.

### Reproducible Test

No new probe was run this session — all findings above are a fresh read of
bytes already captured live against the installation in a prior session:
`world-model/research/2026-09-04-m5-terrain-files-deep-probe-raw-2.txt`,
lines 95–618 (`probe_syria_terrain_files_deep.sh`'s Part 2 output — head
1024 bytes + tail 256 bytes of each of `Scenes/Syria.scn5`,
`surface/Syria.tile`, `surface/Syria.ng5`, `surface/Syria.surface5`,
`surface/Syria.onlay.sup4`, plus one `clipmaps/normalmap` sample for
comparison). To regenerate: re-run the same script (staged, read-only,
`world-model/tools/wsl/probe_syria_terrain_files_deep.sh`) via the
`wsl-probe-sync` skill.

**If Finding 5 is pursued further**, the concrete next probe is: extend
`probe_syria_terrain_files_deep.sh` (or a new sibling script) to (a) walk
`Syria.surface5`'s recursive named-property structure generically — the
"4-byte namelen+name, 1-byte type, 4-byte valuelen, value" shape is already
established and genuinely walkable without knowing every field's semantics,
the same way a ZIP/RIFF/TIFF reader skips unknown chunks — and (b) for a
handful of `Pbase`/quadtree-node blocks found this way, decode the leading
float32 triple and check it against a `land.getHeight` value queried live at
the same (x, z) via the existing M4 probe mechanism. That single
cross-check (mesh-derived elevation vs. live-`land.getHeight` ground truth
at matching coordinates) is what would promote Finding 5 from "inferred,
plausible field-name/magnitude match" to "reproduced-locally, confirmed."

### Possible Approaches

**If Architect wants to reopen this (real option, not free):**

- Finding 5 is a genuinely new, non-trivial lead: `Syria.surface5` most
  likely *does* encode elevation, at LOD-quadtree granularity that could
  outperform any practically-sized live-probe grid. Unlike M5's roads work,
  though, this is a recursive, deeply nested, 30 GB container with unknown
  compression on the actual triangle-data payload (`TRI` blocks) — cracking
  it to the point of extracting a queryable elevation surface is a
  meaningfully larger reverse-engineering project than `.routes`/`.rn4`
  (which was one flat array). Realistic effort: likely 1–2+ weeks of
  incremental probe/decode/verify cycles (matching this project's own
  iterative pattern for `.rn4`), with a real chance of hitting an
  undocumented compression scheme partway through that stalls it — this is
  a probabilistic bet, not a guaranteed win, and should be scoped and staged
  (e.g. "spend N days on the walkable-container-skeleton + one verified
  height sample; stop and report back before going further") rather than
  committed to as a full M7-blocking dependency.
- **A lower-cost partial win**: even without fully cracking `TRI` payloads,
  if `Pbase`/bounding-box-style header fields exist consistently across
  quadtree nodes (Finding 5's inferred anchor point), walking just the
  *node headers* (skipping/seeking past the compressed `TRI` bodies using
  their explicit length fields) could yield a coarse elevation grid at
  "one sample per LOD node" resolution for a fraction of the effort of a
  full mesh decoder — worth scoping as a distinct, smaller first milestone
  before committing to full triangle decode.
- **Fallback if this stalls or is deprioritized**: M4's existing
  `land.getHeight` live-probe + SRTM pipeline remains fully valid and
  already implemented (`src/elevation/`) — this investigation found no
  evidence that changes that recommendation as the safe default. The
  question this session answers is narrower: "is coarsening the *existing*
  probe grid the only lever available for M7 scale?" — **no**, `Syria.surface5`
  is a real, unexplored, potentially-finer-grained alternative lever, not
  yet provably one, that trades known-working-but-coarse for
  potentially-fine-but-unproven-and-costly.
- Given the user's actual objection was to *coarsening an existing working
  mechanism*, not to elevation data quality in the abstract, a pragmatic
  middle path Architect may want to consider: keep the live-probe pipeline
  as the shipped M7 mechanism (it works, it's DCS-authoritative, effort is
  sunk), and treat `Syria.surface5` decoding as an **explicitly separate,
  optional follow-on investigation** timeboxed on its own terms — not a
  blocking dependency for M7 completion.

### Unresolved

- **Finding 5 (`Syria.surface5` likely encodes elevation) is inferred, not
  confirmed.** It rests on field-name semantics (`Pbase`, `maxEdge`, `depth`,
  `TRITYPE`/`TRI`) and one float-magnitude pattern match at a single byte
  offset — the same *kind* of reasoning that correctly predicted `.routes`'
  format in M5, but not yet independently verified. Resolves with: the
  cross-check probe described in Reproducible Test (decode one node's
  anchor point, compare to a live `land.getHeight` call at the same x/z).
- **Whether `TRI` block payloads are compressed, and with what scheme, is
  completely unknown** — no zlib magic bytes were found in any head sample
  (checked automatically by the existing probe script), which either means
  the payload isn't zlib-compressed (plausible: could be raw/quantized
  triangle-strip binary, consistent with a real-time-engine format
  preferring fast decode over small size) or that the compressed region
  simply wasn't reached within the 1024-byte head sample examined. Resolves
  with: reading a `TRI` block in full, at the byte range given by its own
  explicit length field, and attempting to interpret it as raw
  vertex-index/position data before assuming compression.
- **`Syria.ng5`'s body (nav graph) was not decoded far enough to rule out
  it also carrying (x, y, z) node positions** the way `.routes` does for
  roads — if it does, this could be a second, denser (non-road-restricted)
  DCS-native elevation-adjacent dataset, but this session only established
  its header type name and an adjacency-index-shaped record pattern in the
  first 512 bytes, not enough to say either way.
- **Two directly-on-topic ED forum threads remain unread**
  (`forum.dcs.world/topic/157234-can-i-export-terrain-mesh-for-app/`,
  `.../topic/48556-dcs-terrain-tool-for-3rd-party-developers`) — both 403
  on automated fetch. Per established project convention
  (`forum-dcs-world-fetch.md` agent memory), this should be resolved by
  asking the user to open these two URLs manually and paste the content
  back, not by re-attempting automated fetch or by treating the absence as
  a confirmed dead end.
- No live-mission probe or WSL round-trip was run this session — everything
  above is analysis of bytes already captured in a prior session
  (2026-09-04). A real cross-check (Reproducible Test above) still requires
  one more Windows/WSL round-trip.
