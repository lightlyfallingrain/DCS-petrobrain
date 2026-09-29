# X-B26 — can DCS terrain elevation be read directly from DCS's own terrain files?

**Date:** 2026-09-29
**DCS version:** 2.9.29.27278 (per `autoupdate.cfg`, prior sessions; not reprobed this session — no
live DCS access from this machine)
**Theatre:** Syria (primary), cross-checked against Afghanistan/Caucasus/Kola/Mariana Islands for
generalization

> **ANSWERED THE SAME DAY, on the Windows box.** This note was written without live DCS access and
> treats the live probe as the working assumption for want of prior art. Both halves have since been
> measured: the bridge costs ~2 ms at 568 units
> (`aircraft-layer/research/2026-09-29-bridge-call-cost-at-scale.md`) and `.surface5` is confirmed to
> carry elevation but only decodes to a per-tile envelope
> (`world-model/research/2026-09-29-surface5-elevation-confirmed.md`). The conclusion — probe, not
> files — survives, but for the opposite reason to the one recorded here: not absence of prior art,
> but a cheap bridge against an expensive remaining decode.

### Question

X-B26 (`todo/backlog.md`): does DCS ship a readable, sufficiently fine elevation source in its
terrain-module files, such that the live-terrain-sampling design (`plans/live-terrain-sampling/
design-input.md`) can populate its fog-of-war probe store by parsing files instead of probing
`land.getHeight` through the mission-scripting bridge? This gates which of two materially different
builds the user's design gets: a file-reader (no in-mission calls, no frame-rate risk) or a batched
live-probe channel (known-working transport, unmeasured throughput at the needed scale — already
investigated in `aircraft-layer/research/2026-09-28-live-terrain-probing-feasibility.md`).

**This question was already investigated once, twice.** `world-model/research/
2026-09-03-m4-elevation-recon.md` (M4) and `2026-09-05-m7-terrain-mesh-elevation-relitigation.md`
(M7 relitigation) both cover exactly this ground. This note does not re-derive their findings — it
restates them against X-B26's specific framing, checks whether anything has moved since
2026-09-05 (nothing has — no commit since touches `surface5`/terrain-mesh decoding), and adds one
new check: whether the file layout generalizes across terrains (it does, structurally).
`.claude/scripts/gq.sh` reports no graph in this worktree (gitignored, main-checkout-only, per its
own note) — consistent with "not indexed here," not "nothing exists." The two prior notes above
were found by directory search of `world-model/research/`, which is exactly the fallback the
graph-query rule exists to reduce reliance on; they are the authoritative prior answer here.

### Findings

**1. What ships, and in what form — confirmed, restated from M4/M7, generalization newly checked.**

- **evidence: reproduced-locally** — **source:** `world-model/data/raw/dcs/2026-09-02/
  DCS-files.txt` (this session), `2026-09-03-m4-elevation-recon.md`, `2026-09-05-m7-terrain-mesh-
  elevation-relitigation.md`.
- No terrain module ships a flat, regular height grid anywhere in its file tree. The only structured
  candidate is `surface/<Terrain>.surface5` (`landscape5::Surface5File` header) — a recursive
  named-property container whose field vocabulary (`Land`, `Pbase`/`Nbase`, `nextLodIndex`,
  `maxEdge`, `depth`, `TRITYPE`/`TRI`) reads as an adaptive LOD-quadtree triangulated mesh. For
  Syria it is 30.4 GB, by far the largest file in the terrain module.
- **New this session**: the same four-file family (`Scenes/<T>.scn5`, `surface/<T>.ng5`,
  `surface/<T>.onlay.sup4`, `surface/<T>.surface5`) ships identically named under every installed
  terrain — `Afghanistan`, `Caucasus`, `Kola`, `MarianaIslands`, `Syria` all confirmed present in the
  file listing. So the *shape* of the file-route question generalizes across theatres; the *byte-level
  decode* (Finding 5 below) has only ever been attempted against Syria's copy and would need
  re-verification per terrain before trusting it elsewhere — a LOD-quadtree format could differ in
  header constants, byte order of a field, or tile-boundary conventions terrain-to-terrain even if
  the container grammar is shared.
- `clipmaps/` (the visual imagery pyramid, separately confirmed real satellite/scanned-chart imagery
  by `world-model/.claude/agent-memory/investigator/clipmap-container-format.md`) has exactly three
  subdirectories confirmed for Syria/Afghanistan/Kola: `colortexture`, `normalmap`, `splatmap`. No
  `heightmap`/`elevation` clipmap layer exists — ruled out as a second lead this session (a plain
  directory-listing check, not previously stated explicitly in M4/M7).
