### Definition of Done — BL-B99 (`--pov-view`), `feature/pov-view`

**Scoped to tip `4dad8d9dfb046c8c55c6d1da04d5d8950a47a782`.** Verdict below is a statement about
this exact commit, not about the branch — if it has moved since, re-run.

#### Code Quality

- [x] **Diff-detected subprojects, each run from inside the subproject**: `git diff --name-only
  e9fb4a2b..HEAD` touches only `body-layer/*` (code/tests/CLAUDE.md), two `.claude/agent-memory/`
  files, and `plans/pov-view/*` — no other subproject's source changed. From `body-layer/`:
  - `ruff format --check src tests` — 176 files already formatted. PASS
  - `ruff check src tests` — all checks passed. PASS
  - `cd body-layer && mypy src` — no issues, 76 source files. PASS
  - `pytest tests -q` — **2621 passed, 4 xfailed** — matches the Reviewer's re-review numbers
    exactly (ran against the same tip). PASS
  - `tools/generate_defaults.py` — reports `config/defaults.toml` already up to date; byte-diff
    against a pre-run copy is empty. PASS
  - `-m body --help` lists `--pov-view` with its full help text, matches `CLAUDE.md`'s
    documented description word for word. PASS
- [x] No unhandled errors/panics in data paths — `pov_view.py`/`ascii_canvas.py` are pure render
  functions with no I/O; Reviewer confirmed no `ContactStore` mutation and read-only posture.
- [x] No debug output or leftover TODOs introduced by this feature — Reviewer's full read covered
  this; re-confirmed by my own `mypy`/`ruff`/test run against the same tip finding nothing new.

#### Scope & Correctness

