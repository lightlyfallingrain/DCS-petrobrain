---
name: feedback_probe_script_robustness
description: Technique confirmed useful after a real probe-script crash — brute-force offset scoring + overflow-safe math instead of trusting one hand-derived byte offset
metadata:
  type: feedback
---

When a probe script's correctness depends on a byte offset derived by hand
(counting header fields, walking a sentinel, etc.), don't trust the derived
offset directly in a WSL/Windows round-trip probe — verify it programmatically
instead. This surfaced as a real bug: `probe_syria_terrain_files_deep.sh`'s
first version derived the `.routes` float64-triple data-start offset by hand
(class name + 6×int32 + 8-byte sentinel + 2×int32 = byte 99), which turned out
to be wrong and crashed the probe with `OverflowError` deep in a distance
calculation on garbage-decoded floats. See
[[project_m5_roadnet_format_decode]].

**Why:** Windows/WSL probe round-trips are expensive (a human has to run the
script on a separate machine and sync output back) — a script that crashes
loses the whole session's wall-clock cost, and the failure mode (uncaught
exception deep in arithmetic) gives no diagnostic signal about *why* the
offset was wrong.

**How to apply:** When a probe needs to locate a variable-position data
region:
1. Don't hand-derive a single trusted offset. Brute-force-score a small
   window of candidate offsets (e.g. the plausible container-header size
   range) by a cheap correctness heuristic specific to the data — for
   coordinate arrays, "decodes to values inside the known coordinate
   envelope" + "consecutive points are smoothly connected" worked well and
   is reusable for any DCS-coordinate polyline/point-array probe.
2. Make all downstream math (distance calculations, range checks) explicitly
   overflow/non-finite-safe (`math.isfinite`, try/except around `**`), so a
   wrong-offset candidate degrades to a low score instead of crashing the
   whole script.
3. Test the probe script locally against synthetic fixture files (correct
   shape + `os.urandom` garbage) before syncing it out for a real
   Windows/WSL run — catches exactly this class of bug for free, no DCS
   access needed.
