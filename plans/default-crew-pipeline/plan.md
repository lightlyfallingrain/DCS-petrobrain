### Goal

Make the crew session (belief pipeline + `CrewConsole` + speech in/out) what `body-layer` simply
does — no mode flags — and remove the F10 radio menu and the in-cockpit text overlay from every
layer; rename `body-layer/src/logger.py` to `body.py`.

### Address check (done before writing this plan)

`git rev-parse HEAD` on this worktree is already `9c59eecf...`, the expected tip. No merge was
needed.

### What "the pipeline" means, concretely

`body-layer/src/logger.py`'s `main()` currently branches three ways: `--crew-text` (the player
session), `--console` (a debug REPL, same belief engine), and neither (a plain `on_change` text
logger with no belief at all — `PerceptionLogger`). The user's words single out `--console`'s REPL
("I don't care about the console, I care about the pipeline") and make the crew session
unconditional. The plain-text-logger branch (the `else:` arm, no belief, no `ContactStore`) has no
place once the crew session is unconditional either — it is not named in BL-B96.md, but once
`--crew-text`'s branch is what always runs, there is nothing left to select it against, and leaving
it as dead code behind no flag at all serves nobody. **Deciding to delete it too, not just leave it
unreachable, is this plan's own call** (see Decisions, below) — flag it to the user as a scope
reading, not a silent default.

So after this change `main()` has **one** path: build `ConsolePerceptionRunner` + `CrewConsole`,
start the poll thread, run `_run_crew_text_repl`. `--console`, `_run_console_poll_loop`,
`_run_console_repl`, `belief/console.py`'s `Console` class and `format_event_for_overlay`, and the
plain-logger `else:` arm (`PerceptionLogger`, `_build_sources(..., emit_mode="on_change")`) are all
deleted. `ConsolePerceptionRunner` itself **stays** — despite its name, it is the shared belief
engine both old branches ran on, not REPL-specific, and the "console" in its name is cosmetic
(not in scope to rename here — flagged as optional, see Decisions).

### Affected files

**body-layer:**

- `src/logger.py` → **renamed to `src/body.py`** (mechanical commit, see Implementation Plan
  stage 1). Within it:
  - Delete `--console`, `--f10-commands`, `--overlay`, `--speech-audio`, `--speech-input` as CLI
    flags — their behaviour becomes unconditional. Keep `--audio-adapter-url` as a flag (now
    required — see Decisions) since it is a cross-machine address, same posture as
    `--aircraft-layer-url`/`--brain-url`.
  - Delete `--crew-text` as a flag too — same reasoning, its behaviour is now the only behaviour.
  - Delete `_run_console_poll_loop`, `_run_console_repl`, the `elif args.console:` branch and the
    `else:` plain-text-logger branch in `main()` (see "What 'the pipeline' means" above).
  - Delete `_poll_f10_commands` and the `f10_commands_enabled`/`f10-commands` plumbing through
    `_run_crew_text_poll_loop`'s signature and its one call site in `main()`.
  - Delete the `overlay_client` field and its `format_event_for_overlay`/`push_text_line` block
    from `ConsolePerceptionRunner.run_once` (dead once `--console`/`--overlay` are gone — the
    crew-text overlay mirror lived in `CrewConsole._print`, a separate code path, and goes with it
    too).
  - Delete `CrewConsole(..., overlay_client=...)`'s wiring in `main()`; delete the
    `overlay_client`/`speech_client` *conditionality* in `CrewConsole` only to the extent it was
    `None`-when-flag-unset — `speech_client` becomes unconditionally built (an `AudioAdapterClient`
    from the now-required `--audio-adapter-url`); `overlay_client` is deleted outright, not just
    defaulted — see `belief/crew_console.py` below.
  - `main()`'s mutual-exclusion/companion-flag `parser.error()` calls that reference deleted flags
    (`--crew-text`/`--console` exclusivity, `--speech-audio`/`--speech-input` requiring
    `--audio-adapter-url`, `--detection-trace`/`--group-trace`/etc. requiring `--console or
    --crew-text`) simplify: those debug logs now require nothing (the crew pipeline always runs)
    except `--slew-trace`, whose own guard text ("requires `--crew-text`") becomes vacuous and is
    deleted outright.
  - Startup audio-adapter reachability check: add one probe call before the poll thread starts
    (see "Audio adapter unreachable" below) using the warn-and-keep-trying mechanism, not a
    `parser.error`.
