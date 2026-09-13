"""Streamed file hashing -- the one place this plan touches the raw
`.osm.pbf` bytes a second time (the classification/parsing pass already
reads them once; this reads them again, sequentially, to compute the
cache's invalidation key).
"""

import hashlib
from pathlib import Path

# 1 MiB chunks: large enough that Python-level loop overhead is negligible
# against the OS-level disk read this call is dominated by, small enough
# that this function never holds more than one chunk of a 476 MB+ (and
# growing) `.osm.pbf` file in memory at once.
_DEFAULT_CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> str:
    """Return `path`'s SHA-256 digest (lowercase hex), reading it in
    `chunk_size`-byte chunks rather than `path.read_bytes()` -- never loads
    the whole file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()
