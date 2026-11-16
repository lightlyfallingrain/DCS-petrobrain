### Review Summary

Reviewed Stages 1-6 of `raster-chart-viewer/` (MI-B4) against `plans/raster-chart-viewer/plan.md`,
`plans/raster-chart-viewer/implementation.md`, and the research note. Branch
`feature/raster-chart-viewer`, tip `5899295af83b3f8e18c457e0c5785949d4dd662b` (fast-forwarded into
this worktree from `origin/main`).

**Scope match to the plan is good.** All four implementer-declared deviations (the added
`GET /terrains/<t>/tiers/<tier>` endpoint, the unified discovery routine, the shared
small-mip-population helper, and the power-of-two-square logical canvas) are reasonable, each
narrows rather than widens scope, and each is documented honestly in `implementation.md` including
the one risk not fully closed (the edge-tile sidestep, left for Stage 7's manual check). No
scope drift beyond what was declared.

**Mosaic math checked by hand and against real data — correct.** `mosaic.py`'s `_sheet_row_index`
reproduces the research note's `ab=+1, aa=0, xab=-1, xac=-2` convention exactly (verified by
tracing the function against each of those four codes), and `MosaicGrid`'s column/row assembly
(`sheet_col = level - min_level`, `sheet_row = max_row_index - row_index`, `col = sheet_col*8 + z`,
`row = sheet_row*8 + x`) matches the plan's `pixel_x/y_global` formula exactly, modulo the
pixel->tile unit scaling. `test_syria_32m_sheet_mosaic_convention` genuinely pins this: it checks
every (sheet, level) combination against its expected (row, col), not just one axis in isolation,
and a second test independently pins the within-sheet x=row/z=column convention. Ran the server
in-process (no network, see "Live spot-check" below) against the real, installed DCS copy
read-only: all 5 terrains discovered with tile counts matching the research note exactly
(Afghanistan 3072, Kola 2240, Mariana 1557 across 4 tiers including the 62-tile "unscaled" tier,
Syria 1280, Caucasus 4351 across 5 tiers), and decoded real Syria/Mariana tiles have varied,
non-blank pixel content.

**The k/mip mapping is correct for every terrain actually discovered**, including non-power-of-two
grids (Afghanistan 48x64 -> `max_level=6`, confirmed live). There is one latent, currently-dead
edge case noted under Optional Refinements.