- The scripting-API route (`land.getHeight`/`land.getSurfaceType`) is Mission-Scripting-only — this
  is unchanged and is the world-model M4 decision already recorded in `world-model/CLAUDE.md`: "no
  offline heightmap exists, so extraction is always a live-mission probe."

**2. Readable or opaque — neither cleanly, and that ambiguity is itself the answer.**

- **evidence: reproduced-locally (header/structure) + inferred (payload semantics)** — **source:**
  `2026-09-05-m7-terrain-mesh-elevation-relitigation.md` Finding 5, `2026-09-04-m5-terrain-files-
  deep-probe-raw-2.txt` lines 95-618.
- `.surface5` is not opaque the way `.edce`/`.dll` are (no encryption, no compiled bytecode) — its
  outer container is a walkable "4-byte namelen+name, 1-byte type tag, 4-byte valuelen, value"
  recursive tree, the same grammar `.tile` already showed cleanly. That much is genuinely readable
  today, mechanically, without guessing.
- But the part that matters — the actual triangle/vertex position data inside `TRI` blocks — has
  never been opened. One float32 triple near the file header was pattern-matched by magnitude class
  to a plausible anchor point (x, elevation, z) at a single byte offset in a single file, on one
  terrain, never cross-checked against a real `land.getHeight` value at the same coordinates, and
  never confirmed on a second sample. No zlib magic was found in the head bytes sampled, which is
  weak evidence against zlib compression but does not rule out another scheme or a compressed region
  simply outside the sampled window.
- **Classification: unproven-but-plausible, not "readable."** It sits in neither of the two buckets
  the task named (`.routes` confirmed-parseable vs. `.edce` confirmed-opaque) — closer to "an
  unopened lock with a description of what's probably inside."
- No public documentation or community reverse-engineering of `landscape5::`/`Surface5File` exists
  anywhere searched (WebSearch + GitHub, per M7 relitigation Finding 7) — this project would be
  first, not verifying someone else's work.

**3. Resolution — unknown, cannot be compared to SRTM's 1000 m/11.52 m stddev.**

- **evidence: inferred, weak.** If the LOD-quadtree hypothesis is right, the finest level stores
  triangles at whatever granularity DCS's own render mesh uses, which is plausibly finer than
  SRTM — but this is a structural inference from field names, not a measured number. No resolution
  claim is defensible until at least one node's triangle data is actually decoded.

**4. Does a file read match `land.getHeight`'s surface — unresolved, and this is the same gap M7
flagged three weeks ago.**

- **evidence: none yet; a cheap test exists and was never run.** The exact cross-check M7's
  relitigation proposed remains the right one and is still undone: decode one quadtree node's
  anchor point from `Syria.surface5`, and compare it to a live `land.getHeight` call at the matching
  `(x, z)` (the M4 probe mechanism, or the now-existing mission-scripting bridge described in
  `aircraft-layer/research/2026-09-28-live-terrain-probing-feasibility.md`, already does this kind of
  call). This is the one measurement that would convert Finding 2 from "plausible" to "confirmed,"
  and it needs exactly one probe value plus one decode attempt — not a sortie's worth of anything.

**5. Cost shape — the file route's *promise* (a cheap dense full-theatre pre-build) is not
established, and the fog-of-war design's own cost is small regardless of source.**

- **evidence: inferred (arithmetic on established numbers), reproduced-locally (M8's write cost).**
- The task's own comparison point — Syria at a naive dense 30 m flat grid — is real and large:
  Syria's bbox is roughly 767 km (x) × 711 km (z) (`project_m7_theatre_extent` agent memory), so a
  uniform 30 m grid is on the order of (767000/30) × (711000/30) ≈ 25,500 × 23,700 ≈ **605 million
  cells**, i.e. several GB even at one `float32` per cell before any index overhead — this matches
  the task's own "~600M cells/~2.4GB" figure and confirms it independently. **This number is not
  changed by which elevation source feeds it** — a decoded `.surface5` mesh sampled onto a uniform
  30 m raster would be exactly as large as an SRTM raster at the same resolution. The file route's
  real advantage, if it works, is accuracy and no per-call bridge cost, not a smaller dense build.
- **The user's actual design is not a dense full-theatre build** — it is sparse, flight-following
  accumulation, exactly what M8's probe store already implements (tri-state per-chunk coverage,
  "never resample what's already held finer"). That store's write cost is already measured and
  cheap regardless of source: **~23 ms per 2,601-point chunk** (`plans/m8-incremental-store/
  implementation.md`, cited in the aircraft-layer feasibility note). So the cost-shape answer for
  the design as actually specified is: **cheap, as-you-fly accumulation either way** — the open
  question is only how the *samples themselves* get produced (parse a file locally with no per-call
  cost, vs. a `dostring_in` bridge call whose per-batch cost is the aircraft-layer note's own
  unresolved Finding 3), not how they get stored.
