# Plan: cockpit visibility limits for Petrovich's naked-eye channel

Status: **draft, awaiting user approval — not implemented.** Raised 2026-09-17 from co-pilot-station
screenshots (`win-mac-sync/from-windows/Screen_260917_0000{55,59,105,125}.jpg`, co-pilot forward /
**right** / **left** / wide; `...{135,138,142,152}.jpg` are the pilot station, out of scope —
Petrovich is the co-pilot).

## The problem

`perception/visibility.py`'s naked-eye gate is a single azimuth cone:

```python
def _within_fov(ownship_heading_deg: float, candidate_bearing_deg: float) -> bool:
    delta = (candidate_bearing_deg - ownship_heading_deg + 180.0) % 360.0 - 180.0
    return abs(delta) <= NAKED_EYE_FOV_HALF_WIDTH_DEG   # 60.0
```

**There is no elevation term at all.** A contact 90 m below and 60° off the nose passes this gate
exactly as easily as one on the horizon. In a helicopter at low level that is not an edge case —
it is the normal case: at 100 m AGL a contact 200 m out sits ~27° below, at 500 m out ~11° below.
So Petrovich currently sees *through the fuselage and through the floor*, and can report contacts
he has no way of seeing. That is a violation of this project's core "knowledge bounded by what he
could actually perceive" invariant, even though it never touches DCS ground truth.

What the screenshots show, from the co-pilot seat:

- **Forward** (`...55`, `...125`): genuinely good. Wide azimuth, and a steep downward view — the
  nose glazing lets him look well below the horizon.
- **Right** (`...59`): horizon and mid-distance still visible, but the near ground below is cut off
  by the sill and side console. No steep depression.
- **Left** (`...105`): more obstructed again — structure fills the near/lower half of the frame,
  leaving ground visible only in an upper wedge toward the horizon.

So the missing constraint is **depression as a function of azimuth**: steep looking ahead, shallow
looking abeam, and blocked below abeam entirely. Azimuth alone cannot express that.

Secondary finding, already recorded in `todo/todo.md`: `NAKED_EYE_FOV_HALF_WIDTH_DEG = 60.0` is the
**9K113's** angular limit (user, 2026-09-16), not anything established about a human looking through
cockpit glass. This plan replaces that constant rather than re-guessing it.

## Feasibility — the enabling fact

`aircraft-layer`'s `TelemetrySample` **already carries `pitch_rad` and `bank_rad`** on the wire.
`perception.source.OwnshipState` simply does not read them. So full body-frame occlusion needs no
aircraft-layer change, no `Export.lua` edit, and no Hook redeploy — two new fields on an existing
dataclass and two lines in `from_telemetry_dict`.

That matters because a banking helicopter is exactly when the mask is most wrong: roll 30° left and
the real crew *gains* a downward view to the left. Modelling that is cheap here and would be
expensive if the data were not already present.

## Design

**D1 — Replace the azimuth cone with a body-relative occlusion mask.** Compute the candidate's
direction in the *airframe* frame (heading, pitch, bank applied), then test it against a mask
defined as a maximum depression angle per azimuth band. Keep a hard rear cutoff, matching
`docs/concept/state-transitions.jpg`'s "there is no visibility to rear hemisphere".

**D2 — Mask shape: a small explicit table, linearly interpolated.** Coarse by intent — the user's
direction was "no need to take to canopy beam, that's too much detail". Shape, with the numbers
themselves to be filled at implementation and flagged uncalibrated:

    |relative azimuth|      max depression below horizon
    0-20    (nose)          steep
    20-50                   moderate
    50-80   (abeam-ish)     shallow
    80-100  (abeam)         very shallow / horizon only
    >100    (rear)          blocked entirely

Upward visibility is not modelled: nothing this project cares about is above a helicopter at low
level, and the rotor/roof would make it fiction anyway. State that as a deliberate omission.

**D3 — Mechanism and calibration in separate commits.** This project already has that rule, from
BL-2.6 (`body-layer/CLAUDE.md`: "mechanism and calibration never share a commit"). The mechanism —
body-frame transform, mask lookup, gate wiring — is testable against synthetic geometry with no
reference to real Mi-24P numbers. The angles are a separate, arguable, retunable question. Landing
them together would make the table look load-bearing and the mechanism look uncertain, when it is
the reverse.

**D4 — This composes with, and does not duplicate, the backlogged scan steering.** Two different
constraints that intersect:

- *this plan*: what the airframe permits him to see at all — static, always applies
- *backlog "Scan commands should drive naked-eye perception"*: where he is currently looking within
  that — dynamic, driven by commands

Effective visibility is the intersection. Building either as though it subsumes the other produces
a mess; they must stay separate predicates that compose.

## Open questions for the user

1. **Left/right asymmetry.** The **left** view (`...105`) looks materially more obstructed than the
   right (`...59`). Model the asymmetry, or keep one symmetric mask for now? Symmetric is simpler
   and probably adequate at this coarseness; asymmetric is more faithful and costs only a wider
   table.

   Note what asymmetry would mean downstream, since it is not neutral: `scan_left` and
   `scan_right` would then have genuinely different detection performance, and Petrovich would be
   measurably worse at finding things to his left. That is either welcome realism or a confusing
   crew behaviour depending on taste — worth deciding deliberately rather than inheriting it from
   a table.
2. **Where the angles come from.** Reading them off these screenshots means inferring from an
   unknown camera FOV and is good to maybe ±10-15°. Acceptable for a first mask given D3, but if
   better evidence is wanted cheaply, a few targeted screenshots at known slew angles — or the
   Mi-24P cockpit model's own geometry — would do better. Worth an Investigator pass, or not?
3. **Does the pilot station ever matter?** Screenshots `...135/138/142/152` are the pilot seat.
   Out of scope now (Petrovich is the co-pilot), but if a future wingman/pilot-perspective ever
   lands, the mask becomes per-station rather than global. Design accordingly now, or ignore?

## Effort/value

**Value: high.** This removes a standing no-omniscience violation on the channel that produces most
contact reports, and it is not a corner case — at low level, most ground contacts are below the
horizon, exactly where the current gate is blindest. It also retires the mis-sourced 9K113 constant
properly instead of swapping in another guess.

**Effort: moderate, and the code is the easy half.** The data is already on the wire; the geometry
is one rotation plus a table lookup in a module that is already well-tested and self-contained.
`OwnshipState` gains two fields (defaulted, so existing test fixtures are unaffected).

**The hard part is the numbers, not the mechanism** — which is precisely why D3 splits them. Nobody
should treat the first table as calibrated; it is a documented, coarse, retunable first pass whose
provenance is "read off four screenshots", stated as such.

**Recommendation: worth doing.** But the first table will be approximate, and the honest place to
sharpen it is a sortie plus targeted captures, not more desk work.
