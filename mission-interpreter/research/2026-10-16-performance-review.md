# Mission Interpreter — whole-subproject performance review

**Date:** 2026-10-16. Whole-subproject pass, the last of `X-B8`'s six — world-model,
aircraft-layer, body-layer, audio-adapter, brain-layer have each had their own pass; this is
mission-interpreter's. Reviewed at `main` tip `8c30148a`.

## Framing, stated up front because it decides every verdict below

**Mission-interpreter is entirely offline and has no seat in the runtime loop.** It runs once,
pre-mission, and produces one artifact body-layer loads at startup. There is no per-tick, no
per-poll, no hot path anywhere in this subproject — the question is not "does this hold a 5 Hz
budget" but **wall-clock the pilot waits through**, and resource use that could fail a run outright.

**The roadmap's own finding bounds how much any of this matters today**:
`mission-interpreter/ROADMAP/mission-interpreter-roadmap.md` records that MI-6's compact artifact
reaches body-layer and **nothing pilot-reachable reads it** — `mission_phase` touches four
body-layer files, none of them `attention.py`, `callouts.py`, `crew_console.py`. So a performance
problem here currently costs the pilot minutes at the desk, before flying, and nothing at all once
airborne. That changes once the brain layer wires MI's output into the tick, not before.

## What was measured and what was reasoned

- **Parse cost (measured, this review, below)**: `read_miz` benchmarked directly against the
  committed synthetic fixture.
- **Transport overhead (measured, this review, below)**: `WorldModelClient`'s HTTP round-trip cost
  in isolation, against a trivial local `http.server` double.
- **World-model's own per-call query cost (measured, but not by this review — cited)**:
  `world-model/research/2026-10-05-performance-review.md`, finding 2, gives `describe_position`
  as **136.8 ms mean / 497.7 ms p95** against the real `syria-full.sqlite` store — the committed,
  authoritative figure for that query, not a figure I generated here.
- **Real-mission call counts (unmeasured — flagged, not estimated with false confidence)**: the
  three missions the 2026-09-24 acceptance pass actually ran against
  (`MI24-outpost-M03/M04/M06.miz`) are not in this checkout (mission content isn't committed,
  `research/samples/` only ever held the third-party Bagram sample, itself gitignored and absent
  here too). I have **no real waypoint/group/zone count to anchor an absolute total on**, so the
  sensitivity table below is presented as a rate (cost per enrichable item), explicitly not as "the
  Outpost missions cost X seconds."
- **The wall-clock total (measured, but not by this review — cited)**: the acceptance card's own
  1:12 resident / 3:19 cold / 2:28 warm-ish. This review's job is to say where those minutes
  plausibly go, not to re-measure the total.

Knowledge graph and agent memory were queried before writing this
(`.claude/scripts/gq.sh`, `python3 .claude/scripts/memory-search.py`) — no prior mission-interpreter
performance pass exists in either store; this is the first.

---

## Findings

### 1. World-model enrichment is one HTTP round-trip per item, fully serialized, no batching — the credible driver of "minutes, not seconds"

- **Location:** `src/world_enrich/enrich.py` — `_enrich_route_point:111`, `_world_ref_for:162-167`
  (called once per group via `_enrich_group:96`, once per trigger zone via
  `_enrich_trigger_zone:118-123`), `enrich_threat_signals:150-159`. Every one of these is a plain
  generator/tuple comprehension calling `WorldModelClient.get_describe_position` /
  `get_find_place_by_name` synchronously, one call at a time, with no memoization and no bulk
  endpoint to call into even if there were — `world-model/src/api/server.py` exposes exactly three
  `GET` routes (`describe_position`, `find_place_by_name`, `line_of_sight`), no batch form of any
  of them.
