# M5 recon — road-file byte-format go/no-go, and terrain-mesh/elevation file recon

**Date:** 2026-09-03 (continued 2026-09-04)
**DCS version:** 2.9.29.27278 (per M0)
**Theatre:** Syria (roads cross-checked against Caucasus; terrain-mesh candidates Syria-only)

### Question

Two related questions, both aimed at deciding whether DCS-native *static files*
(rather than live-mission scripting) can supply geometry for the World Model:

1. (Continuing `2026-09-03-m5-roadnet-file-recon.md`) Is the `.rn4`/`.routes`
   binary container actually parseable — plaintext, simple fixed-record binary,
   known compressed container, or opaque/compiled — enough to judge whether a
   from-scratch parser is ~1-2 weeks of implementer effort or a rabbit hole?
2. (New ground) Does the Syria terrain module ship terrain heightfield/mesh
   data as static files that could replace or reduce M4's live-mission
   `land.getHeight` polling?

### Findings

**Part 1 — road/route file format**

- **The `.rn4`/`.routes` container header is a simple, consistent, fully
  decodable structure** — reproduced-locally by writing a Python `struct`
  decoder against the actual bytes already captured in
  `2026-09-03-m5-roadnet-files-probe-raw.txt` (first 512 / last 256 bytes of
  each file; no further DCS access needed for this step). Layout, identical
  across `Syria.rn4`, `Syria.routes`, `Damascus.rn4`, `Incirlik.rn4`, and both
  `Caucasus.rn4`/`.routes`:
  - 8 × little-endian `int32`: `[2, 48, <byte-count>, 0, 0, 0, 0, 0]`
  - one length-prefixed ASCII string (4-byte LE length + bytes): the class
    name, either `landscape4::lRoadNetwork` or `landscape4::lRoutesFile`.
  — **evidence:** reproduced-locally — **source:** `/tmp` decode script run
  against `2026-09-03-m5-roadnet-files-probe-raw.txt` this session.
- **The 3rd header `int32` (`<byte-count>`) exactly equals the file's own
  size in bytes for every `.rn4` file checked** (`Damascus.rn4`: header says
  376000, actual size 376000; `Incirlik.rn4`: header 825352, actual 825352;
  `Syria.rn4`: header 2275957360, actual 2275957360; `Caucasus.rn4`: header
  203468160, actual 203468160 — all exact matches). **The same field does
  *not* match for either `.routes` file checked** (`Syria.routes`: header
  says 2249141352 vs. actual size 2251462776, short by 2,321,424 bytes;
  `Caucasus.routes`: header 978211232 vs. actual 980525840, short by
  2,314,608 bytes) — **evidence:** reproduced-locally — **source:** same
  decode script. Not explained this session (see Unresolved); possibly a
  "primary data length" field that excludes a trailing index/table specific
  to `.routes`, but that's speculation.
- **`.rn4` files carry a length-prefixed string table of road/taxiway
  segment-type names immediately after the class name**, prefixed by a
  count field. For `Syria.rn4` the count field reads exactly **23**, and
  counting actual string entries visible in the 512-byte sample independently
  also gives 23 (`track`, `secondary`, `primary`, ... `rail_tunnel`) —
  the two numbers agreeing is strong internal-consistency evidence the
  header field really is "string table length." **evidence:**
  reproduced-locally — **source:** same. (`Syria.routes` has no comparable
  string table — its header field in the equivalent position reads `3`, but
  the bytes immediately following are plain `int32`s, not length-prefixed
  strings; not yet explained, see Unresolved.)
