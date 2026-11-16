# Definition of Done: raster-chart-viewer (RC-1, Stages 1-6)

**Verdict: PASSED**

**Scoped to tip `91e2296c4236164633624121b0d587e4bac92b0a`** on `feature/raster-chart-viewer`
(fast-forwarded into this worktree from a HEAD — `22d9fb45` — that was a strict ancestor of this
tip; tree clean before and after the fast-forward). This verdict describes that one commit. If
the branch moves again before merge, re-run this check.

The feature's own commits in this batch (excluding the two `main`-merge commits that carried in
unrelated BL-16/BR-2 docs):

```
91e2296c Reviewer: approve raster-chart-viewer RC-1 performance-review fixes
6a653545 implementer memory: None-sentinel default for call-scoped resource reuse
32df4b38 raster-chart-viewer: fix the two NOW performance findings (RC-1)
58b5389d RC-1 performance review: raster-chart-viewer Stages 1-6 + thread-safety fix
679b47d4 raster-chart-viewer: security deep analysis (RC-1 batch, Stages 1-6 + reviewer fix) — APPROVED
83645d7c raster-chart-viewer handoff note: port corrected to 7801
ef98643f Reviewer: raster-chart-viewer fix-1 + port re-review -- APPROVED
a80611ed raster-chart-viewer: TileCache thread safety + port 7801 (reviewer + port fix)
e7fbebc7 Reviewer: raster-chart-viewer Stages 1-6 (MI-B4) -- CHANGES REQUIRED
d22756d8 raster-chart-viewer: own ROADMAP/ (RC- prefix); MI-B4 moves to RC-1
5899295a raster-chart-viewer: implementation decision log + agent memory
77c93f84 raster-chart-viewer: README with Stage 7 live-check run instructions
8b31eecf raster-chart-viewer stage 6: background warm-up per (terrain, tier)
98a6c186 raster-chart-viewer stage 5: viewer page + vendored OpenSeadragon 4.1.1
e0d3a6ec raster-chart-viewer: add GET /terrains/<t>/tiers/<tier> grid metadata
bbe9a4ba raster-chart-viewer stage 4: HTTP server (ThreadingHTTPServer) + CLI
1d0597a3 raster-chart-viewer stage 3: tile composition + the amended cache
3d8cd47b raster-chart-viewer: discovery.py tests (single-zip + Caucasus layouts)
b7287c3c raster-chart-viewer stages 1-2: discovery/mosaic/tilename + DDS mip decode
4fead4ac raster-chart-viewer: plan wording matches amended cache; Windows build handoff
caa68abb raster-chart-viewer plan: U1-U3 answered, cache amended
3019f1ab Architect plan: raster chart viewer (MI-B4)
05a738fe raster-chart-viewer: all-terrains RasterCharts recon; MI-B4 corrected
41e420ff MI-B4: in progress on feature/raster-chart-viewer, all-terrains scope
```

## Acceptance boundary — stated up front

**What this feature's fixtures structurally cannot reach:**

1. **The sheet-mosaic convention (U3)** was measured and edge-matched against **Syria only**. The
   same formula is applied to Afghanistan, Kola, Mariana Islands and Caucasus's structurally
   different zip-per-sheet layout, but no fixture or synthetic test can tell "parses without
   raising" apart from "renders as a continuous map, not a scrambled one" — only a human eye on a
   real zoomed-in/zoomed-out view can. This is exactly why Stage 7 exists, not a gap in testing.
2. **OpenSeadragon's real pan/zoom rendering has never executed in a browser**, in any role's pass
   on this feature, including this one. The power-of-two-canvas edge-tile sidestep
   (`implementation.md`, "Notable Discoveries") was reasoned through and verified at the HTTP/decode
   level against real DCS data, but never watched render — if the sidestep doesn't fully hold, a
   residual edge-tile visual glitch would only show up on a real screen.
3. **Windows-side behaviour** (the venv/Pillow install, the firewall rule, native-Windows-I/O warm-up
   timing on the largest grids) has only been reasoned about and partially probed over the WSL
   bridge — never run on the actual Windows DCS machine.

None of these three gates this merge, per root `CLAUDE.md`'s "Workflow" (live acceptance does not
gate a merge) — they are exactly Stage 7's job, tagged `#needs-flight` on `[[RC-1]]`, with an
acceptance card published (below) for when the user next has Windows-box time.

