### Goal

Add `mission-interpreter/src/synth/`, MI-4's capable-model synthesis stage: fill in
`MissionUnderstanding.purpose`/`task`/`known_threats` (currently `None`/`()` placeholders left by
MI-3) using Ollama's `qwen3:14b` (non-thinking) over briefing text + `EnrichedMission` geometry +
a sanitized threat-signal summary derived from `trigrules`/hidden groups — every produced value
tagged `INFERENCE`/`ASSUMPTION` with `basis` and (new) `confidence`, never `FACT`, and never a
verbatim trigrules/hidden-unit leak. Tactical relationship analysis (terrain masking, threat-to-
route proximity) stays explicitly out of scope, per Decision 3's 2026-09-13 narrowing.

### Prerequisite check (do before/alongside Implementer stage 1)

- **Ollama daemon: confirmed running** (`ollama list` succeeded).
- **`qwen3:14b`: NOT pulled.** `ollama list` shows only `qwen3.6:27b`, `qwen3.5:9b`,
  `gemma4:12b`/`gemma4:e4b` — none is the model Decision 3 resolved on. Run
  `ollama pull qwen3:14b` before any live-model stage (unit tests against the fake Ollama double
  do not need this). Flagging per this role's "never run real external-resource operations
  silently" posture — this is a small model pull, not a full-theatre build, but still a real
  environment change outside this plan's scope to perform unasked.
- Ollama's exact `/api/chat` structured-output (`format: <json-schema>`) support and the
  `think: false` toggle's real behavior for `qwen3:14b` on the locally installed Ollama version
  could not be verified here (no network access from this session). This is ordinary software
  documentation, not a DCS-internals claim, so it does not route through `investigator` — but
  Implementer must confirm it directly against the running daemon (`ollama show qwen3:14b
  --modelfile` once pulled, a real `/api/chat` call) before finalizing `synth/prompts.py`, and
  treat "structured output isn't honored" or "thinking leaks through anyway" as a real finding to
  design around, not an assumption to code against blind.

### Affected Modules / Files

- `mission-interpreter/src/schema/tags.py` — add `Confidence = Literal["low", "medium", "high"]`
  and a `confidence: Confidence | None = None` field on `Tagged[T]` (default `None`, so every
  already-shipped MI-1–MI-3 `FACT`/`OBSERVATION` value stays valid without a confidence
  judgment — confidence is only meaningful once a model, not a deterministic mapping, produced the
  value). **Breaking to two already-passing tests** (`test_tagged_int_round_trips_through_json`,
  `test_tagged_str_round_trips_through_json` in `test_schema_tags.py`) whose exact-dict assertions
  will gain a `"confidence": None` key — Implementer updates the expected dicts as part of this
  change, this is not a regression to chase.
- `mission-interpreter/src/schema/understanding.py` — add a `Threat` dataclass (`kind: str`,
  `description: str`, `area_ref: WorldRef | None`); change `known_threats` from
  `tuple[Tagged[str], ...]` to `tuple[Tagged[Threat], ...]` (the `str` placeholder was never
  populated by MI-3, so this is a pre-population type correction, not a live-data migration).
