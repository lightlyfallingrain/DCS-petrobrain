# BL-B22 — Pull-only briefing-derived belief

- [ ] **BL-B22 — Pull-only briefing-derived belief (Decision 3, `plans/sortie-2026-09-26-fixes/
  decisions.md`, 2026-09-26) — a real exception to the no-omniscience callout gate, not built.** #status/open
  The user's spec: a unit believed to be at a location per the mission briefing is legitimate
  knowledge (a crew briefing is something Petrovich perceived, before the flight), but it may
  *only* be spoken in answer to a direct player question ("where are the trucks?" -> "beyond the
  hill at 2 o'clock"), never volunteered, and only position ("roughly where"), never state
  ("doing what"). `sortie-2026-09-26-fixes`' Fix A deliberately placed its observability gate only
  on the spontaneous path (`ContactStore.tick`/`route_event`) so this can be added later as a
  separate query path through the existing `describe_contact`/`render_contact_report` machinery,
  without needing to touch or work around the gate. **Three prerequisites, none built yet**:
  briefing-derived contacts reaching belief at all (Mission Interpreter output reaching
  body-layer — see [[BL-7]]'s own still-open "phase data is unreachable in a sortie" entry below for
  the sibling MI-integration gap), free-text questions (today "where are the trucks?" is a
  `fallthrough` to the brain layer, not a parsed command), and terrain knowledge to phrase "beyond
  the hill at 2 o'clock" (world-model ridge/relief query). Not actionable until at least the first
  two exist; recorded here so the constraint on Fix A's design isn't lost before this becomes
  buildable.

- **Detection under real world conditions — weather, light, vegetation.** Raised by the user
  2026-09-19, not started, no milestone assigned. **The framing matters more than the list:** every
  detection test so far has been flown in near-perfect visual conditions, which makes the current
  calibration *an upper bound on what is possible*, not a model of what usually happens. Conditions
  do not replace it; they multiply down from it.

  That gives the work the same shape as the optics split the detection-cones milestone owns, and
  the two compose cleanly rather than competing: **optics multiply apparent size up, conditions
  multiply detectability down, and the three calibrated angular thresholds stay fixed in the
  middle.** Neither needs a new acuity ladder. This is worth stating before anyone starts, because
  the obvious alternative — a separate detection model per condition — would throw away a
  calibration that cost a screenshot campaign and one invalidated merge.

  Four factors, in the order their cost-to-value argues for:

  1. **Vegetation and terrain cover — cheapest by a wide margin, because the data is already
     here.** Forest and other vegetation make ground detection hard and often impossible. World-model
     already resolves landcover (`forest`/`orchard`/`scrubland`/`open fields`/`barren`) and it
     already reaches body through `belief/enrichment.py`'s `inside_landcover` — it simply is not
     wired to `perception/visibility.py`. Nothing new has to be extracted from DCS. Note the
     asymmetry this introduces: a contact *in* forest is hard to see, and a contact *against* forest
     is a different problem again (contrast, factor 4).

     **Update 2026-09-20 — ED already does this, and decomposes it better than the sketch above.**
     `Scripts/AI/Detection.lua` sets `trees_LOS_test_T4 = true`, and all five installed theatres
     (Syria included) are Terrain-4, so **ED's AI detection samples tree geometry for line of
     sight**; our `line_of_sight_clear` samples the bare terrain mesh only, making us strictly more
     permissive through forest than the engine. Separately `background_factors[FOREST] = 0.3`, but
     the file states in capitals that background applies to **airborne targets only** — so ED models
     "hard to see an aircraft against trees" and deliberately does *not* model "hard to see a tank
     against trees" as a contrast effect. That resolves the asymmetry this bullet anticipated: the
     two halves are an **LOS term and a background term**, they apply to different target classes,
     and only the first one touches ground units.

     **First real condition measurements exist, 2026-09-26** — the user's own, in
     `docs/concept/detection-in-non-perfect-conditions.md` (low light at three sun angles, two rain
     presets, four instruments each), analysed in
     `body-layer/research/2026-09-26-condition-factors-first-analysis.md`. **They do not support
     the shape stated above.** Two findings, both structural rather than numerical: the condition
     factor varies 0.04–0.25 *within one condition* depending on which instrument is looking, so a
     scalar applied after the optic multiplier cannot express it; and the wide/narrow ordering
     **reverses** between rain and darkness, because rain attacks the *windscreen* (which the eye
     and binoculars look through and the sight does not) while darkness attacks *contrast* (where
     magnification does not help and the sight's orange filter does). The term is therefore at
     least `f(condition, optical path)`, needing a per-`Optic` property that does not exist today.
     The tiers also compress rather than scaling together — type collapses to zero for the naked
     eye in every measured rain and low-light row while class survives at short range. Also
     measured, and it closes an open question in factor 2 below: **NVG is useless for detection**
     in this aircraft. Do not re-derive the shape from this paragraph — read the analysis, which
     carries the error bands, and note the user's own caution that measurement precision itself
     degrades with the conditions being measured, which argues for a few coarse condition tiers
     rather than a continuous curve.

     **Decision 2026-09-25 (user): the two channels get two different vegetation models, and the
     split is not a compromise — it is what each channel actually is.**

     - **Naked eye and binoculars: model forest statistically.** A per-landcover-class transmission
       probability, not a geometric test. This is the honest description rather than an
       approximation of one: a sweeping unaided gaze through woods *is* probabilistic — you catch
       things through gaps, and whether you see a given vehicle depends on where you happened to be
       looking as you swept. We hold landcover polygons, not trunks; a polygon cannot answer "is
       there a tree on this exact ray", and pretending otherwise would invent geometry we do not
       have.
     - **The 9K113 sight: ask DCS for the real line of sight.** One narrow line to one target,
       pointed deliberately, usually just before shooting — the case where precision is worth a
       live call, and the only channel whose per-poll call count makes one affordable.

     **Both the cost argument and the fidelity argument point the same way**, which is why this is
     worth building rather than settling for one model everywhere: the channel that cannot afford
     per-candidate DCS calls is exactly the one that does not need them, and the channel that needs
     precision makes one call per poll.

     **Three things to settle before it is built:**

     1. **Flicker is the real failure mode, and it is not a smoothing problem.** An independent
        random draw per poll makes a contact strobe in and out at 5 Hz — Petrovich repeatedly
        reporting and losing the same thing. The draw must be **stable per contact-and-geometry**,
        re-rolling only when something meaningful changes (ownship moves enough, the contact moves,
        the gaze shifts). A seeded, deterministic draw is required rather than preferred:
        everything in this subproject must be replayable with no live DCS session, which an
        unseeded draw breaks.
     2. **The two models will disagree, and that is correct.** Naked eye glimpses something the
        sight finds blocked, or the reverse — both are real. What must never happen is one channel
        contradicting *itself* between consecutive polls, which is (1) restated as an invariant.
     3. **A live-DCS LOS call inside a perception gate fights the no-live-DCS testability rule.**
        The shape that survives it: DCS LOS as an *additional* gate on the sight channel only,
        layered over world-model's offline primitive rather than replacing it, with the offline
        answer as the fallback when the bridge is unavailable and the recorded answer used on
        replay. `query.line_of_sight` stays authoritative everywhere else, including Mission
        Interpreter's own use of it.

     **Prerequisite, gating only the second half: does `land.isVisible` actually test trees, or only
     the terrain mesh?** Unverified — ED's *AI detection* sampling tree geometry
     (`trees_LOS_test_T4`) is a different claim from the *scripting API* doing so, and this
     project's rule is not to design against an unverified DCS-internals claim. `land.getIP` may be
     the more useful call, since it returns where the ray was blocked and so distinguishes a ridge
     from a treeline 200 m short of the target. The transport is not in question —
     `net.dostring_in("scripting", …)` has been in production since 2026-09-13 — but per-call cost
     at realistic candidate counts, and whether a result returns synchronously or needs a side
     channel, are both open (the same two questions left unanswered when the mission-bridge probe
     item was closed). **Needs an investigator pass plus a probe on the Windows box, run before the
     9K113 slice is scoped rather than during it.** If the answer is terrain-only, the sight half
     has nothing to call and the statistical model has to cover every channel.

     Calibration cost is small and composes with the conditions campaign rather than adding to it:
     one transmission number per landcover class, obtainable from a screenshot ladder rather than
     from flying.
  2. **Light level — dawn, day, dusk, night.** The user: *"light/dark/dusk matters immensely."*
     Mission time and sun elevation are the inputs; the effect is large and non-linear, and dusk is
     the interesting case rather than full night, because full night is nearly a binary. Needs a
     decision on whether Petrovich has any low-light aid at all.

     **Update 2026-09-20 — the inputs need no new channel.** `Export.lua` ships
     `LoGetMissionStartTime()` and `LoGetModelTime()` (both documented in the installed file), so
     time of day is already reachable on the existing telemetry path. With the mission date (the
     Mission Interpreter already parses it from the `.miz`) and ownship lat/long (already in
     telemetry), sun elevation is ordinary astronomy computed locally — **no Hook, no
     `net.dostring_in`, no new transport.** That makes this factor materially cheaper than factor 3
     and fully independent of it, which was not true when the four were first ordered.
  3. **Weather — visibility, fog, precipitation, cloud.** ~~**Needs an investigator pass
     first**~~ — **the pass is done (2026-09-19 desk, 2026-09-20 install).** `Export.lua` exposes
     **no** weather getter beyond `LoGetVectorWindVelocity` and `LoGetBasicAtmospherePressure`;
     fog is confirmed absent from that channel, so the Hook -> mission-sandbox bridge is the only
     candidate route and its reachability is still unprobed. ED's own fog is a **time series**
     (`fog2.manual = {{time, visibility, thickness}, ...}`), not a constant, so anything built here
     must sample rather than read once. Do not plan against assumed fields.

     There is prior art to read before inventing a curve, and 2026-09-20 made it concrete:
     `min_contrast_f` and `min_fog_transparency` are **Mi-24P HelperAI's own thresholds applied on
     top of the engine detector's outputs** (`wDetector::getContrastFactor`,
     `getMaxVisibilityDistWithFog`), while the engine's own fog term is
     `atmosphere_transparency_factor.fog_transparency_threshold = 0.085` in `Detection.lua`.
     `perception/visibility.py`'s docstring names the first two as deliberately unaddressed here.
  4. **Colour separation and camouflage — explicitly deferred by the user.** It is why units are
     painted the way they are, and it is the factor that interacts with all three above rather than
     standing alone. Do not start it with the others.

  **Do not start any of this without the user's instruction** — the note exists so that detection
  logic written between now and then leaves room for a conditions modifier instead of hard-coding a
  clear-day assumption, not as a call to build it.

- **PREREQUISITE for the detection-cones milestone: research ED's own detection and identification
  model.** Raised by the user 2026-09-19: *"ED native model should be researched in detail for
  detection and identification logic. What is there that we have not thought of, what is there that
  we are missing?"* Started as a desk pass from the Mac (forums, Hoggit, the existing
  `world-model/data/raw/dcs/2026-09-02/DCS-files.txt` listing); **the deep pass happens on the
  Windows box**, where the installed DCS tree can actually be read rather than inferred.

  **It gates the cones milestone's *later* slices rather than the whole thing** (narrowed
  2026-09-20, see the interdependence note below). The questions it answers are about dwell, scan
  pattern and range uncertainty — none of which slice 1 builds — so slice 1 can proceed without it
  and the deep read is needed before slice 2. Two of the questions it answers would change that
  milestone's design rather than its details:

  - Whether ED separates *detected / visible / type known / **distance known*** as distinct states.
    If it does, that is a near-exact analogue of our own PRESENCE → CLASS → TYPE lattice, and the
    fourth flag speaks directly to the range-uncertainty work the cones milestone owns — ED may
    already model the thing being deferred.
  - Whether ED models sensor field of view, scan pattern or dwell. That is the cones milestone's
    central mechanism, and the one part with no precedent anywhere in this codebase.

  **Desk pass done 2026-09-19** —
  `aircraft-layer/research/2026-09-19-ed-native-detection-identification-gap-analysis.md`. Four
  results worth carrying forward:

  - ~~**The movement suspicion was wrong, and that is useful.**~~ **THIS BULLET WAS ITSELF WRONG —
    corrected 2026-09-20 from the installed tree.** It said *"neither ED nor we model movement or
    dwell."* ED models both. `Scripts/AI/Detection.lua` has a `motion_factor` (detection-distance
    bonus up to 1.5x, keyed to angular speed over angular size, saturating at 10) and an aspect-
    and class-dependent detection-*time* model (1 s for a target ahead at max range, 10 s behind;
    10 s and 60 s respectively for ground units), plus a scan-time term for optic sensors. The
    desk pass reached its conclusion honestly — the Mi-24P tree genuinely contains neither term —
    but generalised from the module to the engine. Full reading:
    `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md` findings 2-3.

    **What survives, and matters more than the correction:** ED's motion term and our own
    movement-detection design answer *different questions* and must not be swapped. ED's ratio
    reduces algebraically to `v_perp / size` — body-lengths per second, range-invariant — and it
    asks "is this easier to spot". Ours is an absolute angular rate and asks "can the crew tell it
    is moving". ED has no moving/stopped state at all, so our design is not redundant. The
    argument for building it on crew realism rather than parity stands unchanged; only the
    "nothing to catch up to" premise is gone.
  - **ED never exposes a raw numeric range on any crew-facing channel** — only a 24-bucket range
    fragment, or nothing. That corroborates rather than merely supports moving range uncertainty
    into this milestone: ED's own AI crew does not get a number either.
  - **Weather is live-readable after all.** `world.weather.getFogThickness()` and
    `getFogVisibilityDistance()` are real getters (DCS 2.9.10+), reversing the assumption that
    weather was `.miz`-only. They live in the Mission Scripting sandbox rather than `Export.lua`, so
    they need the Hook → `net.dostring_in` → UDP bridge already proven for F10 commands — untested
    against the `"mission"` target specifically.
  - ~~**The formula is still only partly known**, and the next artifact is named: `./Scripts/AI/
    Detection.lua` … **the single highest-value thing to read on the Windows box.**~~ **DONE
    2026-09-20** — read, along with `Skill_Factors.lua` and the detector symbol tables:
    `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md`. Four results that
    change what slice 2 is planning against:

    - **ED models dwell and scan, with numbers.** Detection takes time; the time depends on aspect
      (6x penalty for a ground unit behind you versus ahead) and, for optics, on the ratio between
      the area being swept and the instrument's field of view. This was the part of the cones
      milestone described here as having "no precedent anywhere in this codebase." It has one now.
    - **The `min_contrast_f` hunt is closed.** The consumer is the engine's own `wDetector`, which
      `CockpitMi24.dll` constructs and calls directly (`getContrastFactor`, `isTargetDetected`);
      `Detection.lua` configures it via `wDetectorInfo::load_from_state`. So ED's two constant sets
      are **layered, not alternative** — engine detection first, module reporting filter on top —
      which is the same two-stage shape as our own `hybrid_source` -> `classification` split.
    - **Petrovich-class omniscience has a number: 27x.** `Skill_Factors.lua`'s `HUMAN_SKILL` tier
      (its own comment: *"for example, gunners on UH-1"*) multiplies visual detection distance by
      27.0 against the excellent-AI baseline, which clips against the 50 km absolute cap. This
      project is not working around an accident; it is replacing a deliberate concession.
    - **One disagreement to settle deliberately, not discover mid-build:** ED gives optics a
      *recognition* advantage over and above magnification (`recognition_distance_ratio_threshold`
      0.5 for optics vs 0.25 for the naked eye). Our 2026-09-17 calibration concluded the opposite
      — that the tiers belong to the eye and the optic only multiplies the angle. Ours is
      screenshot-calibrated on this aircraft and ED's is a game-tuning constant, so this is not a
      defect; it is a real, specific disagreement that slice 2 should decide on the record.

  **Not everything ED does is worth copying.** Our tier semantics are this project's own modelling
  choice and are already documented as never verified against ED internals; the goal is a crew
  simulation, not a reimplementation of ED's AI. The research should say plainly where adopting
  ED's approach would be wrong, and where we have reinvented something ED already does better.
  Nothing found may become a route to omniscience: a field that would let Petrovich know what a
  crew member could not perceive is unusable however readable it is.

