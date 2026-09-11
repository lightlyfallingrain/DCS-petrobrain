# body-layer/CLAUDE.md

Subproject instructions for the Body Layer. Augments root `CLAUDE.md` — read that first for
overall Petrobrain architecture; this file adds stack/testing/structure specifics that apply
only within `body-layer/`.

See `plans/body-layer/plan.md` for the full architecture (scope/boundaries, the brain-facing
API design, the data model, BL-x milestones) and `plans/pb1-perception-logger/plan.md` for the
concrete plan this subproject's first code was built against. See
`aircraft-layer/CLAUDE.md`/`WORKFLOW.md` for the sibling subproject this one is a network client
of.

## What this is

The deterministic process that owns Petrovich's belief state — contacts, attention, mission
phase, events, spatial semantics — sitting between the brain (LLM, not built yet) and the
aircraft layer (DCS I/O). BL-0/BL-1 built the tier-independent perception scaffolding
(`PerceptionSource` interface, bearing/range/LOS geometry, a replay harness, an aircraft-layer
HTTP client, a text-only logger) plus its one concrete `PerceptionSource`,
`HybridPerceptionSource` — a live-DCS spike (`plans/pb1-perception-logger/plan.md` stage 1,
`aircraft-layer/research/2026-09-08-pb1-live-spike-results.md`) found every native geometry
channel dead and one real detection-existence channel (HelperAI's `list_indication`) alive, so
this is a hybrid design (real detection gate + `LoGetWorldObjects`-derived geometry via
`perception.association`), not a choice between two originally-anticipated tiers.
**Current BL-x milestone status: see `ROADMAP.md`** (this directory), not this file — status
changes faster than this doc gets touched.

## Tech stack

- Python 3.11+, fully type-hinted, `mypy --strict` (`pyproject.toml`). Stdlib only for
  body-layer's own code (`urllib.request` for the aircraft-layer HTTP client, `json`, `math`),
  consistent with `aircraft-layer/`'s and `world-model/`'s dependency policy. The one dependency
  declared in `pyproject.toml` (`pyproj`) is transitive — body-layer never imports it directly,
  it comes in through world-model's `query`/`coordinates` packages (see next point).
- **World-model seam: in-process Python import, not HTTP** (`plans/body-layer/plan.md` §1,
  narrowed to "same box always" by `plans/pb1-perception-logger/plan.md` decision 3). `mypy_path`
  and `pytest`'s `pythonpath` both include `../world-model/src` alongside this subproject's own
  `src`, so `perception.geometry` can `from query.describe import describe_position` directly.
  If body-layer is ever run on a box that did not build the world-model `.sqlite` it reads, the
  user is responsible for copying the built file over manually — not a sync mechanism this
  subproject implements.
- **Aircraft-layer seam: real HTTP, always** — `aircraft_client.AircraftLayerClient` polls
  `GET /telemetry/latest`, `GET /world_objects/latest`, and `GET /petrovich_indication/latest`
  over the LAN, since aircraft-layer/DCS may be a different box than body-layer (unlike the
  world-model seam above).
- Formatter/linter: `ruff format` / `ruff check`.
- Test runner: `pytest`.

## Commands

```sh
ruff format body-layer/src body-layer/tests   # format
ruff check body-layer/src body-layer/tests    # lint
mypy body-layer/src                            # type check (strict)
pytest body-layer/tests -q                     # test
```

**mypy config discovery is CWD-only, and `--config-file` alone does not fix it**:
`mypy_path` in `pyproject.toml` is itself resolved relative to the working directory the
`mypy` process is run from, not relative to the config file's location. Running
`mypy body-layer/src` (or even `mypy --config-file body-layer/pyproject.toml body-layer/src`)
from the repo root fails with `import-not-found` on the `world-model` seam import even
though the code is correct. The only correct invocation is `cd body-layer && mypy src`.

Run a single test: `pytest body-layer/tests/test_file.py::test_name -q`.

**Running the live logger** (`src/logger.py`'s `main()`): `src` isn't installed as a package,
same non-optional-`PYTHONPATH` situation as `aircraft-layer`'s collector (see its `WORKFLOW.md`).
**Must use `body-layer/.venv`'s interpreter, not the system/plain `python`** — the world-model
seam pulls in `pyproj`, which is only installed in this subproject's own venv (see
`## Tech stack` above on why that dependency exists). **Also requires `--world-model-db`**
(PB-1.5): `NakedEyePerceptionSource`'s terrain line-of-sight gate needs a built world-model
region `.sqlite` to run at all, per `docs/concept/PETROBRAIN_RUNTIME.md`'s naked-eye section
and the world-model seam note above — there is no default and no way to run the logger without
one. From `cd body-layer`:

```sh
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger --aircraft-layer-url http://<aircraft-layer-host>:7791 --theatre <TheatreName> --world-model-db <path-to-region.sqlite>
```

(Or `source .venv/bin/activate` first, then drop the `.venv/bin/` prefix.) Plain `python -m
logger` (no venv) fails with `ModuleNotFoundError: No module named 'pyproj'` once it reaches the
world-model import chain.

Omitting `../world-model/src` from `PYTHONPATH` fails immediately at startup with
`ModuleNotFoundError: No module named 'coordinates'` (the world-model seam, imported
transitively via `perception.association`), not a delayed failure once a poll needs elevation
data — both path entries are required from the first line.

Add `--console` (PB-2 Stage 3, extended by Stage 4) to run the belief-consuming pipeline instead
of the plain text logger: both sources are built at `emit_mode="every_poll"` and fed into a
`belief.contacts.ContactStore` (`ingest` + `tick`) each poll, per Stage 3's fix for source-level
debounce starving the belief layer's decay/lifecycle logic of continuity. `main()` runs that poll
loop on a background daemon thread and drives an interactive `belief.console.Console` REPL over
stdin in the foreground — type `contacts`, `show <id>`, `history <id>`, `find <text>`,
`watch <id>` / `unwatch <id>`, or `stats` and press enter. The REPL reads `ConsolePerceptionRunner.
last_t_sim` (updated by the poll thread every poll) as each command's `now_sim`.

Add `--overlay` alongside `--console` (BL-2.5, `plans/dcs-text-panel-output/plan.md`) to also
mirror belief lifecycle events (`CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`) to a DCS
in-cockpit text overlay via the same `--aircraft-layer-url` instance's `POST /text/push` — no
separate URL/flag needed. Defaults off; without it, behavior is unchanged. See
`aircraft-layer/WORKFLOW.md`'s "Deploy the overlay Hook script" section for the DCS-side half of
this channel — UNVERIFIED against a live DCS session as of authorship.

`--overlay` also combines with `--crew-text` (`plans/overlay-speech-callouts/plan.md`): instead of
the lifecycle-event mirror above, it pushes every line `CrewConsole` speaks — readbacks, contact
reports, drained lifecycle events, and injected urgent calls (prefixed `"!! "` on the pushed
overlay copy only, never on the printed/stdout copy) — verbatim, i.e. exactly what a crew member
would actually say, a radio-callout feed rather than a debug mirror. `--console` and `--crew-text`
stay mutually exclusive with each other; `--overlay` is valid alongside either.

## Testing

- Everything in this subproject must be testable without a live DCS session or a running
  aircraft-layer collector — this is `plans/body-layer/plan.md` §2's "hard design requirement,"
  not a nice-to-have: observations are meant to be replayable from a recorded stream. `replay.py`
  and `tests/fixtures/` exist to make that concrete from BL-0 onward.
- `tests/fixtures/` is **not** gitignored (unlike `world-model/data/`) — small, synthetic
  fixture frames are committed directly, per `plans/pb1-perception-logger/plan.md` decision 4.
  Never commit a fixture captured from a real Windows-box DCS session without treating it like a
  `world-model/data/`-class capture first (see that plan's "Risks & Unknowns").
- The aircraft-layer HTTP client is tested against a real `TelemetryAPIServer`-style loopback
  server in tests, mirroring `aircraft-layer/tests/test_api.py`'s pattern, not by mocking
  `urllib` — cheap to spin up and catches real wire-format mismatches.

## Structure

- `src/perception/source.py` — the tier-independent `PerceptionSource` protocol
  (`poll(now_sim, ownship_state) -> list[Observation]`) plus the `OwnshipState`/`Observation`
  dataclasses every tier's implementation returns. No concrete tier lives here.
- `src/perception/geometry.py` — bearing/range/LOS-terrain-masking helpers, shared by every
  tier (per both investigator sessions, no tier has a native range field). Calls world-model's
  `query.describe_position` for a single-point elevation lookup, and `store.reader.sample_grid`
  directly for the LOS sampling loop's repeated per-point elevation reads — the latter is a
  documented, deliberate deviation from routing every read through `describe_position` (which
  also joins roads/settlements/navaids irrelevant to a bare elevation sample); see the module
  docstring.
- `src/perception/association.py` — pure, fixture-testable single-detection <-> world-object
  resolution: a range-cap + forward-hemisphere plausibility filter (no coalition/IFF filtering)
  over a `LoGetWorldObjects` candidate pool, keyword-overlap type-match scoring, and a
  confident/ambiguous/drop decision. No network I/O — see `plans/pb1-perception-logger/plan.md`'s
  "Association design" section for the full algorithm.
- `src/perception/hybrid_source.py` — `HybridPerceptionSource`, the only concrete
  `PerceptionSource` this project builds. Gates on HelperAI's real
  `list_indication(HELPERAI_DEVICE_ID)` classification text (via
  `aircraft_client.get_petrovich_indication_latest()`), debounces on text change, and calls
  `association.py` + `geometry.py` to resolve geometry against a `world_objects` candidate.
  `source: "petrovich_detection_associated"` on every emitted `Observation`.
- `src/perception/visibility.py` (PB-1.5, retuned BL-2.6) — `check_visibility`, the naked-eye
  channel's three composed plausibility gates (range cap, angular-radius recognition tier, terrain
  LOS via `geometry.py`). `VisibilityResult.tier` is a **computed achieved tier**
  (`"lowres"`/`"medres"`/`"hires"`, BL-2.6 Stage 6) rather than the constant `"medres"` PB-1.5
  originally returned — a candidate that clears the gate can resolve closer-in to a tighter tier
  than the gate itself requires. `NAKED_EYE_GATING_TIER_NAME` is the gate's own threshold and
  **moved `"medres"` -> `"lowres"` at BL-2.6 Stage 7** (its own commit, separate from Stage 6's
  tier-computation mechanism, per this plan's "mechanism and calibration never share a commit"
  rule) — this widened the detection envelope ~1.86x (~3.5x area) so the presence tier became
  reachable at all. The tier -> "existence/class/class/IFF" semantics reading is this project's own
  modeling choice, not verified against ED internals (investigator finding, `plans/
  classification-refinement/plan.md` Session 6 addendum Q1) — documented here so a future reader
  does not "correct" it toward an ED semantics that was never established.
- `src/perception/naked_eye_source.py` (PB-1.5, retuned BL-2.6) — `NakedEyePerceptionSource`, the
  naked-eye/binocular channel: scans `LoGetWorldObjects` candidates through `visibility.py`'s
  gates and `geometry.py`'s bearing/range, emitting one `Observation` per still-visible candidate
  per poll. `_classification_for_tier` (BL-2.6 Stage 6) maps `VisibilityResult`'s achieved tier to
  `(classification_raw, classification_level)` on the classification lattice
  (`belief.classification.SpecificityLevel`): `hires` -> `reporting_names.reporting_name_for
  (object_type)` at level `TYPE` (Decision 1, 2026-09-09 — the naked-eye channel's own path to a
  specific type via ground truth, departing from the architect's original cap-at-class
  recommendation); `medres` -> the `OP_*` class at level `CLASS` (today's pre-BL-2.6 behaviour);
  `lowres` -> `classification.PRESENCE_CLASS` at level `PRESENCE` ("something is there," reachable
  only since Stage 7 moved the gate). Because `hires` values come from ground truth rather than a
  vocabulary match, "Petrovich can never mis-identify, only fail to identify" now applies to this
  channel's `hires` tier too, not only to the scope/HelperAI channel.
- `src/aircraft_client.py` — HTTP client for the aircraft-layer LAN API
  (`GET /telemetry/latest`, `GET /world_objects/latest`, `GET /petrovich_indication/latest`). A
  real network call, unlike the world-model seam. `push_text_line` (BL-2.5,
  `plans/dcs-text-panel-output/plan.md`) is this client's one write call
  (`POST /text/push`, the aircraft layer's only inbound path) — unlike the
  `get_*` methods above, it raises `AircraftLayerError` on any failure
  rather than swallowing it, since `logger.ConsolePerceptionRunner`'s
  per-push try/except is where that failure is meant to be caught.
- `src/replay.py` — BL-0 replay harness: drives any `PerceptionSource.poll()` over a recorded
  sequence of ownship states, no live DCS/aircraft-layer connection required.
- `src/belief/` — PB-2's observation-*consumption* package (`perception/` stays observation
  *production*): `percept.py` (`Percept`/`percept_of`, the structural no-omniscience boundary —
  belief code never sees `Observation.derived_world_position` or a DCS object id),
  `contacts.py` (`Contact`/`SightingSpan`/`ContactStore` — append-only observation log,
  `ingest`/`tick`). `Contact.classification` (BL-2.6) is the folded, monotone-non-decreasing best
  claim (`belief.classification.ClassificationBelief`, via `fold_classification`) and is what
  every user-facing surface reads. `Contact.last_class_raw` is kept **with its exact original
  meaning unchanged** — the most recent percept's raw classification string — because it, not
  `classification`, is `association_over_time.py`'s spatial-gate input; feeding the gate the
  folded best claim would make it monotonically stricter over a contact's life and start
  rejecting genuine re-observations of something already refined once. **This dual field is a
  real readability cost, not an oversight — read the two docstrings before touching either one.**
  `Contact.last_position_uncertainty_m` (a live-acceptance bug fix, 2026-09-09/10,
  `plans/classification-refinement/plan.md`) is `last_position`'s own error budget, fed
  symmetrically into `association_over_time.py`'s spatial gate alongside the incoming percept's —
  fixing a real duplicate-contact bug where the gate budgeted only the incoming percept's
  uncertainty and treated `last_position` as exact, so a stationary object's re-quantised implied
  position could jump a full bucket-width between polls and fail the gate.

  `association_over_time.py` (percept→contact spatial + class-compatibility
  gating, distinct from `perception/association.py`'s within-one-poll detection→world-object
  resolution), `decay.py` (per-attribute half-lives, the `certainty` lifecycle ladder —
  `observed`/`tracked`/`estimated`/`lost`; `position_confidence` (BL-3) is the numeric,
  continuously-decaying counterpart to that ladder, keyed off `POSITION_HALF_LIFE_S`;
  `classification_confidence_at` (BL-2.6) finally consumes `IDENTITY_HALF_LIFE_S`, which had been
  declared since BL-2 and never read — decays `Contact.classification.confidence` only, never
  `.level`, which stays sticky by design — see `classification.py`'s entry below),
  `events.py` (`CONTACT_DETECTED`/`CONTACT_LOST`/
  `CONTACT_REACQUIRED`/`CONTACT_CLASSIFICATION_CHANGED` derivation). `tools.py` (BL-2 Stage 4) —
  the brain-facing query API's body, minus a transport: `get_contacts`/`describe_contact`/
  `get_contact_history`/`find_contact` return `plans/body-layer/plan.md` §3.4's
  `{facts, summary, phrasing_hints}` triple, plus `watch_contact`/`unwatch_contact`/`get_stats`
  (a bare attention enum + source field on `Contact`, no policy/cooldown — that is BL-4). All four
  contact-facing functions take an optional `enrichment: belief.enrichment.EnrichmentContext |
  None = None` (BL-3, see `enrichment.py`'s entry below) — `None` (the default) leaves `facts` in
  exactly its pre-BL-3 shape, so existing callers/tests are unaffected; supplied, it adds
  `position.confidence`, `semantic`, `relative_now`, and (where derivable) `motion_when_seen`.
  `console.py` (BL-2 Stage 4) — a line parser + pretty-printer over `tools.py`, owning no belief
  logic of its own; every command (`contacts`, `show <id>`, `history <id>`, `find <text>`,
  `watch <id>`/`unwatch <id>`, `stats`) dispatches 1:1 into a `tools.py` function. `Console` carries
  the same optional `enrichment` field (BL-3), threaded into every dispatch, with the identical
  no-enrichment-means-no-change guard.
  `format_event_for_overlay` (BL-2.5, `plans/dcs-text-panel-output/plan.md`) —
  `"<contact id>: <kind>, <summary>"` for one `belief.events.Event`, reusing
  `tools.describe_contact`'s existing `summary` field rather than new belief-reading logic, and
  reusing the `"<id>: ..."` convention `console.py`'s own `contacts`/`show <id>` rendering already
  uses rather than inventing a second one; the leading id is what lets the overlay tell six
  distinct contacts apart from repeated events on one (a live-acceptance follow-up fix,
  2026-09-09 — the original `"<kind>: <summary>"` line carried no contact id at all).
  `CONTACT_CLASSIFICATION_CHANGED` gets its own transition rendering (BL-2.6, `plans/
  classification-refinement/plan.md` Stage 4): `"<id>: CONTACT_CLASSIFICATION_CHANGED, <previous>
  -> <classification>, <summary>"` — only that kind, every other kind's line is untouched (BL-2.5's
  overlay restyle was flown and rejected once already; this is not a reopening of that question).
  An optional `enrichment` (BL-3) appends one short semantic fragment — the highest-confidence
  `SemanticFact.text` among `facts["semantic"]`, if any — to whichever line results, lifecycle or
  classification-transition alike. Consumed by `logger.ConsolePerceptionRunner`'s `--overlay`
  mirror, not by the console REPL itself.
- `src/belief/enrichment.py` (BL-3, `plans/bl3-world-enrichment/plan.md`) — the world-enrichment
  orchestration: `SemanticFact` (`{text, confidence, provenance, feature_id}`), `semantic_facts_for`
  (calls world-model's `query.describe_position` once per contact, maps the result into that flat
  list, combining each feature's confidence with `position_confidence` above), `WorldEnrichmentCache`
  (keyed by `contact_id`, recomputes only when a contact's `last_position` actually changed —
  deliberately outside `belief.contacts.Contact` to keep zero shared surface with BL-2.6's
  concurrent work on that file), `relative_geometry` (bearing/clock/range/relative-altitude from a
  *current* ownship position — never cached, since ownship moves every poll), `motion_when_seen`
  (direction derived from a contact's two most recent distinct implied positions, `None` when fewer
  exist). `EnrichmentContext` bundles `conn`/`theatre`/`ownship`/the cache and is the one object
  threaded through `tools.py`/`console.py`/`logger.py` above.
- `src/belief/classification.py` (BL-2.6, `plans/classification-refinement/plan.md` Stages 1-2) —
  the classification specificity lattice: `SpecificityLevel` (`UNKNOWN`/`PRESENCE`/`CLASS`/`TYPE`,
  a total order 0-3) over a shallow tree of *values* (a `TYPE` value's parent is its `CLASS`
  value). `ClassificationBelief` is one contact's held claim (`value`, `level`, `confidence`,
  `established_sim`). `fold_classification` is the fusion rule `Contact.record` calls instead of
  overwriting: higher level + parent-consistent (or unresolvable) refines; same level + same value
  reinforces; **lower level holds — the held claim survives untouched, which is the fix for the
  last-writer-wins oscillation this milestone replaces**; same-or-higher level + resolvable +
  incompatible contradicts, collapsing to the deepest common ancestor and starting a
  `CLASSIFICATION_CONTRADICTION_LOCKOUT_S` (30 s) lockout against re-promotion. Also re-homes
  `_op_class_of`/`class_compatibility` from `association_over_time.py` (a pure move, Stage 1 — that
  module still imports both names so its own callers are unaffected) since `parent_class_of` needs
  the identical ED-vocabulary resolver. An unresolvable parent (scope free text `object_model.
  profile_for` can't match) always yields `unknown` comparability, on both the association gate's
  check and this lattice's — one vocabulary bridge serving both, not two. Confidence is an
  explicitly-placeholder per-level constant (not calibrated), decayed over time by
  `decay.classification_confidence_at` (`IDENTITY_HALF_LIFE_S`) — **the level itself never decays**,
  only confidence does; a contact identified as a T-72 two minutes ago does not revert to
  "something," he becomes less sure of it.
- `src/logger.py` — the PB-1 deliverable: `PerceptionLogger` polls ownship telemetry + a list of
  `PerceptionSource`s, formats each `Observation` as flat text; fully tested against a fake
  source, tier-agnostic. `main()` is the one place that plugs in the concrete
  `HybridPerceptionSource` and (PB-1.5) `NakedEyePerceptionSource` and drives the poll loop
  (`python -m logger --aircraft-layer-url ... --theatre ... --world-model-db ...` — see
  "Running the live logger" above; `--world-model-db` is required by `NakedEyePerceptionSource`'s
  terrain LOS gate) — untested by design, same posture as `aircraft-layer/src/collector/
  __main__.py`'s own live-process entrypoint. PB-2 Stage 3 adds `ConsolePerceptionRunner` and a
  `--console` flag alongside it: same file, same `main()`, a second poll-loop branch that builds
  both sources at `emit_mode="every_poll"` and ingests+ticks a `belief.contacts.ContactStore`
  instead of formatting text lines — `ConsolePerceptionRunner` itself *is* tested (against fakes,
  mirroring `PerceptionLogger`'s own tests), only `main()`'s CLI wiring is not. The default
  (no `--console`) path is unchanged and still uses `emit_mode="on_change"`. Stage 4 adds
  `_run_console_poll_loop`/`_run_console_repl`: `main()`'s `--console` branch now runs the poll
  loop on a background daemon thread and a `belief.console.Console` REPL over stdin in the
  foreground, both against the same `ContactStore`, coordinated through
  `ConsolePerceptionRunner.last_t_sim`. A Stage 6 live-testing fix renamed
  `_run_poll_loop` → `_run_console_poll_loop` and moved `world_model_conn`'s open (and
  `_build_sources`) onto that thread itself — `sqlite3.Connection` is thread-affine, and only the
  poll thread ever touches it, so it must be opened there rather than on the main thread before
  spawning. The runner no longer prints its periodic contact-count line in `--console` mode
  (`output=None`) — that line was spamming the REPL's own prompt/output on every poll; state is
  queried on demand via `contacts`/`stats` instead. BL-2.5 adds `ConsolePerceptionRunner.
  overlay_client: AircraftLayerClient | None` (mirroring `output`'s optional-sink pattern) and a
  `--overlay` flag (`main()`, default off, only meaningful with `--console`): when set, every
  lifecycle event newly appended by a poll's `tick()` call is formatted
  (`belief.console.format_event_for_overlay`) and pushed (`AircraftLayerClient.push_text_line`)
  to the in-cockpit text overlay, one `try`/`except AircraftLayerError` per push — the one place
  in this file a defensive try/except is load-bearing rather than cosmetic, since a failed push
  must degrade to "no overlay line for this event," never stop the poll loop or skip the rest of
  the batch. `PerceptionLogger`'s plain per-`Observation` stream does not get this wiring
  (line-noise vs. signal tradeoff). BL-5a adds `--crew-text` (mutually exclusive with
  `--console`; `--overlay` combines with either, see below) and `--brain-client debug|null`:
  `_run_crew_text_poll_loop`/
  `_run_crew_text_repl` mirror `_run_console_poll_loop`/`_run_console_repl` exactly, reusing the same
  `ConsolePerceptionRunner`, except the poll loop also calls `belief.crew_console.CrewConsole.
  drain_events` after each `run_once()` — the same post-`tick()` hook point `--overlay` uses — and
  the REPL dispatches into `CrewConsole.handle_line` instead of `belief.console.Console.handle_line`.
- `src/belief/utterance.py` (BL-5a, `plans/bl5a-text-mode-crew-interaction/plan.md`) — the
  deterministic intent parser: `PlayerUtterance`/`PartialParse` (§5/§3.5's shapes, trimmed to what
  this milestone populates) and `parse_utterance`, a small ordered table of `(regex, intent)` pairs
  evaluated top-down, first match wins — the same evaluation shape `belief.classification`'s lattice
  and `belief.attention.effective_attention` already use elsewhere. A verb match alone never yields
  a `"handled"` disposition — only a verb match *and* exactly one resolved reference candidate do;
  zero or several always escalate with `reason_escalated` (`unmatched`/`ambiguous_reference`) rather
  than guessing. Reference resolution is a literal `CONTACT_<n>` id, or `belief.tools.find_contact`
  after stripping leading filler words (`that`/`the`/`a`/`an`) — place-name phrasing (`find_place`)
  stays unmatched until BL-5 merges (documented gap, not a bug). No fabricated per-candidate score —
  `find_contact` (BL-2) has no ranking to carry through.
- `src/belief/speech.py` (BL-5a, extended by `plans/overlay-speech-callouts/plan.md`'s addendum) —
  `OutgoingSpeech` (§5's record, trimmed), the three body-written templated classes (§2.1/§3.6):
  `render_readback`, `render_contact_report` (single-contact only — no clustering exists yet,
  `docs/concept/PETROBRAIN_RUNTIME.md` line 336), and `route_event`, the outbound routing gate.
  **Contact-report format (2026-09-10 user decision, extended 2026-09-11):**
  `"<COALITION> <unit type>[, <clock> o'clock, <range> km][ <best semantic fact text>]."`, built by
  a shared, id-less `_contact_report_text(facts)` helper — no longer a verbatim echo of
  `tools.describe_contact`'s `summary`. `render_contact_report` is a thin wrapper over it (no id,
  since the player already named the contact); `_render_lifecycle_text`'s `CONTACT_DETECTED`/
  `CONTACT_REACQUIRED` branches call the same helper and prepend `f"{contact_id}: "` (the one place
  in this module an id needs to be spoken, since the player has not yet named this contact
  themselves). `CONTACT_LOST` (`"{id} lost."`) and `CONTACT_CLASSIFICATION_CHANGED`
  (`"{id} identified as {classification}."`) stay minimal, unextended — a lost contact has no
  current position to report, and a classification update is not a new sighting. Coalition is
  always `"UNKNOWN"` — no IFF/coalition perception channel exists, and reading `LoGetWorldObjects`'s
  real coalition into `Contact` would break the no-omniscience invariant `percept.py` enforces; a
  real implementation should *infer* coalition from unit-type vocabulary + which side's terrain the
  contact sits in, not ground truth (`ROADMAP.md` backlog, deferred). Unit type reads the
  classification lattice's level+value (`_unit_type_display`/`_OP_CLASS_DISPLAY`): `"ground
  contact"`/`"unidentified contact"` at presence/unknown, a human word for a `class`-level `OP_*`
  bucket, the reporting name verbatim at `type` level. The semantic fragment is the
  highest-confidence `belief.enrichment.SemanticFact.text` among `facts["semantic"]`, mirroring
  `belief.console.format_event_for_overlay`'s own selection; omitted (not "unknown") when no
  `EnrichmentContext` was supplied or no semantic facts exist, same absent-not-null convention as
  clock/range. `route_event` accepts `belief.events.Event | UrgentCall` and checks which
  one it got *before* anything else — an `UrgentCall` (Stage 5's manual bypass-gate test harness,
  constructed only by `crew_console.py`'s `!inject-urgent` command; no real threat-detection channel
  exists) speaks immediately with `bypass_gate=True`, no ack/cooldown touched; a `belief.events.Event`
  renders through a per-kind template and auto-acknowledges (`belief.tools.acknowledge_event`) the
  moment it is spoken, so a future brain's `poll_events` never re-surfaces it. `CONTACT_ATTENTION_
  CHANGED` deliberately has no template (returns `None`, not acknowledged) — the player's own
  command already got a readback, and area-driven attention changes are not yet narrated
  proactively (a real, documented gap). `UrgentCall` is a separate small type rather than a
  `bypass_gate` field grafted onto the shared BL-4 `Event` dataclass — `events.py` is out of this
  milestone's Affected Modules.
- `src/belief/escalation.py` (BL-5a) — `handle_player_utterance` (§3.5), the one body→brain entry
  point: builds `EscalationPayload` (transcript + `belief.utterance.PartialParse`, never the bare
  transcript alone — the brain disambiguates, it never parses from scratch) and hands it to a
  `BrainClient` (a two-method `Protocol` for a later `ask_player` round trip). `situational_header`
  is a documented stand-in (`{contact_counts, our_position}`, `our_position` present only when an
  `EnrichmentContext` is supplied) — §3.5's "D2 header" is a design discussion, not a data-model
  entry, and no code builds the real header yet. `NullBrainClient` does nothing (the honest "no
  brain yet" behaviour — §3.5: "if the brain does nothing, body says nothing"); `DebugPrintBrainClient`
  additionally prints the payload to stderr for session visibility, still producing no spoken output.
- `src/belief/crew_console.py` (BL-5a) — `CrewConsole`, the typed-input/printed-output player-facing
  session, deliberately **not** an extension of `belief.console.Console` (that module is an explicit
  developer debug tool; `CrewConsole` runs typed sentences through `parse_utterance`'s grammar and
  speaks proactively, neither of which `Console` does — see the plan's "Module boundary" decision).
  `handle_line` dispatches a `"handled"` parse to `belief.tools.set_attention`/`describe_contact` +
  a `belief.speech` template, and an `"escalated"` one to `handle_player_utterance` (silent, since
  neither stand-in `BrainClient` speaks). `drain_events` (called from `logger.py`'s `--crew-text`
  poll loop after each `tick()`) runs `store.unacknowledged_events` through `route_event` — reading
  the unacknowledged queue directly rather than tracking a separate high-water mark works because
  `route_event` itself acknowledges any event it renders, so a handled kind drops out on the next
  call and an unrendered kind (`CONTACT_ATTENTION_CHANGED`) is harmlessly re-skipped every poll.
  `!inject-urgent <contact_id> <text>` is Stage 5's clearly-labelled test harness for the
  bypass-gate/urgent-call path — not a production intent or a real detector.
  `overlay_client: AircraftLayerClient | None` (`plans/overlay-speech-callouts/plan.md`) is a
  second, deliberately separate optional-sink field from `aircraft_client` above — `aircraft_client`
  is BL-6's reserved-for-a-different-purpose field (live search-trigger commands, no reader today),
  while `overlay_client` is read every time `_print` runs. `_print` (the single funnel point both
  `handle_line` and `drain_events` already call for every line of spoken text) is where the overlay
  push lives: after printing a line to `output` it also pushes the same text to
  `overlay_client.push_text_line`, wrapped in its own `try`/`except AircraftLayerError`
  (log-and-continue), the same per-push isolation shape `logger.ConsolePerceptionRunner.run_once`'s
  BL-2.5 push loop uses. A line whose source `OutgoingSpeech` carried `bypass_gate=True` (i.e. only
  an injected urgent call, never a routine readback/contact report/lifecycle line) gets a `"!! "`
  prefix on the *pushed* overlay copy only — `output`'s printed copy stays exactly the text
  `belief.speech` produced, since the prefix is an overlay-display concern, not a change to what
  was spoken. `logger.py`'s `--crew-text` branch wires this field the same way `--console`'s own
  `overlay_client` wiring already works: `aircraft_client if args.overlay else None`.
- `tests/fixtures/` — committed fixture frames for the replay harness's own tests (see Testing).
  `association.py`'s own fixtures (including the ambiguous multi-candidate scene) are
  hand-authored directly in `tests/test_association.py` rather than as separate files, since a
  live ambiguous scene is harder to stage than a single-target one — noted in that test module's
  own docstring.
