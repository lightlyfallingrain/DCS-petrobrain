---
name: project_raster_chart_viewer_threadsafety_round2_approved
description: raster-chart-viewer RC-1 fix-1 re-review (TileCache lock) and port 7800->7801 change -- approved; records how the lock fix and the test were independently re-verified, and the one lock-scope tradeoff worth knowing about later.
metadata:
  type: project
---

Re-reviewed `feature/raster-chart-viewer` commit `a80611ed` (`e7fbebc7..a80611ed`) against this
role's own Required Fix 1 from the first pass (`[[feedback_reproduce_thread_safety_claims_dont_just_read_them]]`).
Verdict: APPROVED. Full addendum in `plans/raster-chart-viewer/review.md`, "## Re-review (fix 1 +
port)".

**What held up on a second, independent pass:**
- One `threading.Lock` now covers every `TileCache` method that touches `_total_bytes` or the cache
  directory, including reads (`get_composed_tile`, `has_small_mip`, `get_small_mip`), not only
  writes. The `_enforce_cap_locked()` split (assumes lock already held, never re-acquires) has no
  reentrant-acquire path anywhere, confirmed by tracing every call site rather than trusting the
  docstring's claim.
- **Re-verified the regression test by mutation, not by reading the commit message.** Swapped the
  pre-fix `cache.py` (`git show e7fbebc7:...`) into the working tree, ran the new concurrency test
  3x -- failed all 3 for the exact stated reason (31/3200, `FileNotFoundError`) -- restored the
  fixed file byte-for-byte (diffed against the committed version to confirm the restore was exact),
  ran it 5x clean. This is the same method `[[feedback_reproduce_thread_safety_claims_dont_just_read_them]]`
  used to find the original defect; this entry is the confirmation that *re-verifying someone
  else's fix* needs the same discipline, not just a re-read of the diff.

**One thing worth remembering if this ever needs a performance pass:** the fix holds the lock
across `Image.open(path).convert("RGBA")` in `get_small_mip` -- correct (Pillow's lazy open means
anything less would reopen the vanish-mid-read hazard), but it serializes every small-mip PNG
decode across every thread, where before the fix concurrent decodes could at least partially
overlap under the GIL. `compose_view_tile`'s block loop can call this up to 4096 times in one
request (Afghanistan's grid). Not flagged as a required fix -- these are <=128px images, decode is
cheap, and this service has no Petrovich dependency at all (single-user LAN hobby tool) -- but if a
future pass ever profiles a laggy pan, the fix is to copy bytes under the lock and decode outside
it, not to touch the locking scope on the write side.

**Port 7800->7801 (found by the main loop, not Reviewer): verified by grepping the bare number
repo-wide, not just `DEFAULT_PORT`** -- this is the same lesson the architect's own memory file
(`feedback_grep_default_port_before_assigning_one.md`) recorded about Piper hiding in a bare URL
string, applied here as the *verification* half rather than the *choosing* half. Confirmed every
operative mention (`server.py`, `README.md`, `CLAUDE.md`) was updated and 7801 collides with
nothing else repo-wide. The remaining `7800` mentions in `plan.md`/`implementation.md` are
deliberate historical corrections (`docs/PROCESS.md`'s "supersession is marked, not deleted"), not
live references -- did not ask for those to be rewritten. Found one genuinely stale, out-of-scope
mention (`docs/handoff/2026-11-16-raster-chart-viewer-windows-build.md`, written before any of this
existed) and flagged it as non-blocking rather than silently ignoring it or wrongly escalating it
to a required fix -- it predates the fix commit and was never in either review's scope.
