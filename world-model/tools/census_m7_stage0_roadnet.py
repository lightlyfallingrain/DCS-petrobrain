#!/usr/bin/env python3
"""M7 Stage 0: full-theatre `.routes` census against the new `syria-full`
region.

Not part of the pipeline -- a throwaway measurement script per
`plans/m7-full-theatre-pipeline/plan.md` Stage 0 ("Run the existing
`.routes` walk against the whole bbox ... and record real full-theatre
road/route counts"). This is a **measurement only**: it walks
`Syria.routes` and reports counts, it does not build or write a `.sqlite`
store -- the plan's "Execution boundary" reserves the actual full-theatre
build for the user, on their Windows DCS machine.

Reuses `build.ingest_roadnet.ingest_roadnet` unchanged against
`build.region.REGIONS["syria-full"]`'s rectangular bbox -- the same
call shape `build.pipeline.build_region` uses, so this script's counts are
directly comparable to what a real build would ingest. The walk itself was
already perf-proven at 446s / ~22.5MB peak RSS over the whole file in M5
Stage 5 (`world-model/research/2026-09-04-m5-first-persistent-model.md`);
this script changes only the bbox filter, not the walk itself.

Run from `world-model/`:

    .venv/bin/python tools/census_m7_stage0_roadnet.py
"""

import json
import logging
import sys
import time
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from build.ingest_roadnet import ingest_roadnet
from build.region import REGIONS

_ROUTES_PATH = (
    _WORLD_MODEL_ROOT / "data" / "raw" / "dcs" / "syria" / "roads" / "Syria.routes"
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    if not _ROUTES_PATH.exists():
        print(f"error: {_ROUTES_PATH} does not exist", file=sys.stderr)
        sys.exit(1)

    region = REGIONS["syria-full"]
    logger.info(
        "syria-full region: centre=(%.1f, %.1f) half_extent_x_m=%.1f "
        "half_extent_z_m=%.1f",
        region.centre_x,
        region.centre_z,
        region.half_extent_x_m,
        region.half_extent_z_m,
    )
    logger.info("walking %s (%d bytes)...", _ROUTES_PATH, _ROUTES_PATH.stat().st_size)

    start = time.perf_counter()
    features, stats = ingest_roadnet(
        _ROUTES_PATH,
        region.centre_x,
        region.centre_z,
        region.half_extent_x_m,
        region.half_extent_z_m,
        source_id=None,
    )
    elapsed_s = time.perf_counter() - start

    clipped = sum(1 for f in features if f.tags.get("clipped"))

    result = {
        "region": region.name,
        "routes_path": str(_ROUTES_PATH),
        "wall_time_s": elapsed_s,
        "routes_found_whole_file": stats.routes_found_whole_file,
        "routes_in_region": stats.routes_in_region,
        "routes_in_region_clipped": clipped,
        "resync_events": stats.resync_events,
        "sync_loss_events": stats.sync_loss_events,
        "bytes_covered": stats.bytes_covered,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
