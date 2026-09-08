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
aircraft layer (DCS I/O). Currently at BL-0/BL-1: the tier-independent perception scaffolding
(`PerceptionSource` interface, bearing/range/LOS geometry, a replay harness, an aircraft-layer
HTTP client, a text-only logger) plus its one concrete `PerceptionSource`,
`HybridPerceptionSource` — a live-DCS spike (`plans/pb1-perception-logger/plan.md` stage 1,
`aircraft-layer/research/2026-09-08-pb1-live-spike-results.md`) found every native geometry
channel dead and one real detection-existence channel (HelperAI's `list_indication`) alive, so
this is a hybrid design (real detection gate + `LoGetWorldObjects`-derived geometry via
`perception.association`), not a choice between two originally-anticipated tiers. None of
BL-2+'s contact/attention/brain-API machinery has been built yet.

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
- `src/aircraft_client.py` — HTTP client for the aircraft-layer LAN API
  (`GET /telemetry/latest`, `GET /world_objects/latest`, `GET /petrovich_indication/latest`). A
  real network call, unlike the world-model seam.
- `src/replay.py` — BL-0 replay harness: drives any `PerceptionSource.poll()` over a recorded
  sequence of ownship states, no live DCS/aircraft-layer connection required.
- `src/logger.py` — the PB-1 deliverable: `PerceptionLogger` polls ownship telemetry + a
  `PerceptionSource`, formats each `Observation` as flat text; fully tested against a fake
  source, tier-agnostic. `main()` is the one place that plugs in the concrete
  `HybridPerceptionSource` and drives the poll loop (`python -m logger --aircraft-layer-url ...
  --theatre ...`) — untested by design, same posture as `aircraft-layer/src/collector/
  __main__.py`'s own live-process entrypoint.
- `tests/fixtures/` — committed fixture frames for the replay harness's own tests (see Testing).
  `association.py`'s own fixtures (including the ambiguous multi-candidate scene) are
  hand-authored directly in `tests/test_association.py` rather than as separate files, since a
  live ambiguous scene is harder to stage than a single-target one — noted in that test module's
  own docstring.
