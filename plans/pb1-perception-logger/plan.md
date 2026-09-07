### Goal

Build PB-1 ("text-only perception logger, no LLM": time, aircraft position, Petrovich
detections, bearing/range) by standing up the `body-layer` subproject's BL-0 (harness/replay)
and BL-1 (observation ingestion) slices, against a `PerceptionSource` abstraction that is built
tier-independent and only committed to a concrete tier (real Petrovich feed vs. ground-truth
proxy) after a cheap, targeted live-DCS spike — not before.

### Context this plan is built on

- Aircraft-layer telemetry (ownship kinematic state, `GET /telemetry/latest`) is done and
  merged (`51654ec`) — the BL-0 prerequisite that blocked the body-layer plan's drafting is
  resolved.
- Investigator ran two sessions this same day
  (`aircraft-layer/research/2026-09-07-petrovich-perception-export.md`), resolving PB-0's
  perception unknown enough to design against, though **neither session reached a live DCS
  instance** — both are desk research, Session 2 materially stronger than Session 1:
  - **Session 1**: `get_param_handle` is falsified for HelperAI's UI chain (primary source
    read of the actual cockpit Lua). Petrovich's UI instead declares named `controllers`
    (`middle_list_text`, `az_text`, `el_text`, `hdg_text`, `list_red_arrow`, …) architecturally
    matching what `list_indication`/`list_cockpit_params` are documented to query. **No
    `range_m` field exists anywhere in Petrovich's UI, in any tier** — range must always be
    derived externally regardless of which tier is used.
  - **Session 2**: found real, actively-maintained production code
    (`asherao/DCS-ExportScripts`, LGPL-3.0) whose `Mi-24P.lua` calls `list_indication(8)`
    directly from Export.lua for a *different* indicator (kneeboard chaff/flare counter, not
    HelperAI) on this exact aircraft. This **confirms `list_indication` is Export.lua-callable
    for the Mi-24P in general**, falsifying the earlier forum claim that dynamic reads need a
    Hook script — at least for some device IDs. It also gave the **exact wire format**: one raw
    string per call, repeating `-----...-----\n<Key>\n<Value>\n` blocks, one per currently-
    populated named controller — resolving "one blob vs. individually addressable" concretely
    (a parseable string, not a table). `LoGetWorldObjects`'s field list was cross-checked at
    moderate confidence (`ID`/`Name`/`Country`/`Coalition`/`LatLongAlt`/`Heading` — **no
    Pitch/Bank/Yaw for world objects**, only heading).
  - **What is still genuinely unknown, resolvable only by a live probe, not further desk
    research**: HelperAI's own numeric device ID (needed as `list_indication(n)`'s argument —
    not the same device as the kneeboard example); whether HelperAI is reachable the same way
    given it's registered as an "auxiliary sight" render target rather than an ordinary panel
    indicator; what `<Value>` actually contains for `middle_list_text`/`az_text`/etc.; whether
    target IDs persist frame-to-frame; `LoGetWorldObjects`'s coalition/visibility-scope
    semantics (one relevant forum thread still 403'd).
- `plans/body-layer/plan.md` (drafted 2026-09-07, not yet accepted — 6 open decisions in its
  §10) reconciles PB-1 = BL-1 and sketches the `observation:`/`contact:` schema. This plan makes
  BL-1 concrete and narrows §10 decision 6 (proceed synthetically vs. wait) with a third option:
  build the tier-independent scaffolding now, decide the concrete tier from one cheap live
  spike rather than from further argument.

**Why the plan sequences a spike before committing to a tier**: Session 2's finding
meaningfully lowered Tier 1's remaining risk (one unknown fact — the device ID — plus one
behavioral unknown, down from two open mechanism questions), which changes the economics: a
live probe is far cheaper than building Tier 3's full LOS/degradation heuristic, and if Tier 1
pans out it avoids that heavier build entirely. Neither tier should be locked in from a desk
chair when a cheap, decisive test is available first.

