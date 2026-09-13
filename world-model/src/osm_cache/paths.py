"""The one place mapping a base-store path to its OSM-cache sibling and its
population-time `.tmp` path, so no consumer hardcodes either convention.
"""

from pathlib import Path


def osm_cache_store_path(base_db_path: Path) -> Path:
    """`data/world-model/<region>.sqlite` -> `data/world-model/<region>-osm-cache.sqlite`."""
    return base_db_path.with_name(f"{base_db_path.stem}-osm-cache{base_db_path.suffix}")


def osm_cache_tmp_path(base_db_path: Path) -> Path:
    """The path a cache is populated at before `writer.finalize_cache`
    atomically renames it to `osm_cache_store_path(base_db_path)`. Never a
    valid cache to read from -- see `writer.py`'s module docstring."""
    canonical = osm_cache_store_path(base_db_path)
    return canonical.with_name(canonical.name + ".tmp")
