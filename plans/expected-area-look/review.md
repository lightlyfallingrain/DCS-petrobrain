### Review Summary

Reviewed `feature/expected-area-look` (`BL-B111`) at `5776c2c5`, merged `--ff-only` from a
clean, up-to-date worktree base (`main@b92d59c9`). Full read of `plan.md`, `alignment.md`,
`explore-notes.md`, `implementation.md` (first pass through pass 3), and the diff of every
touched file (`belief/expected_area.py` in full; `contacts.py`, `callouts.py`, `body.py`,
`optic_policy.py`, `perception/forest.py`, `events.py`, `speech.py`, `aircraft_client.py`,
`mission_memory/admission.py`, the Lua Hook and its Python schema/receiver/sender/API, all as
diffs against `main`). Ran both touched subprojects' own checks from inside each (venvs did not
exist in this worktree; recreated per the pinned versions prior `implementation.md` passes used —
`numpy==2.4.6`, `pyproj==3.8.0`, `ruff==0.16.6`, `mypy==2.3.1`, `pytest==9.1.1`, Python 3.12).

**All checks pass:**
- aircraft-layer: `ruff format --check`/`ruff check` pass; `mypy src` clean (26 files);
  `pytest tests -q` — 702 passed; `luac5.1 -p` on the outer Hook file passes, and — following this
  codebase's own documented caveat that `luac5.1 -p` never looks inside a `dostring_in` string
  literal — I extracted the bridged LOS chunk (lines 452–789) to its own file with placeholder
  `local`s for the three load-time-spliced constants and syntax-checked it separately: clean.
- body-layer: `ruff format --check`/`ruff check` pass; `mypy src` clean (81 files);
  `pytest tests -q` — 3160 passed, 4 xfailed, matching `implementation.md`'s own reported count
  exactly.
- `/invariant-check`: all mechanical invariants PASS (no omniscience leak, no unsanctioned
  cross-subproject import, no `sys.path` smuggling, `BINOCULAR_RANGE_MULTIPLIER` has not
  returned, no stray `print()` in `perception`/`belief`, no bare `except`). The two WARN
  categories found (`except: pass` in four `__main__.py`/`body.py` entrypoints,
  `# type: ignore[misc]` on five `self.__init__(...)` reset calls) are all pre-existing patterns
  this codebase already uses elsewhere for the identical reset-mechanism trap — `ContactStore.
  reset_for_new_mission`'s own `# type: ignore[misc]` matches `tasks.py`/`crew_console.py`/
  `mission_memory/store.py`/`admission.py`'s existing instances of the same shape, not a new one.

**The `%d`-only template safety argument holds mechanically**: `SET_PROBES_TEMPLATE` has exactly
14 `%d` conversions (2 + 2×6, matching `MAX_PROBE_POINTS = 6`), confirmed by inspection and by
`test_line_of_sight_hook_lua.py`'s own mechanical assertion (`directives == ["%d"] * 14`). The
probe evaluation chunk fails closed on `getHeight`/`isVisible` pcall failure (empty token, never
a guessed `1`/`0`) — verified by reading the spliced bridged chunk directly, not just the
docstring's claim. `land.isVisible`/`land.getHeight` were not re-probed live (no DCS available
here) — the Stage 1 Windows card is still owed and is named in the test-card sources.