- **`Syria.routes`' data region decodes cleanly as an array of
  little-endian `float64` (x, y, z) triples, and the values are exactly the
  right shape and magnitude for a DCS-coordinate road-centerline polyline
  sample.** Decoding the first four 24-byte triples from the byte offset
  immediately following the header block gives:
  `(214985.70, 18.74, -45079.89)`, `(214985.65, 18.74, -45079.88)`,
  `(214982.84, 18.69, -45078.98)`, `(214958.38, 18.07, -45069.10)` — i.e.
  a large, plausible planar x-coordinate (~215 km, well inside the known
  Syria coordinate envelope — cf. `nodesMap.lua`'s `maxX=248852` from
  `2026-09-03-m5-recon.md` Finding 28, and the Gemerek testbed at x≈461,320
  showing the true extent runs well past that mission-generator working
  envelope), a small altitude-shaped y value (~18 m), a large plausible z
  (~-45 km), and **tiny, smoothly-decreasing deltas between consecutive
  triples** — exactly what a densely-sampled road-centerline point sequence
  should look like, not what random/unrelated binary data would look like.
  **evidence:** reproduced-locally (hand-verified with `struct.unpack('<3d',
  ...)` against the captured bytes) — **source:** same decode script, this
  session. This is the single strongest finding of this investigation: it
  confirms `.routes` is a **flat float64 (x,y,z) point array** in DCS engine
  coordinates, not an opaque or compiled blob.
- **A first attempt to hand-decode `.rn4`'s post-string-table binary records
  from the printed hex dump produced implausible values** (e.g. one field
  read as 48,842,496) — almost certainly a manual hex-transcription
  alignment error (copying multi-line `xxd` output by hand is error-prone),
  not evidence the format itself is irregular. **evidence:** inferred (this
  specific negative result is not trusted) — **source:** this session; the
  fix is the byte-exact script below, not more hand transcription.
- **The deep-dive probe (`probe_syria_terrain_files_deep.sh`) ran on the real
  installation and confirmed the `.rn4`/`.routes` header decode exactly as
  predicted, but its first version crashed** decoding `.routes` float64
  triples at a hand-derived data-start offset (99) — `OverflowError` in the
  consecutive-point-distance calculation, meaning at least one "triple" at
  that offset decoded to a wildly implausible float64 (garbage, not a
  coordinate). — **evidence:** reproduced-locally (crash traceback) —
  **source:** `2026-09-03-m5-terrain-files-deep-probe-raw.txt`. The crash
  itself is informative: offset 99 (derived by manually walking
  `class-name + 6×int32 + 8-byte sentinel + 2×int32`) is **not** actually
  where the float64 array starts — it does not match this session's earlier
  hand-decode, which found plausible triples starting around byte offset
  ~80. The exact correct offset was not re-derived by hand this session;
  instead the probe script was rewritten to **measure** it (see Reproducible
  Test) rather than trust another manual derivation.
- **Before the crash, the full `Syria.rn4` string table (23 entries) and a
  64-int32 raw sample of the post-string-table binary region were captured
  successfully** — this data was analyzed locally (no further DCS access
  needed) and gives a first real go/no-go read on the `.rn4` per-record
  layout: treating the sample as rows of 8 int32 (32 bytes) each yields 8
  full rows with **two columns exactly constant across all 8 rows** (column
  index 1 = always `1`, column index 4 = always `2`) and a third column
  that increments by one every two rows (`0,0,1,1,2,2,3,3` — a pair index),
  plus a fourth column that is the classic reversed-pair-counter pattern
  `1,0,3,2,5,4,7,6`. No other tested stride (2, 4, 16, or 32 int32) produces
  as strong or as statistically supported a regularity signal (16- and
  32-int32 "candidates" tie on constant-column fraction but only because
  they're tested against too few rows — 4 and 2 respectively — to be
  meaningful). — **evidence:** reproduced-locally (this session, local
  Python analysis of the already-captured 64-int32 sample; independently
  re-derived by the fixed probe script's new `rn4_stride_analysis()`
  heuristic, which agrees: stride=8 int32 wins with 2/8 constant columns
  over 8 rows) — **source:** `2026-09-03-m5-terrain-files-deep-probe-raw.txt`
  Part 1, decoded in this session.
  **Verdict: `.rn4`'s post-string-table region is very likely a fixed
  32-byte (8×int32) record**, with at least two constant "marker/tag"
  fields and at least one self-referential pair/index field — this is
  strong, non-coincidental structure (constant columns across 8
  independently-sampled rows is not what noise or a compressed/encrypted
  blob would produce), consistent with a node/edge or directed-segment-pair
  encoding. The exact semantic meaning of each of the 8 fields (which one
  is a string-table type index, which is a coordinate/`.routes`-array
  offset, which is a node id) is **not** resolved — the 64-int32 sample is
  too small to disambiguate that, and it needs either a larger sample (the
  fixed probe script now reads 512 int32 instead of 64) or cross-referencing
  against a second terrain (Caucasus) to confirm the layout generalizes.
  This is enough to upgrade the go/no-go call (see Possible Approaches)
  from "leaning GO, pending byte-exact record structure" to **"GO"** — the
  record structure is not a rabbit hole, it is exactly the kind of regular
  fixed-stride binary layout M1/M2's own container decodes already showed
  this game engine favors.
