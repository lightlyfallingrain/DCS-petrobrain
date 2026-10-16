# DoD Gate: emitter-visibility Stage B (AC-B8 + BL-B73)

Run against `feature/emitter-events` @ tip `aafb20a89fb7bbe377d036325bee17c29ee85264`
(Performance's APPROVED-MONITOR commit). **This verdict is scoped to that sha.** Worktree fast-
forwarded cleanly from a stale base (`5015a66`); tree was clean, no divergence.

Full role sequence on this branch: `f02ec43` implement → `031abd3` review NEEDS REVISION →
`1e6c697` fix → `8303d3b` re-review APPROVED → `b8b2212` roadmap correction → `6e61488` security
deep analysis APPROVED → `aafb20a` performance APPROVED-MONITOR.

Stage A's own DoD pass (`plans/emitter-visibility/dod-check.md`) is a separate file for a separate
commit and is not overwritten here.

---

## Code Quality

**Mechanical checks, both touched subprojects, re-run myself at this exact tip** — a fresh
worktree carries no `.venv` (git worktrees don't copy one), so these ran with each subproject's
own `.venv/bin/<tool>` from the main checkout, cwd inside the subproject directory (mypy's
config discovery is CWD-only).

| subproject | ruff format | ruff check | mypy --strict | pytest |
|---|---|---|---|---|
| aircraft-layer | 1 file would reformat (pre-existing, not touched by this branch — see below) | 1 pre-existing EXE001 (same file, not touched) | `Success: no issues found in 23 source files` | `293 passed in 39.99s` |
| body-layer | all 298 files formatted | all checks passed | `Success: no issues found in 60 source files` | `2041 passed, 4 xfailed in 16.05s` |

Both the file/finding counts match the dispatch's expected baseline exactly.

**The two ruff findings are not this branch's.** Both land in `aircraft-layer/research/` —
`2026-10-06-unit-id-join-reduce.py` (format) and `2026-10-05-security-audit.md`'s embedded code
block (also counted by `ruff format`'s file walk — EXE001 is the `.py` file's shebang-not-
executable). Confirmed: `git diff --name-only main...HEAD -- aircraft-layer body-layer` does not
list either path. Pre-existing, out of scope for this gate.

- **No unhandled errors/panics in data paths**: `_handle_datagram` catches `JSONDecodeError`/
  `UnicodeDecodeError`/malformed-envelope/`FiringParseError` and drops-with-debug-log on each,
  never raising into `serve_forever`'s loop. `EmitterTracker.ingest`/`_apply`/`snapshot` have no
  path that can raise on well-typed input (pure dict mutation under the GIL, same posture
  `F10CommandQueue.drain_all` already accepts in this codebase).
- **No debug output left in committed code**: `grep`'d the diff for `print(`/`TODO`/`FIXME`/`XXX`/
  `pdb.set_trace` across every added line in `aircraft-layer/src`, `body-layer/src`,
  `aircraft-layer/dcs-export` — none introduced. The module's `logger.debug`/`logger.info` calls
  are the project's standard logging posture, not leftover debugging.
- **No leftover TODOs introduced by this feature** — same grep, clean.
- **All new/modified files staged**: `git status --porcelain` is empty (see bottom of this report).

## Scope & Correctness

**Implementation matches the plan** (`plans/emitter-visibility/plan.md`, Stage B section and
Co-moving Fields table), checked against the running code, not against `implementation.md`'s
account of itself:

- **Latch** — `FIRING_MIN_VISIBLE_S = 1.5`. `_apply`'s `S_EVENT_SHOOTING_END` branch sets
  `expires_at_sim = max(now, since_sim + FIRING_MIN_VISIBLE_S)`, the single formula the module
  docstring says covers both of the plan's two END rows (same-batch and later-batch). Confirmed
  by reading `firing_receiver.py` directly.
- **Watchdog** — `FIRING_WATCHDOG_S = 180.0`. Set on `S_EVENT_SHOOTING_START`, pruned every
  `ingest()` call against the batch's own `dcs_model_time_s`. The constant's own comment and the
  module docstring now correctly scope it to "unit alive, `END` dropped" only, with destruction
  explicitly handed to `_DEATH_KINDS` — the fix round's required correction, verified APPROVED by
  Reviewer's mutation test (revert to `10.0` → both new tests fail for the stated reason) and
  independently re-confirmed as internally consistent by Security and Performance.
- **Per-kind death semantics** — `_apply`'s `_DEATH_KINDS` branch removes a `FIRING` entry
  immediately but explicitly leaves a (not-yet-reachable) `LAUNCH_SMOKE` entry alone, with a
  comment naming exactly why (`[[BL-B74]]` will start creating those). Matches the plan's
  Co-moving Fields row ("a `LAUNCH_SMOKE` entry is kept — smoke outlives the launcher").
- **Clean slate on `onSimulationStart` and bridge reconnect** — `ingest()` clears `self._active`
  whenever `dcs_model_time_s` regresses past `_RESTART_TOLERANCE_S` (0.5 s), which is what a
  mission restart or bridge reconnect produces; a same-mission jitter of less than half a second
  does not trip it. The Lua Hook's own `onSimulationStart`/`onSimulationStop` handlers
  (`petrobrain-firing-events-hook.lua:296,324`) gate the poll to run only within one mission
  lifetime, so a restart naturally produces exactly the time regression the collector detects.
- **Schema/receiver/endpoint triple** — `schema/firing.py` (`FiringRawEvent`/`FiringEventBatch`/
  `FiringParseError`), `collector/firing_receiver.py` (`FiringEventsReceiver`, loopback-only,
  port 7798 — confirmed distinct from all seven other loopback ports this codebase already uses),
  `GET /firing/latest` in `api/server.py` wired unconditionally in `collector/__main__.py` (no
  opt-in flag — this one is always-on, same posture as the velocity/LOS feeds).
- **`CONTACT_FIRING_SEEN`** — `belief/events.py`/`belief/callouts.py` give it its own
  `_FIRING_THREAT_BAND`/`_FIRING_TARGETS_OWNSHIP_THREAT_BAND`, both strictly below
  `_DEFAULT_THREAT_BAND`, so a `PRESENCE`-only firing contact is no longer buried at the lowest
  priority — the specific design finding (#2 in "Answers to the five design questions") that made
  this stage more than a channel.
- **`visibility.py` is untouched in Stage B**, as the plan states. Confirmed independently by
  Security at the byte level (`git diff` across all three Stage B commits returns empty for that
  file) — not re-derived here, but relied on as a hard check rather than an assumption.

**No unplanned scope added silently.** The only departure from the plan's original text is the
provenance/schema question the fix round itself resolved (Stage A's `Percept.provenance`/
`Contact.is_burning` widening, reviewed and approved in Stage A's own cycle, unrelated to this
stage) — Stage B's three commits touch exactly `firing_receiver.py`, its test file, and the two
plan/implementation docs for the required-fix round, confirmed by `git diff 031abd3..1e6c697`
(Reviewer's own check, re-verified here by `git diff --stat` producing the same file list).

**No CLAUDE.md invariants violated**: no omniscience leak (the channel reports presence only, no
classification path, tier clamp inherited unchanged from Stage A); DCS stays authoritative (the
event stream is the source of truth, body-layer only consumes); provenance/timestamps preserved
(`dcs_model_time_s` + `received_wall_clock_s` on every snapshot); no in-process cross-subproject
import introduced (aircraft-layer and body-layer stay HTTP-coupled — `EMITTER_KIND_FIRING` is a
bare string agreed by convention, not a shared import, exactly as the module's own comment states).

**All new files staged**: confirmed via `git status --porcelain` below.

## Testing

- **Core logic covered**: `test_firing_schema.py` (parse/validate), `test_firing_receiver.py`
  (latch, watchdog, death-removal, mission-restart reset, snapshot shape — 17 tests including the
  two from the fix round), `test_contacts_firing.py`/`test_emitters.py` (body-layer fold-in,
  `targets_ownship` wiring), `test_events.py`/`test_callouts.py` (the new threat-band override).
- **Meaningful, not decorative**: the fix round's two new tests were independently verified by
  mutation (Reviewer reverted `FIRING_WATCHDOG_S` to `10.0` and reran — both failed for the stated
  reason). Not re-run a third time here; Reviewer's own mutation check is a strict superset of
  what a bare pass/fail rerun would additionally tell me for this two-file, one-constant fix, and
  the full suite rerun above (2041 passed) confirms nothing regressed since.
- **No existing tests broken**: full suite green at this tip, exact count match to the expected
  baseline (293 / 2041+4xfail).

## Documentation

- **Reviewer findings addressed**: `review.md`'s one Stage B required fix (`FIRING_WATCHDOG_S`
  conflation) is fixed and APPROVED in `review-2.md`. `review-2.md`'s own Optional Refinement
  (both roadmap entries still stating the conflated framing) is now corrected — `AC-B8.md` already
  carried `b8b2212`'s correction before this gate ran; this gate's own roadmap edits (below) do not
  reintroduce the stale framing.
- **Non-obvious behaviour explained**: the module docstring and per-constant comments in
  `firing_receiver.py` now explicitly separate the two watchdog cases (destruction vs. dropped
  `END`) rather than leaving a reader to re-derive the distinction — the exact shape the fix round
  was asked to produce.

## Security

- `plans/emitter-visibility/security-plan-review.md` — APPROVED (Stage A, not re-litigated).
- `plans/emitter-visibility/security.md` — APPROVED (Stage A deep analysis, all findings resolved).
- `plans/emitter-visibility/security-stage-b.md` — **APPROVED**, one non-blocking low/low finding
  (a literal `;`/`:` in a unit name could corrupt the delimited wire format, fail-closed — dropped
  poll, not misattribution; carried forward as a watch item for `[[BL-B74]]`, not a blocker here).

## Performance

- `plans/emitter-visibility/performance.md` — Stage A's own pass, not re-litigated.
- `plans/emitter-visibility/performance-stage-b.md` — **APPROVED — MONITOR**. Collector-side
  `EmitterTracker` is O(events-in-batch)/O(active-emitters), never O(theatre) or a cross-product;
  body-layer's `resolve_emitters` doubles Stage A's pass count but stays O(N) once per poll; the
  LOS Hook's sort-key splice reads the firing-units table once per call, outside the comparator.
  No required fix.

---

## Acceptance boundary — what these fixtures structurally cannot reach

Every test above is a fixture: synthetic `FiringRawEvent`s, synthetic batches, synthetic
candidate geometry. This is a perception/crew-cognition feature running against a live DCS
scripting bridge, and fixtures cannot settle:

- **Whether `S_EVENT_SHOOTING_START` retriggers mid-burst, or fires once per trigger-pull.** This
  is the single open question the plan's Risks & Unknowns names for this exact stage, and it is
  precisely the kind of question a fixture cannot answer — the fixture *is* the assumption about
  DCS's own event semantics, not a check of it. User direction 2026-10-16 settled the *design*
  response to this uncertainty (`FIRING_WATCHDOG_S = 180.0` is a pure backstop given that bursts
  are paired and short; do not tune it down for "looking long"), but did not fly the sortie that
  confirms the underlying DCS behaviour. The named live check: hold a unit firing continuously at
  the player past 180 s and read the detection trace for either a silent drop while still visibly
  firing, or repeated `START` events within one continuous burst.
- **Whether the production Hook (`petrobrain-firing-events-hook.lua`) actually registers and
  drains against a real DCS process.** The 2026-09-25 probe confirmed `world.addEventHandler`
  registration and one ground-gun `SHOOTING_START` naming the player — but that was the *probe*
  script, and `AC-B5`'s own lesson is that promoting a probe to production is exactly the step
  that must not be skipped nor assumed equivalent. This production Hook has never run against a
  live DCS session.
- **Whether *"taking fire, two o'clock"* / *"something firing, two o'clock, far"* land naturally
  in the cockpit**, including timing relative to other callouts now competing for the same
  (previously near-empty) `CONTACT_FIRING_SEEN` threat band.
- **Whether a firing section's clustering reads as sane prose with several units shooting at
  once** — the plan's own cardinality answer (one `count_bucket` cluster, no new machinery) is
  reasoned, not flown.

A fixture PASS here is not a flight PASS — this is the acceptance-boundary statement the worked
example (the 9K113-sight/F10-vocabulary case) exists to generalise, not a formality repeated for
its own sake.

---

## Roadmap entries

Checked the convention against a comparable entry first (`BL-14.md`, `#status/done #needs-flight`,
"Not yet flown as the combined acceptance sortie covering Stages 5-7 together").

- **`aircraft-layer/ROADMAP/AC-B8.md`** — marked `[x]` **#status/done #needs-flight**. Delivered-
  2026-10-16 note added naming what shipped and the one outstanding sortie, without disturbing
  `b8b2212`'s existing watchdog-framing correction.
- **`body-layer/ROADMAP/BL-B73.md`** — same, `[x]` **#status/done #needs-flight**, naming the
  shared retrigger question plus the cockpit-wording/clustering judgement that is Stage B's own
  (not AC-B8's) to fly.
- **`body-layer/ROADMAP/BL-B74.md` (Stage C, SAM launch) stays `#status/open`, untouched** —
  confirmed by reading the file: `[ ]`, no commits against it on this branch. It is correctly
  **not** closed by this merge.
- This differs from Stage A's own DoD choice (`BL-B72.md`/`AC-B7.md` left fully `#status/open`
  rather than `done #needs-flight`) — that was the right call *there* because those entries'
  prose still read as the full three-emitter item and named unmeasured obligations the Stage A
  dispatch itself had not resolved. `AC-B8`/`BL-B73`'s prose already scopes to exactly what Stage
  B delivers, nothing more, so the `done #needs-flight` convention fits here rather than requiring
  the same full-open posture.

---

## Milestone-completion question

**Does Stage B's completion change what the next milestone should be, or invalidate a downstream
assumption?**

No invalidation, one real reduction in Stage C's remaining cost: `EmitterTracker`'s per-kind
death-semantics branch (`_DEATH_KINDS`) already distinguishes `FIRING` (removed on death) from
every other kind by name rather than by an unconditional delete, specifically so `[[BL-B74]]`'s
`LAUNCH_SMOKE` entries will be *kept* on death without this method needing to be revisited — the
comment in `_apply` says so explicitly. So Stage C's collector-side scaffolding (the one piece of
new per-unit state the plan's Co-moving Fields table calls out as the hard part) is already
partially built, not newly discovered as easier; this was foreseen in the plan, not a surprise
found here.

The open DCS question (retrigger behaviour) does not block Stage C's design: Stage C keys off
`S_EVENT_SHOT`, a different, already-parsed-but-currently-no-op event kind in the same schema, not
off `S_EVENT_SHOOTING_START`/`_END`. Whatever the retrigger sortie finds will refine
`FIRING_WATCHDOG_S`'s justification, not Stage C's mechanism.

---

## What the user has to do

**This stage needs a production Hook deployed on the Windows DCS machine** — `WORKFLOW.md` has no
section for it yet (not written by this feature; the deploy is a manual step following the
existing overlay/F10-commands pattern exactly, documented here rather than left implicit):

1. Copy `aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua` to
   `Saved Games\DCS\Scripts\Hooks\petrobrain-firing-events-hook.lua` on the Windows box. Never edit
   the deployed copy in place.
2. This loads into the GUI Lua state at DCS **application** startup, not per-mission — restart DCS
   itself (not just the mission) after copying.
3. `net.allow_dostring_in = { "scripting" }` in `Saved Games\DCS\Config\autoexec.cfg` must already
   be present — the same opt-in the F10-commands and LOS Hook scripts already require. If it is
   already there for those, nothing further is needed here.
4. **No new collector flag** — `FiringEventsReceiver` is wired unconditionally in
   `collector/__main__.py` (confirmed by reading it: no `if args.something:` gate), so restarting
   the collector process picks this up automatically once the Hook script is deployed.
5. Watch `dcs.log` for a `PetrobrainFiringEvents`-tagged registration line (mirroring the
   `PetrobrainF10Commands`/`PetrobrainOverlay` tags the other two Hook scripts already use) and the
   collector's own log for `firing events receiver listening on 127.0.0.1:7798` — absence of either
   means the deploy did not take, same diagnostic posture as the two existing Hook scripts.

**Branch to check out for any of this: `feature/emitter-events`.** The root checkout is currently
on `main`; nothing about this gate requires moving it — check out `feature/emitter-events` only
in whatever environment will actually run the DCS session and the body-layer/aircraft-layer
processes for the sortie below.

---

## Acceptance Testing Plan: Emitter Visibility — Gun Fire (Stage B)

**Goal:** verify that a unit firing a gun/autocannon becomes visible to Petrovich at any range out
to the player bubble and through tree cover, is announced with the correct "taking fire" vs.
"something firing, far" wording, and settle the one open DCS question this stage's watchdog value
depends on.

**Branch:** `feature/emitter-events`. Checkout: `git checkout feature/emitter-events`.
**Restart both the collector and the DCS application** (the Hook script change needs the latter;
`BL-B68`, stale belief surviving a mission restart, is a known deferred defect — restart the
body-layer service between missions too, same caveat Stage A's own acceptance plan named).

**Prerequisites**
- [ ] Type-checked and importable: `cd aircraft-layer && .venv/bin/mypy src` and
      `cd body-layer && .venv/bin/mypy src` (both ran clean at this tip, re-run if the Windows box
      pulls a different commit).
- [ ] `petrobrain-firing-events-hook.lua` deployed per "What the user has to do" above, DCS
      restarted, `autoexec.cfg`'s `net.allow_dostring_in` entry present.
- [ ] Collector restarted on the Windows box; confirm its log line for the firing-events receiver.
- [ ] `--console`/`--crew-text` body-layer run against the same `--aircraft-layer-url`.

**Test Cases**
1. A ground AI unit (AAA/autocannon-armed) fires at a target that is **not** the player, well
   outside naked-eye range/through tree cover — expect *"something firing, [bearing], far"* and a
   `PRESENCE`-level contact admitted at that position, never upgraded to a classification.
2. The same unit fires **at the player** — expect *"taking fire, [bearing]"*, and confirm from the
   detection trace (`--detection-trace PATH`) that `emitter_kind` reads `firing` with
   `targets_ownship=true` for that candidate.
3. A short burst (a few seconds) — confirm the sighting does not vanish before the burst visibly
   ends (the latch, `FIRING_MIN_VISIBLE_S`), and does disappear within roughly a second of the gun
   actually falling silent.
4. **The open-question check**: hold one unit firing continuously at the player for longer than
   180 seconds. Read the detection trace across that window — does the sighting ever drop while
   the unit is still visibly firing (watchdog fired despite the unit being alive — would indicate
   `S_EVENT_SHOOTING_START` does not retrigger and 180 s is not generous enough), and does the log
   show repeated `START` events during the one continuous burst (would indicate it does retrigger,
   making the watchdog largely decorative for this case)? Either answer is useful; record it.
5. Kill the firing unit mid-burst — expect the sighting to disappear immediately (within one poll),
   not wait out any part of the watchdog.
6. Restart the mission while a unit is firing — expect no stale `FIRING` entry carried into the new
   mission (the clean-slate check).

**Edge Cases to Probe**
- A dense scene with several units in the look wedge simultaneously (near the `MAX_SIGHTLINES_PER_
  CALL = 128` nearest-first cap) — confirm a firing unit far enough away to be truncated out of the
  LOS call's sort key is still admitted, per the sort-key splice mitigation Stage B shipped.
- Two units both firing at once, one at the player and one not — confirm each gets its own correct
  wording rather than one bleeding into the other's callout.

**Pass Criteria**
The feature passes if all six test cases produce the expected result, the detection trace confirms
the mechanism rather than just the callout text, and no regression is visible in the burning-unit
channel (`BL-B72`, Stage A) or ordinary naked-eye detections during the same flight.

**Ask the user:** Does the feature pass acceptance testing? (yes / no + details — in particular,
what the 180-second burst check in Test Case 4 showed.)

---

## Commit

Everything in this report, the two roadmap edits (`AC-B8.md`, `BL-B73.md`), and the `NOTES.md`
addition are committed in the worktree at `feature/emitter-events`'s tip plus one commit. Full
file list and status below (added to this report after the commit, per the dispatch's
instruction).
