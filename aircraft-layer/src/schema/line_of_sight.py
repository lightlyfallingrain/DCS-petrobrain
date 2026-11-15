"""DCS-driven line-of-sight wire format -- `plans/dcs-driven-los/plan.md`
(X-B29).

`petrobrain-line-of-sight-hook.lua` polls, once a second, the same
`net.dostring_in("scripting", ...)` bridge `petrobrain-mission-telemetry-
hook.lua` already uses for unit velocity -- but unlike that feed, this one
is **cone-scoped** (plan Second Revision, SS8-SS10): the snippet only
computes a sightline for an object inside the currently-commanded look-
direction wedge (`PB_LOOK_HOUR`/`PB_LOOK_FOV_DEG`, set by the inbound
look-direction command channel, see `collector.command_sender.
LookDirectionSender`), not for every object in the player bubble.

**The enumerated population is AI units *and* static objects** (`BL-11`
Stage 4, 2026-10-06; evidence `aircraft-layer/research/2026-10-06-unit-id-
join-results.md`). The Hook previously walked `coalition.getGroups()` ->
`grp:getUnits()` only, so statics -- 278 of 404 objects, 68.8%, in the
measured sortie's own mission, including eight `ZSU-23-4 Shilka` -- could
never appear in a result and never received a verdict. A static is
**indistinguishable from a unit on this wire**: same entry shape, same
`unit_name` join key, nothing here branches on it. The field names
`units_in_bubble`/`units_in_wedge` are therefore now counts of *objects*
(units + statics); they keep their names so the wire format and every
existing consumer stay unchanged.

Wire format (Hook -> collector), one JSON datagram per poll (matches
`petrobrain-mission-telemetry-hook.lua`'s own envelope shape):

    {"payload": "<compact string below>", "bridge_call_ms": <float>}

The compact string packs everything `dostring_in` can return across the
Hook/mission-scripting boundary (one scalar) into one delimited string,
mirroring `unit_velocity.py`'s own packing:

    "<units_in_bubble>|<units_in_wedge>|<sightlines_computed>|<hour_used>|"
    "<fov_half_deg_used>|<dcs_model_time_s>|<entries>"

`entries` is `"<unit_name>:<building_clear01>:<terrain_clear01>;..."`,
semicolon-separated, `01` meaning a literal `0`/`1` (never a bare Lua
boolean, which has no stable string form across a `dostring_in` round
trip). Empty population still returns a well-formed string (entries empty).

`units_in_bubble`/`units_in_wedge`/`sightlines_computed` are the plan's
own observability triad (SS1/SS10/SS12): `units_in_wedge` turns the plan's
uniform-azimuth cone-population *estimates* into a measurement, and
`sightlines_computed < units_in_wedge` would mean the `MAX_SIGHTLINES_PER_
CALL` guard (a blow-up backstop, not a policy -- plan SS10) actually bit.
**That comparison is the thing to watch after `BL-11` Stage 4**: adding
statics roughly triples the candidate population, the pre-statics
measurement was median 43 / max 71 per result, and whether the cap of 128
now binds is unmeasured. The Hook also logs it directly (`cap_hit`, plus
its own `LOS cap bit` line) so a sortie answers it by grep.
`hour_used`/`fov_half_deg_used` are the wedge the snippet actually queried
with this poll, independent of whatever body-layer most recently pushed --
see `annotate_los`'s own docstring (`perception/detection_trace.py`) for why
this is recorded per poll rather than assumed to track the push.

`building_clear`/`terrain_clear` are two independently-computed, separately
published fields (`world.searchObjects`/`SEGMENT` and `land.isVisible`
respectively, plan "REVISION (2026-09-29)") -- never pre-ANDed on the wire,
so a misbehaviour after both are live stays attributable to one half. The
join on the body-layer side (`naked_eye_source._resolve_los_by_unit_name`)
is what combines them into one `live_los_clear` verdict.

`samples` is keyed by `unit_name`, the same join key `unit_velocity.py`
already established for the sibling feed (`LoGetWorldObjects`'s own
`UnitName`) -- `LoGetWorldObjects` and the mission-scripting environment
share no other identifier. A duplicate `unit_name` within one poll is
resolved last-entry-wins at this parsing step, the same documented,
accepted limitation `unit_velocity.py`'s own `from_wire` carries.

`agl_m` (`plans/bl-b104-ground-contacts-on-ground/plan.md` Stage 5) is a
fourth, optional field on each entry: `"<unit_name>:<building_clear01>:
<terrain_clear01>:<agl_m>"`. `None` when the field is absent entirely (an
older deployed Hook script, pre-Stage-5) or present but empty (the
Hook's own `land.getHeight` pcall failed that poll) -- never a guessed
height, same tri-state discipline as `WorldObjectSample.is_ownship`.
Helicopter-landed/hovering detection is the only consumer; every other
LOS reader is unaffected by this field's presence or absence.

**Point probes (`plans/expected-area-look/plan.md`, `BL-B111`, Stage 1).**
A second, independent query rides the same poll: up to `MAX_PROBE_POINTS`
*terrain points* (not units), pushed by the collector's `probe_points`
command, each answered `land.isVisible` terrain-clear-or-not, **fail
closed** (unlike `terrain_clear` above, which fails `True` on error -- see
the Hook's own module docstring for why a probe answer must never guess
"clear"). The answer **rides in the JSON envelope as its own optional
key, never as an eighth pipe-delimited field** (plan: "so an old collector
with a new Hook, and the reverse, both keep working"):

    {"payload": "<...the seven pipe fields above...>",
     "bridge_call_ms": <float>,
     "probes": "<seq>|<i>:<0|1|>;..."}

`probes` is omitted, or an empty string, whenever no check is open (`N ==
0`) or the datagram came from a pre-Stage-1 Hook -- both read as "no probe
answers this poll", via `ProbeAnswers.from_wire`'s own optional-field
contract on `LineOfSightSnapshot.probes`. The timestamp is **not**
repeated on this sub-wire -- a probe answer is computed inside the same
mission-scripting poll as the rest of this snapshot, so it shares that
snapshot's own `dcs_model_time_s` (`LineOfSightReceiver` passes it in)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class LineOfSightParseError(ValueError):
    """Raised when a line-of-sight wire payload does not match the
    expected shape."""


#: `plans/expected-area-look/plan.md` Stage 1 -- "two open checks x three
#: points". The collector-side cap on an inbound `probe_points` command's
#: own `points` list, matched by the Hook's own `_safeClampInt`-bounded
#: `PB_PROBE_N` and by `SET_PROBES_TEMPLATE`'s fixed `2 + 2*6` `%d`
#: conversions -- a protocol constant shared by both ends of the wire, not
#: a behaviour-affecting tunable (root `CLAUDE.md`'s tuning policy: this
#: bounds a fixed-shape template, it does not change what Petrovich does).
MAX_PROBE_POINTS = 6


@dataclass(frozen=True, slots=True)
class ProbeAnswer:
    """One queried point's own terrain-clear verdict -- `index` is its
    position in the `probe_points` command's own `points` list (0-based),
    `clear` is `True`/`False`/`None`. **`None` means "cannot look", never
    "empty"** (plan E11/E5): the Hook's own `land.getHeight`/`land.
    isVisible` pcall failed, or this index was never answered at all --
    both collapse to the same fail-closed `None` on this side, since
    nothing downstream may ever treat an unanswered probe as a clear
    terrain point."""

    index: int
    clear: bool | None


@dataclass(frozen=True, slots=True)
class ProbeAnswers:
    """All probe answers from one poll, `seq`-matched against whichever
    `probe_points` command they answer -- `belief.expected_area`'s own
    caller is the one place that compares `seq` and `dcs_model_time_s`
    against the open check's own look window (plan Stage 2's "matched by
    seq" clause); this class only parses and carries the wire shape.

    `clear` is a tuple indexed exactly like the wire's own `<i>` token,
    length `MAX_PROBE_POINTS`, `None` at every index the wire did not
    mention -- so a caller can always index it `0..MAX_PROBE_POINTS - 1`
    without checking length first."""

    seq: int
    #: This poll's own `dcs_model_time_s` (`LineOfSightSnapshot`'s, not a
    #: second wire field) -- module docstring's "not repeated on this
    #: sub-wire" note.
    dcs_model_time_s: float
    clear: tuple[bool | None, ...]

    @staticmethod
    def from_wire(raw: str, *, dcs_model_time_s: float) -> ProbeAnswers:
        """Parse one `"<seq>|<i>:<0|1|>;..."` sub-wire string. Raises
        `LineOfSightParseError` on a malformed string -- the caller
        (`LineOfSightReceiver`) drops the *whole* envelope's `probes` field
        on that, same "malformed -> dropped, never guessed" posture as
        every other parse in this module, but does not drop the rest of
        the snapshot (a bad probe sub-wire says nothing about whether the
        LOS payload itself parsed)."""
        seq_str, _, entries_str = raw.partition("|")
        seq = _parse_int(seq_str, "probes.seq")
        clear: list[bool | None] = [None] * MAX_PROBE_POINTS
        for entry in entries_str.split(";"):
            if not entry:
                continue
            index_str, _, flag_str = entry.partition(":")
            try:
                index = int(index_str)
            except ValueError as exc:
                raise LineOfSightParseError(
                    f"probes entry index must be an integer, got {entry!r}"
                ) from exc
            if not (0 <= index < MAX_PROBE_POINTS):
                raise LineOfSightParseError(
                    f"probes entry index {index} out of range in {entry!r}"
                )
            if flag_str == "":
                clear[index] = None
            elif flag_str == "1":
                clear[index] = True
            elif flag_str == "0":
                clear[index] = False
            else:
                raise LineOfSightParseError(
                    f"probes entry flag must be '0', '1', or empty, got {entry!r}"
                )
        return ProbeAnswers(
            seq=seq, dcs_model_time_s=dcs_model_time_s, clear=tuple(clear)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "dcs_model_time_s": self.dcs_model_time_s,
            "clear": list(self.clear),
        }


@dataclass(frozen=True, slots=True)
class LineOfSightVerdict:
    """One unit's building/terrain LOS verdict for one poll. Two
    independently-computed fields, never pre-combined -- see the module
    docstring's "never pre-ANDed on the wire" note."""

    unit_name: str
    building_clear: bool
    terrain_clear: bool
    #: `None` when absent (legacy wire) or empty (the Hook's own pcall
    #: failed that poll) -- see module docstring. Default `None` keeps
    #: every pre-Stage-5 construction site compiling.
    agl_m: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "building_clear": self.building_clear,
            "terrain_clear": self.terrain_clear,
            "agl_m": self.agl_m,
        }


@dataclass(frozen=True, slots=True)
class LineOfSightSnapshot:
    """All line-of-sight verdicts from one mission-scripting poll, plus
    that poll's dual-clock timestamps, the cone actually queried with
    (`hour_used`/`fov_half_deg_used`), and the observability triad
    (`units_in_bubble`/`units_in_wedge`/`sightlines_computed`) -- mirrors
    `UnitVelocitySnapshot`'s provenance shape."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    hour_used: int
    fov_half_deg_used: int
    units_in_bubble: int
    units_in_wedge: int
    sightlines_computed: int
    bridge_call_ms: float
    verdicts: dict[str, LineOfSightVerdict]
    #: `plans/expected-area-look/plan.md` Stage 1 -- `None` when the
    #: envelope carried no `probes` key, or an empty one (no check open
    #: this poll, or a pre-Stage-1 Hook). See module docstring's "Point
    #: probes" section.
    probes: ProbeAnswers | None = None

    @staticmethod
    def from_wire(
        payload: str,
        *,
        bridge_call_ms: float,
        received_wall_clock_s: float,
        probes_raw: str | None = None,
    ) -> LineOfSightSnapshot:
        """Parse one compact wire string (module docstring) into a typed
        snapshot. `entries` may be empty (nothing in the queried wedge this
        poll).

        `probes_raw` is the envelope's own separate `"probes"` key
        (**not** part of `payload` -- module docstring's "never as an
        eighth pipe-delimited field"), passed through by
        `LineOfSightReceiver`. `None` or `""` both mean "no probe answers
        this poll" and leave `probes` at `None`; anything else is parsed
        via `ProbeAnswers.from_wire`, sharing this snapshot's own
        `dcs_model_time_s`."""
        parts = payload.split("|", 6)
        if len(parts) != 7:
            raise LineOfSightParseError(
                "expected '<units_in_bubble>|<units_in_wedge>|"
                "<sightlines_computed>|<hour_used>|<fov_half_deg_used>|"
                f"<t>|<entries>', got {payload!r}"
            )
        (
            units_in_bubble_str,
            units_in_wedge_str,
            sightlines_computed_str,
            hour_used_str,
            fov_half_deg_used_str,
            t_str,
            entries_str,
        ) = parts

        units_in_bubble = _parse_int(units_in_bubble_str, "units_in_bubble")
        units_in_wedge = _parse_int(units_in_wedge_str, "units_in_wedge")
        sightlines_computed = _parse_int(sightlines_computed_str, "sightlines_computed")
        hour_used = _parse_int(hour_used_str, "hour_used")
        fov_half_deg_used = _parse_int(fov_half_deg_used_str, "fov_half_deg_used")
        try:
            dcs_model_time_s = float(t_str)
        except ValueError as exc:
            raise LineOfSightParseError(
                f"field 'dcs_model_time_s' must be a number, got {t_str!r}"
            ) from exc

        verdicts: dict[str, LineOfSightVerdict] = {}
        for entry in entries_str.split(";"):
            if not entry:
                continue
            verdict = _parse_entry(entry)
            verdicts[verdict.unit_name] = verdict

        # A malformed `probes_raw` is dropped on its own -- never promoted
        # to a `LineOfSightParseError` that would also reject the (valid)
        # LOS payload this method already finished parsing above. Module
        # docstring: "a bad probe sub-wire says nothing about whether the
        # LOS payload itself parsed."
        probes: ProbeAnswers | None = None
        if probes_raw:
            try:
                probes = ProbeAnswers.from_wire(
                    probes_raw, dcs_model_time_s=dcs_model_time_s
                )
            except LineOfSightParseError:
                probes = None

        return LineOfSightSnapshot(
            dcs_model_time_s=dcs_model_time_s,
            received_wall_clock_s=received_wall_clock_s,
            hour_used=hour_used,
            fov_half_deg_used=fov_half_deg_used,
            units_in_bubble=units_in_bubble,
            units_in_wedge=units_in_wedge,
            sightlines_computed=sightlines_computed,
            bridge_call_ms=bridge_call_ms,
            verdicts=verdicts,
            probes=probes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dcs_model_time_s": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "hour_used": self.hour_used,
            "fov_half_deg_used": self.fov_half_deg_used,
            "units_in_bubble": self.units_in_bubble,
            "units_in_wedge": self.units_in_wedge,
            "sightlines_computed": self.sightlines_computed,
            "bridge_call_ms": self.bridge_call_ms,
            "verdicts": {
                name: verdict.to_dict() for name, verdict in self.verdicts.items()
            },
            "probes": self.probes.to_dict() if self.probes is not None else None,
        }


def _parse_int(raw: str, field: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise LineOfSightParseError(
            f"field {field!r} must be an integer, got {raw!r}"
        ) from exc


def _looks_like_agl_token(raw: str) -> bool:
    """`True` for an empty string (no verdict that poll) or anything
    `float()` accepts -- the shape Stage 5's own Lua side always emits
    for the fourth field, never for `building_clear01`/`terrain_clear01`
    (always a literal `"0"`/`"1"`)."""
    if raw == "":
        return True
    try:
        float(raw)
    except ValueError:
        return False
    return True


def _parse_entry(entry: str) -> LineOfSightVerdict:
    # rsplit, not split: a unit_name is not expected to contain a colon, but
    # DCS mission-editor names are free text -- same defensive posture
    # `unit_velocity.py`'s own `_parse_entry` takes toward untrusted
    # Hook-side strings.
    #
    # `agl_m` (Stage 5) is a fourth, optional trailing field, so an entry
    # may have either shape on the wire (an old, not-yet-redeployed Hook
    # script still emits three fields). The two are told apart by content,
    # not a version flag: the Stage-5 wire always emits `building_clear01`/
    # `terrain_clear01` as a literal `"0"`/`"1"` and `agl_m` as a float-or-
    # empty token, so a four-way split whose middle two fields are each
    # `"0"`/`"1"` and whose last is empty-or-numeric is accepted as the
    # new shape; anything else falls back to the three-field legacy split.
    # This cannot perfectly disambiguate a colon-containing unit_name in
    # every case -- the same documented, accepted limitation `unit_
    # velocity.py`'s own `_parse_entry` already carries for that field.
    four_fields = entry.rsplit(":", 3)
    if (
        len(four_fields) == 4
        and four_fields[1] in ("0", "1")
        and four_fields[2] in ("0", "1")
        and _looks_like_agl_token(four_fields[3])
    ):
        unit_name, building_str, terrain_str, agl_str = four_fields
    else:
        three_fields = entry.rsplit(":", 2)
        if len(three_fields) != 3:
            raise LineOfSightParseError(
                "expected '<unit_name>:<building_clear01>:<terrain_clear01>"
                "[:<agl_m>]', "
                f"got {entry!r}"
            )
        unit_name, building_str, terrain_str = three_fields
        agl_str = ""
    if not unit_name:
        raise LineOfSightParseError(f"empty unit_name in entry {entry!r}")
    building_clear = _parse_bool01(building_str, entry)
    terrain_clear = _parse_bool01(terrain_str, entry)
    agl_m = None if agl_str == "" else float(agl_str)
    return LineOfSightVerdict(
        unit_name=unit_name,
        building_clear=building_clear,
        terrain_clear=terrain_clear,
        agl_m=agl_m,
    )


def _parse_bool01(raw: str, entry: str) -> bool:
    if raw == "1":
        return True
    if raw == "0":
        return False
    raise LineOfSightParseError(
        f"expected a literal '0' or '1' clear flag, got {raw!r} in entry {entry!r}"
    )