- **No public documentation of this exact container was found** (unchanged
  from `2026-09-03-m5-roadnet-file-recon.md`) — but the container itself
  turns out to be simple enough that documentation isn't really needed: it's
  a textbook "magic ints + length-prefixed class name + length-prefixed
  string table + flat binary array" serializer, the kind every game engine
  reinvents. **evidence:** inferred, from the decoded structure itself.

**Part 2 — terrain mesh / elevation files**

- **Syria's terrain module does not obviously ship a dedicated, identifiable
  heightfield file** the way it ships dedicated road files. Filename
  reconnaissance against `world-model/data/raw/dcs/2026-09-02/DCS-files.txt`
  found no `.dem`/`.hgt`/`heightmap`/`.raw` files anywhere under
  `Mods/terrains/Syria/`, and `clipmaps/` contains exactly three texture
  families — `colortexture/`, `normalmap/`, `splatmap/` — no fourth
  elevation/height clipmap directory. **evidence:** reproduced-locally
  (filename grep against the already-synced listing) — **source:**
  `world-model/data/raw/dcs/2026-09-02/DCS-files.txt`.
- **The only remaining static-file candidates are unread, single-purpose,
  differently-named binary formats, none sharing the `.rn4`/`.routes`
  `landscape4::` magic** (that magic string was only searched for in
  filenames, not contents, in this pass — see the new deep-dive probe
  script below for a real content check):

  > **CORRECTION 2026-09-05 (recorded here 2026-09-21) — the content check was run, and this
  > claim is false.** `surface/Syria.onlay.sup4` (680 MB) carries the header
  > **`landscape4::lSuperficialFile`** — *the same `landscape4` magic family* as `.routes`/`.rn4`
  > (`2026-09-05-m7-terrain-mesh-elevation-relitigation.md` Finding 4; raw bytes in
  > `2026-09-04-m5-terrain-files-deep-probe-raw-2.txt` from line 446). The same pass identified
  > `Syria.ng5` as `navGraph5File` (guessed "unclear" below) and `Syria.surface5` as
  > `landscape5::Surface5File`, carrying LOD-quadtree mesh vocabulary.
  >
  > **So the terrain-mesh NO-GO this section argues for was resting on a premise the bytes
  > contradict.** The practical outcome did not change — the relitigation deferred the mesh route
  > on decode *cost*, not on impossibility, and called `Syria.surface5` "a genuinely new,
  > non-trivial lead" rather than a dead end. But the reason changed completely, and that matters
  > for anyone reopening it.
  >
  > **This note flagged its own weakness in the same breath** — the parenthesis right here says
  > the magic string was matched against *filenames, not contents*, and proposes the probe that
  > later disproved it. The hedge was correct and was written down; the bolded sentence in front
  > of it is what a reader (or a graph query) carries away. **A caveat inside the claim does not
  > weaken the claim as it travels.**
  - `Mods/terrains/Syria/Scenes/Syria.scn5` — exactly one file, the only
    entry under `Scenes/`; by file naming convention (`.scn5` "scene v5")
    this is plausibly the terrain's master scene graph and could reference
    mesh/height data, but its size and structure are completely unknown —
    **evidence:** inferred (filename/directory shape only) — **source:**
    same listing.
  - `Mods/terrains/Syria/surface/Syria.tile`, `Syria.ng5`, `Syria.surface5`,
    `Syria.onlay.sup4` — four files, one each, distinct extensions
    suggesting four distinct sub-formats (`.tile` = tile index?, `.ng5` =
    unclear, `.surface5` = surface material definitions v5?, `.onlay.sup4`
    = overlay/blend "superimposed" layer v4?) — none opened yet.
    **evidence:** inferred (filename shape only) — **source:** same listing.