**DDS mip byte-offset arithmetic is correct**: `mip_byte_size`/`mip_byte_offset` match the research
note's measured 1,398,128+128=1,398,256 total exactly, and `test_decode_mip_matches_independent_
downsample` checks decoded mips against a genuinely independent (plain box-average, not Pillow
`resize`) reference, not a self-confirming comparison.

**Cache rules (composed-tile JPEG + small-mip-only ingredients, `SMALL_MIP_MIN=3`, 1GB shared cap,
oldest-mtime eviction) are implemented as specified and well tested** for the single-threaded case
— `test_cache.py`'s zip-open-counting tests precisely exercise the plan's own acceptance wording,
including the subtlety the implementer's own log flags (the small-mip population helper being
called from *every* inflate branch, not only the small-mip-triggered one).

**Thread safety is where this review found a real, reproducible defect — see Required Fix 1.**
`discovery.read_tile_bytes` opens a fresh `zipfile.ZipFile` per call rather than holding one open
across requests, which correctly avoids the specific hazard the task flagged (a shared `ZipFile`
object is not safe across threads) — that part of the design is sound. But `TileCache` itself has
no locking around its shared `_total_bytes` counter or its `_enforce_cap` eviction sweep, and
`ThreadingHTTPServer` plus the background `warmup.WarmupScheduler` thread write into the same
`TileCache` concurrently by construction. This is not a theoretical concern: a direct stress test
against `TileCache` (no HTTP involved) reliably crashes within a couple of hundred concurrent
writes under a modest cache cap.

Request-path safety (static file traversal, and the terrain/tier/level/x/y regex groups in the API
routes) was checked and is sound — see "Request-path safety" below.

### Required Fixes

1. **`TileCache` is not safe under concurrent writers, and this is reliably reproducible, not
   hypothetical.** `_write` does `self._total_bytes += len(data) - existing_size` with no lock, and
   `_enforce_cap` calls `sorted(..., key=lambda f: f.stat().st_mtime)` over a live directory listing
   with no lock either. Two threads evicting concurrently can have one thread's `unlink()` remove a
   file that the other thread's `sorted()` is still calling `.stat()` on for sort-key purposes —
   that call site has no `try/except`, unlike the deletion loop below it, which does.

   Reproduced directly against `TileCache` (not a contrived race — ordinary concurrent
   `put_composed_tile` calls under a cap small enough to force eviction):

   ```
   FileNotFoundError: [Errno 2] No such file or directory: '.../T/32m/0/2_1.jpg'
     File ".../cache.py", line 173, in _enforce_cap
       files = sorted(
       File ".../cache.py", line 175, in <lambda>
         key=lambda f: f.stat().st_mtime,
   ```
   31 of 3200 writes failed this way, consistently across 3 repeated runs, with 32 threads and a
   20000-byte cap forcing constant eviction.

   This is squarely in the concurrency pattern the service is built for: `ThreadingHTTPServer`
   serves one thread per connection, OpenSeadragon issues several parallel tile requests while
   panning, and `warmup.WarmupScheduler` runs a background thread writing into the same cache the
   whole time. The exception is unhandled all the way up through `compose_view_tile` into
   `server.py`'s `_handle_tile`, which has no `try/except` around it — `BaseHTTPRequestHandler`'s
   default handling logs a traceback and drops the connection rather than returning a clean error,
   so this surfaces to a real viewer as an intermittently broken/stalled tile, worse the closer the
   cache sits to its cap (i.e., the longer a session runs — the opposite of "works until you stop
   looking").

   Separately, even without a crash, the unguarded `self._total_bytes += ...` is a classic
   lost-update race under concurrent writes (not reliably reproduced in isolation here, likely
   because the critical section is too short for the GIL to preempt without an intervening I/O
   call, but nothing prevents it) — left unaddressed, the tracked total can drift from the real
   on-disk size over a long-running session, silently defeating the stated 1GB cap.

   **Fix:** serialize `TileCache`'s mutating operations (`_write`, `_enforce_cap`, and the
   `_total_bytes` read-modify-write) behind one `threading.Lock`. This also incidentally closes a
   second, smaller hazard: two threads calling `_write` on the *same* path concurrently (realistic
   whenever two viewers, or a viewer and the warm-up, request the same view tile at the same time)
   each call `Path.write_bytes`, which opens in truncate mode — interleaved truncate+write from two
   threads on the same path can leave a short-read/corrupt file on disk even without any exception.
   A single lock around the write removes this too. Add a regression test that exercises concurrent
   `put_composed_tile`/`put_small_mip` calls under a small cap and asserts no exception and that the
   tracked total matches the actual on-disk size afterward — the existing `test_cache.py` has no
   concurrency test at all, which is how this got through.

### Optional Refinements

- **`MAX_MIP_LEVEL` clamp and `block` can disagree if a future terrain's grid ever needs `k > 10`**
  (optional — currently dead code for every discovered terrain, `k` tops out at 6 for Afghanistan,
  the largest grid). In `compose_view_tile`, `mip = min(k, MAX_MIP_LEVEL)` clamps the *mip* used for
  decoding, but `block = 2**k` and `slot_size = TILE_SIZE_PX // block` are computed from the
  unclamped `k`. If `k` ever exceeded 10, `slot_size` would shrink past the clamped mip's actual
  pixel size (or hit integer-division-to-zero at `k=11`), silently mis-placing or zero-sizing pasted
  sub-images rather than degrading to "blurriest mip available" as the comment at `MAX_MIP_LEVEL`'s
  definition promises. Worth either clamping `block`/`slot_size` from the same `mip` value, or
  dropping the comment's "degrades gracefully" claim if the clamp is only meant to prevent an
  index-out-of-range and isn't actually exercised end-to-end. Not a blocker: no terrain on any
  installed copy comes close to needing this, and it's explicitly flagged in the source as a
  defensive cap that "never actually binds."
- **`cache.py`'s path-building helpers (`_composed_tile_path`/`_small_mip_path`) don't themselves
  guard against a `terrain`/`tier_label` value that escapes the cache directory** (e.g. `".."`).
  Not currently reachable — `server.py` always validates `terrain`/`tier` against the
  already-discovered `TerrainIndex`/`MosaicGrid` dictionaries before ever calling
  `compose_view_tile`, so an attacker-controlled string never reaches these functions through the
  HTTP layer today. Still, `TileCache` is a public class with no such guarantee documented on its
  own API, so a future caller that skips the HTTP layer's validation (another CLI tool, a test
  helper reused carelessly) would not be protected. A one-line assertion or sanitization in
  `TileCache` itself would make the safety property local to the class that needs it, rather than
  relying on every caller to have validated first.