- [x] Implementation matches `plans/pov-view/plan.md`, including the two post-plan amendments
  (main-loop vertical-scale override, user's bg-tint amendment) and both rounds of review fixes —
  all recorded in the plan/implementation docs and verified by the Reviewer's re-review at this
  same tip, not just claimed.
- [x] No unplanned scope added silently — the one plan deviation (`half_angle_deg` keyword) is
  documented in `plan.md`'s own "Deviations" section with its reason.
- [x] No CLAUDE.md invariants violated — the no-omniscience boundary exemption is the same one
  `eyesight_view.py` already documents and the roadmap entry restates for this tool; `--pov-view`
  is additive/off-by-default per the "New CLI flags are additive" invariant.
- [x] All new files staged — confirmed via `git status --porcelain` at this tip (clean; see below).

#### Testing

- [x] Core logic covered: geometry (`elevation_deg`, including the directly-overhead degenerate
  case), per-optic boresight resolution, draw order (believed > ground truth > eye-line/grid),
  player-bubble filtering on both ground-truth and believed sides, glyph pinning (both review
  rounds added mutation-resistant tests after the first round shipped with an unpinned glyph).
- [x] Tests are meaningful, not decorative — Required Fix 1 in `review.md` was caught *by*
  mutation-testing an existing assertion and finding it didn't pin the real character; the fix
  commit's new tests close that gap and the re-review repeated the mutation method rather than
  taking the new tests on faith.
- [x] No existing tests broken — `test_eyesight_view.py` passes unchanged (confirmed by both
  Reviewer passes and this run); full suite count only grew.

#### Documentation

- [x] Reviewer findings addressed: both Required Fixes (shared ·/× glyphs; persistent
  border/gridlines with eyes drawn as `‖` not the gridline's own `|`) are resolved and re-verified
  independently by the re-reviewer (not just re-read) — raw ANSI dumped, draw order checked by
  direct construction (ground truth placed exactly on an eye-edge azimuth), `set_bg` composition
  verified cell-by-cell. Verdict: APPROVED.
- [x] Non-obvious behaviour documented: `body-layer/CLAUDE.md` gained module-map entries for
  `ascii_canvas.py`/`eyesight_view.py`/`pov_view.py` and a flag-docs paragraph for both views;
  `pov_view.py`'s own module docstring carries the ground-truth exemption disclosure.

#### Security

**Performance and security passes are waived by the user for this feature** (2026-10-25: *"For
BL-B99, skip perf and sec as this is debug tool only."*). No `security-plan-review.md` or
`security-review.md` exists for `plans/pov-view/`, and none is expected — `review.md`'s re-review
section records the waiver explicitly ("Performance and security passes are waived by the user for
BL-B99 (debug tool only), per the dispatch instructions — not run").

**Scope of the waiver, stated per this role's instruction**: it covers this debug tool only —
`pov_view.py`, `ascii_canvas.py`, and the `--pov-view` flag's wiring in `body.py`. It has **no
lapse condition beyond the tool staying debug-only and off by default**. If `--pov-view` (or
`ascii_canvas`'s `set_bg`/tint mechanism) is ever reused by non-debug, player-facing code, or the
flag's default changes to on, the waiver no longer covers that use and a normal security/
performance pass is owed for it.

**Executing the unblock condition** (this role's standing instruction after the 2026-10-17 retro
finding): the waiver names its own clearing condition — "debug tool only, off by default" — not a
future action to run, so there is nothing to execute here. The thing that *is* checked mechanically
is that the flag really is off by default and additive: confirmed above via `--help` (no behaviour
changes when `--pov-view` is omitted — the existing full suite, which runs `body.py` without the
flag throughout, passed unchanged) and via the Reviewer's own confirmation that `eyesight_view.py`
never calls the new `set_bg` layer.

#### Overall DoD Verdict: **PASS**

---

### Acceptance boundary — what the fixtures structurally cannot reach

This is a debug/calibration instrument, not belief-affecting code, so the risk profile is
different from most features this gate sees — but the honest line still has to be drawn, the same
way the F10-vocabulary worked example in this role's own brief does:

- **Every test above runs against synthetic fixtures and direct function calls.** Nothing here has
  touched a live `SightHead`, a real `Gaze`, or actual DCS telemetry. The per-optic boresight table
  (gaze for unaided/binocular, `SightHead.world_az_true_deg`/`world_el_deg` for the two sight
  optics) is *correct against the code it reads*, proven by dedicated tests — whether those fields
  themselves carry sensible values during an actual sortie is a question this gate cannot answer.
- **The horizon-relative elevation choice is explicitly "revisit if it reads wrong in flight"** —
  the roadmap entry's own words. No fixture can tell whether a ground target visually holding its
  row while banking *feels* right to a pilot; that is exactly the kind of thing only flying it
  answers (acceptance card test 8).
- **Colour legibility in a real cockpit terminal is unverifiable from here.** The bg-tint
  mechanism was verified by dumping raw ANSI escape codes and confirming composition is correct —
  that proves the *mechanism* works, not that the three tints (blue/gray/brown) are visually
  distinguishable against whatever terminal and lighting the user actually reads this on.
- **No live DCS session exists in this worktree or the one any review ran in.** `--help` and the
  full offline test suite are the only things that can run here; the acceptance card marks the run
  commands themselves `UNVERIFIED` for exactly this reason.

#### Live acceptance — deferred, not waived

Unlike performance/security, **live acceptance of this feature is not waived** — it is outstanding,
pending a sortie. BL-B99's own roadmap entry carries `#status/in-progress`; it should move to
`#status/done #needs-flight` once merged, and the `#needs-flight` tag stays until a real flight
clears the acceptance card's eight test cases (published:
https://claude.ai/artifact/NVKCE77Z2sNqgHQS29B3aL), naming which sortie cleared it.

**Do not block this merge on that sortie** — the user has already authorised merging once DoD
passes, consistent with this project's standing rule that live verification happens in bursts and
must not gate the work.

### Milestone question — does this change BL-B89 or anything else downstream?

`feature/9k113-scan-procedure` (BL-B89, unmerged, tip `406c1ce6`) touches `gaze.py`/
`optic_policy.py`/`body.py` — the same three files this plan's own Risks section flagged as a
dependency this plan reads from but does not own.

**Dry-run check** (`git merge-tree feature/pov-view feature/9k113-scan-procedure`, run at this
worktree's checkout): one textual conflict, in `body-layer/ROADMAP/body-layer-backlog.md` (both
branches have touched the backlog file — a trivial doc conflict, not a code one).
`body-layer/src/body.py` and `body-layer/tests/test_body.py` **auto-merge cleanly**, no conflict.

**This does not clear the plan's own flagged risk** — a textual auto-merge says nothing about
whether BL-B89 changes *what* `Gaze.center_elevation_deg`/`OpticState.look_elevation_deg` mean, or
whether `runner.optic` still only reads as a sight optic when `sight_head.mode == "free"` (the
guarantee `_render_pov_frame`'s boresight table depends on). Per the plan's own Risks section:
**when BL-B89 merges, re-check `_render_pov_frame`'s boresight-resolution table against whatever
`gaze.py`/`optic_policy.py` actually land as** — this is a semantic check, not something a merge
conflict would have caught either way.

No other milestone or subproject is touched by this diff (confirmed above: only `body-layer/*`,
two agent-memory files, and `plans/pov-view/*`).

### Knowledge harvest

Checked `.claude/agent-memory/implementer/feedback_ascii_canvas_additive_bg_layer.md` and
`feedback_plan_prose_vs_code_reality.md`, and `.claude/agent-memory/reviewer/
feedback_glyph_strings_unpinned_and_unextracted.md` — all three already committed on this branch,
by the Implementer/Reviewer themselves, nothing further to add from this pass. `memory-search.py`
turned up no prior DoD memory on this class of issue (debug-tool waivers, additive-CLI-flag
pattern) — not a recurring category yet, so no new pattern memory is warranted.

No candidate for `notes/` found beyond what the two existing agent-memory files and
`body-layer/CLAUDE.md`'s own module-map entries already capture — the glyph-pinning lesson and the
additive-bg-layer mechanism are both implementer/reviewer-specific technique, not general project
knowledge, and both are already recorded where a future agent touching this code would look
(agent-memory, searched by role) rather than in a `notes/` topic file a human would browse.

### Reviewer confidence

Full read, both rounds — re-review explicitly re-verified mechanisms rather than re-reading claims
(raw ANSI dump, direct construction of the eye-edge/ground-truth draw-order case). No spot-check
flagged.