## Checks run (this session, from inside `raster-chart-viewer/`)

`.venv` did not exist in this worktree; created it and installed the pinned tool versions from
`raster-chart-viewer/CLAUDE.md`.

| Check | Result |
|---|---|
| `ruff format --check src tests` | PASS — 19 files already formatted |
| `ruff check src tests` | PASS — 0 errors |
| `cd raster-chart-viewer && .venv/bin/mypy src` (strict) | PASS — 9 source files, no issues |
| `pytest tests -q` | PASS — 55 passed |
| `/dod-check` mechanical script | 1 FAIL (see "Code quality scan" below — judged a false positive) |

**Run-command verification** (per this role's own "run every command" rule): started a real
server instance from `src/` with `--dcs-install <fake path> --port <os-assigned> --host
127.0.0.1 --cache-dir <scratch>` — it bound the port and logged "listening on
127.0.0.1:<port>" exactly as `README.md` describes, confirming the module invocation, the
required `--dcs-install` flag, the default port (7801), and the "stand in `src/`" instruction are
all correct, not merely plausible by reading. A live HTTP round-trip against a real server is
already exercised by `test_server.py`'s own real-server `urllib` check (part of the 55 passing
tests); a separate shell `curl`/`urllib` spot-check from this session was blocked by the
sandbox's network-tool permission classifier (consistent with a prior DoD memory,
`feedback_curl_blocked_in_worktree_sandbox.md` — not a defect in the feature).

### No DCS-derived binary data committed

```sh
git ls-files raster-chart-viewer | grep -iE '\.(jpg|jpeg|png|dds|tif|zip)$'
```

returns only the vendored OpenSeadragon UI icon PNGs under `static/openseadragon/images/` — no
chart imagery, no DDS, no zip, nothing decoded from a real DCS install, anywhere in the tree.

### Module independence

No import from any other subproject in any `src/` module (checked by hand, every `import`/`from`
line across all 9 source files): stdlib (`zipfile`, `http.server`, `pathlib`, `threading`,
`argparse`, `logging`, `json`, `re`, `math`, `io`) plus `PIL` only. Nothing else in the repo
imports from `raster-chart-viewer/`.

## Code quality scan

No TODO/FIXME/debug-print/bare-except found anywhere in `src/`. The mechanical `/dod-check`
script's "error suppression" check flagged one line:

```
raster-chart-viewer/src/raster_chart_viewer/warmup.py:112: except Exception:
```

**Read in context and judged not a defect.** This is `WarmupScheduler._warm_up`'s per-entry loop:
a documented, deliberate catch-log-continue so one bad zip entry doesn't abort the rest of the
tier or crash the background thread — it calls `logger.exception(...)` (full traceback) before
continuing, never swallows silently. This is the same pattern already in production use at
background-thread boundaries elsewhere in this repo (`body-layer/src/belief/speech_worker.py`,
`crew_console.py`, `body.py`), not a one-off. Not a required fix.

## Scope & correctness

- **Matches `plans/raster-chart-viewer/plan.md`'s Stages 1-6** exactly, per Reviewer's own scope
  check (`review.md`: "Scope match to the plan is good... No scope drift beyond what was
  declared"). The four implementer-declared deviations (the added
  `GET /terrains/<t>/tiers/<tier>` endpoint, the unified single-zip/Caucasus discovery routine, the
  shared small-mip-population helper, the power-of-two-square logical canvas) were each reviewed
  individually, each narrows rather than widens scope, and each is documented in
  `implementation.md`.
- **No invariants violated**: read-only against the DCS install (confirmed directly — no write call
  anywhere touches the install path), module independence preserved, no chart data committed, no
  cross-subproject coupling introduced without justification (this feature introduces none).