- **`TileCache.get_small_mip` opens images via `Image.open(path)` without a `with` block** — works
  correctly today (Pillow lazily loads and `.convert("RGBA")` forces the read), but leaves the
  underlying file handle to be closed by GC rather than deterministically, which is a long-running-
  process smell on a server that serves many requests per hour. Cosmetic; not required.

### Request-path safety (checked, no issue found)

- **Static file serving** (`server.py`'s `_serve_static`) resolves the candidate path and checks
  `candidate.relative_to(resolved_static_dir)`, which is robust against both forward-slash `../`
  traversal and (on the Windows deployment target, where this server actually runs) backslash-based
  traversal, since the guard is based on where `Path.resolve()` ends up, not on pattern-matching the
  request string. Verified directly: `GET /../pyproject.toml` -> 403/404
  (`test_static_path_traversal_rejected`), and traced the Windows-backslash case by hand since no
  Windows machine is available here — `pathlib.WindowsPath` treats backslash as a separator the same
  way `.resolve()` would collapse it, so the same `relative_to` check still catches it.
- **The `/tile/...` and `/terrains/.../tiers/...` routes** only ever reach `cache`/`mosaic` code
  with `terrain`/`tier` values pulled from the already-discovered, closed sets (`terrains.get(...)`,
  `index.tiles_for_label(...)`, `grids.get(...)`), each gated by a 404 before use — not with the raw
  regex-captured string. `level`/`vx`/`vy` are regex-constrained to `\d+` and converted via `int()`
  before any filesystem use. No path-traversal vector through the API routes.

### Checks run

From inside `raster-chart-viewer/` (created the venv per the task instructions — one did not exist
in this worktree):

- `ruff format --check src tests`: pass (19 files already formatted)
- `ruff check src tests`: pass
- `cd raster-chart-viewer && .venv/bin/mypy src` (strict): pass, 9 source files, no issues
- `pytest tests -q`: pass, 50/50

### Live spot-check against the real, installed DCS copy (read-only; no network tooling available
in this environment, so exercised in-process rather than over HTTP)

Ran `discovery.discover_terrains` / `mosaic.MosaicGrid` / `cache.compose_view_tile` directly against
`/mnt/f/Games/DCS World` (read-only; confirmed no write ever touches the install) with a scratch
cache dir under `/tmp`, deleted afterward (`rm -r`, confirmed gone):

- All 5 terrains discovered: Afghanistan, Caucasus, Kola, MarianaIslands, Syria.
- Tile counts per tier matched the research note exactly, including Caucasus's 5-tier zip-per-sheet
  layout (16m: 1412, 32m: 2406, 64m: 237, 128m: 193, 256m: 103 = 4351) and MarianaIslands' "unscaled"
  tier (62 tiles, confirming U2 live).
- Syria 32m grid: 32x32 tiles, `max_level=5`; decoded a real full-res tile, pixel extrema
  `(1, 255)` — genuine varied content, not blank.
- Fetched the most-zoomed-out overview tile for all 4 Mariana tiers (the slow, all-entries-at-once
  case warm-up exists to hide); all returned varied, non-blank 1024x1024 JPEGs.

This confirms the decode pipeline and mosaic placement work end-to-end against real data for the
terrains sampled. It does **not** confirm the OpenSeadragon pan/zoom rendering itself (no browser in
this environment) or the sheet-mosaic convention on any terrain other than Syria (U3, explicitly
deferred to Stage 7 per the plan) — both remain the user's own Stage 7 acceptance step.

### Verdict

CHANGES REQUIRED

One required fix (`TileCache` thread safety), demonstrated and reproducible, localized to
`cache.py`. Everything else reviewed — scope, mosaic math, DDS offsets, cache rules in the
single-threaded case, request-path safety, module independence (no cross-subproject imports, own
venv), vendoring/licensing, and the live data check — is sound. Once Required Fix 1 lands with a
concurrency regression test, this should pass Reviewer on a second pass without needing another
full read; the rest of this review does not need to be redone.

### Review Confidence

Full read of all `src/` modules, all tests, both plan documents, the research note, and
`raster-chart-viewer/CLAUDE.md`. Ran the full check suite and the full test suite from a freshly
created venv. Did not run the actual OpenSeadragon viewer in a browser (none available in this
environment) or the Windows-side Stage 7 live check — those remain the user's own acceptance step,
as the plan itself states. Thread-safety finding is based on direct reproduction against `cache.py`
in isolation (not inferred from reading alone) and against real DCS data in-process (not over HTTP,
since outbound network tool calls were not available in this environment).

## Re-review (fix 1 + port)