- **If** `.surface5` decode succeeded and yielded a queryable elevation function, a full pre-build
  into the *existing* base-store 1000 m grid (M7's shape, not a new 30 m dense grid) would cost
  whatever one theatre-wide walk of a 30 GB file costs — untested, but structurally similar to M7's
  existing full-theatre SRTM ingest (449 s for a comparable-scale pass over 131 staged tiles), so
  plausibly of the same order, not obviously prohibitive. This is speculative pending Finding 2/4.

**6. Unresolved, explicit.**

- **Whether `.surface5`'s `TRI`/`Pbase` blocks actually encode elevation, and at what resolution.**
  Resolves with: decode one node fully (byte range from its own length field) and cross-check its
  anchor point against a live `land.getHeight` call at the same `(x, z)` — see Finding 4. This is the
  single highest-value next step if the file route is to be pursued at all; nothing else below
  matters until this either confirms or kills it.
- **Whether `TRI` payloads are compressed, and with what scheme.** Resolves with: reading a full
  `TRI` block (not just its head bytes) and attempting a raw vertex-index/position interpretation
  before assuming compression.
- **Whether the Syria decode, if it succeeds, transfers to other terrains without re-verification.**
  The file *names* generalize (confirmed this session); the byte layout has only ever been sampled
  for Syria. Resolves with: repeating the same head/tail byte capture (`probe_syria_terrain_files_
  deep.sh`'s pattern) against one other terrain's `.surface5` (Kola is the theatre already flagged as
  the next stress case in `project_m7_kola_stress_test` agent memory, and has its own separate,
  unrelated elevation-source gap — SRTM doesn't cover ~68-69°N at all — so it's a natural next
  target for both questions at once).
## Forum threads READ 2026-09-29 (user pasted both) — no prior art, and the negative is informative

Both 403'd threads were opened manually by the user and pasted back. **Neither documents the
`.surface5` format, and neither offers an extraction method.** Recording the content rather than
leaving them as an open lead, so nobody re-fetches them:

- **`topic/157234` — "Can I export terrain mesh for app?" (2017).** Someone asking *this exact
  question*, for this exact purpose: a route-planning app needing DCS terrain heights, explicitly
  wanting the game's own data because *"it may or may not match real data"* — the same concern that
  produced this project's 11.52 m stddev problem. The replies point only at external DEMs (SRTM,
  paid providers). **The asker's own conclusion: *"I guess I'll just use a lua script in game to
  query the terrain height over a grid of lats and longs to get what I need."*** That is the live-
  probe route, chosen by someone who wanted the file route and did not find one.
- **`topic/48556` — "DCS Terrain Tool for 3rd party developers?" (2010).** About terrain *authoring*,
  not runtime files: the SDK is a **3ds Max** toolchain for building new theatres, and map makers
  describe creating a "land mesh" and populating it. Relevant only as corroboration of the shape of
  the problem — DCS terrain is an authored mesh compiled into a runtime artifact, not a heightmap
  that ships and can be sampled. Contains one dead-looking wiki pointer (`en.wiki.eagle.ru/wiki/
  All_about_land`, 2010-era).

**What this does to the recommendation.** It does not make the decode impossible, but it removes the
cheapest hoped-for outcome (someone has already named or cracked the format) and adds evidence for
the opposite: the only person found publicly asking this question gave up on files and went to
in-game Lua queries. Combined with the existing finding that no public documentation or community RE
of `.surface5` exists anywhere, **the expected value of the byte-decode spike drops and the
live-probe route's relative standing rises.** The spike is still cheap (hours) and still worth doing
before committing, but it should now be timeboxed as a *disproof* attempt rather than approached as
likely to succeed — and the live-probe design should be treated as the working assumption rather
than the fallback.

- **Two directly-on-topic ED forum threads remain unread**, 403'd on automated fetch both times this
  was tried (`forum.dcs.world/topic/157234-...`, `.../topic/48556-...`). Per this project's own
  standing convention (`forum-dcs-world-fetch.md` agent memory), this needs the user to open both
  URLs manually and paste content back — not another automated attempt, and not treated as a
  confirmed dead end. **This is the one item where I need something from the user rather than the
  Windows box**: if either thread contains a working extraction method or a name for this format
  that a search engine can then chase, it could shortcut the whole decode effort below.
- **No DCS install file beyond what's already in `DCS-files.txt` is needed to take the next step**
  (the node-decode-and-cross-check in Finding 4) — that step needs a byte-range read of an already-
  identified file plus one live `land.getHeight` call, both of which need the Windows box's DCS
  install and a running mission, not a new file fetch. If the user wants to run it: the exact
  target is `Mods/terrains/Syria/surface/Syria.surface5`, and the exact live-probe call to compare
  against already exists via `aircraft-layer/research/2026-09-28-live-terrain-probing-feasibility.md`'s
  Reproducible Test item 1 (a `land.getHeight` call riding the existing mission-telemetry bridge).

### Reproducible Test

None run this session (desk research only, per this project's execution-boundary rule — the
Windows-side DCS install was not touched). Two things are ready to run, in priority order:

1. **The Finding 4 cross-check** — decode one `.surface5` quadtree node's anchor point (byte offset
   and float32 layout already identified in `2026-09-05-m7-terrain-mesh-elevation-relitigation.md`
   Finding 5) and compare it to a live `land.getHeight` value at the same `(x, z)`, obtained via the
   `dostring_in` bridge snippet the aircraft-layer note already specifies. This single test resolves
   both "is this even elevation" and "does it match the live surface," which are the two things this
   whole question turns on.
