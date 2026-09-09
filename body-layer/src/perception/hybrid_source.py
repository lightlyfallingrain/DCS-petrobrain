"""`HybridPerceptionSource` -- the only concrete `PerceptionSource` this
project builds (`plans/pb1-perception-logger/plan.md`'s "Single
implementation, not two" section explains why there is no second tier to
branch on).

Each `poll()`:
1. Fetches the latest HelperAI indication (`GET /petrovich_indication/
   latest`). If `middle_list_text` isn't populated, or hasn't changed since
   the last poll that produced an `Observation` (debounce, see below),
   returns `[]` -- absence/no-change reported as absence, not a fabricated
   or repeated poll.
2. Fetches the latest `LoGetWorldObjects` snapshot (`GET /world_objects/
   latest`), converts it to `association.WorldObjectCandidate`s, and drops
   the player's own aircraft via `association.filter_ownship()` --
   `LoGetWorldObjects` is unfiltered ground truth and includes ownship
   itself, identified by the aircraft-layer's `is_ownship` flag (see that
   function's docstring; the flag replaced an earlier 50 m proximity
   heuristic found necessary via a live sortie,
   `plans/pb1.5-naked-eye-detection/debug.md`).
3. Calls `association.associate()` to resolve which candidate (if any) the
   detection refers to.
4. Builds one `Observation` from the resolved candidate's geometry, or
   returns `[]` if `associate()` found nothing plausible (a drop, logged as
   a rate signal, not per-instance noise -- per the plan's Association
   design section).

Debounce is a simple "only emit when `middle_list_text` differs from the
text that produced the last emitted `Observation`" check -- the exact window
is an implementation detail, not an architectural one (plan stage 6), picked
here because it's the cheapest thing that stops a persisting detection from
spamming `logger.py`'s output every poll tick while still re-emitting
immediately on any real change (including a detection clearing and a new
one appearing later, even with the same text -- see `poll`'s handling of a
momentarily-empty `middle_list_text` resetting the debounce state).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from aircraft_client import AircraftLayerClient
from perception.association import WorldObjectCandidate, associate, filter_ownship
from perception.source import DerivedWorldPosition, Observation, OwnshipState

logger = logging.getLogger(__name__)

#: The HelperAI controller name association gates on -- the confirmed-live
#: "which target is currently selected" text
#: (aircraft-layer/research/2026-09-08-pb1-live-spike-results.md finding 1).
MIDDLE_LIST_TEXT_FIELD = "middle_list_text"

SOURCE_PETROVICH_DETECTION_ASSOCIATED = "petrovich_detection_associated"


@dataclass
class HybridPerceptionSource:
    """See module docstring. `theatre` is required for
    `WorldObjectCandidate.from_dict`'s lat/lon -> DCS x/z conversion
    (world-model's coordinate subsystem is per-theatre)."""

    aircraft_client: AircraftLayerClient
    theatre: str

    _last_emitted_classification: str | None = field(
        default=None, init=False, repr=False
    )
    _observation_count: int = field(default=0, init=False, repr=False)
    _dropped_count: int = field(default=0, init=False, repr=False)

    def poll(self, now_sim: float, ownship_state: OwnshipState) -> list[Observation]:
        indication = self.aircraft_client.get_petrovich_indication_latest()
        if indication is None:
            return []

        fields = indication.get("fields", {})
        classification = fields.get(MIDDLE_LIST_TEXT_FIELD)
        if not classification:
            # No current detection -- reset debounce so the *next* populated
            # text (even if identical to the last one seen before this gap)
            # is treated as new, per the module docstring.
            self._last_emitted_classification = None
            return []
        if classification == self._last_emitted_classification:
            return []  # unchanged detection -- debounced, don't re-emit

        world_objects = self.aircraft_client.get_world_objects_latest()
        if world_objects is None:
            self._record_drop(classification, "no world-objects snapshot available")
            return []

        candidates = filter_ownship(
            [
                WorldObjectCandidate.from_dict(obj, theatre=self.theatre)
                for obj in world_objects.get("objects", [])
            ]
        )
        result = associate(classification, ownship_state, candidates)
        if result is None:
            self._record_drop(classification, "no plausible world-object candidate")
            return []

        self._last_emitted_classification = classification
        self._observation_count += 1
        observation = Observation(
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
        return [observation]

    def _record_drop(self, classification: str, reason: str) -> None:
        self._dropped_count += 1
        logger.info(
            "dropping detection %r: %s (%d total drops this session)",
            classification,
            reason,
            self._dropped_count,
        )
