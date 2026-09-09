### Goal

Add a second, independent `PerceptionSource` — naked-eye visual spotting — that reports
plausibly-visible ground objects from unfiltered `LoGetWorldObjects` data, gated by a synthetic
range/FOV/terrain-LOS detectability filter rather than any real DCS detection signal, since
investigation confirmed no such signal exists for ambient (non-scope) spotting.

### Context this plan is built on

- PB-1 (done, merged) built `HybridPerceptionSource`
  (`body-layer/src/perception/hybrid_source.py`): detection *existence* is gated on real
  HelperAI `list_indication(6)` text, which only populates once the crew has actively selected a
  target via the ASP-17 scope. Geometry comes from `association.py` matching that text against
  `LoGetWorldObjects` candidates.
- `body-layer/src/perception/geometry.py` already has bearing/range/terrain-LOS helpers,
  deliberately stopping short of a detectability decision — its own docstring names this as
  "a concrete tier's job... not this shared helper's," referring to the original plan's
  never-built "Tier 3" (a pure geometric proxy with no real detection gate at all). PB-1.5 is
  that deferred Tier 3, scoped specifically to naked-eye spotting.
- **Investigator findings this session**
  (`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`),
  resolving both open DCS-internals questions before this plan finalized:
  - **Q1 (export-layer filtering):** `LoGetWorldObjects` takes only a *category* argument
    (`"units"` default / `"ballistic"` / `"airdromes"`, per the primary-source reference
    `Export.lua` at `win-mac-sync/from-windows/Export.lua.reference-file-from-DCS-installation.lua`
    lines 624-629) — no radius or coalition filter exists. Every community export script filters
    client-side after the unfiltered call. Per-call cost at this project's realistic object
    counts is unquantified (directionally "can be inefficient" per Tacview's wiki, no hard
    numbers). Recommendation: add a cheap Lua-side manual distance filter before building the
    JSON payload, as a cap on payload/parsing size regardless of whether a real FPS problem is
    ever proven.
  - **Q2 (real ambient-detection signal) — the architecturally load-bearing question:**
    **confirmed absent.** All three HelperAI list leaves already tested live in PB-1's spike
    (`middle_list_text`/`lower_list_text`/`lower_lower_list_text`) stay empty until scope
    selection; two untested sibling leaves (`upper_list_text`/`upper_upper_list_text`) share the
    identical `show_list` gate in `HelperAI_page_common.lua`, structurally almost certainly the
    same behavior though not directly observed. No other Mi-24P indicator device is a plausible
    independent candidate. One unread forum bug report suggests Petrovich's voice callout may
    fire with **no Lua-readable companion signal at all**. Net: a clean "confirmed absent," with
    a cheap, non-blocking live-probe follow-up described in the research file (log the full
    HelperAI dump at the exact moment of a voice callout during a naked-eye-only pass, no scope
    slew) if the user wants to close the residual gap later.

**What Q2's answer means for this plan**: unlike `HybridPerceptionSource`, whose primary defense
of "Petrovich must never be omniscient" is that detection *existence* is real (HelperAI actually
populated something), the naked-eye channel has **no real existence signal to lean on at all**.
Its entire defense of the invariant is the synthetic detectability filter (range + FOV + terrain
LOS) built below. This is exactly the risk PB-1's own plan flagged for the never-built Tier 3:
*"Tier 3's detectability gate is not an optional refinement, it is the entire mechanism standing
between this data source and true omniscience."* That statement applies to this plan at full
force. See Decisions Requiring User Input #1 — this is not a decision the architect can make
alone.

### Affected Modules / Files

