### Review Summary

Reviewed MI-4 (`feature/mi4-capable-model-synthesis`) against the locked plan (`f047604`) and
`implementation.md`. Read every changed file in full (schema, `filter/threat_signals.py`,
`world_enrich/enrich.py`+`schema.py`, all three `synth/` modules, all new/extended tests, ROADMAP.md/
CLAUDE.md diffs, both implementer agent-memory files). Ran mission-interpreter's own commands
myself rather than trusting the reported numbers.

**Coordinate-leak boundary (priority 1): holds.** Traced the full data flow: `derive_threat_signals`
(reads `RawMission` directly, hidden/lateActivation groups only, emits `ThreatSignal(kind, x, z)` —
the module's own docstring is explicit that this raw position is *not yet* sanitized) →
`enrich_threat_signals` (resolves to `WorldRef` via `client.get_describe_position`, the stated "last
point the raw coordinate exists in memory") → `prompts._threat_signal_line`/`_place_name` (reads
only `WorldRef.position`'s `nearest_settlement` dict or a `name_matches` entry's `name`, never `x`/
`z`; `EnrichedThreatSignal` doesn't even have an `x`/`z` field to misuse). `test_synth_synthesize.py`'s
`test_prompt_never_contains_a_raw_coordinate` actually exercises the real leak mechanism: it builds a
`WorldRef` whose `position` dict carries an easily-greppable `x`/`z` alongside a real settlement name,
builds the actual prompt messages through `build_messages`, and asserts the coordinate values are
absent from the serialized message text while the settlement name is present. This is not a decorative
"field absent" check — it proves the specific code path that could leak (reading `position` instead of
the settlement sub-key) is blocked. Confirmed strong.

**Structural overclaim prevention (priority 2): holds.** `prompts.RESPONSE_SCHEMA`'s
`epistemic_status` enum is genuinely `["INFERENCE", "ASSUMPTION"]` (`_EPISTEMIC_STATUS_ENUM`), sent
as Ollama's `format` JSON-schema parameter — `FACT`/`OBSERVATION`/`UNKNOWN` are not accepted values at
the schema level. `synthesize._validated_epistemic_status` is real defense in depth, not a rubber
stamp: `test_model_claiming_fact_is_rejected_not_upgraded` feeds a response with
`epistemic_status: "FACT"` through the fake double and asserts the result reverts to `None`/`()`,
not an upgraded/accepted value. Confirmed the rejection path is genuinely exercised, not just the
valid-values path.

**Two Ollama exceptions (priority 3): holds.** `ollama_client.py` raises `OllamaUnavailableError` only
from `urllib.error.URLError`/`OSError` (connection-level) and `OllamaOutputError` from every other
failure mode, including HTTP error status (`urllib.error.HTTPError`, correctly reasoned in a comment
as "reachable, just not useful"), malformed envelope JSON, missing `message`, non-string `content`,
malformed `content` JSON, and non-object parsed content. `test_synth_ollama_client.py` exercises both
distinctly against a real loopback `http.server` double (not a mock) — one connection-failure test
(bad port) and six distinct output-error cases. This is real coverage, not one path tested and the
other assumed symmetric.

**`Tagged[T].confidence` (priority 4): holds.** The two previously-failing exact-dict assertions in
`test_schema_tags.py` were updated to include `"confidence": None`, not loosened (still exact-dict
`==`, not a subset/partial match). A `confidence` round-trip test was added. Range/type validation:
the dataclass field itself is a bare `Literal["low","medium","high"] | None` with no runtime
`__post_init__` guard — consistent with how `epistemic_status` is already handled elsewhere in this
schema, so not a new gap this plan introduced. Values arriving from the one place that currently
produces `confidence` (the model) *are* validated at the boundary: `synthesize._validated_confidence`
rejects anything outside the three literal strings, and
`test_invalid_confidence_is_rejected` parametrizes over `"FACT"`, `"urgent"`, `""`, `None`, `5`, all
correctly causing degradation.

**Non-thinking mode (priority 5): sent correctly, honestly flagged as unconfirmed.** `chat_json`'s
payload includes `"think": False`, which matches Ollama's documented `/api/chat` parameter for
disabling `qwen3`'s extended-thinking mode. Both the module docstring and `mission-interpreter/
CLAUDE.md` are upfront that this was designed against documentation, not confirmed live before the
model was available — appropriate handling of a genuinely unverified claim (not silently asserted as
fact). The model is now present locally (confirmed by running `test_synth_live_ollama.py` myself,
below) and the live test passing is at least consistent with `think: false` being accepted without
error, though it doesn't independently prove thinking output was suppressed rather than just ignored.

**Auto-pull disclosure (priority 6): real design gap, required fix.** `OllamaClient.chat_json` has no
guard against calling `/api/chat` with a model that isn't pulled — Ollama's daemon silently downloads
it as a side effect. The plan's own Prerequisite-check section states this project's posture as "never
run real external-resource operations silently," and this exact class of incident already has a prior
occurrence in this project's memory (`feedback_full_build_execution.md`: "never run real full-theatre
builds yourself... violated once"). A `chat_json` call is now a routine, low-visibility code path any
future caller (MI-5/MI-6, or a config typo in the model name) could invoke without realizing it may
trigger a multi-GB download. This one turned out benign only because the user happened to be pulling
the same model concurrently — that's luck, not a property of the code. See Required Fixes.

**Live-validation quality-check boundary (priority 7): mostly clean, one confusing passage.**
`implementation.md`'s stage-6 write-up is careful almost everywhere to separate "no epistemic_status
ever came back as FACT/OBSERVATION/UNKNOWN" (a structural claim, correctly substantiated) from "have
not read the real briefing to judge quality" (correctly deferred to the user) — and `ROADMAP.md`'s
MI-4 entry states this distinction cleanly ("Remaining: human quality judgment on the live output").
But `implementation.md` line 52 reads: *"This is a reasonable per the concept doc's bar (...), but I
have not read the real sample's actual briefing text myself to make that judgment"* — the sentence is
grammatically broken and, read at face value, asserts the output *is* reasonable per the human-quality
bar in the same breath as disclaiming the ability to judge that. It doesn't rise to a real overclaim
(the very next clause walks it back, and `ROADMAP.md` gets it right), but it's sloppy in exactly the
spot this plan asked to be careful about. Optional cleanup, not blocking.

**Verification run myself, not trusted from the report:**
- `ruff format --check src tests` — pass (34 files already formatted)
- `ruff check src tests` — pass
- `mypy src` (strict) — pass, no issues in 24 source files
- `pytest tests -q` — 73 passed, including `test_synth_live_ollama.py` (model is present on this
  machine too, confirmed by running that one test directly — 1 passed)

### Required Fixes

- **`OllamaClient` has no fail-closed guard against triggering a model auto-pull.** Given this
  project's explicit "never run real external-resource operations silently" posture (stated in this
  plan's own Prerequisite-check section) and a prior incident of the same class already in project
  memory, this needs a mechanical guard, not just a docstring caveat. Concretely: check the model is
  present (e.g. an `/api/tags` lookup, mirroring `test_synth_live_ollama.py`'s own
  `_ollama_has_model` helper) before issuing `/api/chat`, and raise `OllamaUnavailableError` (or a new,
  clearly-named exception) if it's absent, rather than letting the daemon silently start a multi-GB
  download. A `pull_if_missing: bool = False` constructor/method parameter is an acceptable
  alternative shape if the team wants an opt-in path later, but the default behavior must not be
  "silently downloads."
- **`implementation.md`'s account of what the plan said about pulling the model is not accurate** and
  is repeated verbatim in `.claude/agent-memory/implementer/project_mi4_ollama_synth.md`. Both quote
  the plan as having "explicitly said 'do not attempt to pull the model yourself... just scope it out
  honestly as a pending user follow-up'" — this exact text does not appear anywhere in
  `plans/mi4-capable-model-synthesis/plan.md`. What the plan actually says (Prerequisite check /
  Risks section) is that stage 6 is blocked "until the user *or Implementer* runs `ollama pull
  qwen3:14b`" — i.e. it does not forbid the Implementer from pulling it, and arguably contemplates the
  opposite. The Implementer's actual behavior (not running `ollama pull` directly) was reasonable
  either way, but a decision log misquoting the plan it's supposed to be accountable to is a real
  accuracy problem — fix the quote/characterization in both files (implementation.md and the agent
  memory entry) to reflect what the plan actually says, distinct from what the Implementer chose to
  do on their own judgment.

### Optional Refinements

- `implementation.md` line ~52's garbled sentence conflating "no bad epistemic_status observed" with
  "this is reasonable per the human-quality bar" reads as a near-miss on the very distinction this
  review was asked to check — reword for clarity (optional, since the surrounding text and
  `ROADMAP.md` already get the distinction right).
- `tests/test_synth_live_ollama.py`'s module docstring still states "`qwen3:14b` is **not** pulled
  locally... this test is expected to skip until a human runs that pull" — stale relative to
  `implementation.md`'s own disclosure that the model was auto-pulled and the test actually ran.
  Harmless (the skip condition itself is still correct and reachability-based, not hardcoded to the
  stale claim), but worth a one-line update next time this file is touched.

### Verdict
APPROVED WITH MINOR FIXES

Both required fixes are narrow and low-risk: one is a guard clause in `OllamaClient` (a genuine
design gap given this project's stated posture on unattended external-resource operations, but not a
structural rework — the plan's own module boundaries and test doubles already support adding it
cleanly), the other is a documentation correction with no code impact. Everything else — the
coordinate-leak boundary, the structural + defense-in-depth overclaim prevention, the two-exception
Ollama client, the `Tagged.confidence` addition, and test coverage generally — is solid and matches
the plan's intent with no scope drift.

### Review Confidence
Full read — every changed file was read in full (not diff-only), the coordinate-leak and
FACT-rejection tests were traced against the actual code they exercise rather than taken on
description, and all four of this subproject's own commands (`ruff format --check`, `ruff check`,
`mypy --strict`, `pytest -q`) were run directly, including the live-Ollama test, rather than trusting
the Implementer's reported "73 passed."
