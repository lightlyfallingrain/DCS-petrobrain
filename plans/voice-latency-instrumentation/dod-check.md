# Definition of Done: voice-latency-instrumentation

**Scope of this verdict**: `feature/voice-latency-instrumentation` at tip `47952413001de6a243bbc0ed6508379c78ad9ded`
("Reviewer: approve BL-B87/BL-B88 fix commit"). **The branch has moved one commit past this since
dispatch** — `11e76349` ("Sortie feedback F8: speech async, one mouth; layers don't wait on each
other"), a docs-only append to `docs/acceptance/2026-10-20-sortie-feedback.md` (confirmed:
`git show --stat 11e76349` touches only that one file, 20 insertions). That commit is new flight
feedback captured per this project's capture-then-explore rule, not yet explored or planned — it is
**outside this review's scope**, and this verdict does not cover it. If anything merges after this
point, re-run this check against the new tip.

**Not merged.** Per dispatch instruction: the user approved merging this after
`feature/9k113-narrow-search` merges first. This is the DoD gate, not the merge. **Live acceptance is
a later flight** (measuring the readback delay with the new instrumentation) — not solicited here.

## Code Quality — PASS

Subprojects touched, determined from the diff (`git log --no-merges --name-only
9d83b910^..HEAD`, the architect-plan commit to the reviewed tip), not from memory: **audio-adapter,
aircraft-layer, body-layer** (plus `docs/`, `plans/`, `.claude/` bookkeeping — not code
subprojects). All three run their own format/lint/type/test commands per their own `CLAUDE.md`
"Commands" sections, each run myself inside this worktree:

