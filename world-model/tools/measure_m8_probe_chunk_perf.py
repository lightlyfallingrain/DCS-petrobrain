#!/usr/bin/env python3
"""M8 Implementation Plan step 5: performance sanity for one `add_probe_chunk`
call and `describe_position` with the probe store attached -- **not** a
full-theatre `syria-full` build (per the plan's step 5, that stays the
Windows machine's job, see `docs/M7_RUN_INSTRUCTIONS.md`'s precedent).

Builds a small synthetic base store plus a probe store, both entirely
local and disposable (a `tempfile.TemporaryDirectory`), at the **locked
production defaults** (`CHUNK_SIZE_M=5000`, `PROBE_SPACING_M=100` -> a
2,601-point chunk, matching the plan's "Locked parameters" table), then
times:

- one `add_probe_chunk` call (probe ingest + grid upsert + chunk-scoped
  terrain classification), and
- 100 `describe_position` calls with the probe store `ATTACH`ed, at random
  points inside the probed chunk.

Prints one JSON object to stdout.

    .venv/bin/python tools/measure_m8_probe_chunk_perf.py
"""

import datetime
import json
import random
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from build.pipeline import add_probe_chunk, open_region_db
from build.region import RegionDefinition
from probe_store.paths import probe_store_path
from query import describe_position
from store.chunks import CHUNK_SIZE_M, chunk_bounds, chunk_index_for
from store.models import Region
from store.writer import insert_region, open_for_build

_PROBE_SPACING_M = 100.0
_REGION = RegionDefinition.square(
    theatre="Syria",
    name="m8-perf-region",
    centre_x=50_000.0,
    centre_z=50_000.0,
    half_extent_m=20_000.0,
)


@dataclass(frozen=True)
class ChunkPerfReport:
    points_in_fixture: int
    add_probe_chunk_ms: float
    describe_position_probe_attached_mean_ms: float
    describe_position_probe_attached_p95_ms: float


def _generate_full_chunk_fixture(path: Path, chunk_ix: int, chunk_iz: int) -> int:
    """Write a full 51x51 (2,601-point) chunk-scoped probe output file at
    the locked spacing, with a repeating sawtooth elevation surface (real
    variation, so the ridge/valley classifier has something to do rather
    than a perf run over a flat no-op field)."""
    min_x, max_x, min_z, _max_z = chunk_bounds(chunk_ix, chunk_iz, CHUNK_SIZE_M)
    n = round((max_x - min_x) / _PROBE_SPACING_M) + 1
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for i in range(n):
            x = min_x + i * _PROBE_SPACING_M
            for j in range(n):
                z = min_z + j * _PROBE_SPACING_M
                height_m = 50.0 * ((i % 7) - 3) + 20.0 * ((j % 5) - 2)
                f.write(
                    json.dumps(
                        {
                            "name": f"r{i}c{j}",
                            "x": x,
                            "z": z,
                            "height_m": height_m,
                            "surface_type": 1,
                        }
                    )
                    + "\n"
                )
                count += 1
    return count


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        base_path = tmp_path / "m8-perf-region.sqlite"
        # Built directly via `store.writer`, not `build.pipeline.build_region`
        # -- this script only needs a valid `region` row + schema version for
        # `add_probe_chunk`'s base-store identity check, not real towns/
        # beacons/OSM/roadnet data (see `test_describe_position.py`'s
        # `_fixture_conn` for the same direct-writer fixture pattern).
        conn = open_for_build(base_path)
        insert_region(
            conn,
            Region(
                name=_REGION.name,
                theatre=_REGION.theatre,
                centre_x=_REGION.centre_x,
                centre_z=_REGION.centre_z,
                half_extent_x_m=_REGION.half_extent_x_m,
                half_extent_z_m=_REGION.half_extent_z_m,
                built_at=datetime.datetime.now(datetime.UTC).isoformat(),
            ),
        )
        conn.close()

        chunk_ix, chunk_iz = chunk_index_for(_REGION.centre_x, _REGION.centre_z)
        probe_output = tmp_path / "chunk_fixture.jsonl"
        n_points = _generate_full_chunk_fixture(probe_output, chunk_ix, chunk_iz)

        start = time.monotonic()
        add_probe_chunk(base_path, probe_output, chunk_ix, chunk_iz)
        add_probe_chunk_ms = (time.monotonic() - start) * 1000.0

        probe_path = probe_store_path(base_path)
        min_x, max_x, min_z, max_z = chunk_bounds(chunk_ix, chunk_iz, CHUNK_SIZE_M)
        rng = random.Random(20260906)
        latencies_ms: list[float] = []
        conn = open_region_db(base_path)
        try:
            for _ in range(100):
                x = rng.uniform(min_x, max_x)
                z = rng.uniform(min_z, max_z)
                start = time.monotonic()
                describe_position(conn, "Syria", x, z, probe_db_path=probe_path)
                latencies_ms.append((time.monotonic() - start) * 1000.0)
        finally:
            conn.close()

        latencies_ms.sort()
        mean_ms = sum(latencies_ms) / len(latencies_ms)
        p95_ms = latencies_ms[
            min(len(latencies_ms) - 1, round(0.95 * (len(latencies_ms) - 1)))
        ]

        report = ChunkPerfReport(
            points_in_fixture=n_points,
            add_probe_chunk_ms=add_probe_chunk_ms,
            describe_position_probe_attached_mean_ms=mean_ms,
            describe_position_probe_attached_p95_ms=p95_ms,
        )
        print(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    main()
