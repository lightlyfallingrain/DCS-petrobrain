"""`HybridPerceptionSource` -- the only concrete `PerceptionSource` this
project builds (`plans/pb1-perception-logger/plan.md`'s "Single
implementation, not two" section explains why there is no second tier to
branch on).

Each `poll()`:
1. Fetches the latest HelperAI indication (`GET /petrovich_indication/
   latest`). Reads all five `*_list_text` leaves (`LIST_TEXT_FIELDS`), not
   just `middle_list_text` -- `aircraft-layer/research/2026-09-08-pb1-5-
   worldobjects-filter-and-ambient-detection.md` Finding 6 established these
   five leaves are a scrolling **window into a multi-row target list**, not
   one selected target: real sampled data held `Slava cruiser` +
   `Tarantul III corvette`, and separately `SA-3 launcher` +
   `SA-3 Low Blow radar`, as distinct simultaneous rows. Collapses to the
   distinct populated texts, in `LIST_TEXT_FIELDS` order, de-duplicated
   within this poll (`middle_list_text` and `lower_list_text` are frequently
   the same text, per Finding 6's table). If nothing is populated, or the
   whole set of distinct texts is unchanged since the last poll that
   produced `Observation`s (debounce, see below), returns `[]`.
2. Fetches the latest `LoGetWorldObjects` snapshot (`GET /world_objects/
   latest`), converts it to `association.WorldObjectCandidate`s, and drops
   the player's own aircraft via `association.filter_ownship()` --
   `LoGetWorldObjects` is unfiltered ground truth and includes ownship
   itself, identified by the aircraft-layer's `is_ownship` flag (see that
   function's docstring; the flag replaced an earlier 50 m proximity
   heuristic found necessary via a live sortie,
   `plans/pb1.5-naked-eye-detection/debug.md`).
3. Calls `association.associate()` once per distinct populated leaf text, in
   order, to resolve which candidate (if any) each refers to. A candidate
   claimed by one leaf is removed from the pool before the next leaf is
   associated, so two leaves naming two real, distinct objects (the SA-3
   pair above) cannot both resolve to the same candidate.
4. Builds one `Observation` per successfully-resolved leaf. A leaf for which
   `associate()` finds nothing plausible is dropped individually (logged as
   a rate signal, not per-instance noise -- per the plan's Association
   design section) without blocking the other leaves in the same poll.

Debounce compares the *whole set* of distinct populated texts this poll
against the set that produced the last emitted `Observation`s -- the exact
window is an implementation detail, not an architectural one (plan stage 6),
picked here because it's the cheapest thing that stops a persisting
detection set from spamming `logger.py`'s output every poll tick while still
re-emitting immediately on any real change (including every leaf clearing
and the same text reappearing later -- see `poll`'s handling of a
momentarily-empty leaf set resetting the debounce state). This mirrors PB-1's
single-`middle_list_text`-value debounce exactly when only one leaf is ever
populated, which is why every existing on_change test still passes
unmodified.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Final

from aircraft_client import AircraftLayerClient
from perception.association import WorldObjectCandidate, associate, filter_ownship
from perception.source import DerivedWorldPosition, Observation, OwnshipState

logger = logging.getLogger(__name__)

#: The five HelperAI list-text controller names, in on-screen top-to-bottom
#: order -- a scrolling window into a multi-row target list (see module
#: docstring, Finding 6). `upper_list_text` is defined in
#: `HelperAI_page_common.lua` but never observed populated across 3,652 live
#: samples (Finding 5); kept in this tuple anyway for symmetry and because a
#: future DCS patch could start populating it -- reading a field that's
#: always absent costs nothing.
LIST_TEXT_FIELDS: Final[tuple[str, ...]] = (
    "upper_upper_list_text",
    "upper_list_text",
    "middle_list_text",
    "lower_list_text",
    "lower_lower_list_text",
)

SOURCE_PETROVICH_DETECTION_ASSOCIATED = "petrovich_detection_associated"


def _distinct_populated_texts(fields: dict[str, Any]) -> tuple[str, ...]:
    """The populated `LIST_TEXT_FIELDS` leaves' text values, in field order,
    de-duplicated by text (first occurrence wins) -- see module docstring
    point 1."""
    seen: list[str] = []
    for field_name in LIST_TEXT_FIELDS:
        text = fields.get(field_name)
        if text and text not in seen:
            seen.append(text)
    return tuple(seen)


@dataclass
class HybridPerceptionSource:
    """See module docstring. `theatre` is required for
    `WorldObjectCandidate.from_dict`'s lat/lon -> DCS x/z conversion
    (world-model's coordinate subsystem is per-theatre)."""

    aircraft_client: AircraftLayerClient
    theatre: str

    _last_emitted_texts: tuple[str, ...] | None = field(
        default=None, init=False, repr=False
    )
    _observation_count: int = field(default=0, init=False, repr=False)
    _dropped_count: int = field(default=0, init=False, repr=False)

    def poll(self, now_sim: float, ownship_state: OwnshipState) -> list[Observation]:
        indication = self.aircraft_client.get_petrovich_indication_latest()
        if indication is None:
            return []

        fields = indication.get("fields", {})
        distinct_texts = _distinct_populated_texts(fields)
        if not distinct_texts:
            # No current detections -- reset debounce so the *next* populated
            # text set (even if identical to the one seen before this gap)
            # is treated as new, per the module docstring.
            self._last_emitted_texts = None
            return []
        if distinct_texts == self._last_emitted_texts:
            return []  # unchanged detection set -- debounced, don't re-emit

        world_objects = self.aircraft_client.get_world_objects_latest()
        if world_objects is None:
            for classification in distinct_texts:
                self._record_drop(classification, "no world-objects snapshot available")
            return []

        candidates = filter_ownship(
            [
                WorldObjectCandidate.from_dict(obj, theatre=self.theatre)
                for obj in world_objects.get("objects", [])
            ]
        )

        observations: list[Observation] = []
        for classification in distinct_texts:
            result = associate(classification, ownship_state, candidates)
            if result is None:
                self._record_drop(classification, "no plausible world-object candidate")
                continue

            # Remove the claimed candidate before associating the next leaf
            # so two leaves naming two real, distinct objects (e.g. the SA-3
            # launcher + radar pair) cannot both resolve to the same
            # candidate -- see module docstring point 3.
            candidates = [
                candidate
                for candidate in candidates
                if candidate is not result.candidate
            ]

            self._observation_count += 1
            observations.append(
                Observation(
                    id=f"OBS_{self._observation_count}",
                    contact_id=None,
                    t_sim=now_sim,
                    t_wall=time.time(),
                    source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
                    classification_raw=classification,
                    bearing_deg=result.bearing_deg,
                    range_m=result.range_m,
                    ownship_at_observation=ownship_state,
                    derived_world_position=DerivedWorldPosition(
                        x=result.candidate.x,
                        z=result.candidate.z,
                        confidence=result.confidence,
                        method=result.method,
                    ),
                    provenance=(
                        "petrovich_indication+world_objects/ambiguous_association"
                        if result.ambiguous
                        else "petrovich_indication+world_objects"
                    ),
                )
            )

        if observations:
            # Mirrors PB-1's original single-classification debounce, which
            # only advanced `_last_emitted_classification` on a successful
            # association -- a persistently-unassociable detection is
            # retried every poll, not silently debounced away.
            self._last_emitted_texts = distinct_texts
        return observations

    def _record_drop(self, classification: str, reason: str) -> None:
        self._dropped_count += 1
        logger.info(
            "dropping detection %r: %s (%d total drops this session)",
            classification,
            reason,
            self._dropped_count,
        )
