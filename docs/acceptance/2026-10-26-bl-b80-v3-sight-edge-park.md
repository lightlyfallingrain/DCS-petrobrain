# Acceptance card — BL-B80 v3 Stage 6, ASP-17 sight edge-park

Published card: https://claude.ai/artifact/H4Q7cCrVqEh2G8sj75L6Su

**Branch to fly: `main`** — this merges right after DoD, so check out `main` after the merge lands
(ask if unsure it has). `git checkout main` from the repo root.

**Setup:** air start, straight and level, player in the pilot seat, Petrovich in the CPG seat.
Same convention as every other 9K113 test on this project (operating-altitude-envelope memory:
50–800 m AGL normal).

## What changed

The pilot's own sortie feedback (2026-10-26 §2): the real DCS mark moved inside the HUD while the
debug view showed Petrovich's simulated sight pointing well off to the side. Root cause: the real
sight's closed loop was validity-gated against the sight's **gimbal** limits (±60°/+20°/−15°), not
the much narrower ASP-17 readable window (≈±4.3° azimuth) — so the loop ran unsaturated far outside
where the mark can actually be read. Fix: the real sight is now **always** closed-loop, steering
toward the simulated direction radially projected onto the inset ASP-17 field whenever the
simulated sight is outside it — continuously, not a one-shot park.

## 1. Setup — before DCS launches (Windows box)

Turn on the per-frame slew trace, which is what Step 4 below reads. **This flag is checked once
when `Export.lua` loads, so it must exist before you start the mission** (touching it after DCS is
already running has no effect for that session).

Create an empty file (any content is fine) at:

```
Saved Games\DCS\Scripts\aircraft_layer_slew_debug.flag
```

This is a different flag from the general debug log (`aircraft_layer_debug.flag`) — it is
per-frame, every frame OBSERV is on, so it is opt-in separately. Output lands at:

```
Saved Games\DCS\Logs\aircraft_layer_slew_trace.log
```

Then run the collector as usual (`aircraft-layer/WORKFLOW.md`, "Run the collector") and the body
crew session as usual, e.g. (Mac, pointed at the Windows box):

```zsh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python -m body \
  --aircraft-layer-url http://<windows-box-ip>:7791 \
  --audio-adapter-url http://127.0.0.1:7795 \
  --theatre <YourTheatre> \
  --world-model-db ../world-model/data/<your-region>.sqlite
```

**UNVERIFIED (needs Windows + a live DCS session) — these are the exact commands per the committed
`WORKFLOW.md`/`RUN.md`, but nobody has run this specific stage's build live yet.**

## 2. Symptom gone — the mark parks at the HUD edge, not off to the side

**Do:** call a target well off boresight — 3+ o'clock, same as the pilot's own original
observation — with Petrovich's sight engaged (OBSERV on), target outside the ASP-17 field.

**Expect:** the real ASP-17 cross hair parks near the HUD edge, on the line toward the target, and
stays there — not drifting to an arbitrary position and not pegging at the gimbal's own ±60°
mechanical stop.

**Record:** does the cross hair visibly sit on the bearing line toward the called target, at the
edge of the HUD, every time you try a different o'clock position?

## 3. Continuous edge slide, not a one-shot park

**Do:** with the target still outside the field, slowly change which direction you've called (or
let Petrovich's own search sweep move the simulated sight) so the simulated direction sweeps along
outside the field — e.g. 2 o'clock to 4 o'clock.

**Expect:** the real cross hair slides smoothly along the HUD edge, tracking the sweep, rather than
jumping to one spot and sticking.

**Record:** does the cross hair's edge position visibly move as the called direction changes, or
does it latch at one point and ignore further changes?

## 4. Inside the field, the cross stays on target

**Do:** call a target that is within the ASP-17 field (near boresight, or bring an off-field target
back toward boresight).

**Expect:** the cross hair tracks the simulated sight direction closely and smoothly, same as
before this fix — this stage should not have changed in-field behaviour.

**Record:** any new jitter, lag, or stall near the field boundary as the target crosses in/out?

## 5. The elevation measurement — this is the prize block

`ASP17_FIELD_EL_HALF_DEG` and the margin are both **guesses** right now (the azimuth half-angle,
4.3°, was measured; elevation was not). The user's own decision, verbatim: *"Elevation - measure in
flight."* This is what Step 1's flag/log exists for.

**Do:** with Petrovich's sight tracking a fixed-world-direction target (so it holds steady in body
frame only while the aircraft doesn't move), **pitch the nose up, then down**, through a few
degrees each way, while watching the HUD. Because the simulated sight holds the target's *world*
direction, pitching changes the *body-frame* elevation the real sight is asked to reach — driving
it toward, and past, the elevation field edge in each direction.

**Expect:** the cross hair climbs/descends with the pitch until it reaches an edge, then stops
there (clipped) rather than continuing to the gimbal's mechanical stop.

**Record, from `aircraft_layer_slew_trace.log` after the flight** (bring the file back): each
logged frame now carries raw `mark_el_raw` (the real 555 reading) and `mark_clipped`. Find the
frames where `mark_clipped` flips to `true` while pitching up, and again while pitching down — the
`mark_el_raw` value at each of those transitions is the real elevation clip edge on that side.
Two numbers wanted: the up-side edge and the down-side edge (expect them to be roughly symmetric
around 0°, but do not assume it).

## What this card cannot test

- Whether DCS's own intermittent-obedience quirk (suppressed by dither in probe testing, never
  fully explained) resurfaces during ordinary flight outside the field — nothing can see it there.
- Whether the margin (0.5°, also a guess) is right — too tight and you may see `homing`/`closed`
  mode flicker right at the boundary; too loose and the cross hair parks visibly short of the true
  edge. Flag either if you notice it, but this card does not have a pass/fail number for it yet —
  that is Step 5's job to establish first.

## Bring back

- Did the cross hair park at the HUD edge toward the called target (Step 2), or still wander?
- Did it slide continuously along the edge as the called direction swept (Step 3)?
- The two raw `mark_el_raw` clip-edge values from the slew-trace log (Step 5) — the actual prize.
- Any mode flicker (`homing` ↔ `closed`) right at the field boundary.
- **Anything that surprised you is worth more than anything on this list.**