- **All new/modified files staged and committed**: `git status --porcelain` was empty immediately
  after the fast-forward merge, before this DoD pass added anything (confirmed below after this
  pass's own additions are staged too).

## Testing

55/55 tests pass. Per Reviewer's and Performance Reviewer's own independent mutation-based
re-verification (not re-derived here, since both already ran it and it would not change by
re-running): the concurrency regression test, the three zip-batching tests, and the low-water-mark
eviction test were each shown to fail for the exact stated reason against a reverted version of
the code they guard, then pass against the fix — genuine regression tests, not decorative ones.
No existing test was broken by either the thread-safety fix or the two performance fixes.

## Documentation

- **Reviewer findings addressed**: all four review sections in `plans/raster-chart-viewer/review.md`
  end `APPROVED` — the original Stages 1-6 pass (CHANGES REQUIRED → Required Fix 1, TileCache
  thread safety), the fix-1-plus-port re-review (APPROVED), and the performance-fix review
  (APPROVED). Every required fix across all passes is landed.
- **Accepted-items ledger** (`.claude/scripts/accepted-items-ledger.sh plans/raster-chart-viewer`):
  the script reported *"decisions U1 U2 U3 not yet answered (no `**Answered` line) — nothing
  accepted to check"* — a **format mismatch**, not an unanswered-decisions problem: the architect
  wrote the answers as `**U1 → (a)**`/`**U2 → ...**`/`**U3 → ...**` under a heading literally titled
  "Decisions Requiring User Input — all answered 2026-11-16", rather than a line starting with the
  literal string `**Answered`, which is the one token the script's regex looks for. The script
  itself says this case "passes" (exit 0) rather than failing, since it can only see what it is
  told to look for. Accounted for by hand instead:
  - **U1** (Windows-side venv with Pillow, launched from WSL bash) — **built**: exactly this shape
    is what `README.md`'s "Stage 7" section documents, and the module/CLI this venv would run was
    verified for real this session (see "Checks run" above).
  - **U2** (Mariana's 62 no-scale-prefix tiles exposed as their own "unscaled" tier) — **built and
    tested**: `test_discovery.py` has a dedicated test for it (`implementation.md`'s own "Tests
    Added" list), and the implementer's real-data smoke run confirmed it live against the actual
    installed Mariana Islands terrain (`implementation.md`, "Notable Discoveries": "MarianaIslands
    (16m/32m/64m/unscaled — U2 confirmed live)"). Reviewer independently reproduced this
    (`review.md`: "MarianaIslands' 'unscaled' tier (62 tiles, confirming U2 live)").
  - **U3** (build every terrain first; ship the ones that render correctly, file a follow-up for any
    that don't) — **explicitly deferred to Stage 7**, by the plan's own design, not an oversight:
    `README.md`'s "What to check" section states this verbatim ("a terrain that renders scrambled is
    a follow-up to file, not a blocker for the rest (U3's own answer)"). This is the live-acceptance
    boundary stated at the top of this report, tagged `#needs-flight`.
- **Security sign-off**: `plans/raster-chart-viewer/security-review.md` is APPROVED. One low-risk
  finding (unbounded `level`/`vx`/`vy` digit length reaching an uncaught exception, bounded impact:
  one dropped connection, no crash, no data exposure) was filed as `[[RC-B1]]` rather than fixed
  in-line, per the security role's own "surface and let the user decide" posture for low-risk
  findings — correctly not a blocker.
- **Non-obvious behaviour explained**: the cache design's two supersessions (the original
  every-mip-cached design, and the stop-exactly-at-cap eviction), the DDS mip-offset formula, the
  OpenSeadragon level/mip mapping, and the power-of-two-canvas sidestep are all explained in module
  docstrings, `CLAUDE.md`, and `implementation.md`'s "Notable Discoveries" — not left to be
  rediscovered.

## Roadmap move consistency

- **`mission-interpreter/ROADMAP/MI-B4.md`** is a closed stub: `#status/done`, body states "Closed
  here by moving it, not by finishing it," names `[[RC-1]]` as the destination, and says the ID is
  retired and must not be reused.
- **`mission-interpreter/ROADMAP/mission-interpreter-roadmap.md`** index line for MI-B4 says "moved
  2026-11-16 to `[[RC-1]]`."
- **`raster-chart-viewer/ROADMAP/RC-1.md`** carries the full entry (moved, not duplicated — the
  moved-here note says so explicitly) under its new ID; no content lost.
- **`raster-chart-viewer/ROADMAP/raster-chart-viewer-roadmap.md`** indexes `[[RC-1]]` and
  `[[RC-B1]]` correctly; prefix/ID-space documented (`RC-`, `RC-B<n>`, `RC-W<n>`).
- **Root `ROADMAP.md`'s status table** already carried a Raster Chart Viewer row before this DoD
  pass; updated by this pass to reflect the DoD-PASSED/merging state and the outstanding Stage 7
  live check, naming `main` as the branch to fly.
- **No ID reuse**: `RC-1` is new in its own sequence; `MI-B4` is retired, not reassigned.
- `.claude/scripts/roadmap-tag-vocabulary-gate.sh` / `roadmap-entry-consistency-gate.sh` were run
  repo-wide; both report pre-existing failures elsewhere in the repo (aircraft-layer research tags,
  body-layer BL-16 double-index, unrelated dangling links) — **none mention `raster-chart-viewer`,
  `RC-1`, `RC-B1` or `MI-B4`**, confirming this pass introduced no new violations.

## Milestone-completion question (root `CLAUDE.md`, "Milestone Completion")

**Does finishing Stages 1-6 change what the next milestone should be, or invalidate an assumption
downstream milestones rely on? No.** This is a standalone crew-reference tool with no Petrovich
dependency and nothing else in the repo imports from it (confirmed above) — nothing downstream was
built on an assumption about it, and nothing about its own next step (Stage 7, a live check, or a
`[[RC-B1]]` follow-up fix) changes any other subproject's roadmap. The only open question this
milestone itself raises — whether the sheet-mosaic convention generalises past Syria — is scoped
entirely to RC-1's own Stage 7 and U3's already-decided fallback (ship the terrains that work, file
a follow-up for the ones that don't).

## Recurring-fix pattern surfaced (process signal, not a code defect in this feature)

Reviewer's Required Fix 1 here (`TileCache` unsafe under concurrent `ThreadingHTTPServer`
request threads plus a background warm-up thread, no lock) is the **fifth-plus** occurrence of the
same category across this repo's agent memory: body-layer's `ContactStore` (poll thread vs. REPL
thread), body-layer's REPL-thread sqlite/`EnrichmentContext` reuse, world-model's HTTP server over
one shared `sqlite3.Connection` (MI-2 — the one case caught by the Implementer itself, before
Reviewer), and an `accept()`-guard race in aircraft-layer-hardening. In every case but MI-2, the
catch landed at Reviewer, via a real stress test rather than a code read — each costing a full
extra review round-trip. Recorded as a DoD-role memory
(`.claude/agent-memory/dod/project_recurring_threadinghttpserver_shared_state_race.md`) with a
recommendation: this is a candidate for a standing checklist item earlier in the sequence
(Architect's plan or Implementer's own self-check — "does this design put two threads against the
same mutable object, and if so, how was that verified") rather than a cost repeatedly paid at
Reviewer.

## Notes harvested

`/notes-harvest raster-chart-viewer` surfaced seven `implementation.md` candidates. Six were
judged either too narrow/single-use (specific to this one OpenSeadragon integration, already
documented in-place in `implementation.md`/`CLAUDE.md`) or purely procedural (no generically
reusable insight). One was added: `notes/testing-and-provenance.md` gained a bullet on
`test_warmup.py`'s original timing defect — waiting on a proxy counter (`open_count == N`) is not
the same as waiting on the real completion signal the test's assertions actually depend on
(`has_all_small_mips`), even though the two usually move together. This generalises beyond this
feature (a distinct mechanism from the file's existing `thread.join()` entry) and was judged worth
keeping for future concurrency-test authors.

## Acceptance testing

**Stage 7 is the user's own live LAN/Windows check and has not been flown.** Per root `CLAUDE.md`'s
"Workflow" and this role's own instructions, live acceptance does not gate this merge.

**Acceptance: PENDING (live).**

- **Card published**: https://claude.ai/artifact/21AkKixYQcXaLDKfnbRSvN (source:
  `docs/acceptance/2026-11-16-raster-chart-viewer-rc1-stage7-sortie.md`). Every setup/run command on
  the card was executed for real this session (against a local fake-data instance, not real DCS
  data — the card says so explicitly) before publishing; the Windows-specific and real-data
  portions are labelled unverified on the card itself.
- **`[[RC-1]]` tagged `#needs-flight`** in `raster-chart-viewer/ROADMAP/RC-1.md`, naming `main` as
  the branch to fly and listing exactly what Stage 7 must verify.
- **Root `ROADMAP.md`'s status table** updated to match.
- This batch's live check and `[[RC-B1]]`'s own fix (if ever picked up) are the two items a single
  future Windows session can clear together — no need for separate trips.
