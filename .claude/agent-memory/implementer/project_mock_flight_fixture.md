---
name: mock-flight-fixture-harness
description: Cross-layer mock-flight HTTP+world-model chain test harness built for body-layer -- what it found and reusable geometry-design constraints.
metadata:
  type: project
---

`body-layer/tests/support/{mock_aircraft_layer,mock_world_model}.py` +
`tests/fixtures/mock_flight_canonical.json` + `tests/test_mock_flight_chain.py`
(2026-09-10) drive the real HTTP wire shape + real perception/belief pipeline +
real (synthetic) world-model store through 20 poll frames, single-threaded and
threaded-console variants. Both new tests passed against `main` unmodified --
the duplicate-contact runaway and cross-thread sqlite bugs this harness exists
to catch did **not** reproduce; already fixed pre-session, consistent with
prior [[project_pb2_stage0_scope_channel_repair]]/BL-x notes.

**Geometry design constraint worth remembering**: `AircraftLayerClient.
get_world_objects_latest()`/`get_petrovich_indication_latest()` return raw dicts
with zero validation against `TelemetrySample`/`WorldObjectsSnapshot` schema
classes -- a fixture only needs to match `to_dict()`'s *shape*, not go through
the aircraft-layer schema parsers at all. World-object lat/lon must be computed
by actually calling world-model's `coordinates.dcs_to_wgs84(theatre, x, z)` at
fixture-authoring time (not hand-picked), since `perception.association.
wgs84_to_dcs` really runs unmonkeypatched in this harness.

**Classification-lattice surprise**: a naked-eye object detected concurrently by
the Hybrid channel from frame 0 at `TYPE` level will *never* show a
`CONTACT_CLASSIFICATION_CHANGED` event even as naked-eye's own tier crosses
medres->hires, because `fold_classification`'s "lower level holds" rule blocks
every later `CLASS`-level percept from touching an already-`TYPE`-level held
claim. Don't design a fixture assuming a visible mid-flight reclassification
event without checking which channel founds the contact first.

Mock server correctness: frame-advance must be keyed on `/telemetry/latest`
only (track `_next_telemetry_index` separately from `_served_index`, the index
most recently served by telemetry) -- otherwise two sources' calls to
`/world_objects/latest`/`/petrovich_indication/latest` within one poll can see
different frames.
