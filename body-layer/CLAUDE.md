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
phase, events, spatial semantics — sitting between the brain (`brain-layer/`, an HTTP peer as
of `plans/brain-layer/plan.md`'s BR-1 Stage 1) and the aircraft layer (DCS I/O). BL-0/BL-1
built the tier-independent perception scaffolding
(`PerceptionSource` interface, bearing/range/LOS geometry, a replay harness, an aircraft-layer
HTTP client, a text-only logger) plus its one concrete `PerceptionSource`,
`HybridPerceptionSource` — a live-DCS spike (`plans/pb1-perception-logger/plan.md` stage 1,
`aircraft-layer/research/2026-09-08-pb1-live-spike-results.md`) found every native geometry
channel dead and one real detection-existence channel (HelperAI's `list_indication`) alive, so
this is a hybrid design (real detection gate + `LoGetWorldObjects`-derived geometry via
`perception.association`), not a choice between two originally-anticipated tiers.
**Current BL-x milestone status: see `ROADMAP.md`** (this directory), not this file — status
changes faster than this doc gets touched.

**The surface is *commands*, not "F10 commands."** `CrewConsole.handle_command`
(`plans/voice-command-completeness/plan.md` Stage 1, renamed from `handle_f10_command`) is the
single dispatcher for every player-issued command token, reached from three input surfaces: the
DCS F10 radio menu, a spoken voice command, and a committed confirm-band answer. The F10 menu is
one legacy transport into that dispatcher, not the concept it names — per user direction
2026-09-19, voice is primary and the F10 menu "may go stale" once it is retired; the transport
names (`F10CommandQueue`, `get_f10_commands`, `--f10-commands`) stay as-is deliberately (see that
plan's Decision 4) since they describe the F10 radio-menu transport specifically, which is real
and still running, and renaming code scheduled for deletion buys nothing.

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

Add `--f10-commands` alongside `--crew-text` (`plans/f10-crew-commands/plan.md`, vocabulary widened
by `plans/f10-command-vocabulary/plan.md`) to poll and dispatch player-selected DCS F10 radio-menu
commands — the 15-token scan/watch/cancel vocabulary (`Scan` -> `Ahead`/`Left`/`Right`/`Full`/eight
compass `Bearing` items, `Watch` -> `Nearest`/`Nearest Air Defence`, `Cancel Task`) — through `CrewConsole.
handle_command`, the same output funnel typed/spoken text already goes through. Only meaningful
with `--crew-text`; defaults off, a true no-op when absent, same additive posture as `--overlay`.
See `aircraft-layer/WORKFLOW.md`'s "Deploy the F10 commands Hook script"
section for the DCS-side half of this channel (including its `autoexec.cfg` opt-in) — UNVERIFIED
against a live DCS session as of authorship.

Add `--speech-audio --audio-adapter-url URL` alongside `--crew-text` (BL-10 first slice, `plans/
tts-voice-output/plan.md`) to synthesize and play every line `CrewConsole` speaks via a running
`audio-adapter` instance's `POST /speak` — the same lines `--overlay` mirrors to the in-cockpit text
overlay, pushed through the identical `_print` funnel, just to a different sink/process. Only
meaningful with `--crew-text`; `--speech-audio` requires `--audio-adapter-url` (`parser.error` if
omitted); defaults off, a true no-op when absent, same additive posture as `--overlay`/
`--f10-commands`. `--overlay` and `--speech-audio` are independent and combine freely. See
`audio-adapter/CLAUDE.md` for how to run that process, including its own `--target local` no-other-
subproject-needed dev path.

Add `--speech-input --audio-adapter-url URL` alongside `--crew-text` (Stage 3, `plans/
inbound-speech/plan.md`) to poll and dispatch recognised speech transcripts through
`CrewConsole.handle_transcript` — the inbound counterpart to `--speech-audio`'s outbound path,
polling the same `audio-adapter` instance's `GET /transcripts/poll` instead of pushing to
`POST /speak`. Independent of `--speech-audio` (a separate concern, audio in vs. audio out) —
both share one `AudioAdapterClient` instance when both are set, but either works alone. Only
meaningful with `--crew-text`; `--speech-input` requires `--audio-adapter-url`; defaults off, a
true no-op when absent, same additive posture as `--f10-commands`. Needs `audio-adapter` run with
`--whisper-model` for `GET /transcripts/poll` to ever have anything to drain — see
`audio-adapter/CLAUDE.md`.

Add `--speech-log PATH` alongside `--crew-text --speech-input` to write one JSON line per
recognised transcript: what was heard, the seven recognition fields, and what was done about it
(`act`/`confirm`/`say_again`/`fallthrough`, plus the acted token). **It exists because an utterance
matching no command was previously unobservable** — it fell through to escalation, and the default
brain client does nothing, so the single most useful case for debugging recognition left no trace
anywhere. Matched utterances are logged too: a false fire is only findable by seeing what he
actually acted on. `parser.error`s without both flags; defaults off, a true no-op when absent, same
additive posture as `--detection-trace`. Unbuffered, unlike the detection trace — speech is a
handful of rows per sortie, and the row most worth having is the one immediately before something
went wrong, which a buffer would still be holding when the process was killed to investigate.

Add `--detection-trace PATH` alongside `--console` or `--crew-text` (BL-9, `plans/
bl9-debug-visualization/plan.md`) to write a per-poll, per-object naked-eye visibility-gate trace
(JSONL) to `PATH` — the answer to "why did Petrovich not see that" after a flight: which of
`check_visibility`'s three gates (cockpit mask / angular-size-or-range-cap / terrain LOS) decided
each `LoGetWorldObjects` candidate's fate, at what true range/bearing, plus (once admitted) which
`Contact` it was folded into. Reduce a raw trace with `body-layer/tools/
summarize_detection_trace.py PATH` for the actual flight-debrief table (first-admitted range per
object, and the never-admitted-but-in-FOV list) — the raw JSONL is not meant to be read directly.
`parser.error`s if passed without `--console` or `--crew-text` (there is nothing to join against
belief without one of those poll loops); defaults off, a true no-op when absent, same additive
posture as `--overlay`/`--f10-commands`. Only the naked-eye channel is traced — the scope/hybrid
channel has no geometric gate chain to instrument (a real HelperAI detection either exists or it
doesn't). The join itself (`src/detection_trace_writer.py`) is the one module in this codebase
deliberately allowed to hold both ground truth and belief at once, and is read-only against
`ContactStore` — see that module's own docstring for the boundary this preserves.

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

**Per-module detail lives in `docs/STRUCTURE.md`, and you are expected to read the entry for any
module before modifying it.** That file holds the *why* — decisions made, reversed and re-made with
the reasoning attached, calibration values derived twice, a formula that was shared between two
gates and had to be un-shared, a dual field that looks redundant and is not. It was split out of
this file on 2026-09-27 because it had grown to ~97KB (~24K tokens), the largest always-loaded
context item in the repo, for detail that only matters once you are inside one module.

What stays here is the map, and the invariants that someone who has *not* read the detail could
break without noticing.

### Invariants — break these and the failure is silent

- **No omniscience is structural, not a convention.** `belief/percept.py` (`Percept`/`percept_of`)
  is the boundary: belief code never sees `Observation.derived_world_position` or a DCS object id.
  `detection_trace_writer.py` is the single sanctioned exception — it may hold ground truth and
  belief at once, is read-only against `ContactStore`, and passes no ground-truth field back into
  `ingest`/`Percept`/`Contact`. Do not add a second exception.
- **Mechanism and calibration never share a commit.** A change to how a gate computes and a change
  to the numbers it computes against are separate commits, so a behaviour shift always has one
  attributable cause. BL-2.6 Stages 6/7 are the worked example.
- **`Contact.last_class_raw` and `Contact.classification` are both needed.** The folded best claim
  is what user-facing surfaces read; the raw most-recent string is what
  `association_over_time.py`'s spatial gate consumes, because feeding the gate the folded claim
  makes it monotonically stricter over a contact's life and it starts rejecting genuine
  re-observations. This dual field is a real readability cost, deliberately paid — read both
  docstrings before touching either.
- **A classification's `level` never decays; only its `confidence` does.** A contact identified as
  a T-72 two minutes ago does not revert to "something"; Petrovich becomes less sure of it.
- **Two `Observation`s sharing both `source` and `t_sim` may never resolve to the same contact.**
  `ContactStore.ingest` enforces it via a per-batch `claimed[(source, t_sim)]` pre-scan. It holds
  because each channel emits one observation per thing per poll — a precondition any new
  `PerceptionSource` must satisfy, not an invariant re-checked at runtime.
- **The tier → "existence/class/class/IFF" semantics reading is this project's own model, not
  verified against ED internals.** Documented so a future reader does not "correct" it toward an ED
  semantics that was never established.
- **The default optic is `UNAIDED_OPTIC` (naked eye), not binoculars.** Modelling Petrovich as
  permanently glassed-up was the single biggest source of over-detection in this channel (user
  direction, 2026-09-20). Binoculars are a deliberate, narrower, raised act.

  **The import-direction clause that used to close this bullet was deleted 2026-09-27: it described a
  constant the code no longer has, and named the direction backwards.** It read
  "`BINOCULAR_RANGE_MULTIPLIER` is declared in `visibility.py`; `optics.py` imports it, never the
  reverse." Cones slice 2A **retired** that constant — a flat range multiplier *is* the
  permanently-glassed-up model, so deleting it was the point — and doing so dissolved the real
  circular import the clause was guarding: `optics.py` now imports nothing from `visibility.py`, and
  `visibility.py` imports `Optic`/`UNAIDED_OPTIC`/`within_optic_fov` from `optics.py` as an ordinary
  top-level import. Both modules' docstrings say so. What survives is the first sentence — the naked
  eye is the default — and `/invariant-check` now holds the rest mechanically: it fails if an
  assignment to `BINOCULAR_RANGE_MULTIPLIER` reappears anywhere in `src/`.
- **New CLI flags are additive and a true no-op when absent.** Every flag added since `--overlay`
  follows it: defaults off, unchanged behaviour without it, `parser.error` for a missing companion
  argument. Keep that posture.
- **Everything must be testable without a live DCS session or a running collector** — `plans/body-layer/plan.md`
  §2's hard design requirement, not a nice-to-have. See `## Testing` above.
- **Module independence**: the world-model seam is an in-process import and is the sole sanctioned
  one. `belief/audio_client.py` is this subproject's own copy of a client shape rather than an
  import from `audio-adapter/`, and it stays that way.

### Module map

Perception — observation *production*:

- `src/perception/source.py` — the tier-independent `PerceptionSource` protocol, plus `OwnshipState`/`Observation`. No concrete tier here.
- `src/perception/geometry.py` — bearing/range helpers; LOS is a thin wrapper delegating to world-model's own `query.line_of_sight`.
- `src/perception/association.py` — pure within-one-poll detection ↔ world-object resolution. No network I/O.
- `src/perception/hybrid_source.py` — `HybridPerceptionSource`: gates on HelperAI's real `list_indication` classification text, resolves geometry via `association`/`geometry`.
- `src/perception/visibility.py` — `check_visibility`, the naked-eye channel's four composed gates (cockpit mask, per-optic FOV, angular-radius tier, terrain LOS). Owns `BINOCULAR_RANGE_MULTIPLIER`. **Heavily revised; read its entry.**
- `src/perception/optics.py` — `Optic` plus `UNAIDED_OPTIC` (the default) and `BINOCULAR_OPTIC`. The 9K113 sight is deliberately deferred to its own slice.
- `src/perception/clustering.py` — position-only resolution clustering. Separability is a 3D angle subtended at the observer compared against apparent angular size, **not** a world-space ellipse. **Read its entry before changing the predicate.**
- `src/perception/naked_eye_source.py` — `NakedEyePerceptionSource`; emits one `Observation` per *cluster*, not per candidate. `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` caps cluster admission, not per-object.
- `src/perception/gaze.py` — gaze/scan geometry helpers, incl. `legs_within_wedge`.
- `src/perception/detection_trace.py` — `GateOutcome`/`DetectionTrace`/`DetectionTraceCollector` (BL-9). One entry per `check_visibility` call. `None` default is a proven no-op.

Belief — observation *consumption*:

- `src/belief/percept.py` — `Percept`/`percept_of`, the no-omniscience boundary itself.
- `src/belief/contacts.py` — `Contact`/`SightingSpan`/`ContactStore` (`ingest`/`tick`), the append-only observation log. `tick` order is **lifecycle → classification → cardinality → attention**.
- `src/belief/association_over_time.py` — percept→contact spatial + class-compatibility gating. Isotropic and quantisation-derived. **Its entry explains why it must not share clustering's formula.**
- `src/belief/decay.py` — per-attribute half-lives and the `observed`/`tracked`/`estimated`/`lost` certainty ladder.
- `src/belief/events.py` — lifecycle/classification/cardinality event derivation, with `EVENT_COOLDOWN_S` suppression.
- `src/belief/classification.py` — the specificity lattice (`UNKNOWN`/`PRESENCE`/`CLASS`/`TYPE`) and `fold_classification`'s fusion rule: refine / reinforce / **hold** / contradict-with-lockout.
- `src/belief/cardinality.py` — `classification.py`'s deliberate twin over ED's count vocabulary; interval containment stands in for specificity level.
- `src/belief/enrichment.py` — world-enrichment orchestration (`SemanticFact`, `semantic_facts_for`, `WorldEnrichmentCache`, `relative_geometry`, `EnrichmentContext`).
- `src/belief/mission_phase.py` — mission-phase relevance (BL-7).
- `src/belief/tools.py` — the brain-facing query API's body, minus a transport; returns the `{facts, summary, phrasing_hints}` triple. Note its **absent-not-null** convention for `facts`.

Surfaces and transports:

- `src/belief/console.py` — line parser + pretty-printer over `tools.py`, owning no belief logic; also `format_event_for_overlay`.
- `src/belief/crew_console.py` — `CrewConsole`, and `handle_command` is the single dispatcher for **every** player command token (F10 menu, voice, confirm-band answer). See `## What this is` on why the F10 names persist.
- `src/belief/utterance.py`, `src/belief/speech.py`, `src/belief/escalation.py` — what he says and when: utterance shaping, event→template routing, escalation to the brain.
- `src/belief/voice_commands.py` — speech-transcript recognition to command tokens.
- `src/belief/brain_client.py`, `src/belief/brain_reply.py` — the brain-layer HTTP seam and structured-reply handling.
- `src/aircraft_client.py` — HTTP client for the aircraft-layer LAN API. `push_text_line` and the other writes **raise** rather than swallow; the caller's try/except is the designed catch point.
- `src/belief/audio_client.py` — `AudioAdapterClient` (`POST /speak`, `GET /transcripts/poll`).
- `src/logger.py` — the poll-loop entrypoint and every `--flag` branch. `main()`'s CLI wiring is untested by design; the runners are tested against fakes.
- `src/detection_trace_writer.py` — the sanctioned ground-truth-plus-belief join. Read-only, one-directional, buffered off the poll loop's critical path.
- `src/replay.py` — the BL-0 replay harness; drives any `PerceptionSource` over recorded ownship states.
- `tools/summarize_detection_trace.py`, `tools/speak_samples.py` — post-flight reducer and a dev acceptance aid, not tests.
- `tests/fixtures/` — committed synthetic fixtures; see `## Testing` on why they are not gitignored.