**On the dispatch's named question — the production harness recording "A observed" via `Contact.
record` directly rather than re-ingesting**: this is a harness simplification, not a hidden
production defect, but it surfaces a real, flight-relevant subtlety that is worth naming
explicitly rather than leaving implicit in the implementer's own note. In production,
`body._resolve_expected_area_checks` reads `a_observed[check.a_id] = a.last_seen_sim >
check.opened_sim` — i.e. it only asks whether *A's own* `last_seen_sim` advanced, via whatever
path did that (continuity, almost always, per `OBJECT_ID_MEMORY_S` = 600 s). If a genuine,
non-continuity re-detection of A arrives while a check is already open against it, `ingest`'s own
gate branch treats that sighting exactly as it treats B — `eligible_trigger_target` does not
special-case "this gate match's target is already the `a_id` of an open check" — so it founds a
*second* held contact against the same A rather than recording onto A directly. This is explicitly
the architecture's own stated behaviour ("two independent sightings of the same remembered group,
both still open, is exactly `MAX_OPEN_CHECKS`'s own case," `implementation.md` Pass 3), bounded at
2 concurrent checks, and does not produce a wrong verdict — the second held contact would itself
resolve "same" against A on its own look (composition/displacement correctly recognise it), just
with more latency and one more occupied check slot than a system that resolved it by direct
attribution. **Not a required fix**: it is bounded, fails toward "new" or an extra hold rather than
toward a wrong fact, and the plan's own Risks section already accepts "how often the trigger fires
in flight is unmeasured" as an open, logged (`--expected-area-log`) question. Worth a line in
`STRUCTURE.md`'s `belief/expected_area.py` entry if it is not already there — see Optional
Refinements.

**Co-moving Fields table verified against the actual diff, not the file list**: grepped
`ExpectedAreaCheck(` (two construction sites: `contacts.py`'s gate-fold branch and its
founded-fresh/`merge_echo_or_beside_lost_target` branch, both correct), `OpticState(` (both fresh
construction sites — the `GLASSING` entry in `_start_glass_look` and the `SEARCHING` entry in
`_decide_without_guidance` — both carry `area_look_reports` forward, matching the plan's own
named BL-B71 lesson), and every `replace(` site that could silently drop the dict (none do —
`replace(state, ...)` in `_mark_area_look_interrupted` and the natural-end commit path both
explicitly carry/freeze it). This is the check the Reviewer brief's own worked example (BL-B110's
`hybrid_source.py`) warns a file-list skim would miss, and it did not miss here.

**Trigger precondition history**: `a_out_of_view`'s amendment (`FOCUS_DWELL_S`, 2.0 s) is exactly
what `.claude/agent-memory/architect/feedback_temporal_precondition_tautology.md` and
`.claude/agent-memory/implementer/feedback_tautological_trigger_precondition.md` record, and the
later `expected_area_checks: bool = False` constructor gate (found during Pass 1's own blast-radius
stop) is a sound, narrower fix than widening the time window further — confirmed the premise
(object-id continuity persists across an optic swap on the same source instance, trusted for
600 s, two orders of magnitude past the 4–6 s gaps the ten affected tests use) by reading
`perception/naked_eye_source.py` and `body._apply_active_gaze` directly rather than taking the
implementer's own verification on faith. The premise holds as stated.

**Defaults.toml rendered, not just the source comment**: `EXPECTED_AREA_MAX_HALF_WIDTH_DEG`
(15.0, 4.25–30.0) and `COMPOSITION_MATCH_RATIO` (2.0, 1.2–5.0) both render correctly, matching
source bounds exactly, no truncated backtick spans, no arithmetic mismatch against the code's own
constants. Both tunables' second sentences (the `lo`/`hi` reasoning) are dropped by the generator
exactly as the known, accepted first-sentence-only behaviour already does elsewhere in this file —
not a new instance of the "reaches nobody" defect class, since neither dropped sentence is a safety
warning.

**`body-layer/CLAUDE.md`'s Tuning section "curated ~15" list** does not name either new tunable.
Confirmed pre-existing (the list also omits several `BL-B110`-era tunables already in
`defaults.toml`), not introduced by this plan, and flagged by the implementer rather than silently
left. Not a required fix — see Optional Refinements.

**Behaviour as actions/state params/"when"**: `resolve_checks` is cleanly the one "when" function;
the four `ContactStore` methods it calls are plain actions; `LookEvidence`/`a_observed`/
`relocation_warranted_by_b`/`a_was_announced` are state params assembled by the caller
(`body.py`), never computed inside `belief.expected_area` itself. The module's own docstring
correctly disclaims the plan's earlier four-free-standing-action framing. This fits the project's
shaping rule as well as any module in this codebase currently does.

### Required Fixes

None.

### Optional Refinements

- **Name the "second held check against the same A" subtlety in `STRUCTURE.md`'s `belief/
  expected_area.py` entry** (or confirm it is already covered — I did not find it there), so a
  future reader does not have to re-derive it from `implementation.md`'s Pass 3 note. See the
  "Review Summary" paragraph above for the exact mechanism. Optional because it changes no code
  and the behaviour is already bounded/logged.
- **`body-layer/CLAUDE.md`'s Tuning "curated ~15" list** could be updated to include
  `EXPECTED_AREA_MAX_HALF_WIDTH_DEG`/`COMPOSITION_MATCH_RATIO` (and whatever other `BL-B110`-era
  keys are already missing) in a follow-up docs-only commit. Pre-existing staleness, not
  introduced here, and the implementer's own flag already records it — low urgency.
- **The detection-trace/`sortie-log-triage` gap** Pass 2 flagged (the plan's own Pass 2 item 4
  asked for "the detection trace," which doesn't fit; Pass 3 built `--expected-area-log` instead,
  a better fit) is resolved by Pass 3 — `sortie-log-triage`'s `expected_area_report` exists and
  covers the named counts (checks opened, verdict histogram, cannot-look-cause histogram,
  merge-echo-suppressed count, `CONTACT_RELOCATED`-heard count). No further action needed; noted
  here only so the open item in Pass 2's own report reads as closed rather than lingering.
- **The ≤ 2 s "A out of view" boundary** (a B landing on A within one gaze dwell of A's last
  sighting is treated as "A still in view," so no check opens) is explicitly unmeasured in the
  plan's own Risks section and remains so — the harness has no cell under 6 s. This is a stated,
  accepted risk, not a defect; flagging only so it stays visible as a first-sortie read item
  (`--expected-area-log`'s own check-open counts), per the plan's own instruction.

### Verdict

APPROVED

### Review Confidence

Full read. Plan, alignment, explore-notes, and all four implementation.md sections read in full;
every touched production file's diff against `main` read (not skimmed) for `belief/expected_area.py`
(full file), `contacts.py`, `callouts.py`, `body.py`, `optic_policy.py`, `perception/forest.py`,
`events.py`, `speech.py`, `aircraft_client.py`, `mission_memory/admission.py`, the Lua Hook file and
its Python-side schema/receiver/sender/API; the production harness (`tools/measure_expected_area_look.py`)
read in the relevant section to verify the "A observed" simplification. Both subprojects' own
format/lint/type/test commands run from inside each subproject (venvs recreated in this worktree).
Lua syntax verified for both the outer file and the extracted `dostring_in` bridged chunk.
Not independently re-run: the production acceptance grid itself (`--production 200 300`, several
minutes) — accepted implementation.md's own reported numbers, which are internally consistent with
the plan's own modelled predictions cell-for-cell and were produced by a tool whose logic I did
read and verify matches its own documented behaviour. No live DCS session was available to verify
the Stage 1 Windows card (`land.isVisible`/`land.getHeight` on a real terrain point, `bridge_call_ms`
unmoved) — that card is still owed and is correctly named as such in the plan and test-card sources.