- `src/belief/console.py` — **deleted entirely.** `Console`, every `_handle_*` dispatch function,
  `format_event_for_overlay`, `HELP_TEXT`. Nothing else imports from it except `logger.py`
  (confirmed by sweep) and its own tests.
- `src/belief/crew_console.py`:
  - `overlay_client: AircraftLayerClient | None = None` field and the `_print` block that pushes to
    it (lines ~4447-4457) — **deleted**, not defaulted. The overlay transport is gone in every
    layer; there is nothing left for this field to address.
  - `speech_client: AudioAdapterClient | None = None` stays `Optional` in type (an
    unreachable-at-startup adapter must not crash construction — see "Audio adapter unreachable"),
    but `main()` now always constructs and passes one rather than gating on a flag.
  - `handle_command`/`handle_f10_command`-naming note in the module docstring (root `CLAUDE.md`'s
    "What this is" section, mirrored in this module's own docstring) stays accurate: `handle_command`
    remains the single dispatcher for every command token: voice and confirm-band answers. Only the
    **F10 transport** (the poll-and-feed-in path) is removed, not the dispatcher itself — nothing in
    this file changes for that reason, only the `overlay_client` deletion above.
- `src/aircraft_client.py` — delete `get_f10_commands` (the body-layer-side client call to
  `GET /f10_commands/poll`) and `push_text_line`/overlay-push client method (the `POST /text/push`
  call) — both transports are gone aircraft-layer-side too (below), so these calls have nothing to
  reach.
- `src/belief/audio_client.py` — **unchanged.** Speech in/out stays; nothing here was behind a
  flag at this layer.
- `_format_gaze_line`/`_push_gaze_line` (`logger.py`/`body.py`, ~line 1718/1740) — **deleted
  entirely.** Both exist solely to push Petrovich's current gaze label to the overlay
  (`overlay_client.push_text_line`), called from both `_run_console_poll_loop` (already deleted)
  and `_run_crew_text_poll_loop`; with `overlay_client` gone, the one remaining call site
  (`_run_crew_text_poll_loop`'s `last_gaze_label = _push_gaze_line(...)`) is also deleted. **Missed
  by the first pass of this sweep** — found by re-grepping for every `overlay_client` consumer
  rather than trusting the file list already gathered. Six tests in `test_logger.py` go with them:
  `test_format_gaze_line_names_the_oclock_hour_in_free_scan`,
  `test_format_gaze_line_names_the_commanded_sector`,
  `test_format_gaze_line_names_a_commanded_legs_scan_generically`,
  `test_push_gaze_line_pushes_once_and_is_a_no_op_on_no_change`,
  `test_push_gaze_line_pushes_again_when_the_cone_changes`,
  `test_push_gaze_line_failure_is_isolated_and_still_advances_the_label`.
- `tests/test_mock_flight_chain.py` — `test_mock_flight_chain_threaded_console_smoke` (~line 355)
  exercises the real `--console` threading model end to end (`_run_console_poll_loop` on a
  background thread, `belief.console.Console`/`_run_console_repl` on the foreground) against the
  shared fixture. With that model deleted, this test cannot simply disappear without losing the one
  thing it actually proved: that the *shared poll-loop/REPL threading pattern* (thread-local
  world-model connection, clean shutdown via `stop_event`) survives against a real fixture, not a
  fake. There is no existing crew-text equivalent in this file (confirmed by grep — no
  `test_mock_flight_chain_threaded_crew_text_*`). **Rewrite it against `_run_crew_text_poll_loop`/
  `CrewConsole`/`_run_crew_text_repl` instead of deleting it outright** — same fixture, same
  threading shape, swap the REPL driver. This is the "existing tests must be rewritten rather than
  extended" case `AGENTS.md`'s escalation rules name; flagging it here rather than leaving the
  Implementer to decide silently, but proceeding under the reading that BL-B96.md's "deleting tests
  for removed features is in scope" extends to *rewriting* a test whose subject (the threading
  model) survived even though its REPL did not.
- `body-layer/CLAUDE.md` — the "## Commands" section's `--console`/`--overlay`/`--crew-text`/
  `--f10-commands`/`--speech-audio`/`--speech-input` paragraphs (roughly a dozen paragraphs,
  "Running the live logger" through "Add `--speech-input ...`") describe behaviour that is now
  unconditional or deleted, not optional — these need rewriting, not just the mechanical
  `logger`→`body` rename Stage 1 already covers. The `--detection-trace`/`--group-trace`/
  `--mission-memory`/`--belief-truth-log`/`--eyesight-view` paragraphs' "Only meaningful with
  `--console` or `--crew-text`" clauses become vacuous (always true) and should read as unconditional
  too. "## What this is"'s "reached from three input surfaces: the DCS F10 radio menu, a spoken
  voice command, and a committed confirm-band answer" becomes **two** surfaces once F10 is gone.
- `body-layer/RUN.md` — "## 2. Run the perception logger"'s example command is the plain-text-logger
  invocation (no `--console`/`--crew-text` at all) — the branch Stage 2 deletes. This section needs
  a real rewrite to show the new always-on crew-session invocation (`-m body`, required
  `--audio-adapter-url`, no mode flags), not just the `logger`→`body` substitution Stage 1 covers;
  the "### Arguments" table's required-flags list is also stale against current `main()` already
  (`--world-model-dir`/`--mission-understanding` aren't listed) — fix both while touching this file
  rather than compounding the staleness.
- Tests (see "Test impact" below for the full account):
  - `tests/test_console.py` — **deleted entirely** (55 tests; it exists only to test
    `belief/console.py`'s `Console`/`format_event_for_overlay`, both deleted). The `test_console_
    runner_*` tests in **`test_logger.py`** are a different thing — see below, most of those stay.
  - `tests/test_logger.py` (153 tests, ~52 touching console/f10/overlay by name):
    - `test_console_poll_loop_*` (3: thread-local-connection, survives-a-raising-poll,
      logs-coverage-summary-in-finally) — test `_run_console_poll_loop` directly, which is
      deleted. **Check first whether `_run_crew_text_poll_loop` already has an equivalent test for
      the same three properties** (thread-affine connection, poll-failure survival, finally-block
      coverage log) before writing a new one — if `_run_console_poll_loop` was built by copying
      `_run_crew_text_poll_loop` (the docstring says "identical ... same reasons"), a crew-text
      twin test plausibly already exists and these three are pure duplication, not unique
      coverage.
    - `test_console_runner_without_overlay_client_pushes_nothing`,
      `test_console_runner_overlay_push_failure_is_isolated_per_push`,
      `test_console_runner_pushes_one_line_per_newly_materialized_event` — test
      `ConsolePerceptionRunner.overlay_client`/`format_event_for_overlay` wiring specifically;
      **deleted** (the field they test no longer exists). The other `test_console_runner_*` tests
      (ingestion, decay, ground-threshold, store reuse, `last_t_sim`, group-trace-sink,
      scan-plan update, periodic-count line, mission-phase-tracker) test `ConsolePerceptionRunner`
      itself, which **stays** — do not delete these.
    - Any test constructing `_run_crew_text_poll_loop`/`main()`-equivalent fixtures with
      `f10_commands_enabled=True` or asserting `_poll_f10_commands` behaviour — deleted along with
      the parameter.
  - `tests/test_crew_console.py` — no test named `test_*f10*` was found by the sweep (confirmed by
    `grep`); the `overlay_client` deletion needs its own small check: grep this file for
    `overlay_client=` in test fixtures and drop the kwarg (it will no longer exist on the
    dataclass) rather than leave a `TypeError` for the Implementer to discover live.
  - `tests/test_tools.py` — grep for `overlay_client`/`format_event_for_overlay`-adjacent fixtures;
    sweep found no direct hit but the brief named it as a place to check (pretty-printers) — worth
    a quick grep in Stage 1, not a known change.

**aircraft-layer — F10 removed in full:**

- `dcs-export/petrobrain-f10-commands-hook.lua` — **deleted** (the Hook script; 274 lines).
- `src/collector/f10_command_receiver.py` (`F10CommandReceiver`) — **deleted**.
- `src/schema/f10_command.py` (`F10CommandEvent`/`F10CommandParseError`) — **deleted**; remove its
  re-export from `src/schema/__init__.py`.
- `src/collector/cache.py` — delete `F10CommandQueue` (class at line 343; its own module-docstring
  cross-reference at line ~20/~276 goes with it).
- `src/api/server.py` — delete the `GET /f10_commands/poll` route (`_F10_COMMANDS_POLL_PATH`,
  `_handle_f10_commands_poll`, the `f10_command_queue` constructor parameter and its dispatch in
  `do_GET`), and the module docstring's description of that endpoint (lines ~24-31, ~87).
- `src/collector/__main__.py` — delete `F10CommandReceiver`/`F10CommandQueue` construction, the
  background-thread wiring, and the `--f10-host`/`--f10-port` CLI flags (and their help text /
  usage-string entries).
- Tests: `tests/test_f10_command_api.py`, `tests/test_f10_command_queue.py`,
  `tests/test_f10_command_receiver.py`, `tests/test_f10_command_schema.py` — **deleted entirely**
  (all four exist solely for the removed surface).
- `aircraft-layer/CLAUDE.md` — remove: the F10 bullet in "What this is"'s write-path list; the
  "F10 radio-menu commands ... carry wall-clock provenance only" Tech-stack bullet; the module-map
  description of `f10_command_receiver.py`/`F10CommandQueue`/the `/f10_commands/poll` route; the
  `petrobrain-f10-commands-hook.lua` Structure-section entry.
- `WORKFLOW.md` — remove the "Deploy the F10 commands Hook script" section **but preserve its
  `autoexec.cfg` opt-in instructions** (`net.allow_dostring_in = { "scripting" }`) by moving them
  into the mission-start Hook's own deploy section (see "Mission-start dependency" below — this is
  the one hard constraint in this removal).
- `plans/f10-crew-commands/plan.md`, `plans/f10-command-vocabulary/plan.md` — **left as-is.**
  They are historical decision records, not live documentation; root `CLAUDE.md`'s process does
  not ask for a plan file to be rewritten once its feature is later removed, only for the
  removal's own plan (this one) to say what it removed and why.

**aircraft-layer — overlay removed in full:**

- `src/collector/text_sender.py` (`TextOverlaySender`) — **deleted**.
- `src/api/server.py` — delete the `POST /text/push` route (`_TEXT_PUSH_PATH`, its handler, the
  `text_sender` constructor parameter and dispatch) and its module-docstring description
  (lines ~24-31, ~45).
- `src/collector/__main__.py` — delete `TextOverlaySender` construction/wiring and the
  `--text-overlay-host`/`--text-overlay-port` flags.
- `dcs-export/petrobrain-overlay-hook.lua` and `dcs-export/petrobrain-overlay.dlg` — **deleted**.
- Tests: `tests/test_text_push_api.py`, `tests/test_text_sender.py` — **deleted entirely**.
- `aircraft-layer/CLAUDE.md` — remove the `POST /text/push` write-path bullet, the Tech-stack
  cross-references to it (`text_sender.py` module-map entry, the overlay Hook `.lua`/`.dlg`
  Structure-section entries).
- `WORKFLOW.md` — remove the "Deploy the overlay Hook script" section.

**Mission-start dependency — the one thing this removal must not break:**

`aircraft-layer/WORKFLOW.md`'s mission-start Hook deploy section states explicitly: *"No
`autoexec.cfg` opt-in beyond what the F10-commands Hook already requires ... if this script is
deployed on its own without the F10-commands Hook, add that line"* — i.e. the opt-in
(`net.allow_dostring_in = { "scripting" }`) is documented **once**, under the F10-commands Hook's
own deploy section, and the mission-start (and line-of-sight) Hook sections point at it rather than
repeating it. **It is one line of `Saved Games\DCS\Config\autoexec.cfg`, not a file the F10 Hook's
presence controls** — removing the F10 Hook's `.lua` file does not remove this config line from a
user's existing DCS install, and nothing in body-layer or aircraft-layer code reads the F10 Hook's
existence to decide whether the bridge is enabled. The **risk is purely documentary**: the
instruction for *how to set this up on a fresh machine* currently lives under a section this plan
deletes. **Fix: move the `autoexec.cfg` paragraph (WORKFLOW.md lines ~81-95) into the mission-start
Hook's own deploy section** (the dcs-driven-los Hook's section already states the same requirement
independently and can stay as-is, or point at the same canonical paragraph — Implementer's call,
not architecturally significant). The mission-start detection mechanism itself (`GET
/mission_start/latest`, the Hook script, body-layer's `_check_for_new_mission`) has **zero** code
dependency on the F10 Hook or its receiver — confirmed by the sweep (separate port, separate
schema, separate collector wiring) — so this is a doc-only fix, not a code one.

**Command map / status page:**

- `docs/status/petrovich-commands.html` — three `F10` badges (one legend entry, two per-card) and
  one caption line ("F10 has ahead/left/right/full and the compass points.") describing which
  tokens also have an F10 route. **This page is a hand-drawn view of
  `audio-adapter/src/vocabulary.py`, regenerated by the `/command-map` skill, not hand-edited** —
  the Implementer should not patch the HTML directly; run `/command-map` after confirming whether
  `vocabulary.py`'s own `LEGACY_F10_TOKENS` constant changes (see next bullet) and whether that
  changes the manifest hash `command-map-check.py` validates against.
- `audio-adapter/src/vocabulary.py`'s `LEGACY_F10_TOKENS` — **left unchanged.** This is a pure
  naming/classification constant (which 15 of the full voice vocabulary happen to coincide with the
  tokens the *now-removed* F10 menu used to expose), not a dependency on the F10 transport — voice
  recognition and dispatch do not consult it. Renaming or removing it buys nothing and the sweep
  found 9 live references across `vocabulary.py`'s own tests and comments that would need touching
  for zero behaviour change. Flagging this explicitly so nobody "corrects" it mid-implementation.
  The command map's **badge and caption**, however, describe a real-world affordance (there used to
  be a button) that is now false, so those do need to come off, via `/command-map`, not by hand.

**Backlog entries — mark obsolete, do not delete/reuse IDs** (`BL-B7`, `BL-B8`, `BL-B9`, all
already `[x]` done, confirmed by reading each entry file): add one line to each
`body-layer/ROADMAP/BL-B{7,8,9}.md` noting the F10 transport was removed by `BL-B96` and the
file/menu/vocabulary described no longer exists, per root `CLAUDE.md`'s "Numbers are never reused"
rule. No other roadmap entry needs more than this — the sweep's wider `grep -ril f10 */ROADMAP/`
hit list (AC-5..8, BL-W10/11/12/13/20/21/23/24/26/30/33/34, BL-B10/22/23/42/64/68/72/81/87/97,
BL-10/15, WM-M2, WM-B15, AA-4) is almost entirely **unrelated** "F10 map" (the DCS *paper map*
display mode) or incidental cross-references in prose — read each roadmap entry's own `grep`
context before touching it; do not bulk-edit on the strength of the filename match alone.

**Skills/docs sweep result — no mechanical change needed beyond what's named above.** The broader
grep (`.claude/skills/`, `.claude/agents/`, `docs/`) turned up only: (a) illustrative examples in
`architect.md`/`docs/AGENT_ROLES.md`'s "co-moving fields" guidance ("a pilot command, an F10 item,
a voice token") — these are naming a *category* of externally-written field, not asserting the F10
transport exists, and stay accurate as prose after removal; (b) `security-grep/SKILL.md` and
`extract-feature-diff/SKILL.md` citing "the F10 command hook" as an example of DCS-process-internal
code — becomes a dead example once the file is deleted; low-value cleanup, **optional**, swap for
the mission-start or line-of-sight Hook as the example instead, Implementer's call, not required
for DoD; (c) `docs/acceptance/*.md` sortie-feedback files mentioning F10/overlay — these are
append-only historical records of what was true on the date they were written and must **not** be
edited (root `CLAUDE.md`'s doc conventions treat these as a log, not living documentation).

### Run scripts:

- `run-scripts/run-console.sh` — **deleted** (its entire reason to exist, `--console`/`--overlay`,
  is gone).
- `run-scripts/run-crew-text.sh`, `run-scripts/run-crew-text-debug-view.sh` — drop
  `--crew-text`/`--f10-commands`/`--speech-audio`/`--speech-input` (now unconditional/removed as
  flags), change `-m logger` to `-m body`. `--audio-adapter-url` stays (now required rather than
  optional — both scripts already pass it, so no behaviour change for them).
- `run-scripts/start-mac` — **do not touch**, per the dispatching brief: untracked user file in the
  repo root, outside this worktree's reach anyway.

### Implementation Plan

1. **Mechanical rename, its own commit, no behaviour change.** `git mv src/logger.py src/body.py`;
   update every `import logger`/`from logger import`/`python -m logger` reference across
   `tests/test_logger.py` → keep the filename `test_logger.py` or rename to `test_body.py`
   (Implementer's call — either is defensible; renaming the test file alongside the module it
   tests is the more consistent choice and costs one `git mv`), `run-scripts/*.sh`,
   `body-layer/CLAUDE.md`, `body-layer/RUN.md`. Root `CLAUDE.md`'s own rule: *"Python's stdlib
   `logging` and the many local `logger = logging.getLogger(...)` variables are NOT the module"* —
   confirmed by reading `logger.py`'s own top: `logger = logging.getLogger(__name__)` is a
   per-module convention used throughout this codebase (e.g. `crew_console.py`, `cache.py`) and
   stays untouched everywhere it is not the renamed module's own name. Run the full subproject
   command set (format/lint/mypy/pytest) before moving on — this commit should be green on its own.
2. **Remove `--console` and the plain-text-logger branch** (behaviour change, separate commit from
   stage 1's rename). Delete `belief/console.py`, `_run_console_poll_loop`, `_run_console_repl`,
   the `elif args.console:`/`else:` branches in `main()`, the `--console` flag, and
   `ConsolePerceptionRunner.overlay_client`/the `format_event_for_overlay` call in `run_once`.
   Delete `tests/test_console.py` and the `test_logger.py` tests named in "Affected files" above.
   **Rewrite** (not delete) `test_mock_flight_chain.py`'s `test_mock_flight_chain_threaded_console_
   smoke` against the crew-text threading model, per "Affected files" above. Run the command set.
3. **Make crew-text, speech-audio, and speech-input unconditional** (separate commit). Delete the
   `--crew-text`/`--speech-audio`/`--speech-input` flags; `main()` always builds
   `AudioAdapterClient`, `CrewConsole(speech_client=..., ...)`. `--audio-adapter-url` becomes
   required (`parser.error` if absent, same posture as `--aircraft-layer-url`). Add the
   startup-probe + warn-and-keep-trying mechanism (next bullet). Run the command set.
4. **Audio-adapter-unreachable handling.** Reuse `_ConnectionReporter` (already defined in
   `logger.py`/`body.py` for the aircraft-layer disconnect case) rather than inventing a second
   mechanism: construct one `_ConnectionReporter(label="audio adapter")` shared by the push path
   (`CrewConsole._print`'s existing `except AudioAdapterError: logger.warning(..., exc_info=True)`)
   and the poll path (`_poll_transcripts`'s existing `except AudioAdapterError: logger.warning(...,
   exc_info=True)`) — both currently log a full traceback on **every** failed call, which was
   tolerable while speech was opt-in (a rare, deliberately-triggered failure) and is not tolerable
   once it is the default path (a developer running `body.py` before `audio-adapter` is now the
   common case, not an edge case). Replace both `logger.warning(..., exc_info=True)` calls with
   `reporter.report_failure(exc)` / a matching `reporter.report_success()` on the first successful
   call after a failure — this gives the "one line when it goes away, one when it comes back,
   nothing in between" behaviour the user asked for ("warn and keep trying ... as with a bad config
   file") for free, reusing code already proven correct for the structurally identical
   aircraft-layer case. **The "loud console banner" at startup** is satisfied by the same
   mechanism's first `report_failure` call, which fires on the very first poll/push attempt if the
   adapter is down from the start — no separate startup-only probe is needed, and inventing one
   would duplicate the reporter's own job. Petrovich stays silent (never speaks, never crashes)
   until the adapter answers; everything else (perception, belief, F10-dispatch-equivalent voice
   commands, mission memory) runs unaffected — confirm this by checking that `CrewConsole._print`'s
   non-`speech_client` branches (printing, overlay — now deleted, speech-log) are unconditional on
   `speech_client`'s own state already (they are, per the current code read). Run the command set.
5. **Remove F10 in aircraft-layer.** Delete the Hook script, receiver, schema, cache queue, API
   route, collector wiring, and the four F10-specific test files (listed above). **Before
   deleting `WORKFLOW.md`'s F10-commands deploy section, move its `autoexec.cfg` paragraph into
   the mission-start Hook's own section** (see "Mission-start dependency" above) — do this edit
   *before* or in the same commit as the deletion, not after, so there is never a commit where the
   instruction is simply gone. Update `aircraft-layer/CLAUDE.md` per "Affected files". Run
   aircraft-layer's command set (`ruff format/check`, `mypy --strict` from inside the subproject,
   `pytest`, `luac5.1 -p` over the remaining `.lua` files).
6. **Remove the overlay in aircraft-layer and body-layer.** Delete `TextOverlaySender`, the
   `POST /text/push` route, the overlay Hook `.lua`/`.dlg`, the two overlay test files, and
   `aircraft_client.py`'s `push_text_line`; delete `CrewConsole.overlay_client` and its `_print`
   block; delete `_format_gaze_line`/`_push_gaze_line`, their one remaining call site in
   `_run_crew_text_poll_loop`, and the six tests named in "Affected files" above. Update both
   `CLAUDE.md` files. Run both subprojects' command sets.
7. **Backlog/docs bookkeeping.** Append the obsolescence note to `BL-B7`/`BL-B8`/`BL-B9`. Rewrite
   `body-layer/CLAUDE.md`'s "## Commands" flag paragraphs and "## What this is"'s surface count, and
   `body-layer/RUN.md`'s "Run the perception logger" section and argument table, per "Affected
   files" above. Run `/command-map` to redraw `docs/status/petrovich-commands.html` without the F10
   badges/caption and re-stamp its manifest (`command-map-check.py --stamp`, which refuses if a live
   token is missing from the redraw — a built-in correctness check for this exact step). Update
   `run-scripts/*.sh` per "Run scripts" above.
8. **Full-repo final sweep.** Re-run the four `grep` patterns from the dispatching brief
   (`python -m logger`, `import logger`, `from logger`, `logger.py`, plus `--console`,
   `--crew-text`, `--f10-commands`, `f10`, `overlay`, `text/push`) across the whole repo
   (excluding `docs/acceptance/`, `plans/*/plan.md` for already-merged features, and
   `graphify-out/`) and confirm every remaining hit is one of: a stdlib `logging` variable, a
   `docs/acceptance/` historical record, an already-obsolete-noted backlog entry, or a deliberately
   unchanged item named in this plan (`LEGACY_F10_TOKENS`, the illustrative co-moving-fields
   examples). Anything else is a miss — fix it before DoD.

### Decisions requiring user input

1. **The plain-text-logger (`else:`, `PerceptionLogger`, no `--console`/`--crew-text`) branch is
   being deleted outright, not just left unreachable.** BL-B96's own words do not name it — they
   name `--console`, `--f10-commands`, `--overlay`, `--speech-audio`, `--speech-input` specifically
   — but once the crew session is unconditional, this branch can never run and keeping ~80 dead
   lines (`_build_sources(..., emit_mode="on_change")`, `PerceptionLogger`) around serves no one.
   Reading "the crew pipeline is the default" as "the crew pipeline is now the *only* thing
   `body.py` does" rather than "...the default when no flag says otherwise." If the user wants a
   lighter-weight no-belief smoke-test mode kept for some reason, say so and this plan is revised —
   otherwise proceeding with deletion.
2. **`--audio-adapter-url` becomes a required flag, no default.** Matches `--aircraft-layer-url`'s
   existing posture (a cross-machine address that varies by deployment, never silently defaulted) —
   `audio-adapter/CLAUDE.md`'s own example URLs (`127.0.0.1:7795`) are dev-machine examples, not a
   fixed port guaranteed across every deployment. The alternative — defaulting to
   `http://127.0.0.1:7795` — would make a same-box dev run one flag shorter at the cost of silently
   pointing at the wrong host on the actual Mac/Windows split topology if ever forgotten. Flagging
   this as the kind of "two reasonable approaches, no `CLAUDE.md` rule decides it" case
   `AGENTS.md`'s escalation rules describe — proceeding with "required, no default" as the
   consistent choice, reversible by the user if it proves annoying.
3. **`ConsolePerceptionRunner`'s class name is not changed.** It is the shared belief engine behind
   the one remaining path, and "console" in its name is now purely historical (both the REPL it was
   once named for and the plain-text-logger branch are gone). Renaming it is a clean, low-risk
   follow-up but is **not** part of this plan's scope — BL-B96 asks for `logger.py` → `body.py`,
   not a second module/class rename, and bundling an unasked-for rename into this change would
   widen its diff for no behaviour reason. Noting it here so a future reader does not read the
   leftover name as an oversight.

### Risks & Unknowns

- **The "warn and keep trying" mechanism (`_ConnectionReporter`) has never been exercised for the
  audio-adapter case in a live sortie** — it is a straight reuse of code proven correct for the
  aircraft-layer disconnect, but the first real test is the next flight with `audio-adapter` started
  late or not at all. Watch for: does `report_failure`/`report_success` fire on the *first* call
  correctly (the aircraft-layer case's own docstring says yes — `None` means unreported, so the
  first success is always announced), and does nothing downstream (mission memory, belief,
  voice-command dispatch) silently assume `speech_client.push_speech` succeeded.
- **`test_console_poll_loop_*`'s three tests may or may not be true duplicates of existing
  crew-text-poll-loop coverage** — flagged in "Affected files" as something to verify, not
  assumed; if no crew-text equivalent exists for one of the three properties (thread-local
  connection, poll-failure survival, finally-block coverage log), that property needs a home in
  `test_logger.py`'s crew-text section rather than being lost.
- **Effector-sequence `mission-start`/`mission-start-in-air` triggers and `BL-B90`'s config-error
  spoken line both reuse `CrewConsole._print`'s funnel** — confirmed unaffected by reading
  `_print`'s structure (the `overlay_client` block being deleted is one `if` among several
  independent sinks: `output`, `speech_client`, `speech_log_sink`), but worth a specific check
  during Stage 6's review since it is exactly the kind of "several co-moving sinks in one function"
  shape this project's own process flags as error-prone.

### Effort read

**This is a small-to-medium mechanical removal, not a design problem** — the user's own "supposedly
smallish" estimate is accurate for the *concept* (delete three flags, two files, one route pair),
but the footprint is wider than "smallish" suggests once every layer is counted: ~4 aircraft-layer
test files and ~2 body-layer test files deleted outright, one doc paragraph that must be
*relocated* rather than deleted (the `autoexec.cfg` instruction, to avoid silently breaking
mission-start setup on a fresh machine), and the audio-adapter-unreachable case moving from
"opt-in, rare" to "default path, common" which makes a latent noisy-logging issue
(`exc_info=True` on every failed push) worth fixing now rather than later. None of this is
architecturally hard — every needed mechanism (`_ConnectionReporter`, the per-run log rolling
pattern, the additive-flag convention) already exists in this codebase and is being reused, not
invented.

**A lightweight combined perf+security pass is warranted, and for a reason beyond "the user asked
if wrong": this change removes two inbound network surfaces** (the F10 Hook's loopback UDP
listener, and whatever the overlay's `POST /text/push` accepted) **and adds exactly one new
unconditional outbound dependency** (speech, previously opt-in). Removing attack surface rarely
needs a security pass to bless it, but the *reduction itself* is the kind of fact a security pass
should confirm rather than assume — e.g., that deleting `F10CommandReceiver` does not leave an
orphaned port binding, and that `_handle_f10_commands_poll`'s removal from `server.py` does not
leave a stale route reachable under some fallback dispatch. Performance risk is low (no hot path
touched; `_ConnectionReporter`'s reuse is O(1) per call, identical to its existing use) — a short
combined pass, not two separate deep ones, matches root `CLAUDE.md`'s current once-per-batch
cadence for these two roles.
