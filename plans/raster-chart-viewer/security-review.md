## Security Deep Analysis: raster-chart-viewer (RC-1, batch: Stages 1-6 plus the reviewer's thread-safety fix)

Branch `feature/raster-chart-viewer`, merged `--ff-only` into this worktree at tip
`a80611ed4598c50df6a971e1be88d508b90fd23b`. Scope is all new files under `raster-chart-viewer/`
plus `plans/raster-chart-viewer/` and the two docs the merge also carried. Read the full diff
(`git diff cf5d8f7f..a80611ed`), every `src/` module, `static/index.html`, and both prior review
documents before testing anything.

**Threat model** (root `CLAUDE.md`/user direction, 2026-10-21): single-user, LAN-only hobby tool.
Realistic attackers are (1) malicious code in a dependency and (2) an infected LAN machine probing
an open port. No Petrovich/brain involvement at all (plan's own statement, confirmed by reading —
nothing under `raster-chart-viewer/` imports from or is imported by any other subproject), so LLM
prompt injection is not applicable to this feature.

### Dependency Status

One dependency, `pillow` (`pyproject.toml`: `pillow>=9.1`, floor-pinned, matching this repo's
existing pattern elsewhere). Installed version in every venv referenced by this batch's own
review/implementation reports is 12.3.0.

