# BL-B106 async speech — live acceptance (source of the test card)

Merged to `main` as `820f8b34`, 2026-11-12. Branch to fly: **`main`**. Restart body-layer after
pulling; audio-adapter and the collector are unchanged. No new flags.

Not testable here: the F8 multi-second readback delay itself (synthesis and queue dwell are
unchanged; needs the `join_voice_latency.py` timeline).

1. **Prize — eyes keep working while he talks.** Long line playing (`report contacts`, or a
   multi-line callout) with `--eyesight-view`/`--pov-view` up: the view keeps redrawing at 1 Hz,
   gaze keeps stepping, a `set target` slew starts without waiting. Record: any freeze, how long;
   did a slew start mid-line.
2. **`stop talking`** mid-line, once with a second line queued: silence within ~1 s, no readback,
   queued line dropped. Record: seconds to silence; anything leaked.
3. **One mouth.** Two commands back to back: readbacks in order, never overlapping; routine callout
   waits, urgent still interrupts. Record: overlap, reordering, missing.
4. **Mission restart** mid-callout: line stops, nothing from the old mission spoken into the new.
   Record: any stale line; first line heard.
5. **audio-adapter down** (optional, ground): body-layer keeps ticking; exactly one
   `audio adapter disconnected` warning, one `audio adapter connected` on return, speech resumes.
   Record: disconnected-line count; did speech resume by itself.

Card: see the artifact link in the roadmap entry `body-layer/ROADMAP/BL-B106.md`.