- `mission-interpreter/src/filter/threat_signals.py` (new) — the second, MI-4-specific
  author-only-knowledge boundary: derives sanitized `ThreatSignal(kind: str, x: float, z: float)`
  tuples from `RawMission`'s **hidden/lateActivation groups only** (the ones `filter_crew_available`
  already drops). Never exposes group name/id/unit count/activation timing — only a coarse
  type-category (`kind`, via a small hand-maintained DCS-unit-type → category lookup table;
  unmapped types surface as `"unknown"`, never silently dropped) and the group's raw position,
  which stays internal (see next bullet — never reaches a prompt as raw numbers). This is the
  concrete mechanism behind the plan's "a lateActivation group may still inform derived threat
  expectations... but never as 'this exact unit is here'" line (`plans/mission-interpreter/
  plan.md` line ~111): reads `RawMission` (not `CrewAvailableMission` — the hidden groups aren't on
  that tree at all), lives in `filter/` because it is a boundary decision, not model logic.
- `mission-interpreter/src/world_enrich/schema.py` — add `EnrichedThreatSignal(kind: str,
  world_ref: WorldRef)`.
- `mission-interpreter/src/world_enrich/enrich.py` — add `enrich_threat_signals(signals:
  tuple[ThreatSignal, ...], client: WorldModelClient) -> tuple[EnrichedThreatSignal, ...]`,
  resolving each signal's raw `(x, z)` to a `WorldRef` exactly like existing group/route-point
  enrichment. This is the last point a hidden unit's raw coordinate exists in memory — the prompt
  builder (below) must read only `WorldRef.position`'s place-name fields / `name_matches`, never
  `x`/`z`, when turning this into prompt text.
- `mission-interpreter/src/synth/` (new module):
  - `ollama_client.py` — `OllamaClient` (stdlib `urllib.request`, mirrors
    `world_enrich/world_model_client.py`'s shape: frozen/slots dataclass, `base_url`/`model`/
    `timeout_s`, one method per call). Two distinct exception types, not one:
    `OllamaUnavailableError` (connection refused/timeout/DNS — the daemon isn't reachable) and
    `OllamaOutputError` (200 OK but the body isn't valid JSON, or doesn't match the requested
    schema) — both subclass `OllamaClientError`. Distinguishing them matters here (unlike
    `WorldModelClient`'s single error type) because the two failure modes need different
    user-facing handling: "Ollama isn't running" is an environment problem the user fixes;
    "model produced unusable output" is a prompt/model-quality problem this stage should degrade
    on (leave the field `UNKNOWN`/unpopulated) rather than crash the whole synthesis pass over.
  - `prompts.py` — builds the system + user messages from `MissionUnderstanding`'s already-FACT/
    OBSERVATION fields (theatre, ownship, route, important_locations), `BriefingText`, and
    `EnrichedThreatSignal` tuples (rendered as `"<kind> reported/expected near <place name>"` —
    never coordinates, never a group name). Requests **JSON-mode structured output** via Ollama's
    `format` parameter with a JSON Schema whose `epistemic_status` enum is restricted to
    `["INFERENCE", "ASSUMPTION"]` only — `FACT`/`OBSERVATION`/`UNKNOWN` are not valid values the
    schema itself will accept, so the model is structurally prevented from self-tagging as `FACT`,
    not merely instructed not to (same class of hard-boundary-over-convention as PB-6's grounding
    check, per Decision 3's cross-reference). `think: false` (or whatever the confirmed-live
    equivalent turns out to be, see Prerequisite check) is set on every request.
  - `synthesize.py` — `synthesize_mission_understanding(understanding: MissionUnderstanding,
    briefing: BriefingText, threat_signals: tuple[EnrichedThreatSignal, ...], client:
    OllamaClient) -> MissionUnderstanding`. Calls the client, parses the JSON response into
    `purpose`/`task`/`known_threats` `Tagged` values, and — as defense in depth beyond the JSON
    schema constraint — re-validates every parsed `epistemic_status` is in
    `{"INFERENCE", "ASSUMPTION"}` before accepting it, raising `OllamaOutputError` (caller decides
    whether to leave those fields unpopulated or fail the pass) if the model ignored the
    constraint. Returns `dataclasses.replace(understanding, purpose=..., task=...,
    known_threats=...)` — `MissionUnderstanding` is already frozen/slots, so this is the natural
    update mechanism, no mutation.
- `mission-interpreter/tests/` (new/extended):
  - `test_schema_tags.py` — update the two round-trip assertions for the new `confidence` field;
    add a `confidence` round-trip case.
  - `test_filter_threat_signals.py` — hidden/lateActivation groups produce signals, crew-available
    groups never do, unmapped unit types surface as `"unknown"` rather than being dropped.
  - `test_enrich.py` (extend) — `enrich_threat_signals` against the existing `FakeWorldModelClient`
    pattern.
  - `test_synth_ollama_client.py` — fake `http.server.HTTPServer` double for `/api/chat`, mirroring
    `test_world_model_client.py`'s exact pattern (hand-rolled here per module independence, not a
    shared test double). Cases: happy-path JSON body, malformed JSON body →
    `OllamaOutputError`, connection failure (bad port) → `OllamaUnavailableError`.
  - `test_synth_synthesize.py` — prompt-construction and response-parsing against the fake client:
    happy path; the model attempting to emit `epistemic_status: "FACT"` in its JSON → rejected,
    not silently upgraded; a raw coordinate never appearing anywhere in the constructed prompt
    string (the concrete regression test for the "never leak hidden-unit position" invariant).
  - `test_synth_live_ollama.py` — real integration test, `@pytest.mark.skipif` guarded by a quick
    reachability probe (mirrors this codebase's `REAL_SAMPLE_MIZ_PATH.exists()` skip convention,
    adapted to "can we reach Ollama and is `qwen3:14b` present" instead of "does this file exist").
    Runs `synthesize_mission_understanding` against the real sample mission end-to-end and just
    asserts the call completes and produces a plausible non-empty result — output *quality*
    judgment is a human pass (Implementation Plan stage 6), not something this test asserts.
- `mission-interpreter/CLAUDE.md` — document the new module, the `Tagged.confidence` addition, the
  `filter/threat_signals.py` boundary rule (and why it's a second, MI-4-specific boundary distinct
  from MI-1.5's `crew_available` filter), and the Ollama dependency/testability posture.
- `mission-interpreter/ROADMAP.md` — mark MI-4 in progress against this plan.

### Implementation Plan

1. **Schema extension.** `Confidence` literal + `Tagged.confidence` field; `Threat` dataclass;
   `known_threats` retyped. Update the two breaking round-trip tests. Run the full existing suite
   to confirm nothing else references `known_threats`'s old `str` shape.
2. **Threat-signal filter (minimal, deterministic).** `filter/threat_signals.py` reading
   `RawMission`'s hidden/lateActivation groups only, with the type→category lookup table. Unit
   tests against the synthetic fixture (add a hidden AAA-type group to it, or a local fixture
   variant if extending the shared one risks other tests).
3. **World enrichment for threat signals.** `EnrichedThreatSignal` + `enrich_threat_signals`,
   tested against the existing `FakeWorldModelClient` double.
4. **Ollama client.** `synth/ollama_client.py` against the fake `http.server` double — connection
   failure and malformed-body cases first, since those are the two failure modes the rest of the
   design leans on being distinguishable.
5. **Prompt construction + synthesis + structural rejection.** `synth/prompts.py` +
   `synth/synthesize.py`, unit-tested end-to-end against the fake Ollama double (happy path,
   FACT-rejection, coordinate-leak regression test). No live model needed for this stage.
6. **Validate against a real mission, live model.** Once `qwen3:14b` is pulled and the API surface
   is confirmed (Prerequisite check), run `test_synth_live_ollama.py` and manually inspect the
   result against the real sample mission's actual briefing — apply the concept doc's own bar
   ("a human familiar with the briefing can reasonably say: yes, this correctly understands...").
   This is the point where prompt wording will likely need iteration; expect this stage to take
   more passes than the code around it.
7. **Refine.** `CLAUDE.md`/`ROADMAP.md` updates; decide (informed by stage 6's real output)
   whether a retry-with-stricter-instruction path is worth adding for `OllamaOutputError`, or
   whether "leave unpopulated, log, move on" is good enough for this stage.

### Risks & Unknowns

- **`qwen3:14b` is not pulled locally** — blocks stage 6 (live validation) until the user or
  Implementer runs `ollama pull qwen3:14b`. Stages 1–5 do not need it.
- **Ollama's structured-output/`think` API surface is unverified against the actually-installed
  daemon version** (no network access this session) — a real risk the prompt/schema design leans
  on; confirm before stage 5 is considered done, not after.
- **The unit-type → threat-category lookup table is inherently incomplete** (this project
  deliberately doesn't vendor pydcs's weapon/unit catalogs, Decision 1) — an unmapped type must
  surface as `"unknown"`, never silently dropped, but "unknown-category threat near X" is a weaker
  signal than a real crew briefing would give. Acceptable for a first pass; revisit if it proves
  too coarse against the real sample in stage 6.
- **The hidden-group → threat-signal boundary is the most invariant-sensitive code this plan
  adds** — it deliberately reads `RawMission` (bypassing `CrewAvailableMission`) specifically to
  reach hidden/lateActivation groups, which is correct per the plan's own stated intent but is
  exactly the kind of code a small mistake in could leak a hidden unit's exact position or name
  into a prompt. Ask Reviewer to check `filter/threat_signals.py` and `synth/prompts.py`
  specifically for this, not just general correctness.
- **No mechanical enforcement that `synth/prompts.py` never interpolates a raw coordinate** beyond
  the one regression test named above — worth treating that test as load-bearing, not incidental.
- **`OllamaOutputError` vs. quietly-unpopulated fields**: this plan proposes `known_threats`/
  `purpose`/`task` fall back to their MI-3 `None`/`()` defaults on model-output failure rather than
  failing the whole MI-4 pass, so one bad model response degrades gracefully instead of blocking
  the pipeline — but this means a MI-4 run can silently produce a Mission Understanding
  indistinguishable from "MI-4 never ran" for whichever field failed. Worth a log line at minimum;
  whether it needs a more visible signal is a call to revisit once stage 6 shows how often it
  actually happens.

### Second-order effect

MI-4 is the first stage to give BL-7/MI-6 a real non-empty `INFERENCE`/`ASSUMPTION` example
instead of a schema with those branches permanently empty — that's necessary progress, but it also
means any future prompt/schema tweak here now has two downstream consumers (MI-6's runtime
compaction, eventual BL-7 consumption) to re-validate against, not zero. It does not narrow or
block MI-5 (player questions), which reads/writes `player_intent` independently.

### Decisions Requiring User Input

- **`Ownship.role` stays unpopulated by MI-4.** The concept doc ties `role` (flight lead/wingman)
  to understanding mission purpose, which is exactly what this stage adds — but the locked MI-4
  scope (plan.md, Decision 3) only names purpose/task/threats, not role, and inferring role from a
  single mission's briefing text is a small enough addition that it could plausibly belong here or
  could just as easily wait. Left out of this plan's scope by default (avoid silent scope
  expansion); say if you want it folded into stage 5 instead of deferred.
