---
name: reference-macos-mmap-rss-metric
description: on macOS, "maximum resident set size" is the wrong metric for mmap-based readers; use "peak memory footprint" instead
metadata:
  type: reference
---

When profiling memory for a large `mmap`-based file reader on Darwin (e.g.
`/usr/bin/time -l` or `resource.getrusage(RUSAGE_SELF).ru_maxrss`), the
reported "maximum resident set size" counts every page of the mmap'd file the
OS has ever brought into the process's resident set as a sequential scan
touches it — clean, file-backed, trivially reclaimable pages, not heap. For a
sequential full-file walk this number climbs toward the file's own size
regardless of how little the program's own working set actually grows, and
looks identical to a genuine memory blowup.

**The metric that actually answers "did this program's own memory use scale
with input size" is `/usr/bin/time -l`'s separate "peak memory footprint"
line** — macOS's actual-heap/dirty-memory accounting, excluding reclaimable
clean file-backed pages.

Confirmed during M5 Stage 5: `roadnet.routes.iter_routes` walking the full
2.25 GB `Syria.routes` showed "maximum resident set size" ≈ 2.18 GB (≈ whole
file) but "peak memory footprint" ≈ 22.5 MB — the latter is what actually
confirmed the module's "never loads the file into memory" streaming claim.
Report both numbers with the mechanism explained if this ever needs to go in
a research note or review — reporting only RSS looks like a false-alarm
blowup; reporting only footprint without explaining the RSS gap looks like
cherry-picking.

Relevant to any future `mmap`-based reader profiling (M6 ridge/valley
extraction, M7 full-theatre work) — see
[[feedback-verify-rebuild-row-counts]] for the sibling Stage 5 finding about
verifying rebuild output directly rather than trusting summary text.
