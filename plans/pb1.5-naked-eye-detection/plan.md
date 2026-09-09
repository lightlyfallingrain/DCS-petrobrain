### Goal

Add a second, independent `PerceptionSource` — naked-eye visual spotting — that reports
plausibly-visible ground objects from unfiltered `LoGetWorldObjects` data, gated by a
detectability filter modeled on ED's own published Petrovich detection constants (angular-radius
recognition tiers, not an invented range multiplier) and quantised to ED's own ambient-callout
vocabulary, deliberately decoupled from the still-open question of whether any live DCS signal
mirrors that callout in exportable Lua.

### Context this plan is built on

- PB-1 (done, merged) built `HybridPerceptionSource`
  (`body-layer/src/perception/hybrid_source.py`): detection *existence* is gated on real
  HelperAI `list_indication(6)` text, populated only in a minority of flight time and apparently
  tied to scope/weapon-selection mode (Session 5 Finding 7, below — 2.1% of sampled ticks).
  **Correction to this plan's own prior framing, per Session 5 Finding 6**: the list is not
  "one actively-selected target," it is a scrolling window into a multi-row target list —
  `middle_list_text` is the highlighted row, the `upper_*`/`lower_*` siblings are neighbouring
  rows that can hold *distinct simultaneous* contacts (e.g. `Slava cruiser` + `Tarantul III
  corvette` held at once). Selection moves the highlight within an already-populated set rather
  than causing population of a single slot. Geometry comes from `association.py` matching
  `middle_list_text` against `LoGetWorldObjects` candidates.
- `body-layer/src/perception/geometry.py` already has bearing/range/terrain-LOS helpers,
  deliberately stopping short of a detectability decision — its own docstring names this as
  "a concrete tier's job... not this shared helper's," referring to the original plan's
  never-built "Tier 3" (a pure geometric proxy with no real detection gate at all). PB-1.5 is
  that deferred Tier 3, scoped specifically to naked-eye spotting.