- **What this costs, measured in parts:**
  - Transport overhead alone is negligible: I benchmarked `WorldModelClient.get_line_of_sight_clear`
    against a trivial local `http.server` double (loopback, no real work) — **0.29 ms/call**
    averaged over 200 calls. `urllib.request` and the stdlib handler are not the bottleneck.
  - World-model's own per-call cost is the real driver: **136.8 ms mean / 497.7 ms p95** for
    `describe_position` against the real Syria store (cited above, not mine). `find_place_by_name`
    is a second call per *named* group/zone, on top.
  - **Because every call is sequential**, the enrichment-stage wall-clock is approximately
    `(waypoints + groups + zones + threat_signals) × ~137 ms`, plus one more `find_place_by_name`
    call per named entity. At realistic counts this is not negligible against a one-off LLM call
    that itself runs ~60-200 s:

    | enrichable items (waypoints+groups+zones+signals) | enrichment wall-clock at 137 ms/call |
    |---|---|
    | 20 | 2.7 s |
    | 60 | 8.2 s |
    | 150 | 20.6 s |
    | 400 | 54.8 s |

    I do not know which row the real Outpost missions land on — see "unmeasured" above — but a
    mission with a few dozen named ground groups and a multi-leg route is easily in the 60-150
    range, which is tens of seconds, a non-trivial fraction of a 72-192 s total.
- **Is this credible, or theoretical?** Credible, but **secondary to the LLM load/inference time**
  which the acceptance card already names as "the slow part." This finding does not explain the
  1:12→3:19 cold-vs-resident gap (that is Ollama model load, not world-model) — it explains part of
  the *floor* that remains even with a resident model.
- **Action: MONITOR.** Nobody has measured how many enrichable items a real mission actually
  produces, which is the one number this finding needs to become actionable. Not NOW: there is no
  evidence the enrichment stage is the dominant cost (the LLM synthesis almost certainly is, per the
  cold/resident gap), and "serialize fewer round-trips" is real engineering effort (either a batch
  endpoint on world-model's server, or a `ThreadPoolExecutor`/`asyncio` fan-out on this side) that
  isn't justified yet against an unmeasured, likely-secondary cost, on a subproject whose output
  nothing in flight currently reads.
- **Mitigation, if this is ever picked up:** the cheapest fix is on this side only — fan the already-
  independent `describe_position`/`find_place_by_name` calls out concurrently (a thread pool is
  enough; these are tiny GETs, not CPU work) rather than adding a batch route to world-model's
  server, which would require a second review of that subproject. A concurrent fan-out turns the
  `×137 ms` sum into roughly `×137 ms / (effective concurrency)`, bounded by `describe_position`'s
  own locking/single-writer behavior on world-model's side (not reviewed here — would need a check
  against world-model's reader, which world-model's own 2026-10-05 review covers for the read path
  and does not flag as single-threaded).
- **No redundant/duplicate calls were found** — each call resolves a position or name genuinely
  distinct in the mission tree (route points differ by waypoint, groups by position, zones by
  anchor). The inefficiency is serialization, not wasted work.

### 2. `.miz` parsing and the `DictKey_*` substitution walk: measured negligible

- **Location:** `src/miz/reader.py:read_miz`, `src/miz/dictionary.py:resolve_dict_keys`.
- **Measured:** `read_miz` against the committed synthetic fixture (5 groups, 8,165-byte `.miz`,
  50 runs) averages **2.37 ms**. `resolve_dict_keys` rebuilds the whole mission tree once
  (immutable in/out, one new dict/list per node) — a single full-tree copy, not quadratic, not
  repeated.
- **Credible risk at scale?** No. Even a `.miz` two orders of magnitude larger than the fixture
  (a real multi-hundred-unit mission file is typically hundreds of KB to a few MB of Lua text) is
  still a one-time, linear, sub-second cost against a multi-minute total. This is the kind of
  finding the project's own register calls a clean negative.
- **Action: APPROVED.** No mitigation needed.
- **Caveat:** this is measured against the *synthetic* fixture, not the real Bagram sample or the
  Outpost missions (neither present in this checkout — see "unmeasured" above). Given the linear,
  simple structure of the walk and the sub-3 ms result on a representative (if small) input, I
  don't think a 100-1000× larger real mission changes the order of magnitude, but that is reasoned,
  not measured, and flagged as such.

### 3. MI-4 synthesis: one LLM call per mission, not per item — no hidden fan-out

- **Location:** `src/synth/synthesize.py:synthesize_mission_understanding`,
  `src/synth/prompts.py:build_messages`.
- **Checked specifically because this is the shape that commonly hides a per-item loop**: one call
  per threat signal, or one call per important location, would make synthesis scale with mission
  size rather than stay flat. It does not — `build_messages` assembles theatre/ownship/route-length/
  briefing/threat-signal-lines into a single user message and `synthesize_mission_understanding`
  calls `OllamaClient.chat_json` exactly once. Prompt *length* scales with threat-signal count and
  briefing length, which is bounded in practice (threat signals come only from hidden/
  lateActivation groups, typically a handful per mission) and well inside a local-model context
  window.
