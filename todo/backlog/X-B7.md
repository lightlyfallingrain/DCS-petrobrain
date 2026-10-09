# X-B7 — A real-time ASCII view of what Petrovich is looking at

- [x] **X-B7 — A real-time ASCII view of what Petrovich is looking at, and with what. Built 2026-09-25 (`feature/eyesight-view`) — `--eyesight-view`, plus `--belief-truth-log` below.** #status/done User, 2026-09-25:
  *"it'd help if I could visually see where Petrovich is looking and with what. A realtime ascii
  graphic would do just fine."* Shape, as he described it:
  - **Ownship at bottom centre**, because the rear hemisphere is not visible anyway — so the
    drawing is a forward arc, not a full circle.
  - **A cone or line drawn where he is looking**, coloured by optic: **green = naked eye, blue =
    binocular**.
  - **A one- or two-letter id per contact**: `AA` air defence, `AR` armour, `TR` truck, `G` group,
    `U` unknown.

  **What already exists, so this is not built from nothing** — and checking this first is the
  point of writing it down here:
  - `perception.gaze.gaze_at(t_sim, plan)` is **pure**, so the current gaze is a read, not new
    state. The cones 2C sortie already added an overlay *line* naming the gaze o'clock
    (`logger._push_gaze_line`) for exactly this need — the user's own words then were *"very
    difficult to judge when I don't visually see where Petrovich is looking"*. This item is the
    spatial version of that same complaint.
  - `--detection-trace` ([[BL-9]]) already records, per poll and per candidate, which visibility gate
    decided its fate, at what true range and bearing, plus the optic and the contact it folded
    into. `body-layer/tools/summarize_detection_trace.py` reduces it after a flight. **The data
    this view needs is already being written** — what is missing is a live rendering of it.
  - `perception.optics` carries the optic in use, so green/blue needs no new state either.

  So the likely shape is a reader, not a new subsystem: a terminal view fed from the same per-poll
  state the trace writer already sees. Worth confirming that read before designing anything.

  **Settled by the user, 2026-09-25: this is a debug, testing and calibration tool, and it may show
  ground truth.** His words: *"it's a debug and testing tool. Can break no-omniscience boundary
  because the whole purpose is testing, debugging and calibration."* So it draws what is really
  there alongside what Petrovich believes — that contrast *is* the instrument. A view restricted to
  belief could not answer the question it exists to answer, which is why he could not see something
  he should have.

  **The invariant that still applies, and it is a different one: the view must be read-only and
  one-directional.** No-omniscience constrains what *Petrovich* knows, not what the developer sees
  — but nothing this view reads may flow back into belief. `detection_trace_writer.py` is the
  precedent and the model: it is deliberately allowed to hold ground truth and belief at once, and
  it never calls anything that mutates `ContactStore`, and no ground-truth field it touches is ever
  passed into `ingest`/`Percept`/`Contact`. Build this the same way, and say so in its module
  docstring, because the next reader will otherwise assume the boundary was simply forgotten.

  Worth noting the same tension was already resolved this way once: `--detection-trace` holds both
  and is trusted precisely because the direction of flow is enforced structurally rather than by
  remembering.