- **`Mods/terrains/Syria/terrain.cfg.lua.pak.crypt` is explicitly named as
  encrypted** (`.crypt` suffix on an otherwise-Lua config file), and this
  pattern (`terrain.cfg.lua.pak.crypt` + `manifest.bin`) repeats identically
  for every other installed terrain (Afghanistan, Caucasus, Kola,
  MarianaIslands) — **evidence:** reproduced-locally (filename listing) —
  **source:** same. This is a signal (not proof) that ED deliberately
  protects at least some terrain-defining assets from casual inspection,
  which is a reason for lower prior confidence that `Syria.scn5` or the
  `surface/` files will turn out to be a trivially-parseable plain
  heightfield, even though none of them individually carry a `.crypt`
  suffix.
- No probe of the actual bytes of `Syria.scn5` or the `surface/` files has
  been done — this is genuinely new, unexamined ground, not a
  previously-answered question. `2026-09-03-m4-elevation-recon.md` and
  `.../2026-09-03-m4-dcs-elevation.md` (M4's own elevation work) used live
  `land.getHeight` polling + external SRTM3 and explicitly did not
  investigate static terrain module files — confirmed by reading both notes
  this session.

### Reproducible Test

**Part 1** — the local decode (no DCS access needed, works from bytes already
captured): a Python script using `struct.unpack_from` against
`world-model/research/2026-09-03-m5-roadnet-files-probe-raw.txt`'s hex dumps,
run ad hoc in `/tmp` this session (not persisted as a repo artifact — trivial
to reconstruct from the header/field layout documented in Findings above if
needed again).

**New probe for the still-unread structure** (both parts):
`world-model/tools/wsl/probe_syria_terrain_files_deep.sh`

This is a real, runnable next step, not a placeholder. It does actual
struct-level parsing *on the WSL/Windows side* via an embedded Python3
script (multi-GB files never leave the DCS machine — the script only seeks
and reads small byte ranges):

- Re-reads `Syria.rn4`'s header and walks its **full** string table (not
  just the first-512-bytes sample), then decodes the following binary
  records as an int32 grid, both right after the string table and from a
  byte offset at the file's midpoint (to sanity-check whether the record
  shape looks consistent away from the start — record-length alignment at
  the midpoint isn't guaranteed since record size isn't known yet, but a
  plausible-looking int32 grid there is still informative).
- Re-reads `Syria.routes`' header fields generically (rather than assuming
  the exact layout inferred by hand) and decodes float64 (x,y,z) triples
  from both the start of the data region and a 24-byte-aligned midpoint
  offset, reporting x/y/z ranges and the consecutive-point-distance
  distribution — this directly tests whether the "smooth road polyline"
  finding above holds up away from the very first few points.
- For the Part 2 candidates (`Scenes/Syria.scn5`, `surface/Syria.tile`,
  `surface/Syria.ng5`, `surface/Syria.surface5`,
  `surface/Syria.onlay.sup4`, plus one sample `clipmaps/normalmap/*.tif.clipmap`
  file for comparison): reports size, hex dump of head/tail, checks for the
  `landscape4` magic substring anywhere in the head sample, and checks for
  zlib stream headers (`0x78` + valid FLEVEL byte) with a test-decompress —
  reusing the zlib-chunk precedent already confirmed for `.tif.clipmap`
  files (see agent memory `clipmap-container-format.md`).

To run it: sync into `win-mac-sync/run-wsl/` (the `wsl-probe-sync` skill
handles this), run in WSL bash on the Windows DCS machine with
`DCS_INSTALL_PATH` set, sync `syria_terrain_files_deep_probe_*.txt` back.

**2026-09-04 fix (this session)** — the script crashed partway through its
first real run (see Findings above) and has been revised, still at the same
path, still not re-run against the live installation yet:

