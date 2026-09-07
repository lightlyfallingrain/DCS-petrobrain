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
HTTP client, and a stub text-only logger) — no concrete `PerceptionSource` implementation exists
yet (see plan's stage 1/4, deferred to a live-DCS spike this subproject does not run itself), and
none of BL-2+'s contact/attention/brain-API machinery has been built.

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
  `GET /telemetry/latest` and `GET /world_objects/latest` over the LAN, since aircraft-layer/DCS
  may be a different box than body-layer (unlike the world-model seam above).
- Formatter/linter: `ruff format` / `ruff check`.
- Test runner: `pytest`.

## Commands

```sh
ruff format body-layer/src body-layer/tests   # format
ruff check body-layer/src body-layer/tests    # lint
mypy body-layer/src                            # type check (strict)
pytest body-layer/tests -q                     # test
```

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
- `src/aircraft_client.py` — HTTP client for the aircraft-layer LAN API
  (`GET /telemetry/latest`, `GET /world_objects/latest`). A real network call, unlike the
  world-model seam.
- `src/replay.py` — BL-0 replay harness: drives any `PerceptionSource.poll()` over a recorded
  sequence of ownship states, no live DCS/aircraft-layer connection required.
- `src/logger.py` — the PB-1 deliverable shape: polls ownship telemetry + a `PerceptionSource`,
  formats each `Observation` as flat text. No concrete `PerceptionSource` is wired in yet
  (stage 4+ of `plans/pb1-perception-logger/plan.md`), so there is no `__main__`/CLI entrypoint
  here yet — `PerceptionLogger` is fully built and tested against a fake source.
- `tests/fixtures/` — committed fixture frames for the replay harness's own tests (see Testing).
