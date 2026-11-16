---
name: reference_none_sentinel_default_for_call_scoped_resource_reuse
description: When a function takes an injectable single-item callable (e.g. ReadTileBytes) as a test seam, and the fix is "reuse an expensive resource across the many items one call touches," switch the default from the bare production function to None, and branch inside the function -- this fixes production without touching any test that already injects its own callable.
metadata:
  type: reference
---

Used on `raster-chart-viewer` (RC-1 performance-review fix, 2026-11-16) for
`cache.compose_view_tile`'s and `warmup.WarmupScheduler`'s `read_bytes: ReadTileBytes` parameter.
The bug: `discovery.read_tile_bytes` opened a fresh `zipfile.ZipFile` per entry even when one call's
own loop touched many entries from the same zip (measured 4.1x slower than reuse). The naive fix --
restructure the call site's loop to pre-group entries by zip and batch-read them -- would have
required splitting `compose_view_tile`'s single-pass loop into two passes, because whether an entry
even needs reading depends on a cache check made mid-loop (`cache.get_small_mip(...)`
is-None-or-not), not knowable up front without duplicating that check.

**The actually-used fix is much smaller**: add a *stateful, call-scoped* reader
(`discovery.BatchZipReader`, a `ReadTileBytes`-shaped class with a `dict[Path, ZipFile]` cache,
used as `with batch_tile_reader() as reader: ...`) that transparently reuses handles across
however many times it's called, in whatever order the existing loop already calls it. Then change
the function's own default: `read_bytes: ReadTileBytes | None = None` instead of
`read_bytes: ReadTileBytes = discovery.read_tile_bytes`, and branch at the top: if a caller passed
something, use it exactly as given, unwrapped; if not, open a fresh `batch_tile_reader()` scoped to
this one call/pass and use that instead. No change to the loop body at all.

**Why this is the pattern worth remembering**: every existing test in the suite already injected
its own fake `read_bytes=reader` (a `_CountingReader` test double that never opens a real zip, used
to count entry-level opens) -- none of them relied on the *default value's identity*, only on
`read_bytes=` being honored when passed. So switching the default from a real function to `None`
changed *zero* existing test behavior, while fixing every real caller (`server.py`, `__main__.py`)
that never passes `read_bytes` at all. Confirmed deliberately: ran the full existing suite
unmodified after the change, all green, then added new tests (real on-disk zip, no `read_bytes`
override, `zipfile.ZipFile` construction count via `monkeypatch.setattr(module.zipfile, "ZipFile",
counting_wrapper)`) to prove the production default path specifically.

**How to apply**: whenever a function's "fix" is "make the production default smarter/cheaper" and
every test already injects an explicit override of that same parameter, check whether the fix can
live entirely in a `None`-sentinel branch rather than touching the parameter's literal default
value or the function body the tests exercise. This avoids the "do not modify existing tests
without permission" tension entirely, because there is nothing to modify -- and it's a strong sign
the fix is correctly scoped to "production's default behavior," not "this function's whole
contract."

See also [[feedback_reopen_zipfile_per_entry_within_one_call]] (performance-reviewer's memory on
the underlying defect this fixes) and [[feedback_reproduce_thread_safety_claims_dont_just_read_them]]
(reviewer's memory on the thread-safety fix this reader must not reopen -- a call-scoped `ZipFile`
cache is safe specifically because each instance is discarded at the end of its one call/thread,
never shared across threads or held open across requests).