- **Cones, calibration and the sortie are interdependent — plan it as a loop, not a chain**
  (user, 2026-09-20: *"I need the cone system to be able to tell whether detection ranges make
  sense. It's all inspect and adapt."*).

  The dependency was previously written as a chain: research, then cones; sortie, then calibration.
  That is wrong in a way worth stating, because it would have produced bad data. **Today Petrovich
  sees in every direction at once**, so a range-calibration sortie flown now measures "at what range
  does an all-seeing observer first report" — not the quantity anyone wants. The confound is exactly
  the thing cones exist to remove. And cones need flown numbers to set their own constants. Neither
  can honestly go first.

  **So the milestone gets sliced, and slice 1 is deliberately the part that needs no research and no
  prior sortie:**

  - **Slice 1 — the cone test and the optics table. DONE (2026-09-20).** `perception/optics.py`
    with an `Optic` dataclass and `within_optic_fov`; `check_visibility` takes an `optic` parameter
    and threads its magnification through the range formula.

    **It did not land as written here, and the difference matters.** This entry anticipated
    "mak[ing] the binocular default an explicit choice." The shipped outcome is the opposite: the
    **naked eye is now the default** (`UNAIDED_OPTIC`, M=1.0) and **binoculars became the explicit
    non-default choice**. The old default applied `BINOCULAR_OPTIC` unconditionally to every
    candidate — Petrovich permanently glassed-up, with binocular magnification across the whole
    cockpit-mask envelope at no cost in field of view. **Default detection range dropped roughly
    4×**, which is the largest single correction to over-detection the project has made, and larger
    than anything the cone test itself contributes.

    `BINOCULAR_OPTIC` is a Б-6 6×30 at M=4.0 — *derived* as 6× glass × a ~0.67 unstabilised-platform
    penalty, not the inherited `HelperAI.lua` constant restored — carrying a real 4.25° field-of-view
    half-angle that becomes enforceable once slice 2 can select an optic. The 9K113 was cut from this
    slice. Its figures live in `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`, and
    the deferred backlog item is in `todo/todo.md` — filed on `main` (7a87514) as a side quest, so
    it is not visible from this feature branch.

    Full record, including a 4.0 → 8.0 → 4.0 excursion that the 2026-09-17 photographic ladder
    refuted within a commit: `plans/detection-cones-slice1/plan.md`.
  - **Slice 2 — scanning, dwell and honest range.** The attention state machine, detection as a
    process rather than a predicate, and range as a belief instead of a ground-truth figure.
    **Gated on the ED research deep pass**, because that is precisely what those questions are
    about.

  **The loop, then:** slice 1 → fly it (with [[BL-9]] making belief-vs-truth visible) → adapt the
  constants and the FOV numbers → slice 2 once the ED read has happened. Inspect and adapt at
  milestone boundaries, which is what root `CLAUDE.md` already asks for at merges.

- **Attention direction and detection cones (much-later milestone).** Deliberately deferred, not
  started. **Now also owns range uncertainty** (moved here by the user, 2026-09-19), because that
  turned out to be the same kind of problem: a genuine perception limit that differs by optic, not a
  presentation choice. Summary of what moved, full reasoning below:

  > Count vagueness is presentation — the model may hold an exact twelve and still say "several".
  > **Range vagueness is not**: the eye cannot judge distance at these scales, which is why
  > everything that shoots far has carried a rangefinding solution. Today range reaches belief as a
  > ground-truth figure, so a brain layer asking "how far?" would get an answer no crew member could
  > give — the no-omniscience invariant leaking, which adverbs in the callout would have hidden
  > rather than fixed. The 9K113's stadiametric aide (useful to ~5 km, verify before building) means
  > certainty should *narrow* when he uses the sight. The settled rendering rule, once the belief
  > actually holds uncertainty: precision degrades with distance — "very close", a plain figure
  > close in, "about four kilometres", "eight, nine kilometres". Open: whether attention tightens
  > range — probably **no** by default, since attention does not improve the eye, unless it implies
  > he is looking through the sight.

- **Attention direction and detection cones (much-later milestone).** Deliberately deferred, not
  started. Today's channels implicitly assume Petrovich is looking everywhere at once within
  range/FOV gates. Future design: distinct optical modes (naked eye, binoculars, and the 9K113
  sight, each its own FOV/acuity/movement-tradeoff), an attention/scan state machine, a scanning loop
  interrupted periodically by a full-area sweep. Would change what feeds `Percept`/`Observation` in
  the first place, upstream of everything [[BL-2]] built — a future perception-layer milestone, likely
  well after BL-4.