Re-reviewed commit `e7fbebc7..a80611ed` (`a80611ed4598c50df6a971e1be88d508b90fd23b`,
"raster-chart-viewer: TileCache thread safety + port 7801 (reviewer + port fix)") against Required
Fix 1 above and the port correction. Worktree started at `origin/main` (`f72ae5b3`), a strict
ancestor of the named tip, tree clean; fast-forwarded with `git merge --ff-only a80611ed...`.

### 1. Does the lock cover every shared mutation and every read that depends on it?

Yes. `TileCache.__init__` now creates `self._lock = threading.Lock()` before the first
`_enforce_cap_locked()` call (held explicitly via `with self._lock:`, not through `_write`). Every
public method that touches `_total_bytes` or inspects the cache directory now acquires the lock
before doing so: `get_composed_tile`, `has_small_mip`, `get_small_mip` (reads); `_write` (the sole
writer, used by both `put_composed_tile` and `put_small_mip`) and `_enforce_cap_locked` (mutators).
`_measure_total()` in `__init__` runs before any other thread can hold a reference to this
`TileCache` instance, so it does not need the lock. No method that touches `_total_bytes` or the
cache directory is left unlocked.

### 2. Can anything deadlock? (`Lock` is non-reentrant, `_enforce_cap_locked` split added)