| Subproject | ruff format --check | ruff check | mypy --strict (cd'd in) | pytest |
|---|---|---|---|---|
| audio-adapter | pass (34 files) | pass | pass (16 source files) | **343 passed, 2 skipped** |
| aircraft-layer | pass (67 files) | pass | pass (25 source files) | **377 passed, 2 deselected** |
| body-layer | pass (163 files) | pass | pass (68 source files) | **2269 passed, 4 xfailed** |

Matches the Implementer's and Reviewer's own reported numbers (small pytest-count drift across the
three body-layer check rounds is from each round's own test additions, not regression).

**aircraft-layer's 2 deselected tests** (`tests/test_collector_server_accept_errors.py`) are an
environmental sandbox artifact, confirmed unrelated to this diff: `git diff` against both that test
file and `src/collector/server.py` (the code it exercises), taken from the architect-plan commit to
the reviewed tip, is empty. Reproduced directly in this DoD pass (not re-trusted from
implementation.md/review.md): a bare `pytest tests/test_collector_server_accept_errors.py -q` here
fails `test_close_during_a_blocked_accept_ends_the_loop_cleanly` with `assert not
thread.is_alive()` — a `close()`/`join(5s)` race on a fixed-port (7790) bind, the same symptom the
Reviewer reproduced (3/3 runs), not quite the `OSError: Address already in use` the Implementer's
own account describes. Both are consistent with "sandbox-dependent, not a real conflict any running
process holds" — `ss -tln` here shows nothing listening on 7790 either — but the exact failure mode
is itself sandbox-dependent, worth stating plainly rather than repeating one fixed description.

No unhandled errors/panics on data paths (Security's deep analysis traced every new logging call
site specifically for this — `_log_latency`'s internal catch-and-disable, `audio_sender.py`'s
worker-thread logging matching Python's own `Handler.handleError` swallow, `crew_console.py`'s
pre-existing broad `except Exception` around the speech-log sink call). No debug output or stray
TODOs introduced (Reviewer's own grep-based `/invariant-check` pass, confirmed clean). All new files
staged — confirmed via `git status --porcelain` at the reviewed tip (empty before this DoD pass's
own edits).

## Scope & Correctness — PASS

Implementation matches `plans/voice-latency-instrumentation/plan.md`, including its "Decisions"
override block (user, 2026-10-20): Stage 6 covers every positional readback, not just
`select_target` — confirmed in code (`_handle_select_target`, `_handle_mark_target`, `_handle_step`,
`_handle_follow`, `_handle_watch_nearest`, `_handle_report` all route through `_speak_or_defer`,
`body-layer/src/belief/crew_console.py`); the dispatched command token is logged as the cheap
template substitute, not the full `OutgoingSpeech.template`; no playback-start feedback seam was
added; `--latency-log` records failed attempts too (`outcome:
"synthesis_failed"|"delivery_failed"|"recognition_failed"`, confirmed by reading `server.py`).
`watch_nearest`/`watch_nearest_air_defence`'s inclusion beyond the plan's literally-named set is
justified (shares `follow`'s own renderers exactly) and was independently verified by the Reviewer,
not just asserted by the Implementer.

No unplanned scope added silently — Reviewer's three rounds and this DoD pass's own `git diff`
(`9d83b910^..HEAD`) confirm the touched file set matches `implementation.md`'s own accounting
exactly. No `CLAUDE.md` invariants violated — world-model seam untouched, no DCS-install write
path (all new logs are operator-chosen `--*-log PATH` files, same posture as every existing
`--*-log` flag), no omniscience boundary crossed (correlation id/timing fields are pure
instrumentation, never a belief-state input). All new files staged (`git status --porcelain`
clean at the reviewed tip).

## Testing — PASS

Core logic is covered by tests added across all three subprojects (full enumeration in
`implementation.md`'s "Tests Added" section) — spot-verified a sample myself rather than taking the
count on faith: `test_pending_positional_replies_caps_and_drops_oldest_warning_logged_once`,
`test_truncated_last_line_is_skipped_and_all_other_rows_still_join`, and the three
`test_crew_console_mission_memory.py` tests for Required Fix 1 all exist and pass in this worktree's
own tree. Tests are meaningful, not decorative — both the Reviewer's own re-review and this DoD
pass's spot-checks confirm mutation-testing was actually performed (sha256 matches pre/post patch,
specific "fails for the stated reason" assertions), not merely claimed. No existing tests broken —
the ten `test_crew_console.py` tests that needed fixing for Stage 6's real channel-occupancy
interaction are a genuine behaviour interaction, not a defect papered over (confirmed by reading
`implementation.md`'s own account and spot-checking two of the ten).

## Documentation — PASS

Reviewer findings addressed: Required Fix 1 (`mark_target`'s deferred-write loss) — fixed, re-reviewed,
APPROVED. BL-B87/BL-B88 (Security's deep-analysis findings) — fixed, reviewed, APPROVED, and both
filed as their own `body-layer/ROADMAP/BL-B87.md`/`BL-B88.md` entries, already `#status/done`.
Non-obvious behaviour explained: `body-layer/CLAUDE.md` gained a dedicated "Voice latency
instrumentation" paragraph (read directly, confirmed accurate against the code); `audio-adapter/
CLAUDE.md` and `aircraft-layer/CLAUDE.md` each gained matching short additions (per
`implementation.md`); `tools/join_voice_latency.py`'s own module docstring (rendered by `--help`,
executed myself — see below) carries the full "how to read a timeline" explanation rather than
leaving that only in the plan.

## Security — PASS

`plans/voice-latency-instrumentation/security-plan-review.md`: **APPROVED**. `security-review.md`
(deep analysis): **APPROVED**, with two low-risk findings filed as `BL-B87`/`BL-B88` — both already
fixed and re-reviewed APPROVE in this same branch (not left open).

## Performance — PASS (MONITOR)

`plans/voice-latency-instrumentation/performance-review.md`: **APPROVED — MONITOR**. No required
mitigation. Two watch items named for a future pass if real-flight evidence warrants it (not
blocking): `_pending_positional_replies`'s self-limiting-but-uncapped growth (now mooted by
`BL-B87`'s cap, added after this performance review ran — the cap is a stricter guarantee than the
performance review asked for) and `push_speech`'s pre-existing (not newly-introduced) blocking call
on the poll thread.

---

## How to turn the logs on and read them

Three flags, each a true no-op when absent (same posture as every other `--*-log` flag in this
project). All three commands below were run by me, in this worktree, to confirm the flag names and
help text are real, not reconstructed from the plan:

**1. audio-adapter capture process** (`run-scripts/run-audio-capture.sh` — wherever the microphone
is; the Windows box in flight): add `--latency-log <path>`.

```sh
# run-scripts/run-audio-capture.sh, after the existing arguments:
python.exe -m audio_adapter.capture --adapter-url http://$AUDIO_ADAPTER_IP:7795 \
    --sox-binary $SOX_PATH --ptt dcs \
    --latency-log logs/capture-latency.jsonl
```

(confirmed via `python -m audio_adapter.capture --help`: *"write one JSON line per clip
(correlation id, PTT-release timestamp, post-to-adapter duration, outcome) -- joined with
body-layer's own logs by tools/join_voice_latency.py. Omitted (default): a true no-op."*)

**2. audio-adapter server process** (`run-scripts/run-audio-adapter.sh` / the Windows variant —
wherever Whisper/Piper run; the Mac, per F1's own "latency settled" decision): add
`--latency-log <path>`.

```sh
# run-scripts/run-audio-adapter.sh, after the existing arguments:
pushd ../audio-adapter/ && PYTHONPATH=src .venv/bin/python -m audio_adapter \
    --host 0.0.0.0 \
    --whisper-model ~/whisper-models/ggml-small.en.bin \
    --target aircraft-layer --aircraft-layer-url http://$DCS_COLLECTOR_IP:7791 \
    --latency-log logs/adapter-latency.jsonl
popd
```

(confirmed via `python -m audio_adapter --help`: *"write one JSON line per /speak and /transcribe
attempt (synthesis/delivery/recognition/match durations, correlation id, outcome -- including
failures)."*)

**3. body-layer's logger** (`run-scripts/run-crew-text.sh` — already has `--speech-log`; add
`--belief-truth-log` alongside it, a pre-existing flag this plan only widened with new fields):

```sh
# run-scripts/run-crew-text.sh, alongside the existing --speech-log line:
    --speech-log logs/dcs-speech.jsonl \
    --belief-truth-log logs/belief-truth.jsonl \
```

**After the flight**, copy all the JSONL files off whichever machine wrote them, then from
`body-layer/`:

```sh
python tools/join_voice_latency.py \
    --latency-log capture-latency.jsonl --latency-log adapter-latency.jsonl \
    --speech-log dcs-speech-<stamp>.jsonl \
    --belief-truth-log belief-truth-<stamp>.jsonl
```

Executed myself during this DoD pass against four hand-built JSONL files (one row per stage,
synthetic — not a live flight, see "Acceptance boundary" below) to confirm the command actually
runs and prints a sane joined timeline, not just that `--help` parses:

```
$ python tools/join_voice_latency.py \
    --latency-log capture-latency.jsonl --latency-log adapter-latency.jsonl \
    --speech-log dcs-speech-demo.jsonl --belief-truth-log belief-truth-demo.jsonl

=== demo-corr-1 ===
  capture    outcome='sent' clip_duration_s=1.2 post_duration_s=0.026 t_ptt_release_wall=999.9
  transcribe outcome='ok' transcribe_duration_s=0.21 match_duration_s=0.004
  transcript heard='set target armor 12 oclock' disposition='act' acted_token='select_target' now_sim=None
  spoken     text="Target, armor, 12 o'clock." push_duration_s=0.022 t_sim=42.0
  speak      outcome='ok' synth_duration_s=0.31 deliver_duration_s=0.09

1 correlated utterance(s); 0 row(s) with no id. 0 malformed line(s) skipped.
```

Pipeline-ordered regardless of the order the four `--*-log` flags were given, every duration
attributed to the stage that measured it, no cross-machine `t_wall` subtraction — exactly as the
module docstring describes.

Full `--help` text (reproduced in full in this DoD pass, not reconstructed) explains how to read a
printed timeline: stages print in **fixed pipeline order** (`capture` → `transcribe` → `transcript`
→ `spoken` → `speak`), never by comparing `t_wall` across the Mac/Windows machine boundary; only the
`*_duration_s` fields (each one process's own `time.monotonic()` bracket) are the trustworthy
numbers; a stage that never arrives for a given `correlation_id` is flagged as "never reached:
`<stage>`", which is itself diagnostic.

## Acceptance boundary — what this milestone's fixtures structurally cannot reach

Everything above passed on a synthetic round trip (Reviewer's own construction, through real code
paths) and unit-level tests. That proves the instrumentation mechanism works end to end, and that
Stage 6's defer-and-redraw fires correctly on the modeled-busy case. **It cannot show where the
real F8 delay actually is** — that needs a live flight with the three flags above turned on, reduced
with `tools/join_voice_latency.py`. Two things specifically no fixture can settle:

1. **Stage 6 only fixes the *modeled-busy* case** (a readback queued behind another already-spoken
   utterance). The user's own read of F8 — *"the real problem here is the many second delay"* —
   reads as more consistent with raw STT/network/TTS latency while the channel was modeled *clear*,
   which Decision 2 deliberately left unaddressed pending exactly this evidence.
2. **The audio-adapter queue dwell time** (a recognised transcript sitting in the queue before
   body-layer's ~1s poll drains it) has no measured field anywhere in this chain yet.

This is also this project's `select_target`/F8 analogue of the acceptance-boundary lesson named in
this role's own template: a fixture can confirm the *mechanism* did what it says, never whether it
targets the thing the pilot actually experienced as wrong.

**Recorded as `#needs-flight` on `body-layer/ROADMAP/BL-W41.md`**, not a merge blocker — the next
flight should turn on all three `--latency-log`/`--belief-truth-log` flags and run the reducer; that
single flight both clears the tag and answers whether Decision 2 needs reopening. Not solicited from
the user now, per dispatch instruction (live acceptance is a later flight).

## Bookkeeping

- `body-layer/ROADMAP/BL-W41.md` created (new, `#status/in-progress #needs-flight`) — this feature
  had no milestone-level roadmap entry yet; `BL-B87`/`BL-B88` (the security-finding entries) already
  existed and are unchanged by this pass.
- `body-layer/ROADMAP/body-layer-roadmap.md` index updated with one new `[[BL-W41]]` line.
- ID minted by hand, not by `.claude/scripts/mint-id.sh --list`'s local answer: this worktree's view
  of `body-layer/ROADMAP/` stops at `BL-W39` (its fork point predates `main`'s later merge), but the
  live main checkout (`/mnt/e/DCS-petrobrain/body-layer/ROADMAP/`) already has `BL-W40.md`
  ("Landmark words, not proper names, in spoken callouts", merged `83bf80bc`) — confirmed identical
  across main and the `feature/9k113-narrow-search` worktree. Checked every other active worktree's
  `ROADMAP/` directory (`git worktree list`, then read each one's files directly) for a higher
  unmerged `BL-W`/`BL-` number before picking `BL-W41`; none found higher than 40.
- Notes harvest run (`/notes-harvest voice-latency-instrumentation`); one non-duplicate, non-obvious
  insight added to `notes/planning-and-process-lessons.md` (a defer-mechanism retrofit can bundle an
  un-executed action into the deferred half when a handler's action and acknowledgment were written
  as one step — the general shape of Required Fix 1). The other three candidates (the sandbox test
  failure, the `_handle_report` defensive `enrichment is None` check, the channel-occupancy
  behaviour-change note) were skipped: the first is environment-specific noise, the second is
  already covered by `notes/mission-start-and-reset-patterns-bl-15.md`'s existing "closure captures
  stale state" / "check every way the system can speak" lessons, and the third is already documented
  in `body-layer/CLAUDE.md`'s own committed text.

## Verdict

**DoD: PASSED** at tip `47952413001de6a243bbc0ed6508379c78ad9ded`. Not merged (per instruction).
Live acceptance outstanding, tracked via `#needs-flight` on `body-layer/ROADMAP/BL-W41.md`, not
solicited now.