- `body-layer/src/perception/visibility.py` — **NEW.** Pure, fixture-testable detectability
  filter (no network I/O), mirroring `association.py`'s purity posture: given `OwnshipState` and
  a `WorldObjectCandidate` (reused from `association.py`, not duplicated), returns a
  `VisibilityResult | None` — `None` means "not plausibly visible," a `VisibilityResult` carries
  bearing/range/a confidence score and which gate(s) it passed. Composes three checks:
  1. **FOV cone** — `NAKED_EYE_FOV_HALF_WIDTH_DEG` off ownship true heading (default below).
  2. **Range-by-object-type curve** — a base detection range scaled by a coarse per-type
     multiplier looked up from `object_type` keyword match (same class of heuristic, and same
     "unvalidated starting guess" caveat, as `association.py`'s `_type_match_score`).
  3. **Terrain LOS** — reuses `geometry.line_of_sight_clear` as-is; this is the piece
     `geometry.py`'s docstring already anticipated needing.
  All three gates must pass; failing any one drops the candidate (absence, not a fabricated
  weak-confidence guess — deliberately stricter than `association.py`'s ambiguous-match
  compromise, since there's no real detection here to be ambiguous *about*).
- `body-layer/src/perception/naked_eye_source.py` — **NEW.** `NakedEyePerceptionSource`, a
  second, independent concrete `PerceptionSource` (not a `HybridPerceptionSource` subclass/
  extension — the two have fundamentally different gating mechanisms and shouldn't share a
  class hierarchy that implies a common detection-existence story). Each `poll()`:
  1. Fetches `GET /world_objects/latest` only — no dependency on `/petrovich_indication/latest`.
  2. Runs every candidate through `visibility.py`'s filter.
  3. **Per-object debounce**: tracks the set of `object_id`s that passed the filter on the
     *previous* poll. Emits one `Observation` only for an `object_id` newly entering the
     currently-visible set (mirrors `HybridPerceptionSource`'s change-debounce, but keyed on
     object-id membership rather than text-equality, since there's no text here).
  4. **Simultaneous-detection cap** (`NAKED_EYE_MAX_NEW_PER_POLL`, default below) — caps how many
     *newly-appearing* objects one poll can emit, nearest-first. Guards against an unrealistic
     "instant global awareness" flood the moment the aircraft turns toward a dense object
     cluster. See Decisions #2 — this cap is the plan's other invariant-relevant knob, alongside
     visibility.py's filter itself.
- `body-layer/src/perception/source.py` — add `SOURCE_NAKED_EYE_VISUAL_FILTERED` as a documented
  value for the existing plain-`str` `source` field (still not closing the type, per its existing
  docstring rationale — a third concrete source still isn't enough tiers to justify a `Literal`).
- `body-layer/src/logger.py` — wire both sources into the poll loop. **Decision (local,
  reversible): no new `CompositePerceptionSource` abstraction.** `main()` holds a plain
  `list[PerceptionSource]`, polls each, concatenates the returned `Observation`s before printing
  — `PerceptionSource.poll()` already returns `list[Observation]`, so this needs no new type.
  Revisit only if a third source or real fusion logic (Decision #3) makes a composite class earn
  its keep.
- `aircraft-layer/dcs-export/Export.lua`, `aircraft-layer/src/schema/world_objects.py` —
  **conditional, not required to ship v1.** Per Q1's finding, add a manual Lua-side distance
  filter (drop objects beyond some generous cap, e.g. 10 km, before `encode_world_objects_line`
  builds the JSON payload) as a cheap payload-size cap. This changes `/world_objects/latest`'s
  contract slightly (ground truth becomes "ground truth within N km of ownship," not truly
  global) — small enough to be a same-plan addition, but flagged separately since
  `Hybrid`/`association.py` currently rely on the *unfiltered* global feed and must be checked
  against whatever cap is chosen (their own `RANGE_CAP_M` is already 5000 m, comfortably inside
  a 10 km export cap).
- `body-layer/tests/test_visibility.py`, `test_naked_eye_source.py` — new, hand-authored fixture
  tests mirroring `test_association.py`'s pattern (dense multi-object scenes for the cap/debounce
  logic, edge-of-FOV and edge-of-range cases for the filter itself).
- `docs/concept/PETROBRAIN_RUNTIME.md` — update "Perception adapter" with the two-channel design
  and, explicitly, the asymmetric invariant story between them (real gate vs. synthetic filter).
- `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` —
  already written by Investigator this session; no further research needed to start
  implementation, though its two flagged opportunistic follow-up probes remain open (see Risks).

### Invariant Check

- **DCS authoritative, code owns facts:** satisfied — all geometry is read-only DCS ground
  truth; the visibility filter only *decides what to report*, never invents position/identity.
- **Petrovich must never be omniscient — this is the plan's central risk, not a satisfied box.**
  Unlike `HybridPerceptionSource`, this channel has no real detection-existence signal to point
  to. The entire defense is `visibility.py`'s filter being a *reasonably faithful* model of what
  a human crew could plausibly notice, not an excuse to report everything in range. Concretely:
  strict FOV cone, a conservative (not generous) range-by-size curve, real terrain LOS, and a
  per-poll emission cap are all invariant-load-bearing design choices here, not tuning
  parameters — flagged to the user as Decision #1 before implementation starts.
- **Provenance/uncertainty preserved:** every naked-eye `Observation`'s `provenance` string must
  read differently from Hybrid's (e.g. `"world_objects/visibility_filter_only"`), and its
  confidence should be capped below `CONFIDENT_ASSOCIATION_CONFIDENCE` (Hybrid's clean-match
  value) — a filter pass is structurally weaker evidence than a real HelperAI detection, and the
  schema must say so, not just the docstrings.
- **Read-only DCS access:** satisfied — no new DCS write path, same polling pattern as PB-1.

### Proposed Defaults (starting constants, all named/tunable, none validated)

- `NAKED_EYE_FOV_HALF_WIDTH_DEG = 60.0` — narrower than `association.py`'s
  `FORWARD_HEMISPHERE_HALF_WIDTH_DEG = 90.0` deliberately: Hybrid's window is a loose plausibility
  backstop behind a real gate; this one is the primary gate and should model an actual scanning
  arc, not just "somewhere plausible."
- `NAKED_EYE_BASE_RANGE_M = 2000.0` for a default/unclassified object type, scaled by a small
  per-type multiplier table (e.g. structures ×1.5, vehicles ×1.0, personnel ×0.4) keyed off the
  same keyword-overlap approach `association.py._type_match_score` already uses against
  `object_type` — reused pattern, not new machinery, but an equally unvalidated vocabulary (see
  Risks).
- `NAKED_EYE_MAX_NEW_PER_POLL = 3` — caps newly-emitted detections per poll tick, nearest-first.

### Implementation Plan

1. **`visibility.py`**: FOV + range-by-type + LOS composition, pure and fixture-tested first,
   before any live wiring — same sequencing discipline `association.py` used in PB-1.
2. **`naked_eye_source.py`**: wire `GET /world_objects/latest` polling, `visibility.py`, the
   visible-set debounce, and the per-poll emission cap. Fixture-test the debounce/cap logic with
   dense multi-object scenes (this is the part most likely to have an off-by-one or "reports
   everything on the first poll after a scene populates" bug).
3. **`logger.py`**: wire both sources as a plain list, tag flat-text output by `source`. Confirm
   the existing fake-`PerceptionSource` test pattern still demonstrates interchangeability with
   no new coupling.
4. **Aircraft-layer distance cap** (only if Decision review below confirms it's wanted for v1;
   otherwise defer as a fast-follow once real object counts are observed) — Lua-side filter in
   `Export.lua`, matching Q1's recommendation.
5. **Live acceptance test (user-run, per this project's execution-boundary rule)**: a naked-eye-
   only pass (no scope slew) near manually-placed ground targets at varied ranges/bearings,
   checking (a) in-FOV/in-range targets get reported, out-of-FOV/out-of-range/occluded ones
   don't, (b) the scope channel is unaffected by the new channel running alongside it, (c) no
   flood of Observations when turning toward a dense cluster.
6. **Docs**: update `PETROBRAIN_RUNTIME.md`'s Perception adapter section with the two-channel
   design and its asymmetric invariant story.
7. **Opportunistic follow-up (not blocking, not scheduled)**: the live HelperAI-dump-at-voice-
   callout probe from the research file's Reproducible Test section, if/when the user wants to
   close the residual "is there truly no Lua-readable ambient signal" gap. If it ever turns up a
   real signal, that becomes a preferred, stronger-invariant replacement gate for this channel —
   revisit this plan's Q2 branch at that point rather than assuming the synthetic filter is
   permanent.

### Risks & Unknowns

- **Core invariant risk** (restated from Invariant Check): this channel's entire "not omniscient"
  defense is a synthetic, unvalidated heuristic. If the FOV/range/type-multiplier defaults are
  too generous, this channel functionally becomes the pure ground-truth proxy the original PB-1
  plan explicitly avoided building.
- **Range-by-object-type multiplier table is unvalidated** — same class of risk as
  `association.py`'s keyword vocabulary, compounded here since it's now gating *existence*, not
  just disambiguating an already-real detection.
- **`LoGetWorldObjects` per-call cost is directionally but not numerically confirmed** — Q1 found
  no hard FPS-vs-object-count data; the Lua-side distance filter is a reasonable cap but its
  necessity for *this* project's realistic mission sizes is still unproven either way.
- **No coalition/IFF filtering** — same carried-forward gap as Hybrid/PB-1; more consequential
  here since this channel has a higher detection volume than the single-target scope channel.
- **Cross-channel duplication** — the same physical object could be reported by both channels
  (naked-eye first, then scope-selected later, or vice versa) with different `id`s and no shared
  identity. Left unresolved by design (Decision #3) — BL-2's future contact-memory layer is
  expected to own fusion, not this plan.
- **Two opportunistic Investigator follow-ups remain open** (untested `upper_list_text`/
  `upper_upper_list_text` siblings; the voice-callout-without-list-population live probe) — low
  priority, non-blocking, but should not be forgotten as "resolved."

### Second-Order Effect

This ships the generic "is X plausibly visible from here" detectability primitive
(`visibility.py`) that `geometry.py` explicitly deferred and that the original PB-1 plan named
but never built — any later channel needing the same reasoning (e.g. a future Mission
Interpreter check on "what could the player plausibly have known") can reuse it instead of
re-deriving FOV/range/LOS composition from scratch, at the cost of also being the first place in
the codebase where the omniscience invariant rests entirely on a heuristic rather than a real
signal — future reviewers of any reused-`visibility.py` channel need to re-examine whether that
channel's own detection-existence story is as weak as this one's.

### Decisions Requiring User Input

1. **Is a synthetic FOV+range+LOS plausibility filter, with no real DCS-sourced detection-
   existence signal behind it, an acceptable sole gate for a new perception channel?** This is
   the plan's central architectural risk (see Invariant Check). The alternative is not building
   this channel at all until/unless the opportunistic live probe (Implementation stage 7) finds a
   real ambient signal — i.e. treat naked-eye spotting as out of scope for now rather than ship a
   heuristic-only channel. Recommend proceeding with the heuristic given the user's explicit ask,
   but this needs to be an affirmed choice, not a default.
2. **Simultaneous-detection cap** (`NAKED_EYE_MAX_NEW_PER_POLL`): is nearest-first capping the
   right policy, and is `3` per poll (at whatever poll rate `logger.py` ends up using) a
   reasonable starting value, or should it be range-based ("all within X m") instead of count-
   based? Tied to Decision 1 — this is one of the two knobs actually defending the invariant, not
   a pure implementation detail.
3. **Cross-channel deduplication**: leave scope/naked-eye `Observation`s unfused at this layer
   (recommended — no contact memory exists yet, BL-2's natural job), or is some minimal same-
   poll same-object suppression wanted now? Lower-stakes than 1/2 but worth confirming before
   `logger.py`'s output shape is set.
4. **Aircraft-layer distance-cap timing**: land the Lua-side filter (Implementation stage 4) now,
   alongside this plan, or defer until real object counts are observed to actually need it?
   Local/reversible either way — proceeding with "defer, revisit if perf becomes visible" unless
   the user prefers to land it preemptively now.