- **Investigator findings** (`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-
  ambient-detection.md`, Sessions 1–5, the last two run 2026-09-09 after this plan's first
  version was written):
  - **Q1 (export-layer filtering):** `LoGetWorldObjects` takes only a *category* argument
    (`"units"` default / `"ballistic"` / `"airdromes"`, per the primary-source reference
    `Export.lua` at `win-mac-sync/from-windows/Export.lua.reference-file-from-DCS-installation.lua`
    lines 624-629) — no radius or coalition filter exists. Every community export script filters
    client-side after the unfiltered call. Per-call cost at this project's realistic object
    counts is unquantified (directionally "can be inefficient" per Tacview's wiki, no hard
    numbers). Recommendation: add a cheap Lua-side manual distance filter before building the
    JSON payload, as a cap on payload/parsing size regardless of whether a real FPS problem is
    ever proven. **Unchanged by Session 5** — nothing in the new findings bears on this question.
  - **Q2 (real ambient-detection signal) — the architecturally load-bearing question:** revised
    materially by Session 5, direct install access on the Windows machine. Three findings:
    1. **The `PKV` hypothesis (Session 2/4) is refuted.** `PKV_page.lua`/`PKV_base_page.lua`,
       read in full, are a pure gunsight-reticle renderer — one collimated texture, two hidden
       FOV-ring polys, no text elements, no `list_indication` tree, no `get_param_handle` calls.
       `devices.PKV` does not mirror the ambient callout. Drop it from the plan entirely.
    2. **The `"N CONTACTS, H O'CLOCK"` ambient callout is real, and DCS's own vocabulary for it
       is readable in plain Lua.** `HelperAI_lengths_ng.lua` is a composed-speech fragment bank —
       C-side enum names in trailing comments — that native code assembles the callout from,
       which is why four sessions of grepping for a literal string found nothing. The vocabulary:
       `OP_SEE_GROUND`/`OP_SEE_AIR`; 12 clock bearings (`OP_A1H`…`OP_A12H`); 24 range buckets
       (100 m steps to 1 km, 500 m steps to 5 km, 1 km steps to 10 km, then `OP_D10k`); 8 count
       buckets (`OP_1UNIT` … `OP_MORETHAN15UNITS`); `OP_TARGET_HIGHER`/`OP_TARGET_LOWER`;
       `OP_SINGLE`/`OP_GROUP`; coarse ground/air class enums (`OP_ARMORED`, `OP_TRUCK(S)`,
       `OP_INFANTRY`, `OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM`, `OP_SPAAG`, `OP_ZU23`,
       `OP_GROUPSOMETHING`, `OP_SHIP(S)`, plus air classes). **This does not mean the signal is
       Lua-exportable** — that remains untested — but it retires the plan's prior "confirmed
       absent" framing: the correct framing is "the signal demonstrably exists in DCS; whether
       any exported Lua value mirrors it is untested."
    3. **ED's own naked-eye detection-model constants are readable in plain Lua**, in
       `HelperAI.lua`: `min_angular_radius = { lowres = 0.0043, medres = 0.008, hires = 0.02,
       iff = 0.025 }` (radians, a range-by-target-angular-size curve across recognition tiers),
       plus `min_contrast_f = 0.001`, `extra_eyesight_ratio = 4.0`, `min_fog_transparency = 0.3`,
       and `scan_rad_around_point = 2500` (metres). This is ED's actual detection model, not a
       forum claim, and is a far better basis for this plan's filter than an invented per-type
       range multiplier — see Proposed Defaults.
  - **Session 5, part 2 (same day, re-analysis of the existing PB-1 spike log — no new flight
    needed):** three more findings, closing two of Session 4's open items and surfacing one
    adjacent, out-of-scope issue:
    4. **The untested sibling leaves are now tested, and are dead.** Across all 76 device-6
       samples where `middle_list_holder` was populated, `upper_upper_list_text` is present and
       **empty in every one**; `upper_list_text` never appears in the returned tree at all,
       despite being defined in `HelperAI_page_common.lua`. Session 1's structural inference is
       now reproduced-locally: neither leaf is an ambient-detection candidate. Drop both from the
       queued probe (Implementation stage 7, updated below).
    5. **The HelperAI list is multi-contact, not single-selected-target** — see the corrected
       Context bullet above. Consequence flagged, not fixed, by this plan: `hybrid_source.py`
       currently reads only `middle_list_text` per poll; if the other populated leaves hold
       distinct real contacts, it is silently discarding rows. This is a pre-existing PB-1
       behavior, not something PB-1.5 introduces or touches (PB-1.5 adds a second, independent
       source; it does not modify `hybrid_source.py`'s poll shape) — recommended as a separate
       backlog item, not folded into this plan. See Risks.
    6. **The list is populated only ~2.1% of sampled ticks** (76 of 3,652), consistent with a
       real gate on "something specific" rather than continuous ambient awareness — this is mild
       corroborating evidence for Session 1's original "gated, not ambient" read, though it still
       does not identify what the gate is.
  - The remaining open question is unchanged in substance but the probe design is now sharper:
    **whether any exported Lua value changes at the moment the ambient callout fires.** The 76
    populated samples above cannot be attributed to naked-eye vs. scope-driven detection after
    the fact — the spike flights were not flown under a controlled no-scope-slew protocol and the
    log carries no marker for when the voice callout fired — so this still requires one controlled
    live sortie. See Implementation stage 7 for the revised probe design (on-change full-tree
    `list_indication(6)` logging + a `list_cockpit_params()` changed-only sweep + an in-band
    cockpit-switch marker, superseding both the original `list_indication(1)`/`PKV` probe and the
    named-leaf-targeting probe from earlier plan drafts).

**What this means for this plan**: unlike `HybridPerceptionSource`, whose primary defense of
"Petrovich must never be omniscient" is that detection *existence* is real (HelperAI actually
populated something), the naked-eye channel still has no confirmed real existence signal to gate
on — that part of the picture is unchanged. What *has* changed is the quality of the fallback:
the filter this plan builds is no longer a from-scratch invented heuristic, it is a deliberate
approximation of ED's own published detection model (Finding 3), and it quantises its output to
ED's own perceptual vocabulary (Finding 2) rather than reporting raw metres/degrees a crew member
couldn't actually perceive that precisely. That is a materially stronger defense of the invariant
than the previous plan version had, though still not as strong as a real detection-existence
gate would be — and the two are structurally independent: if the Implementation stage 7 probe
ever finds a real signal, adopting it is a *source swap* behind the same filter/quantisation
machinery, not a redesign. See the rewritten Decision #1 below — this is still not a decision the
architect can make alone.

### Affected Modules / Files

- `body-layer/src/perception/object_model.py` — **NEW.** Pure, fixture-testable, no network I/O.
  Holds the one thing both `visibility.py` and `naked_eye_source.py`'s output-quantisation step
  need from `object_type`: a small hand-authored lookup table, keyed by keyword match against
  `object_type` (same pattern and same "unvalidated starting vocabulary" caveat as
  `association.py`'s `_type_match_score` — reused pattern, not new machinery), mapping each
  recognized type keyword to (a) a characteristic physical size in metres, used as the numerator
  in the angular-radius check below, and (b) an ED coarse-class bucket (`OP_ARMORED`,
  `OP_TRUCK`, `OP_INFANTRY`, `OP_SPAAG`, …, per Finding 2). An unmatched `object_type` falls back
  to a generic size default and ED's own `OP_GROUPSOMETHING` class — using ED's own "unclassified"
  bucket for the fallback case rather than inventing one. One table serves both consumers instead
  of two, which is the concrete duplication this module removes (a second per-type table living
  in `naked_eye_source.py` for class-bucketing alone would just be `association.py`'s vocabulary
  problem built twice).
- `body-layer/src/perception/visibility.py` — **NEW.** Pure, fixture-testable detectability
  filter (no network I/O), mirroring `association.py`'s purity posture: given `OwnshipState` and
  a `WorldObjectCandidate` (reused from `association.py`, not duplicated), returns a
  `VisibilityResult | None` — `None` means "not plausibly visible," a `VisibilityResult` carries
  bearing/range/the recognition tier reached/a confidence score. Composes three checks:
  1. **FOV cone** — `NAKED_EYE_FOV_HALF_WIDTH_DEG` off ownship true heading (default below).
     Orthogonal to the angular-radius check below (look-direction plausibility, not detectability
     range) — unchanged from the prior plan version.
  2. **Angular-radius recognition-tier check, replacing the invented range-multiplier curve.**
     `HelperAI.lua`'s `min_angular_radius = { lowres, medres, hires, iff }` (Session 5 Finding 3)
     is ED's own range-by-target-size curve, expressed as a threshold angular radius per
     recognition tier rather than a flat range. This module works it backwards into a range
     threshold per tier: `range_threshold(tier) = object_model.size_m(object_type) /
     min_angular_radius[tier]`. **This is this project's own derivation from ED's published
     constants, not a verified reproduction of ED's actual formula** — the native code that
     consumes these constants also folds in `min_contrast_f`, `extra_eyesight_ratio`, and
     `min_fog_transparency`, none of which this project has an input for (no fog/contrast signal
     is polled anywhere in the pipeline today) or a confirmed combination rule for even if it
     did. Flagged explicitly in Risks, not silently absorbed into the constant. `scan_rad_around_
     point = 2500` (also from `HelperAI.lua`) is adopted as the channel's outer range cap
     (`NAKED_EYE_RANGE_CAP_M`, replacing the prior version's invented 2000 m base range) —
     ED's own scan-radius constant is a better-grounded outer bound than a guess.
     Gating on the `medres` tier by default is a judgment call worth the user's attention: `lowres`
     is ED's "something is there" threshold (bare existence), `medres`/`hires` are classification
     tiers. Since the channel's output is quantised to a vocabulary that includes a coarse class
     (Finding 2), it needs at least `medres`-level discrimination to be honest about what it's
     reporting — see Proposed Defaults.
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
  3. **Quantises the surviving geometry to ED's ambient-callout vocabulary** (Finding 2) before
     building an `Observation`: bearing snapped to the nearest of the 12 `OP_A1H`…`OP_A12H` clock
     positions (a clean fit — clock bearing *is* a 30°-bucket quantisation of a float, so
     `Observation.bearing_deg`'s existing field type needs no change), range snapped to the
     nearest of the 24 `OP_D…` buckets, and `object_model.py`'s class bucket in place of a free-
     text classification guess. This is the plan's anti-omniscience mechanism at the *output*
     layer, distinct from and additional to `visibility.py`'s gate at the *input* layer — see
     Decision #1's rewrite and Invariant Check.
     **Scope limit, judgment call:** only bearing/range/class are quantised per-object here.
     Finding 2's count/formation buckets (`OP_1UNIT`…`OP_MORETHAN15UNITS`, `OP_SINGLE`/
     `OP_GROUP`) describe an *aggregate* callout across a cluster of objects, which doesn't fit
     this channel's per-object-id debounce/emission model without first building object
     clustering — a real piece of work, not a quantisation detail. Left out of this plan's v1 and
     flagged as a new decision (see Decisions) rather than silently deferred.
  4. **Per-object debounce**: tracks the set of `object_id`s that passed the filter on the
     *previous* poll. Emits one `Observation` only for an `object_id` newly entering the
     currently-visible set (mirrors `HybridPerceptionSource`'s change-debounce, but keyed on
     object-id membership rather than text-equality, since there's no text here).
  5. **Simultaneous-detection cap** (`NAKED_EYE_MAX_NEW_PER_POLL`, default below) — caps how many
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
- `body-layer/tests/test_object_model.py`, `test_visibility.py`, `test_naked_eye_source.py` —
  new, hand-authored fixture tests mirroring `test_association.py`'s pattern: tier-boundary cases
  for the angular-radius check (a candidate just inside/outside `medres` range for its looked-up
  size), edge-of-FOV cases, and dense multi-object scenes for the cap/debounce/quantisation
  logic (including a bearing/range pair that should quantise to a specific `OP_A*`/`OP_D*` bucket
  pair, as a regression anchor for the quantisation math itself).
- `docs/concept/PETROBRAIN_RUNTIME.md` — update "Perception adapter" with the two-channel design,
  the asymmetric invariant story between them (real detection-existence gate vs. an ED-model-
  grounded but still synthetic filter), and the output-quantisation-to-ED-vocabulary approach.
- `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` —
  already written by Investigator across five sessions; no further research needed to start
  implementation, though Session 5's narrowed follow-up probe (Implementation stage 7) remains
  open (see Risks).

### Invariant Check

- **DCS authoritative, code owns facts:** satisfied — all geometry is read-only DCS ground
  truth; the visibility filter only *decides what to report*, never invents position/identity.
- **Petrovich must never be omniscient — this is the plan's central risk, not a satisfied box.**
  Unlike `HybridPerceptionSource`, this channel still has no *confirmed* real detection-existence
  signal to point to (Session 5 narrowed but did not close that gap — see Context). What changed
  is the quality of the fallback defense, now two-pronged instead of one:
  1. **Input-side**: `visibility.py`'s filter is no longer an invented range/type heuristic — it's
     this project's own derivation from ED's published `HelperAI.lua` detection constants
     (angular-radius recognition tiers, ED's own scan-radius cap), a *reasonably faithful* model
     of what a human crew could plausibly notice rather than an excuse to report everything in
     range.
  2. **Output-side, new in this revision**: quantising bearing/range/class to ED's own
     ambient-callout vocabulary (Finding 2) discards precision a crew member could not actually
     have had — reporting "about 1.2 km, 2 o'clock, armored" (bucketed) instead of "1,247 m,
     bearing 47.3°, BMP-2" (exact) is a structural defense against omniscience, not a display
     nicety, because it caps what downstream memory/dialogue code can ever claim Petrovich knew.
  Strict FOV cone, the angular-radius tiering, real terrain LOS, the per-poll emission cap, and
  the output quantisation are all invariant-load-bearing design choices here, not tuning
  parameters — flagged to the user as the rewritten Decision #1 before implementation starts.
  This is a materially stronger position than the prior plan version, but still not as strong as
  a real gate; do not read "ED-model-grounded" as "verified" — see Risks.
- **Provenance/uncertainty preserved:** every naked-eye `Observation`'s `provenance` string must
  read differently from Hybrid's (e.g. `"world_objects/visibility_filter_only"`), and its
  confidence should be capped below `CONFIDENT_ASSOCIATION_CONFIDENCE` (Hybrid's clean-match
  value) — a filter pass is structurally weaker evidence than a real HelperAI detection, and the
  schema must say so, not just the docstrings.
- **Read-only DCS access:** satisfied — no new DCS write path, same polling pattern as PB-1.

### Proposed Defaults (starting constants, all named/tunable; sourced from ED where noted, but
their *combination* into a detectability decision is this project's own derivation, not verified)

- `NAKED_EYE_FOV_HALF_WIDTH_DEG = 60.0` — narrower than `association.py`'s
  `FORWARD_HEMISPHERE_HALF_WIDTH_DEG = 90.0` deliberately: Hybrid's window is a loose plausibility
  backstop behind a real gate; this one is the primary gate and should model an actual scanning
  arc, not just "somewhere plausible." Unchanged by Session 5 — angular radius and FOV are
  orthogonal axes (detectability range vs. look direction).
- **Angular-radius recognition tier, sourced from `HelperAI.lua`'s `min_angular_radius` table**:
  default to `MEDRES = 0.008` rad. `LOWRES = 0.0043` (bare existence, no class implied) and
  `HIRES = 0.02` (fine classification) are also carried as named constants so the tier is a
  one-line change, not a redesign, if the default proves too generous or too strict once tested
  live. `IFF = 0.025` is not used by this plan — friend/foe discrimination is out of scope (see
  Risks, "no coalition/IFF filtering").
- `NAKED_EYE_RANGE_CAP_M = 2500.0` — from `HelperAI.lua`'s `scan_rad_around_point`, ED's own
  scanning-radius constant, replacing the prior draft's invented 2000 m base range/5000 m cap.
  Used as an outer bound regardless of what the angular-radius formula computes for a given
  object's looked-up size, so a very large object (e.g. a ship) can't produce an implausibly long
  detection range from the formula alone.
- **`object_model.py`'s per-type size/class table** — hand-authored starting vocabulary, same
  unvalidated-vocabulary posture as `association.py`'s `_type_match_score` table: a handful of
  keyword-matched entries (e.g. `truck`→6 m/`OP_TRUCK`, `tank`/`bmp`/`btr`→~7 m/`OP_ARMORED`,
  `zu-23`/`shilka`→`OP_ZU23`/`OP_SPAAG`, ship-hull keywords→`OP_SHIP`) plus a fallback
  (`DEFAULT_SIZE_M = 5.0`, `OP_GROUPSOMETHING`) for anything unmatched. **Where the size comes
  from, stated plainly**: `LoGetWorldObjects`/`WorldObjectSample` carries no physical-dimensions
  field (confirmed by reading `aircraft-layer/src/schema/world_objects.py` — only `object_type`,
  position, heading, coalition), and no DCS-exposed per-unit-type dimension database is known to
  exist in Lua (untested, not investigated this round). A hand-authored table is therefore the
  only available v1 option without an aircraft-layer schema change; an aircraft-layer change to
  expose real dimensions is a possible future upgrade, not pursued now (see Risks).
- `NAKED_EYE_MAX_NEW_PER_POLL = 3` — caps newly-emitted detections per poll tick, nearest-first.
  Unchanged by Session 5.
- **`extra_eyesight_ratio = 4.0` is currently unused, and that is probably the derivation's
  largest single error — in the *strict* direction.** Working the tiers into ranges gives, for
  size-as-numerator (metres):

  | object | `lowres` | `medres` | `hires` | `medres` × 4.0 |
  |---|---|---|---|---|
  | infantry (1.8 m) | 419 | 225 | 90 | 900 |
  | Ural truck (6 m) | 1395 | 750 | 300 | 3000 |
  | T-72 (7 m) | 1628 | 875 | 350 | 3500 |
  | SA-3 launcher (9 m) | 2093 | 1125 | 450 | 4500 |

  At bare `medres` a truck is detectable only to 750 m, so `NAKED_EYE_RANGE_CAP_M = 2500` would
  essentially never bind for any ground vehicle — the cap would be decorative. That sits badly
  against two other ED constants: `scan_rad_around_point = 2500` implies ED scans meaningfully out
  to 2.5 km, and Finding 2's callout vocabulary carries range buckets all the way to `OP_D10k`.
  Folding in `extra_eyesight_ratio = 4.0` reconciles all three — `medres × 4` puts a truck at
  3000 m, which the 2500 m cap then actually binds. That consistency is suggestive, **not
  evidence**: the constant's real role in ED's native formula is unknown, and it may apply to a
  different tier, a different quantity, or only to the AI's own scan rather than to detection
  range. Treat this as a live question for the tier decision, not a resolved multiplier.

### Implementation Plan

1. **`object_model.py`, then `visibility.py`**: the size/class lookup table first (pure data plus
   a lookup function, trivially fixture-tested), then FOV + angular-radius-tier + LOS composition
   on top of it, pure and fixture-tested before any live wiring — same sequencing discipline
   `association.py` used in PB-1. Include tier-boundary fixture cases (a candidate just inside vs.
   just outside the `medres` range threshold for its looked-up size).
2. **`naked_eye_source.py`**: wire `GET /world_objects/latest` polling, `visibility.py`, output
   quantisation to the `OP_A*`/`OP_D*`/class vocabulary, the visible-set debounce, and the
   per-poll emission cap. Fixture-test the debounce/cap logic with dense multi-object scenes (this
   is the part most likely to have an off-by-one or "reports everything on the first poll after a
   scene populates" bug), plus at least one quantisation regression case (a known bearing/range
   pair asserted against its expected `OP_A*`/`OP_D*` bucket).
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
7. **Opportunistic follow-up (not blocking, not scheduled)**: the revised live probe from the
   research file's "Session 5 Addendum, part 2" section — superseding every earlier probe design
   in this plan's history (the original named-leaf `list_indication(6)` dump, and the
   `list_indication(1)`/`PKV` probe, both now void per Findings 4/1 above). Concretely: log
   `list_indication(6)`'s full tree **on change only** (not the dead named leaves specifically),
   sweep `list_cockpit_params()` each tick and log **only changed params** (the practical
   substitute for a `get_param_handle` sweep — individual handles aren't addressable by name from
   Export.lua without knowing them in advance), during a naked-eye-only pass with the ASP-17 never
   slewed, with the user actuating a distinctive cockpit switch at the instant each voice callout
   is heard as an in-band, in-log timestamp marker (avoids wall-clock correlation across two
   machines). If this ever turns up a real signal, that becomes a preferred, stronger-invariant
   replacement gate for this channel behind the same filter/quantisation machinery — a source
   swap, not a redesign (see Context) — revisit this plan's Q2 branch at that point rather than
   assuming the ED-model-grounded filter is permanent.

### Risks & Unknowns

- **The derivation's error direction is unknown, and the arithmetic suggests it is strict rather
  than generous** — the opposite of what the next bullet guards against. See Proposed Defaults'
  `extra_eyesight_ratio` table: at bare `medres`, ground vehicles drop out between 225 m and
  1.1 km, well inside ED's own 2.5 km scan radius and far inside a callout vocabulary that reaches
  `OP_D10k`. An over-strict filter fails quietly — Petrovich simply never mentions things a crew
  would obviously see — which is harder to notice in testing than the over-generous failure below,
  and is the more likely outcome of the two on these numbers. The live acceptance test
  (Implementation stage 5) should be read with this in mind: "reported nothing" is a result to
  investigate, not a pass.
- **Core invariant risk** (restated from Invariant Check): even ED-model-grounded, this channel's
  "not omniscient" defense is still a heuristic *derivation*, not a verified reproduction of ED's
  actual formula — the native code also factors `min_contrast_f`, `extra_eyesight_ratio`, and
  `min_fog_transparency`, none of which this project has an input for or a confirmed combining
  rule for. If the `medres` tier default plus `object_model.py`'s size table prove too generous in
  practice, this channel functionally becomes the pure ground-truth proxy the original PB-1 plan
  explicitly avoided building — the same failure mode as before, just with a better-grounded
  starting point, not a solved problem.
- **`object_model.py`'s size/class lookup table is unvalidated** — same class of risk as
  `association.py`'s keyword vocabulary, compounded here since it now gates *existence* (via the
  angular-radius check) as well as the reported class, not just disambiguating an already-real
  detection. A wrong size estimate shifts the effective detection range directly (the formula is
  linear in size).
- **Output quantisation covers bearing/range/class only, not count/formation** — Finding 2's
  `OP_1UNIT`…`OP_MORETHAN15UNITS`/`OP_SINGLE`/`OP_GROUP` buckets describe an aggregate callout
  across a cluster, which this plan's per-object-id emission model doesn't naturally produce
  without object clustering (a real feature, not a quantisation detail). Left out of v1 — flagged
  as a new decision, not silently dropped.
- **`LoGetWorldObjects` per-call cost is directionally but not numerically confirmed** — Q1 found
  no hard FPS-vs-object-count data; the Lua-side distance filter is a reasonable cap but its
  necessity for *this* project's realistic mission sizes is still unproven either way. Unchanged
  by Session 5.
- **No coalition/IFF filtering** — same carried-forward gap as Hybrid/PB-1; more consequential
  here since this channel has a higher detection volume than the single-target scope channel.
- **Cross-channel duplication** — the same physical object could be reported by both channels
  (naked-eye first, then scope-selected later, or vice versa) with different `id`s and no shared
  identity. Left unresolved by design (Decision #3) — BL-2's future contact-memory layer is
  expected to own fusion, not this plan.
- **Adjacent, out-of-scope finding: `hybrid_source.py` may be discarding real multi-contact rows**
  (Session 5 Finding 6/5, see Context). PB-1.5 does not touch `hybrid_source.py` or
  `association.py`'s poll shape — this is flagged here so it isn't lost, not fixed as part of this
  plan. Recommend the user open a separate backlog item ("HelperAI list is a multi-row window, not
  a single-target slot — `hybrid_source.py` should consider emitting one `Observation` per
  populated leaf") rather than scope-creeping it into PB-1.5.
- **One Investigator follow-up remains open**: the revised live probe (Implementation stage 7) —
  low priority, non-blocking, but should not be forgotten as "resolved." (The prior two follow-ups
  — untested `upper_list_text`/`upper_upper_list_text` siblings, and the `PKV` lead — are now
  closed: Findings 4 and 1 respectively.)

### Second-Order Effect

This ships the generic "is X plausibly visible from here" detectability primitive
(`visibility.py`) that `geometry.py` explicitly deferred and that the original PB-1 plan named
but never built — any later channel needing the same reasoning (e.g. a future Mission
Interpreter check on "what could the player plausibly have known") can reuse it instead of
re-deriving FOV/range/LOS composition from scratch, at the cost of also being the first place in
the codebase where the omniscience invariant rests on a heuristic (now ED-model-grounded, still
unverified) rather than a real signal — future reviewers of any reused-`visibility.py` channel
need to re-examine whether that channel's own detection-existence story is as weak as this one's.
Additionally, this plan is the first place the codebase adopts ED's own perceptual vocabulary
(`object_model.py`'s class buckets, the `OP_A*`/`OP_D*` quantisation) as the *shape* of what a
crew member can be said to know — a later Mission Interpreter or dialogue/memory layer (BL-2+)
inherits a ready-made, DCS-native vocabulary for phrasing crew reports instead of inventing its
own, at the cost of that vocabulary's exportability still being unconfirmed for the one channel
that most wants it (this one) — the second-order win and the second-order risk share the same
root cause.

### Decisions Requiring User Input

1. **Is a filter with no real DCS-sourced detection-existence signal behind it — even one modeled
   on ED's own published constants and quantised to ED's own vocabulary — an acceptable sole gate
   for a new perception channel?** The premise this decision rests on is better than the prior
   plan version's: the filter replicates ED's own detection model (Session 5 Finding 3) rather
   than an invented range multiplier, and the design is now explicitly decoupled from the
   exportability question (Implementation stage 7's probe finding a real signal later is a
   *source swap* behind this same filter/quantisation machinery, not a redesign). But it is still
   an approximation of a formula this project cannot fully see (contrast/fog/eyesight-ratio
   factors are unaddressed, see Risks), and it is still not a real detection-existence signal.
   The alternative remains: don't build this channel until/unless the live probe (stage 7) finds
   a real ambient signal — treat naked-eye spotting as out of scope for now. Recommend proceeding
   given the user's explicit ask and the stronger grounding now available, but this needs to be an
   affirmed choice, not a default.
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
   the user prefers to land it preemptively now. Unaffected by Session 5.
5. **Count/formation quantisation scope** (new, from this revision): confirmed out of v1 per
   Affected Modules — `naked_eye_source.py` quantises bearing/range/class per object, not the
   aggregate `OP_1UNIT`…`OP_MORETHAN15UNITS`/`OP_SINGLE`/`OP_GROUP` buckets, since those need
   object clustering this plan doesn't build. Confirm this scope cut is acceptable, or whether a
   minimal clustering pass belongs in this plan after all rather than waiting for BL-2.
6. **Angular-radius recognition tier, and whether `extra_eyesight_ratio` belongs in the formula**
   (new, from this revision): `medres` (0.008 rad) is proposed as the default gating tier over
   `lowres` (bare existence) because the channel's output includes a coarse class, which `lowres`
   alone wouldn't honestly support. But the tier choice cannot be settled independently of
   `extra_eyesight_ratio = 4.0`, which the current derivation ignores: at bare `medres` a truck
   drops out at 750 m and the 2500 m range cap never binds, whereas `medres × 4` puts it at 3000 m
   and the cap becomes meaningful (see the table in Proposed Defaults). Three coherent options —
   bare `medres` (strictest, cap inert), bare `lowres` (truck ≈ 1.4 km, cap still mostly inert),
   or `medres × extra_eyesight_ratio` (truck ≈ 3 km, cap binds, and consistent with ED's own
   2.5 km scan radius). Recommend the third, on the consistency argument, while noting it rests on
   an unverified reading of what that constant multiplies. This is worth deciding before
   implementation rather than tuning afterwards, since it moves detection range by ~4x.
