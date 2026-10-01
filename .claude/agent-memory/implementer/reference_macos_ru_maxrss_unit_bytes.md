---
name: reference-macos-ru-maxrss-unit-bytes
description: resource.getrusage(...).ru_maxrss is bytes on macOS, KB on Linux -- divide accordingly or peak-RSS numbers are off by 1024x
metadata:
  type: reference
---

`resource.getrusage(resource.RUSAGE_SELF).ru_maxrss` returns **bytes** on Darwin/macOS but
**kibibytes** on Linux -- the stdlib docs don't call this out, and it is easy to write
`ru_maxrss / 1024` assuming the Linux convention and get numbers that are quietly 1024x too
large when run on a Mac (e.g. reporting "1,352,672 MB" instead of ~1.3 GB).

Caught live while measuring `ingest_terrain`'s streaming-insert fix (`feature/landform-geomorphons`,
`plans/landform-geomorphons/performance.md`'s blocking memory finding): the first measurement script
divided by 1024 once and printed peak-RSS values ~1000x too large before the unit mismatch was
spotted and `/ 1024 / 1024` (bytes -> MB) was substituted.

**Always divide by `1024 * 1024` for MB on macOS** (this project's dev machine, per
`project_compute_topology.md`), not `/ 1024`. If a script needs to be portable to Linux too, branch
on `platform.system()` or just always compute in bytes and label the unit explicitly in the printed
column header, rather than assuming.

Distinct from [[reference-macos-mmap-rss-metric]] (which is about `ru_maxrss` *over-reporting* real
usage for `mmap`-based sequential file reads, a different pitfall) -- this one is a pure unit-scaling
bug that applies even when `ru_maxrss` is measuring real heap growth correctly (e.g. a Python list
genuinely accumulating objects, not an mmap'd file scan).
