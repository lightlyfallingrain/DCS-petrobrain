"""Frozen dataclasses/enums specific to the probe store.

`store.models.Source` and `store.models.StoredFeature` are reused as-is for
the probe store's `source`/`feature` tables (identical shape -- see
`writer.py`/`reader.py`), so this module only adds what the base store has
no equivalent of: chunk coverage.
"""

from dataclasses import dataclass
from enum import Enum


class ChunkStatus(Enum):
    """Tri-state coverage for one `(kind, chunk_ix, chunk_iz)`.

    Row absence in `chunk_coverage` means `UNQUERIED` -- materializing an
    explicit row for every chunk of every kind up front (~25,500 chunks for
    Syria at 5 km) would only make "unbuilt store" and "never probed"
    indistinguishable from each other by convention rather than by
    construction. `QUERIED_WITH_DATA` and `QUERIED_VOID` are always
    explicit rows written by `writer.upsert_chunk_coverage`. `QUERIED_VOID`
    is a real, meaningful outcome (e.g. `land.getSurfaceType` over open
    water yields nothing storable for that kind) and must never be
    conflated with `UNQUERIED`.
    """

    UNQUERIED = "unqueried"
    QUERIED_WITH_DATA = "queried_with_data"
    QUERIED_VOID = "queried_void"


@dataclass(frozen=True)
class Chunk:
    """One `(kind, chunk_ix, chunk_iz)` coverage record.

    `reader.chunk_status` never returns `None` -- callers get a `Chunk`
    (or bare `ChunkStatus`) whose `status` is explicitly `UNQUERIED` when no
    row exists, keeping the tri-state total at the API surface rather than
    leaking a fourth "row missing" case for callers to handle separately.
    """

    kind: str
    chunk_ix: int
    chunk_iz: int
    status: ChunkStatus