- `.routes` float64-triple decoding no longer trusts a single hand-derived
  data-start offset. `routes_find_data_start_bruteforce()` scores every
  byte offset in `[64, 160)` by decoding ~40 candidate triples and checking
  (a) each triple falls inside Syria's known coordinate envelope
  (`x∈[-100k,600k]`, `z∈[-600k,600k]`, `y∈[-500,9000]`) and (b) consecutive
  points are smoothly connected (distance ≤ 2000 m) — exactly the two
  properties that made the original hand-decode ("a dense, plausible
  road-centerline polyline") convincing in the first place, now applied
  automatically instead of assumed. The best-scoring offset is used for the
  real sample; the old header-arithmetic offset (99) is still decoded too,
  for comparison, but is explicitly labeled a "hint only."
- All float64 decode/distance math is now overflow-safe
  (`_safe_unpack_triple`, `_safe_distance`) — a garbage/misaligned offset
  now degrades to a 0.0 score or a "skipped N non-finite" note in the
  output, never an uncaught exception. Verified locally against synthetic
  fixtures: (1) a file with real Syria-shaped triples at various offsets —
  the scanner finds them correctly; (2) 2000 bytes of pure `os.urandom` —
  the whole pipeline runs to completion with implausible-looking but
  non-crashing output, confirming the fix is robust to true garbage, not
  just to the one specific bad offset seen in the crash.
- `.rn4`'s record-region sample was widened from 64 to 512 int32, and a new
  `rn4_stride_analysis()` function scores candidate strides (2/4/8/16/32
  int32) by counting exactly-constant columns, requiring ≥4 full rows
  before trusting a candidate (avoids the trivial "any stride looks regular
  with only 2 rows to test" trap) and preferring the smaller stride on a
  tie. Verified locally against the existing 64-int32 sample: correctly
  recovers stride=8 int32, matching this session's independent hand
  analysis (see Findings).
- End-to-end dry run against synthetic fixture files (fake `.rn4`/`.routes`
  with the right header shape, fake zero-filled Part-2 candidate files)
  completed with no exceptions — confirms the fix doesn't just avoid the
  one specific crash but runs the full script to completion.

This fixed version is staged at `world-model/tools/wsl/probe_syria_terrain_files_deep.sh`
and needs one more Windows/WSL round-trip (via the `wsl-probe-sync` skill)
before its `.routes`-offset and `.rn4`-stride findings can be promoted from
"heuristic, tested only on synthetic data" to "reproduced-locally against
the real installation."

### Possible Approaches

**Roads/routes — recommendation: GO. Effort estimate: small (days, not
weeks) for a from-scratch parser, pending one more confirmation pass.**

1. The container format is not a rabbit hole. What's been decoded so far —
   a fixed header, a length-prefixed string table, and (for `.routes`) a
   flat `float64` (x,y,z) array — is well within normal "write a small
   binary parser" effort, the kind already done for the clipmap container
   format.
2. **Updated 2026-09-04**: the `.rn4` per-record layout — previously the one
   open unknown blocking a firm GO — now has a real, if still partial,
   answer: local analysis of the 64-int32 sample already captured shows
   strong evidence of a fixed 32-byte (8×int32) record with at least two
   always-constant marker fields and a self-referential pair-index field
   (see Findings above). This is exactly the "flat, fixed-size record
   array" case that Part 1 previously flagged as the good outcome, not the
   "real graph adjacency encoding" case that would have needed more work.
   Recommend upgrading from "leaning GO" to **GO**, with the caveat that
   the exact field semantics (which of the 8 fields is a string-table type
   index vs. a coordinate/node reference) still needs the widened 512-int32
   sample from the fixed probe script (already staged, not yet re-run) to
   fully pin down before an implementer starts writing the production
   parser.
3. `.routes` is the more immediately valuable file if only one is pursued:
   it already decodes as ground-truth DCS road-centerline points (real
   polylines, not reconstructed from a graph), which is a strict upgrade
   over OSM's several-hundred-meter-to-few-km real-world displacement noted
   in M1/M3 recon, at zero DCS runtime cost per point. Its exact data-start
   offset is the one loose end from this session — the fixed probe script's
   brute-force scan needs to run against the real file once more before
   this is fully "reproduced-locally" rather than "reproduced against a
   synthetic fixture" (see Reproducible Test above).
4. OSM remains the right source for road *attributes* (class, surface,
   name) that these files likely don't encode at all — this only affects
   whether road *geometry* can be DCS-native instead of OSM-derived, per
   the existing M3 pipeline design.

**Terrain mesh/elevation — recommendation: NO-GO for now; stick with M4's
existing live-`land.getHeight` + SRTM3 approach.**

1. Unlike roads, there is no file in Syria's terrain module that
   filename/directory-shape evidence points to as "obviously the
   heightfield" — the candidates (`Scenes/Syria.scn5`, `surface/Syria.tile`
   etc.) are single, differently-formatted, completely unread files, and
   the terrain module's config file being deliberately `.crypt`-suffixed
   is a mild signal ED protects at least some terrain-defining assets.
   Pursuing this further means reverse-engineering an entirely new,
   unknown container from scratch, with no internal-consistency check
   available yet (unlike roads, where 6 files across 2 terrains all shared
   one obviously-common format) — a materially weaker starting position
   than Part 1 had before this session's work.
2. This is explicitly *not blocking*: M4 already has a working,
   DCS-authoritative elevation pipeline (`land.getHeight` live-mission
   polling + external SRTM3 for anything outside live-probed points), so
   this would only be pursued as a **cost/latency optimization** to reduce
   Stage-2-style live polling volume, not to unlock a new capability.
   Given that, and given the weaker initial evidence, effort is better
   spent finishing the roads investigation (which has a much stronger
   signal already) before returning to this.
3. If Architect wants this reopened later, the `probe_syria_terrain_files_deep.sh`
   script above already includes the first real byte-level look at
   `Scenes/Syria.scn5` and the `surface/` files (head/tail hex dump +
   `landscape4`/zlib magic checks) — that single probe run would upgrade
   this from "inferred, unread" to a real go/no-go signal at very low
   additional cost, so it's worth running opportunistically even if roads
   remain the priority.

### Unresolved

- **Why `.routes`' header byte-count field doesn't match its actual file
  size** (short by ~2.3 MB in both Syria and Caucasus cases, but not by the
  same delta) — needs either a look at what's at the *end* of the data
  region (a trailing index/table the header count might exclude?) or
  cross-referencing against a `.routes` file small enough to inspect in
  full (no small `.routes` file is known to exist — only the two
  whole-theatre files were found; airfields only have `.rn4`, no paired
  `.routes`).
- **`Syria.routes`' field read as `3` in the position where `.rn4` has a
  string-table count is not yet explained** — the bytes following it are
  plain int32s, not length-prefixed strings, so either this field means
  something else for `.routes` (e.g. "coordinate dimensionality" or
  "sub-format version") or there's a small additional field this session's
  hand-decode missed. The new probe script reports the raw ints generically
  so this can be checked without assuming the answer.
- **The `.rn4` per-record binary structure is now believed likely (fixed
  32-byte / 8×int32 records, strong regularity evidence) but not confirmed
  against the real installation** — the 2026-09-04 local analysis used only
  the 64-int32 sample already captured before the original probe crashed;
  the exact semantic meaning of each of the 8 fields is unresolved, and the
  finding hasn't been cross-checked against a larger sample or a second
  terrain (Caucasus). The fixed probe script now reads 512 int32 and
  auto-scores stride candidates via `rn4_stride_analysis()`, but this has
  only been verified against synthetic fixtures and the pre-existing
  64-int32 sample — **needs one more Windows/WSL round-trip** to promote
  from "reproduced-locally, small sample" to a fully confirmed record
  layout.
- **The `.routes` float64-triple data-start offset is unresolved** — the
  original probe's hand-derived offset (99) demonstrably produced garbage
  (the crash), and this session's hand-decode (offset ~80, described in
  agent memory) was not independently re-verified this session either. The
  fixed probe script's brute-force scorer (`routes_find_data_start_bruteforce`,
  scanning `[64,160)`) is the mechanism meant to resolve this without
  further manual byte-counting, but **has only run against synthetic test
  fixtures so far, not the real `Syria.routes` file** — needs the same
  Windows/WSL round-trip as the `.rn4` stride question above.
- **`Scenes/Syria.scn5` and `surface/Syria.{tile,ng5,surface5,onlay.sup4}`
  have not been opened at all** — completely unread. The new probe script's
  Part 2 section is the first real look; until it's run, the terrain-mesh
  "no-go for now" recommendation rests on filename/directory-shape
  reasoning only, which is explicitly called out as `evidence: inferred` in
  the Findings above, not a confirmed negative.
- **Both forum threads flagged in `2026-09-03-m5-roadnet-file-recon.md`
  remain unread** (`forum.dcs.world` blocks automated fetch — per
  established convention, ask the user to paste content manually rather
  than treating this as an unread gap to re-attempt automatically).
