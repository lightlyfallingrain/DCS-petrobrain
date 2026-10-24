### Review Summary

BL-B96 (default crew pipeline: unconditional crew session/speech, F10 and overlay removed in
full, `logger.py` → `body.py`) reviewed against `plans/default-crew-pipeline/plan.md` (8 stages),
`implementation.md`'s decision log, and `body-layer/ROADMAP/BL-B96.md`.

Scope match is good: the plan's eight stages are all present as separate commits, the CLI surface
matches (`--console`/`--crew-text`/`--f10-commands`/`--overlay`/`--speech-audio`/`--speech-input`
all gone from `argparse`, confirmed by grep and by `--help` output; `--audio-adapter-url` required,
no default), `ConsolePerceptionRunner` kept by name per the plan's own Decision 3, the
plain-text-logger branch deleted per Decision 1, and the F10/overlay removal is genuinely complete
in both subprojects (no leftover routes in `aircraft-layer/src/api/server.py`, no leftover client
calls in `body-layer/src/aircraft_client.py`).

The warn-and-keep-trying mechanism (`connection_reporter.ConnectionReporter`, promoted to its own
module) is correctly non-blocking on both the push path (`CrewConsole._print`) and the poll path
(`_poll_transcripts`): both wrap the call in `try`/`except AudioAdapterError`, report through the
shared reporter, and `return`/continue — nothing sleeps, retries synchronously, or raises out of
the tick. Confirmed by reading both call sites directly, not just the docstring's claim.

The `logger.MISSION_START_RESOLVE_FALLBACK_S` → `body.MISSION_START_RESOLVE_FALLBACK_S` tuning-key
rename is correctly reflected in the **rendered** `config/defaults.toml` (`[body]` section,
`source: body.py:MISSION_START_RESOLVE_FALLBACK_S`), not just the `#:` source comment, and the
generator was used (not hand-edited, per its own tooling convention).

Test coverage: the `test_mock_flight_chain.py` rewrite
(`test_mock_flight_chain_threaded_crew_text_smoke`) is a genuine like-for-like port of the deleted
console-threading smoke test, not a weaker stand-in — same fixture, same background-poll-thread +
foreground-REPL shape, same assertion that no exception crosses either thread. It also incidentally
caught and exercises a real pre-existing bug (REPL-thread `sqlite3.Connection` affinity) that the
implementation fixed in the same stage, which is the right call given the blast-radius argument in
implementation.md. All three touched subprojects' own checks pass clean from inside each
subproject (ruff format/check, mypy --strict, pytest): body-layer 2576 passed/4 xfailed,
aircraft-layer 581 passed, audio-adapter 349 passed/2 skipped — re-run myself, not taken on the
report's word. `invariant-check` is all PASS/pre-existing-WARN, no FAIL. `command-map-check.py`
reports current.

One required fix: the plan explicitly flagged that the command-map status page's F10 badges/caption
describe a now-false affordance and must come off via `/command-map`'s manual redraw step, not the
mechanical token check alone — this did not happen. Two minor/optional items below.

### Required Fixes

1. **`docs/status/petrovich-commands.html` still shows three F10 badges and the caption "F10 has
   ahead/left/right/full and the compass points"** (lines 52, 85-86, 101) — a player-facing claim
   that is now false: the F10 menu no longer exists in this branch. `command-map-check.py` reporting
   "current" does not cover this: that script only validates the token↔card manifest against
   `vocabulary.py`'s `TOKENS`, which didn't change (`LEGACY_F10_TOKENS` was deliberately left as-is
   per the plan's own Decision), so the check passing is not evidence the badges are correct —
   `implementation.md`'s "no redraw needed" conclusion conflates the two. The plan's own words:
   *"The command map's badge and caption... describe a real-world affordance... that is now false,
   so those do need to come off, via `/command-map`, not by hand."* Run the `/command-map` skill's
   manual redraw step (edit the Mermaid cards, drop the `f10` badge spans and the caption's F10
   clause, re-stamp) and republish.

### Optional Refinements

- `aircraft-layer/src/collector/audio_sender.py`'s module docstring (line 12) still reads
  `` `logger.py`'s `--crew-text` poll loop can emit several lines in one poll`` — stale module name
  and a removed flag, in a file this diff touched (28 lines changed) but didn't reach this comment.
  Low-value but easy: `` `body.py`'s poll loop ``, drop `--crew-text` (unconditional now).
- `aircraft-layer/src/schema/watched_args.py:111` (`"the id mismatch itself is \`logger.py\`'s own
  poll-block check"`) — not touched by this diff at all, so it's a pre-existing miss the plan's own
  Stage 8 "full-repo final sweep" should have caught (it isn't in any of that stage's exempted
  categories: not a `logging` variable, not `docs/acceptance/`, not an already-noted backlog entry,
  not `LEGACY_F10_TOKENS`/the co-moving-fields examples). Harmless (prose only), but worth folding
  into this branch or the next sweep.
- `audio-adapter/src/vocabulary.py`'s module docstring and the `LEGACY_F10_TOKENS` comment (lines
  3-32, 49-53) still say "while the F10 path still runs," "that path is being retired," and "When
  the F10 path is removed the split collapses" — all present/future tense, now false: F10 *is*
  removed by this very branch. The plan's Decision to leave the constant's *value* unchanged is
  sound and documented; the surrounding prose simply wasn't revisited to match that decision having
  now taken effect. Not a behaviour defect — optional tense fix only.
- `body-layer/tools/voice_repl.py:18` ("same as the live logger") — a generic leftover reference to
  the pre-rename name; harmless, optional.

### Verdict

**APPROVED WITH MINOR FIXES** — one required fix (the command-map page's stale F10 affordance
claim), which is a documentation/status-page correctness issue, not a behaviour defect in the
shipped code; the three optional items are prose-only and low-risk. No invariant, scope, or test-
coverage problems found. Re-review of the command-map fix alone (not the whole diff) is sufficient
before this goes to DoD.

### Review Confidence

Full read — plan, implementation log, roadmap entry, the full diff stat, and the touched-file
content for every item the plan called out as consequential (CLI flags, `ConnectionReporter` call
sites, tuning rendered output, mission-start/autoexec.cfg relocation, backlog obsolescence notes,
the rewritten threading test, server.py route removal, aircraft_client.py). All three subprojects'
format/lint/type/test commands and `invariant-check`/`command-map-check` were re-run directly in
this review, not taken from the implementation report.
