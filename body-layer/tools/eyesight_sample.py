"""Renders one illustrative sample frame of the real-time ASCII eyesight
view (`eyesight_view.py`) from hand-built fixture data -- no DCS, no
aircraft layer, no recorded trace file needed at all.

Not a test -- a dev/pilot acceptance aid, mirroring `speak_samples.py`'s
own posture ("for a human ear," here "for a human eye"): it exists so the
frame's actual *look* can be judged directly, which is the one thing
`tests/test_eyesight_view.py`'s assertions cannot do.

The fixture below is deliberately built to exercise every feature this
view has at once: a naked-eye free-scan gaze cone, a believed truck sitting
inside the cone (drawn on top of it), a believed air-defence contact off to
one side, a believed group formation, a ground-truth object the naked-eye
gate never admitted (a "why did he not see that" case, drawn dim/`x`), and
one contact beyond the configured radius (rim marker plus legend entry).

Usage (same interpreter/PYTHONPATH requirements as `speak_samples.py`, run
from `body-layer/`):

    python tools/eyesight_sample.py
"""

from __future__ import annotations

from eyesight_view import BeliefMarker, GroundTruthMarker, render_frame
from perception.cockpit_mask import COCKPIT_MASKS, STATION_CO_PILOT
from perception.gaze import FOCUS_CONE_HALF_WIDTH_DEG, Gaze


def build_sample_frame(*, color: bool = True) -> str:
    # Free-scan currently holding 11 o'clock (-60 deg), the same shape
    # perception.gaze._gaze_for_clock_hour produces -- built directly
    # rather than importing that private helper.
    gaze = Gaze(
        center_azimuth_deg=-60.0,
        half_width_deg=FOCUS_CONE_HALF_WIDTH_DEG,
        label="11_oclock",
    )

    ground_truth = [
        # Admitted -- the truck the naked-eye gate let through, currently
        # sitting inside the gaze cone.
        GroundTruthMarker(bearing_deg=-30.0, range_m=1800.0, visible=True),
        # Not admitted -- real, but the gate rejected it this poll (e.g.
        # terrain LOS or range/size); the "why did he not see that" case.
        GroundTruthMarker(bearing_deg=45.0, range_m=3200.0, visible=False),
    ]
    believed = [
        BeliefMarker(label="TR", bearing_deg=-30.0, range_m=1800.0),
        BeliefMarker(label="AA", bearing_deg=60.0, range_m=2600.0),
        BeliefMarker(label="G", bearing_deg=5.0, range_m=900.0),
        # Beyond the default 5km radius -- must appear at the canvas rim
        # and in the trailing legend, never silently dropped (the S-300
        # tracking-radar-mast case from the orchestrator brief).
        BeliefMarker(label="AA", bearing_deg=20.0, range_m=8890.0),
    ]

    rear_cutoff_deg = COCKPIT_MASKS[STATION_CO_PILOT].rear_cutoff_deg
    return render_frame(
        gaze=gaze,
        optic_name="unaided",
        rear_cutoff_deg=rear_cutoff_deg,
        ground_truth=ground_truth,
        believed=believed,
        color=color,
    )


if __name__ == "__main__":
    print(build_sample_frame())