**Session 3 update (same day, user-supplied primary source)**: the previously-403'd forum thread
on `LoGetWorldObjects`'s coalition/visibility scope was pasted by the user and read in full. It
**confirms `LoGetWorldObjects` returns global, unfiltered multiplayer ground truth by default**
— no built-in own-aircraft/coalition filter; a caller must build one itself. This is no longer an
open risk, it's a confirmed design premise: Tier 3's detectability gate is not an optional
refinement, it is the *entire* mechanism standing between this data source and true omniscience.
Also newly noted: the same source reports this export can fail on some public multiplayer
servers (mechanism unconfirmed, no replies on the thread) — low risk for this project
(self-hosted DCS instance per the project's compute topology), but worth remembering if the
design is ever pointed at a third-party server.

### Affected Modules / Files

- `aircraft-layer/dcs-export/Export.lua` — two additions, both minimal and tier-agnostic at the
  interface level:
  1. A debug-log-gated `list_indication(<device_id>)` probe (reusing the existing debug-log
     pattern already in this file, per `aircraft-layer/CLAUDE.md`), added once the device ID is
     known, to run the live spike (stage 1 below).
  2. A `LoGetWorldObjects` poll pushed over the same socket as ownship telemetry, mirroring the
     existing `LoGetSelfData` mechanism exactly — built regardless of spike outcome, since even a
     successful Tier 1 needs *something* to derive range against (see geometry helper below), and
     because it's the fallback if Tier 1 doesn't pan out.
- `aircraft-layer/src/` (Windows collector + LAN API) — new `GET /world_objects/latest`
  endpoint, same shape/lifecycle as `GET /telemetry/latest`. Raw ground truth only: id,
  type/category string, coalition, position, heading (no pitch/bank/yaw — confirmed absent from
  `LoGetWorldObjects`). No detection/interpretation logic here — stays body-side per the
  aircraft-layer plan's decision 3.
- `aircraft-layer/research/` — no new Investigator pass needed to *finalize this plan*; the one
  remaining piece of research (HelperAI device ID + live probe) is execution, not research, and
  is stage 1 of this plan, handed to the user per the project's standing rule that live full-DCS
  work is executed by the user, not run by an agent (see `WORKFLOW.md`-style deploy/run pattern
  already established for aircraft-layer). If the live probe surfaces a genuinely new unresolved
  DCS-internals question (e.g. HelperAI behaves unlike the kneeboard example in some
  unanticipated way), that is the trigger for a fresh Investigator pass — not before.
- **New subproject `body-layer/`** (first code in it — see Decisions Requiring User Input #1).
  - `body-layer/src/perception/source.py` — `PerceptionSource` protocol/ABC:
    `poll(now_sim, ownship_state) -> list[Observation]`. Built first, before either concrete
    tier, so stage 1's spike result is a config choice, not a rewrite trigger.
  - `body-layer/src/perception/geometry.py` — bearing/range/LOS-terrain-masking helpers, calling
    `world-model/src/query` (in-process import, per the body-layer plan's seam decision) for
    elevation/terrain data. **Shared by every tier** — confirmed by both investigator sessions
    that no tier has a native range field, so this helper is load-bearing regardless of which
    concrete `PerceptionSource` gets built.
  - `body-layer/src/perception/petrovich_feed.py` — **built only if stage 1's spike succeeds.**
    `PetrovichFeedPerceptionSource` (Tier 1): parses the confirmed
    `-----...-----\n<Key>\n<Value>\n` wire format (reimplement the small `gmatch`-equivalent
    parsing routine informed by, not copied from, `asherao/DCS-ExportScripts`' `Tools.lua`
    reference implementation — see Decisions/Licensing note below), extracts whatever
    `middle_list_text`/`az_text`/`el_text`/`hdg_text` actually contain once known from the live
    probe, and calls `geometry.py` for range derivation exactly as Tier 3 would have.
  - `body-layer/src/perception/proxy.py` — **built only if stage 1's spike fails or is
    inconclusive** (HelperAI unreachable, or returns unusable content).
    `ProxyPerceptionSource` (Tier 3): calls the aircraft layer's `world_objects` + `telemetry`
    endpoints, applies the detectability gate and the confidence/precision degradation (see
    Implementation Plan / Invariant Check), emits `Observation` records per
    `plans/body-layer/plan.md` §5's schema (`source: proxy_heuristic`).
  - `body-layer/src/logger.py` — the actual PB-1 deliverable: polls ownship telemetry +
    `PerceptionSource.poll()` on a fixed tick, prints/logs each observation as flat text
    (`t_sim, aircraft position, classification, bearing_deg, range_m`). No contact memory, no
    association, no LLM — that's BL-2/PB-2. Written against the interface, so it does not know
    or care which concrete tier is behind it.
  - `body-layer/tests/fixtures/` — recorded `(telemetry, world_objects)` and/or
    `(telemetry, raw list_indication string)` frame pairs for the BL-0 replay harness.
  - `body-layer/src/replay.py` — minimal BL-0 replay harness feeding fixture frames through the
    same `PerceptionSource` interface the live logger uses.
  - `body-layer/pyproject.toml`, `body-layer/CLAUDE.md` — mirror `aircraft-layer/`'s conventions
    (ruff/mypy --strict/pytest, stdlib-only-by-policy), per the project's per-subproject
    CLAUDE.md pattern.
- `docs/concept/PETROBRAIN_RUNTIME.md` — update the "Perception adapter" section's status once
  the spike's outcome is known: which tier PB-1 actually ships against, and why.
- `plans/body-layer/plan.md` — leave as-is; this plan supersedes its BL-1 sketch with a concrete
  design but does not change BL-2+ or its other open decisions, except narrowing §10 item 6 as
  noted above.

### Invariant Check

- **DCS authoritative, code owns facts:** satisfied under either tier — both read DCS state
  read-only via the aircraft-layer I/O boundary; no model is involved anywhere in PB-1.
- **Petrovich must not be omniscient:** the risk profile differs by tier and both need an
  explicit answer, not just "pick whichever tier wins the spike":
  - **If Tier 1 (real feed) ships**: the risk is structurally lower — Petrovich's own rendered
    UI is definitionally bounded by what Petrovich's AI has decided to display, so there's no
    separate "don't leak ground truth" mechanism to build. The residual risk is over-trusting
    string content that turns out, once actually read live, to smuggle in more precision than
    intended (e.g. if `<Value>` for a classification field turns out to be an exact DCS unit
    type string rather than a coarse category) — worth a specific check during stage 2/3's live
    read, not an assumption.
  - **If Tier 3 (proxy) ships**: unchanged from the original design — needs a genuinely separate
    *detectability gate* (LOS/range/optical plausibility, conservative-by-construction, false
    negatives acceptable) **and** a separate *degradation step* (category-level classification
    not exact DCS unit type, confidence scaled by range, `derived_world_position` computed the
    noisy way a real feed's would be, never copied straight from `LoGetWorldObjects`). Without
    the second step the proxy is technically LOS-filtered omniscience, which fails the invariant
    in spirit even though it passes it literally.
- **Read-only DCS:** satisfied by both tiers — `list_indication` and `LoGetWorldObjects` are
  both read calls, no install-tree edits.
- **Provenance/uncertainty/timestamps:** satisfied by the `Observation` schema regardless of
  tier (`source: petrovich_detection` vs. `source: proxy_heuristic`, distinct `provenance`
  strings, `t_sim`/`t_wall`, confidence fields) — already specified in
  `plans/body-layer/plan.md` §5; this plan fills in whichever concrete producer the spike
  selects.
- **World Model authoritative for terrain, DCS/OSM boundary:** satisfied — `geometry.py` calls
  `world-model/src/query`, doesn't reimplement terrain logic.
- **`world-model/data/` gitignore boundary:** `body-layer/tests/fixtures/` is new persisted data
  outside that path — needs its own gitignore treatment (see Decisions below).
- **Licensing:** reference-only reuse of `asherao/DCS-ExportScripts`' (LGPL-3.0) wire-format
  parsing *pattern*, reimplemented rather than copied, keeps `aircraft-layer`'s existing
  stdlib-only/"deliberately dumb" Export.lua policy intact and avoids the `dofile()`-linking
  ambiguity investigator flagged. Recommended, not yet a settled decision (see below).

### Implementation Plan

1. **Live spike: resolve HelperAI's device ID and probe `list_indication` against it.**
   This step needs the user, not an agent — it requires physical access to the Windows DCS
   install and a live mission, consistent with the project's standing practice that live
   full-DCS execution is handed to the user, not run by an agent.
   - Retrieve `Mods/aircraft/Mi-24P/Cockpit/Scripts/device_init.lua` (exact filename
     unconfirmed — grep `Cockpit/Scripts/` if it differs) from the Windows box to find
     HelperAI's numeric device ID.
   - Add the debug-log-gated `list_indication(<id>)` probe to a test `Export.lua` (pattern in
     Affected Modules above) and run one short Mi-24P sortie with Petrovich actively tracking a
     single manually placed, visible ground target.
   - Record the raw string output. This answers, concretely: is HelperAI reachable at all this
     way; what `<Value>` contains for `middle_list_text`/`az_text`/`el_text`/`hdg_text`; whether
     "no current target" means an absent block or an empty one; whether repeated observations of
     the same target carry any stable identifier.
2. **BL-0 slice: harness + tier-independent scaffolding.** In parallel with or right after stage
   1 (does not need to wait on its result): scaffold `body-layer/` (pyproject, CLAUDE.md,
   src/tests layout mirroring `aircraft-layer/`), the aircraft-layer HTTP client, the
   `PerceptionSource` protocol, `geometry.py`'s range-derivation helper, and the minimal replay
   harness. Nothing here depends on which tier wins.
3. **Aircraft-layer: world-objects endpoint.** Add the `LoGetWorldObjects` poll to Export.lua,
   the collector cache, and `GET /world_objects/latest` — build this regardless of stage 1's
   outcome, since it's the Tier 3 fallback and costs little given the existing telemetry
   mechanism to copy.
4. **Branch on stage 1's result:**
   - **Tier 1 succeeded** (HelperAI reachable, content usable): implement
     `petrovich_feed.py` — parse the wire format, map `<Value>` content to `Observation` fields
     per what stage 1 actually found, call `geometry.py` for range.
   - **Tier 1 failed or inconclusive**: implement `proxy.py` — the detectability gate +
     degradation step described in the Invariant Check, validated first against fixtures (known
     geometry, known expected detect/no-detect outcomes) before any live mission use.
5. **Text-only logger (the actual PB-1 deliverable).** Wire `logger.py` against whichever
   `PerceptionSource` stage 4 produced: poll loop, ownship state + `PerceptionSource.poll()`,
   flat-text output matching the runtime doc's PB-1 spec. Run against the replay harness first,
   then one live short Mi-24P sortie with a visible manually-placed target as the acceptance
   check.
6. **Interface-swap smoke test.** Before calling PB-1 done, write one throwaway
   `FakeOtherTierPerceptionSource` (hand-fed fixture data standing in for whichever tier stage 4
   did *not* build) and confirm the logger runs against it unchanged. This is the concrete proof
   that the interface is genuinely tier-agnostic, not just an assertion in this plan — and it
   means the tier not chosen today is provably cheap to add for real later.
7. **Docs.** Update `PETROBRAIN_RUNTIME.md`'s "Perception adapter" section with the actual
   outcome and which tier shipped.

### Risks & Unknowns

- **HelperAI may not be reachable the same way as the kneeboard example** — it's registered as
  an "auxiliary sight" render target (Session 1 finding 1's `purposes` metadata), architecturally
  different from an ordinary panel/MFD indicator. Session 2's confirmation is real but is for a
  *different* device on the same aircraft; stage 1 could still come back negative for HelperAI
  specifically even though the general mechanism is now solid.
- **`<Value>` content format is completely unknown** even after Session 2 — could be a bearing
  string, a target-type abbreviation, both concatenated, or something not directly useful. Stage
  1 must record the raw output rather than assume a parseable shape ahead of time.
- **`LoGetWorldObjects` coalition/visibility scope is now confirmed unfiltered/global**
  (Session 3) — this raises, not lowers, the stakes on Tier 3's detectability gate: if that tier
  ships, the gate is the *only* thing preventing true omniscience, not a refinement on top of an
  already-narrowed feed. Treat it as load-bearing and test it as such, not as a nice-to-have
  polish pass.
- **Export may fail on some public multiplayer servers** (Session 3, mechanism unconfirmed) —
  low risk given this project's self-hosted DCS instance, but would need re-checking if the
  aircraft layer is ever pointed at a third-party server.
- **No Pitch/Bank/Yaw for world objects** (only Heading) is a minor, non-blocking constraint on
  Tier 3's degradation step — noted, not a redesign trigger.
- **Threshold-tuning risk (Tier 3 only)**: if built, the detectability gate's LOS/range/optical
  thresholds have no ground truth to validate against beyond plausibility until real gameplay
  sessions accumulate — same class of risk World Model's M6 ridge/valley classifier hit. Carry
  `detectability_confidence` explicitly, expect re-tuning.
- **Fixture provenance**: any fixtures captured from a real Windows-box session contain real (if
  trivial) mission data — treat like `world-model/data/`-class captures for gitignore purposes.
- **Heading reference (true vs. magnetic)** is an explicitly deferred project decision
  (`division-or-responsibility.md`) but every tier's `bearing_deg` is meaningless without
  picking one — this plan cannot defer it further (see Decisions below).

### Decisions (resolved 2026-09-07)

1. **`body-layer/` created now** as a real sibling subproject to `aircraft-layer`/`world-model`.
2. **Bearing reference: true heading**, for `bearing_deg` throughout the `Observation`/`contact`
   schema — record this once in `plans/body-layer/plan.md` §5.
3. **Where body-layer runs: any LAN box, OS-agnostic, not necessarily the DCS box** — it always
   talks to the aircraft-layer's `GET /telemetry/latest`/`GET /world_objects/latest` over the LAN
   HTTP API (never in-process). **World Model stays in-process with body-layer** (this is
   unchanged from `plans/body-layer/plan.md`'s existing seam decision, not a network service): the
   *runtime query instance* of world-model runs on whichever box body-layer runs on. If that box
   differs from the one world-model was **built** on, the user is responsible for copying the
   built `.sqlite` file(s) over manually before running body-layer — this is a manual step, not a
   new sync mechanism to build.
4. **Fixtures: commit small fixtures** in `body-layer/tests/fixtures/` (no gitignore boundary,
   unlike `world-model/data/`) — keep them small/trivial as already planned.
5. **Licensing: reimplement the small wire-format-parsing pattern now** (not the full LGPL-3.0
   framework); revisit adopting the framework later only if a concrete need (e.g. its 1000+
   device-arg tables) makes it worth it. Can change from reimplement to adopt later without
   redesign — the `PerceptionSource` interface boundary already isolates this choice.
6. **Live spike (stage 1) runs in parallel with BL-0/BL-3 scaffolding (stages 2-3), not
   blocking them.** User runs it on the Windows box whenever convenient; stage 4's tier branch
   waits on its result, stages 2-3 do not.