2. **Re-run `probe_syria_terrain_files_deep.sh`** (or a same-shaped sibling) against one non-Syria
   terrain's `.surface5` to check the generalization claim in Finding 6 at the byte level, not just
   the filename level established this session.

### Possible Approaches

Laid out for Architect, not picked:

- **A. Timebox a small, cheap spike on the file route before committing to the probe route's
  plumbing.** The one test in Finding 4/Reproducible-Test-item-1 is small — one decode, one live
  probe call, one comparison — and if it *confirms* the file route works, it dominates: no bridge
  throughput ceiling, no frame-rate risk, matches the project's standing DCS-native-extraction
  preference. This is cheap enough (hours, not the 1-2 week full-decode estimate, which is only the
  cost of building a *production* reader, not of answering the yes/no question) that it is worth
  doing before Architect commits engineering time to the probe route's new plumbing (the aircraft-
  layer note's Approach B: new collector endpoint + Mac-side puller).
- **B. If the spike fails or the result is ambiguous, proceed with live probing as designed** —
  the aircraft-layer feasibility note already lays out that path in full (Approaches A-C there) and
  nothing in this note weakens it. It remains a known-working channel with an unmeasured but
  probably-tractable throughput ceiling.
- **C. Do not build a dense full-theatre raster from either source** — not what the user's design
  asks for, and Finding 5's arithmetic shows it is expensive under either source. The fog-of-war
  accumulation design (M8's chunk-coverage mechanism) sidesteps this regardless of which elevation
  source eventually feeds it.
- **If A is taken and confirms the file route**, the follow-on engineering (a real `.surface5`
  reader, generalized across terrains) is still the 1-2+ week reverse-engineering project M7's
  relitigation already scoped and costed — that estimate is unchanged by anything found this
  session, and should be its own timeboxed piece of work, not folded into the live-terrain-sampling
  feature itself.

### Bottom line

**Not established as viable yet, and it should not be assumed viable while planning.** The file
route is a real, structurally-generalizing lead (`.surface5` ships, identically shaped, on every
terrain) but the actual elevation payload has never been decoded or cross-checked against DCS's own
`land.getHeight` — it is exactly where M7 left it on 2026-09-05, unmoved by anything in the 24 days
since. The honest recommendation is: **spend the one cheap test (Approach A) to settle it before
choosing**, but if a decision is needed today with no further spike, **plan around live probing**
(Approach B) — it is the route with a known-working channel, even though its own throughput ceiling
is separately unmeasured (`aircraft-layer/research/2026-09-28-live-terrain-probing-feasibility.md`).
