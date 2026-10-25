# BL-B96 — The crew pipeline is the default: no mode flags, F10 and overlay removed, `logger` renamed `body`

- [x] **BL-B96 — Make the player-facing crew session, with speech in and out, what body-layer
  simply does. Remove the `--console` REPL mode, the F10 radio menu and the text overlay entirely,
  and rename the `logger` module to `body`.** #status/done #needs-flight Filed 2026-10-24 at user direction,
  reading `logger --help`.

  > *"help text for logger says*
  > *--console run the belief-consuming pipeline*
  > *--crew-text run the player-facing crew session*
  > *--f10-commands poll and dispatch player-selected DCS F10 radio-menu commands*
  > *--speech-audio synthesize and play every line*
  > *--speech-input poll and dispatch recognised speech transcripts*
  >
  > *These all must be default behavior, not behind an flag.*
  > *Also,*
  > *- i don't care about the console, I care about the pipeline*
  > *- player facing crew session is core functionality, not something to switch off*
  > *- F10 menu can be completely removed, we use audio commands*
  > *- speech-audio by default*
  > *- speech-input by default*
  > *- overlay can be dropped altogether, I don't use it*
  > *- while we're at it rename module logger to body - that's what it is"*

  **Scope, as read from those words:**

  - The belief pipeline and the crew session always run. `--console`'s REPL goes, and so do
    `--crew-text` and `--console` as flags.
  - Speech out (`--speech-audio`) and speech in (`--speech-input`) are always on.
  - The F10 menu is removed **in every layer**:
    - body-layer: the `--f10-commands` flag and the client poll;
    - aircraft-layer: `petrobrain-f10-commands-hook.lua`, `F10CommandReceiver`,
      `F10CommandQueue` and `GET /f10_commands/poll`;
    - its `WORKFLOW.md` deploy section, and the pilot's command map.
  - The overlay is removed in every layer: body-layer `--overlay`, and aircraft-layer
    `petrobrain-overlay-hook.lua` / `.dlg`, `TextOverlaySender` and `POST /text/push`.
  - `body-layer/src/logger.py` becomes `body.py`. Every caller and doc that names it is updated:
    `python -m logger`, the run-scripts, `RUN.md`, `CLAUDE.md` files, test names.

  **Watch for, at planning time:**

  - The mission-start Hook (BL-15) reuses the F10-commands Hook's `autoexec.cfg` opt-in
    (`aircraft-layer/CLAUDE.md`). Removing F10 must not remove mission-start detection.
  - **Audio adapter unreachable at startup: decided 2026-10-24, warn and keep trying.** Offered
    "warn and keep trying" (a loud console banner; Petrovich silent until the adapter comes up;
    everything else runs, as with a bad config file) against "refuse to start". The user: *"Warn
    and keep trying"*.
  - The `BL-B7`/`BL-B8`/`BL-B9` F10 backlog entries become obsolete. They get a note, not
    deletion; IDs are never reused.
  - Sequenced **after** `feature/attack-run-los` merges, because both touch `logger.py` and
    `crew_console.py`.

**Done, merged to `main` 2026-10-25 (`af9254d5`, branch `feature/default-crew-pipeline`).**
Crew-text, speech-audio and speech-input always on; `--console`, F10 command input and the text
overlay removed in both layers; `logger.py` → `body.py`; unreachable audio adapter warns and keeps
trying (`connection_reporter.py`); `--audio-adapter-url` required. Tuning key renamed
`logger.MISSION_START_RESOLVE_FALLBACK_S` → `body.MISSION_START_RESOLVE_FALLBACK_S` (an old-name
override in a local `config/tuning.toml` now only warns). Command map F10 badges dropped.
Review APPROVED, light security+performance APPROVED, DoD PASS
(`plans/default-crew-pipeline/{review,security-perf,dod-check}.md`).

`#needs-flight`: delete the stale F10/overlay Hook `.lua`/`.dlg` from Saved Games `Scripts\Hooks\`;
restart the collector; run `body.py` with `--audio-adapter-url`; confirm speech out and in work with
no flags and the connection warning appears/clears. Watch item (`security-perf.md`, not a defect):
an adapter that times out rather than refuses stalls each poll tick up to 5 s.

Milestone check: does not change BL-B89 or any downstream assumption.