- **Action: APPROVED.** The ~60-200 s synthesis cost the acceptance card measured is model-load and
  inference time on a fixed-size-ish prompt, not something that grows with mission complexity in a
  way this review can find.

### 4. MI-6's compact artifact is deliberately sized, by design, not by accident

- **Location:** `src/runtime/compact.py` — `CompactRoutePoint`, `CompactLocation`,
  `RuntimeMissionUnderstanding`.
- **What the task asked to check:** whether the runtime artifact body-layer reads at startup is
  sized sanely. It is — `CompactRoutePoint`/`CompactLocation` explicitly drop the heavy
  `WorldRef.position`/`.name_matches` JSON blobs (the module's own docstring states this), keeping
  only `x`/`y`/a resolved place name per point. This is a deliberate compaction decision (MI-6's
  plan), not an oversight that happened to work out.
- **Consumer-side check:** `body-layer/src/logger.py:2746` loads the artifact once, at startup
  (`load_mission_understanding`), not per-poll — confirmed by grep, not inferred. There is no
  runtime re-read of this file during a sortie.
- **Action: APPROVED.** No real-mission artifact exists in this checkout to measure an absolute
  byte size against, but the shape (bounded by route-point count and important-location count, both
  small relative to full-mission JSON) and the one-time load point both rule out a scale risk here.

### 5. MI-5's player-question console: interactive, but bounded and off the critical measurement

- **Location:** `src/player_intent/questions.py:detect_questions`, `src/player_intent/console.py`.
- **Why this got a specific look:** the task flagged MI-5 as the one genuinely interactive surface,
  where latency is felt directly rather than amortized into a pre-flight wait.
- **What it actually does:** `detect_questions` is a pure, synchronous ambiguity detector over
  already-built in-memory data (no I/O, no model call) — the acceptance card's own finding (A2) is
  that it currently asks threat-confirmation questions only, which is a *coverage* gap (tracked as
  MI's own backlog item against the brain layer), not a latency one. Once the console emits its
  question set, the time MI-5 "costs" is however long the pilot takes to answer — that is pilot
  think-time, not engine cost, and isn't something to optimize.
- **Action: APPROVED.** No per-item loop, no blocking I/O beyond stdin the user controls.

---

## What this review did not find

No per-request allocation on a hot path (there is no hot path), no full-dataset iteration standing
in for a bounded query, no synchronous I/O blocking anything but the one script that is supposed to
block until it finishes, no redundant re-querying of the same world-model position twice. The one
real inefficiency (finding 1) is serialization of otherwise-independent calls, not wasted work, and
it is dominated — on the evidence available — by Ollama's own load/inference time, which this
subproject's own acceptance record already named as "the slow part" before this review started.

## Verdict

**APPROVED — MONITOR.**

Nothing here needs a code change now. The one candidate for later attention — finding 1, serialized
world-model enrichment calls — needs a measured real-mission item count before it's worth touching,
and even then competes with a currently-larger, already-acknowledged cost (LLM load/inference) for
engineering attention. Given the roadmap's own finding that MI's output reaches no pilot-reachable
code path yet, spending effort narrowing a pre-flight wait that nothing downstream depends on in
real time would be solving a problem one layer early.

## Candidate backlog item

**`X-B8` is the parent item this review answers** (mission-interpreter's slice of the six-subproject
survey) — file this document against it per the parent task's instruction.

One new backlog candidate falls out of finding 1, for whoever next touches mission-interpreter's
world-model seam:

> **Measure real enrichable-item counts (waypoints + named groups + trigger zones + threat
> signals) against an actual multi-leg Syria mission, and if the count is large enough to matter,
> fan `enrich.py`'s independent `describe_position`/`find_place_by_name` calls out concurrently
> (thread pool) instead of adding a batch endpoint to world-model's server.** Not urgent — gated on
> (a) a real count being measured, and (b) MI's output actually reaching a pilot-reachable path, so
> that a faster pre-flight pass is worth something. Candidate ID: next unused in whichever space the
> main loop files it (`X-B<n>` if kept cross-cutting, or a new `MI-B1` if mission-interpreter's own
> backlog section gets opened for the first time — `CLAUDE.md`'s backlog table currently reserves
> `MI-B<n>` with none filed).
