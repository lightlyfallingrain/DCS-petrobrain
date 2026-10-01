"""Combined content identity for a build's SRTM tile set -- this cache's
`dem_identity` meta field.

Reuses `osm_cache.hashing.sha256_file`'s streamed-hash primitive (same
1 MiB-chunk contract) rather than duplicating it; this module only adds
the "combine several files' hashes into one identity" step `osm_cache`
never needed (it hashes exactly one `.osm.pbf`)."""

import hashlib
from pathlib import Path

from osm_cache.hashing import sha256_file


def combined_tile_hash(tile_paths: list[Path]) -> str:
    """SHA-256 over `(name, sha256)` of every path in `tile_paths`, sorted
    by name first -- order-independent in the caller's own list, so
    `srtm_tile_paths` passed in a different order (e.g. a differently
    sorted `glob()`) still produces the same identity for the same actual
    tile set. Each tile is hashed by content (`sha256_file`), not by path
    or mtime, so replacing a tile file with different bytes under the same
    name is correctly seen as a different DEM identity."""
    digest = hashlib.sha256()
    for path in sorted(tile_paths, key=lambda p: p.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(sha256_file(path).encode("utf-8"))
    return digest.hexdigest()