No reentrant-acquire path exists. `_enforce_cap_locked` is documented as "assumes `self._lock` is
already held" and never acquires the lock itself; its two call sites (`__init__`, inside the `with
self._lock:` block, and `_write`, which calls it from inside its own `with self._lock:` block) both
already hold it, and neither calls back into any locking public method. `_write`'s own docstring
states the non-reentrancy constraint explicitly for future callers. `WarmupScheduler` holds its own
separate lock (`warmup.py`) only around its `_started` set, released before it ever calls into
`TileCache`/`read_and_populate_small_mips`, so there is no cross-lock-ordering hazard between the
two classes either. Traced every call site; found none that nests.

### 3. Does eviction tolerate a file that vanishes before it is stat'ed or unlinked?

Yes, and the mechanism now does two independent things correctly. First, because `_enforce_cap_locked`
holds `self._lock` for its entire sweep, no other thread going through this `TileCache` can unlink a
file out from under it anymore — the original race is closed by construction, not just papered
over. Second, the remaining `try/except OSError` around both the `.stat()` (new) and `.unlink()`
(pre-existing) calls is retained for causes the lock cannot rule out (e.g. something external to
this process touching the cache directory), and the stat-before-sort restructuring means a file
that fails its stat is simply skipped (`continue`) rather than only being caught at `unlink()` time
as before — closing the specific gap the original review named (the `sorted(..., key=lambda f:
f.stat()...)` call site had no `try/except` at all pre-fix).

### 4. Is the new concurrency test meaningful? Independently re-verified, not just read.

Re-ran the mutation the implementer describes, myself, rather than trusting the commit message:
checked out the pre-fix `cache.py` (`git show e7fbebc7:...cache.py`) into the working tree in place
of the fixed version, and ran `test_concurrent_writes_under_a_forcing_cap_never_raise_and_respect_cap`
three times. All three runs failed with `errors == []` false — 31 extra items, first one
`FileNotFoundError(2, 'No such file or directory')` — matching the implementer's claimed repro
exactly (31/3200 writes, same exception). Restored the fixed `cache.py` (diffed byte-for-byte
against the committed version to confirm the restore was exact and `git status` was clean
afterward) and re-ran the same test five times: five clean passes. This is a real regression test,
not a decorative one — it fails for the stated reason against the code it is meant to guard, and
passes against the fix.

### 5. Does holding the lock during PNG decode in `get_small_mip` matter for responsiveness?

Correctness-wise, no — the lock must be held across `Image.open(path).convert("RGBA")` because
`Image.open` is lazy; forcing the read with anything less than `.convert()` (or an explicit
`.load()`) while the lock is held would reopen the same vanish-mid-read hazard Required Fix 1
closed for the directory-sweep case. So the scope is not overcautious; it's the minimum needed for
safety given Pillow's lazy-open semantics.

Throughput-wise, this is a real, not hypothetical, narrowing versus pre-fix: before this commit,
concurrent small-mip decodes across different request threads (and the warm-up thread) could at
least partially overlap, since CPython's C-level image codecs can release the GIL during decode;
now every decode serializes behind one process-wide lock, and `compose_view_tile`'s block loop can
call `get_small_mip` up to `block * block` times in a single request (up to 4096 for the largest
measured grid, Afghanistan). **Not a required fix** — these are ≤128px PNGs (`SMALL_MIP_MIN = 3`),
decode is on the order of sub-millisecond to low-single-digit milliseconds each, this is a
single-user LAN hobby tool with no Petrovich dependency (`raster-chart-viewer/CLAUDE.md`: "No
Petrovich behaviour depends on this"), and the composed-tile cache means a repeat of the same view
tile skips this path entirely. Worth knowing if a future session profiles a laggy pan under
concurrent OpenSeadragon tile requests: narrowing to copy raw bytes under the lock and decode/
convert outside it would restore the pre-fix overlap without reopening the hazard, since the bytes
would already be safely in memory before the lock is released. Recorded as optional, not a
blocker, and not worth a change without an actual complaint from the Stage 7 live check.

### 6. Port 7800 -> 7801

Confirmed every operative mention changed and nothing else collides. Grepped the bare numbers
`7800` and `7801` repo-wide (not just `DEFAULT_PORT`, per the architect memory file's own lesson
about Piper hiding in a bare URL string):

- **`7801` appears only inside `raster-chart-viewer/`** (`server.py`'s `DEFAULT_PORT`, `README.md`
  x3, `CLAUDE.md`) plus this feature's own plan/memory documentation — no collision anywhere else
  in the repo.
- **Every remaining `7800` inside `raster-chart-viewer/` is a deliberately-preserved historical
  record, not a live reference**: `plans/raster-chart-viewer/plan.md`'s "Port and firewall"
  section keeps the original (wrong) reasoning and firewall-rule example verbatim, with an explicit
  "Correction, 2026-11-16" paragraph directly underneath — exactly the "supersession is marked, not
  deleted" convention (`docs/PROCESS.md`), and the commit message says this was intentional.
  `plans/raster-chart-viewer/implementation.md`'s one `7800` mention is inline-annotated
  "(corrected to 7801 2026-11-16 — see `plan.md`'s...)" at the point of mention. Neither is
  something a user or a future session would read to find the *current* port.
- **One pre-existing document was not touched and is mildly stale**: `docs/handoff/
  2026-11-16-raster-chart-viewer-windows-build.md`, written before Stages 1-6 existed ("Status:
  Planned and approved. Nothing implemented yet."), lists "Port 7800" under "Decided — do not
  reopen." This predates the port collision being found and predates this fix commit entirely (it
  was not in this commit's diff, and not in the prior review's scope either). Not a required fix:
  it is a dated, point-in-time handoff memo describing the state of a decision at the time it was
  written, in the same spirit as the deliberately-preserved plan.md correction — not a document
  anyone would consult today to learn the server's current port (README.md and CLAUDE.md are).
  Flagging it only so it isn't mistaken for an operative reference later.
- All other `7800`/`7801` hits in the repo are unrelated: audio-adapter's own Piper port (the thing
  this fix moved away from) and aircraft-layer's own port family, neither touched by or relevant to
  this change.

### Checks run (from inside `raster-chart-viewer/`, fresh venv created per task instructions)

- `ruff format --check src tests`: pass (19 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (strict, run with cwd inside the subproject): pass, 9 source files, no issues
- `pytest tests -q`: pass, 51/51 (50 from the original review plus the one new concurrency test)

### Verdict

**APPROVED**

Required Fix 1 is correctly and minimally implemented: the lock covers every shared mutation and
every state-dependent read, no reentrant-acquire path exists, the stat-before-sort restructuring
closes the exact race the original review traced to the line number, and the new regression test
is independently confirmed red against the pre-fix code and green against the fix (not merely read
and trusted). The port correction is complete and consistent across every operative file; the
remaining `7800` mentions are deliberately-preserved historical corrections, not live references,
with one pre-existing, out-of-scope handoff document flagged as mildly stale but not misleading
enough to require touching now. One optional refinement noted (lock scope during `get_small_mip`'s
PNG decode) — not a blocker, and explicitly not worth acting on without a real complaint from the
Stage 7 live check.

### Review Confidence

Full read of the fix commit's diff (`cache.py`, `server.py`, `README.md`, `CLAUDE.md`,
`test_cache.py`, both plan documents, the architect memory file). Ran the full check suite
(format/lint/mypy strict/pytest) from a freshly created venv — 51/51 passing. The concurrency claim
was independently re-verified by mutation, not re-read: swapped in the pre-fix `cache.py`, confirmed
the new test fails for the stated reason (31/3200, `FileNotFoundError`) across 3 runs, restored the
fixed version byte-for-byte, and confirmed 5/5 clean passes. The port change was verified by
grepping the bare number repo-wide, not just `DEFAULT_PORT`. Did not re-run the Stage 7 Windows live
check or exercise the OpenSeadragon viewer in a browser — unchanged from the original review, and
still the user's own acceptance step, untouched by this commit.
