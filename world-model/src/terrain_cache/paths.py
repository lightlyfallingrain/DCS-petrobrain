"""The one place mapping a base-store path to its terrain-cache sibling,
so no consumer hardcodes the convention. Mirrors `osm_cache.paths`."""

from pathlib import Path


def terrain_cache_store_path(base_db_path: Path) -> Path:
    """`data/world-model/<region>.sqlite` ->
    `data/world-model/<region>-terrain-cache.sqlite`. Populated at this
    exact path from the first write -- see `schema.py`'s module docstring
    for why this cache has no separate `.tmp` path, unlike `osm_cache`."""
    return base_db_path.with_name(
        f"{base_db_path.stem}-terrain-cache{base_db_path.suffix}"
    )