Searched for current advisories (`WebSearch`, 2026-11-16): Pillow 12.3.0 is itself the release that
*fixed* a batch of 2026 CVEs (an `ImagingExpand` integer-arithmetic flaw, `CVE-2026-59205`
heap corruption in the `ImageCms` transform API, `CVE-2026-59199`/`CVE-2026-54058` out-of-bounds
reads/writes from near-int32-limit coordinates to `Image.paste`/`crop`/`alpha_composite`/
`tobytes`/`getpixel`, `CVE-2026-54059` a decompression-bomb-check bypass in PCF font loading). One
later issue, `CVE-2026-112892` (unbounded memory expansion in the **MSP** decoder), was reported
after 12.3.0 shipped and is unpatched upstream as of this search. **Not reachable here**: this
service never decodes MSP images, never touches `ImageCms`, and the one place coordinates reach
`Image.paste` (`cache.py`'s `compose_view_tile`) uses `dx`/`dy` from `range(block)` with
`block = 2**k ≤ 2**10` — internally generated, never from request input — so the near-int32-limit
coordinate CVEs are not reachable through this feature's call pattern either. No action needed.

OpenSeadragon, vendored at 4.1.1 (confirmed against the shipped `openseadragon.min.js`'s own
`versionStr:"4.1.1"`), released 2024-04-01. Searched for advisories: none found against this
version or the `openseadragon` npm package generally. BSD-3-Clause `LICENSE.txt` is vendored
alongside it, matching the claim in `raster-chart-viewer/CLAUDE.md`.

No other third-party code. `security-grep`'s dynamic-code-execution category (the one category
where a hit is a finding by default) has zero hits anywhere under `raster-chart-viewer/src`; the
one `eval`-shaped grep hit in this feature's tree is inside the vendored, minified
`openseadragon.min.js` itself — read in context, it is the library's own internal code, not
reachable from this feature's own source.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `cache.py` (whole class, `TileCache`) | Shared mutable state (`_total_bytes`, the cache directory) written from `ThreadingHTTPServer` request threads and the background `WarmupScheduler` thread at once | **Reviewer's Required Fix 1, already landed in this batch's own last commit** (`a80611ed`, "TileCache thread safety + port 7801"). A `threading.Lock` now guards every read/write of `_total_bytes` and every directory-listing/eviction sweep; a regression test (`test_cache.py::test_concurrent_writes_under_a_forcing_cap_never_raise_and_respect_cap`, 32 threads, a cap small enough to force constant eviction) passes. Confirmed by reading the fix and running the full suite (below), not by re-deriving the reviewer's own reproduction. | None — closed. |
| `server.py:178-217` `_handle_tile`; `cache.py:176-186` `TileCache._write` | `level`/`vx`/`vy` parsed from the URL (`_TILE_RE`'s `\d+` groups) via bare `int(...)`, with no bound on digit count or resulting magnitude, before any `try`/`except` | **New finding (Finding 1 below) — reproduced, not merely read.** Low-risk, not a blocker; filed as `[[RC-B1]]`. | Recommended, not required: clamp magnitude/digit-length before `int()`, return `400`. See Finding 1. |
| `cache.py:100-114` `_composed_tile_path`/`_small_mip_path` | No sanitisation of `terrain`/`tier_label` against path-escaping values (`".."`) inside `TileCache` itself | **Pre-existing, already flagged by Reviewer as an Optional Refinement** (`plans/raster-chart-viewer/review.md`, "Optional Refinements"). Confirmed still accurate after this batch's fix commit: `server.py`'s `_handle_tile`/`_handle_tiers`/`_handle_tier_info` all resolve `terrain`/`tier` against the already-discovered `terrains`/`grids` dicts (closed sets) and return `404` before ever calling into `cache`/`mosaic` code, so no attacker-controlled string reaches these path builders through the HTTP layer today. Not this feature's finding to re-litigate (pre-existing, not widened by the batch's own fix commit, which touched locking only). | None required; still worth a defensive assertion inside `TileCache` itself per Reviewer's note, at the user's discretion. |
| `server.py:219-236` `_serve_static` | Static file serving resolves the candidate path and checks `candidate.relative_to(resolved_static_dir)` | Checked directly: `GET /../pyproject.toml` → 403 (`test_static_path_traversal_rejected`, passing). Robust against `/`- and (by `pathlib.WindowsPath` semantics, traced by hand — no Windows box here) `\`-based traversal alike, since the guard is based on where `.resolve()` lands, not on pattern-matching the request string. | None. |
| `server.py` (whole file) | No `do_POST`/body-reading code anywhere | This server only ever defines `do_GET`; `BaseHTTPRequestHandler`'s default handles any other verb with `501`. "Unbounded request body" (the audio-adapter/aircraft-layer shape this project has been bitten by before) is not applicable — there is no body-reading code to have a missing bound on. | None — not applicable. |
| `discovery.py:82-89` `read_tile_bytes` | `zipfile.ZipFile(...).read(entry_name)` with no size cap on the inflated output | Zip bombs are explicitly named in this task's threat model, but the entries here come from the **local, user-installed DCS files**, not from anything a LAN peer can influence through this service (no upload/write endpoint exists anywhere). Relevant only if the DCS install itself were already compromised, which is a much larger compromise than this feature introduces or can defend against. Informational, not a finding against this feature. | None. |
| `server.py:60` `DEFAULT_HOST = "0.0.0.0"`; `ThreadingHTTPServer`, no connection cap, no auth on any endpoint | Unauthenticated, LAN-wide bind; unbounded thread-per-connection | Matches `aircraft-layer`'s own `TelemetryAPIServer` posture exactly (same host default, same server class, already the accepted project pattern for every other LAN service here) and the explicit, user-approved threat model for this whole project (single-user, LAN-only, no auth layer exists anywhere in this repo). Not a new risk this feature introduces. | None — inherited, accepted pattern. |

### Finding 1 — Unbounded `level`/`vx`/`vy` digit length reaches an uncaught exception (filed `[[RC-B1]]`)

**Reproduced directly**, not inferred from reading:

- A `vx` value of 5000 `'9'` digits matches `_TILE_RE`'s `\d+` group fine, but
  `int(match.group("vx"))` raises `ValueError: Exceeds the limit (4300 digits) for integer string
  conversion` — confirmed interactively against this exact regex and Python 3.12 (this machine;
  the service targets 3.11+, same `sys.int_info.default_max_str_digits` default of 4300 since the
  CVE-2020-10735 fix landed in both). This is CPython's own guard, so it is not a CPU-exhaustion
  vector — it is simply an unhandled exception at a request boundary.
- A `vx` of 300 `'9'` digits (comfortably under that 4300-digit ceiling, so `int()` succeeds)
  produces the composed-tile cache filename `"999...9_0.jpg"` (306 characters). Writing that file
  with `Path.write_bytes` raises `OSError: [Errno 36] File name too long` — reproduced directly
  against a real temp directory on this machine. The same limit applies on the Windows/NTFS
  deployment target (255 UTF-16 code units per path component), so this is not a POSIX-only
  artifact of the test environment.

Neither `_handle_tile` nor `TileCache._write` wraps the relevant call in `try`/`except`, so both
exceptions propagate out of `do_GET` uncaught. Traced what happens next rather than assumed:
`http.server.ThreadingHTTPServer` (via `socketserver.ThreadingMixIn.process_request_thread`)
catches `Exception` at the top of each request's own thread and calls `handle_error` (a traceback
to stderr) — **this does not crash the server or disturb any other connection**, it drops only the
one request, which the client sees as an empty/reset response rather than a clean `4xx`.

**Why this is a real, if low-severity, finding under this project's threat model**: it is reachable
by any LAN peer with zero prerequisites — the `int()` call happens before `_handle_tile` ever
checks whether `terrain`/`tier` are known — and "send an open port a long or odd numeric path
segment" is exactly the kind of low-effort probing the stated "infected machine scanning the LAN"
attacker does. **Why it does not block this batch**: the practical effect is bounded to a dropped
single connection plus one logged traceback per attempt — no crash of the service, no data
returned to the attacker, no corrupted cache state (the exception happens before anything is
partially written), nothing persists. Risk matrix:

**Finding:** `level`/`vx`/`vy` path segments have no bound on digit count or magnitude before
reaching `int()` and, downstream, a cache filename — an unusual-but-reachable request produces an
uncaught `ValueError`/`OSError` instead of a clean `4xx`.
**Location:** `raster-chart-viewer/src/raster_chart_viewer/server.py:181-183` (`_handle_tile`'s
`int(...)` calls), `raster-chart-viewer/src/raster_chart_viewer/cache.py:176-186` (`TileCache._write`).
**Probability:** medium — trivial to trigger, no special knowledge or valid terrain/tier needed,
and exactly the shape of input a port-scanning/fuzzing LAN peer tries without even targeting this
service specifically.
**Impact:** low — one dropped connection and one stderr traceback per attempt; the service, the
cache, and every other concurrent connection are unaffected. No RCE, no information disclosure to
the client (the traceback goes to the server's own log, never the response), no persistence.
**Recommended action:** reject `level`/`vx`/`vy` above a small sane bound (e.g. `>= 10**9`, or cap
the regex/`int()` input to a short fixed digit count) before conversion, returning `400` instead.
Cheap, narrowly scoped, no design change.

Filed as `[[RC-B1]]` (`raster-chart-viewer/ROADMAP/RC-B1.md`), per this role's closing-step rule —
not fixed in this pass, since it does not block, and not left unfiled.

### Checks run

From `raster-chart-viewer/` (existing `.venv`, reused as left by the prior Implementer/Reviewer
passes — `pillow`/`ruff==0.16.6`/`mypy==2.3.1`/`pytest==9.1.1`):

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `cd raster-chart-viewer && .venv/bin/mypy src` (strict): pass, 9 source files
- `pytest tests -q`: pass, 51 passed (50 + the reviewer's new concurrency regression test)

`.claude/skills/security-grep`'s pattern sweep run repo-wide (not just this feature): the only
hits inside `raster-chart-viewer/src` are three outbound `Content-Length` header-setting lines
(responses the server sends, not an untrusted `Content-Length` it trusts on input — there is no
request-body reading anywhere in this feature) and the handful of `raise`/`assert` lines already
accounted for above (all either startup-time construction errors or internal invariants, none
reachable from a crafted HTTP request).

### Verdict

**APPROVED.**

The one Required Fix from Reviewer's pass (`TileCache` thread safety) landed in this batch's final
commit, is correctly scoped (one lock around every mutating/reading operation on shared state),
and is backed by a real concurrency regression test that fails without the fix and passes with it
— confirmed by reading the diff and running the suite, not taken on the implementation report's
word alone. This agent's own pass found one further issue (`[[RC-B1]]`, above), reproduced
directly; it is low-risk by the project's own threat model (LAN-only, single-user, no auth
anywhere) and does not block — filed to the backlog rather than fixed in-line, per the user's
"low-risk finding → surface and let the user decide" rule. Everything else checked against this
feature's threat model (path traversal, dependency CVEs, dynamic code execution, hardcoded
secrets, unbounded request bodies, zip-bomb exposure, auth posture) is either sound or an
already-accepted, inherited project pattern.

### Required Fixes

None.
