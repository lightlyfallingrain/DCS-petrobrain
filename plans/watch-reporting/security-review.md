## Security Deep Analysis: watch-reporting

Branch `feature/watch-reporting`, head `4051534`, branched from `main` at `3409b66`. Scope per
project direction: single-user, LAN-only, active development — this is a robustness/crash-surface
pass over new untrusted-shaped inputs, not a hardening audit of a public service.

### CVE Status

No new third-party dependencies. Both touched subprojects (`body-layer`, `audio-adapter`) stay
stdlib-only per their own `CLAUDE.md`; `threat.py` uses only `json`/`dataclasses`/`pathlib`/`typing`
from the standard library. Nothing to check against an advisory database.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/threat.py:113-139` | New data file parsed at import (`json.load` on `body-layer/data/threat_envelopes.json`) | **Fails loudly, not silently.** No `try`/`except` anywhere between the file open and the module-level `_LOADED` assignment, and nothing downstream (`contacts.py:98`, a plain top-level `from belief.threat import envelope_for`) wraps the import either. A missing file, truncated JSON, or a missing `entries`/`threat`/`range_max_m` key raises `FileNotFoundError`/`JSONDecodeError`/`KeyError` at process import time, which crashes `logger.py`'s startup with a visible traceback before any polling begins. This is the opposite of the failure mode the task asked me to check for — a truncated file cannot produce an empty table that quietly makes every engagement test return "no envelope." | None — this is the correct behaviour and matches the plan's "no fallback envelope, ever" rule (4a). |
| `body-layer/src/belief/crew_console.py:486`, `:1009` (also `:474`, `:477`, `:762`, all sharing `_CLOCK_REPORT_LABELS`) | Dict-index (not `.get()`) on a value that arrives over the audio-adapter → body-layer wire | **A genuine, if currently unreachable, crash path.** `_CLOCK_REPORT_LABELS[follow_clock]` (`_describe_token_for_confirm`, reached when a `follow` command lands in the confirm band) and `_CLOCK_REPORT_LABELS[clock]` (`_resolve_follow_target`'s no-match message) both index a 9-entry dict (`{1,2,3,4,8,9,10,11,12}`) with a plain `[...]`, not `.get(...)`. The wire-boundary validation in `logger.py`'s `_poll_transcripts` (lines ~1038-1045) checks only `isinstance(value, (int, str)) and not isinstance(value, bool)` for every `slots` value — it does not check that a `clock` value is one of the nine legal forward hours. Today this is unreachable through the intended path: `audio-adapter`'s `vocabulary.parse_clock` (`vocabulary.py:657-672`) only ever returns a value from `_CLOCK_WORD_TO_HOUR`, itself restricted to `FORWARD_CLOCK_POSITIONS`, so `command_matcher._parse_follow_slots` can never emit an out-of-range clock today. But the two processes are independently versioned local processes that get restarted separately (per `plans/watch-reporting/plan.md` Decision 2b-i, "a breaking change costs a coordinated restart") — a future vocabulary edit, a partial/rolling restart during development, or simply a bug in a later change to `parse_clock` would reach this `KeyError` with nothing between the wire and the crash. | Recommend a fix, not a blocker at this project's stage (see risk below). |
| `body-layer/src/logger.py:1109-1138` (`_run_crew_text_poll_loop`'s `while not stop_event.is_set()` body) | No exception isolation around per-poll dispatch | `_poll_f10_commands`/`_poll_transcripts` each wrap only their own outbound HTTP call (`get_f10_commands()`/`get_transcripts()`) in `try/except AircraftLayerError`/`AudioAdapterError`. Nothing wraps the subsequent dispatch into `CrewConsole.handle_command`/`handle_transcript`. If the `KeyError` above (or any other exception from a future command handler) fires, it propagates out of the `while` loop entirely. The poll loop runs on a background daemon thread (per `body-layer/CLAUDE.md`), so the process does not crash, but perception/belief/speech updates silently stop for the rest of the sortie — only a stderr traceback marks it, and the foreground REPL keeps accepting input and looking alive. | Same finding as above, one level up — the isolation gap is what turns a single bad transcript into "the whole poll loop is dead," not just "one command failed." |
| `audio-adapter/src/command_matcher.py` (`_parse_follow_slots`, `_phrase_match_ratio`, verb anchor) | Catastrophic-backtracking / unbounded-loop check on `follow`'s free-text slot parsing | No regex is used anywhere in this path (`parse_clock`/`parse_range_km`/`parse_descriptor` are plain `str.split()` + dict/set lookups; `_phrase_match_ratio` is `difflib.SequenceMatcher` over word lists bounded by the phrase table's own size, a few dozen entries). No adversarial-length blowup is reachable — a longer transcript makes `_phrase_match_ratio`'s scan linearly longer, nothing worse, and it is further bounded upstream by whatever a whisper transcription actually produces in practice. | None. |
| root `CLAUDE.md` module-independence invariant | body-layer ↔ audio-adapter shared vocabulary check | No violation. `command_matcher.py`/`vocabulary.py` import nothing from `body-layer`; `crew_console.py`/`voice_commands.py` import nothing from `audio-adapter` — the `slots` shape and the descriptor/clock/range vocabularies are hand-duplicated on each side exactly as the plan states (`crew_console.py:223-231`'s `_FOLLOW_DESCRIPTOR_OP_CLASSES` is annotated "hand-synced mirror... module independence"). Confirmed by grep across both changed modules' import blocks, not just read from the docstrings' own claims. | None. |
| `body-layer/data/threat_envelopes.json`, `docs/concept/Threat Database - ....html` | Extracted-data commit hygiene | `*_files/` is gitignored (`.gitignore`); only the 160 KB HTML and the JSON payload are tracked, no 1.8 MB asset directory landed in history. Provenance (`source`/`retrieved`/`provenance`/`units`) is read from the file's own header at runtime (`threat.py:142-147`), never restated as a literal that could drift. | None. |
| `body-layer/src/belief/contacts.py:1085-1163` (Decision 4/4f-ii engagement block) | LOS/altitude/range gating logic reachable from belief data, not external input | `envelope_for`/`los_clear`/`ownship` are all `None`-safe (`los_clear is None` → fail-open, `envelope_for` returning `None` → state cleared) — this is simulation-internal belief state, not attacker-shaped input, and every branch degrades rather than raises. No finding. | None. |

### SBOM

Not regenerated — no dependency manifest changed on this branch (stdlib-only in both touched
subprojects, confirmed above).

### Verdict

APPROVED, with one recommended (non-blocking) fix.

Nothing in this branch is exploitable in the sense this project's threat model cares about
(single-user, LAN-only, both ends of every seam are local processes the user runs themselves). The
one real finding is a robustness gap, not a security vulnerability: `_CLOCK_REPORT_LABELS[clock]`'s
plain dict index, three call sites deep from an HTTP wire boundary that validates type but not
range, sitting inside a poll loop with no exception isolation around command dispatch. It cannot
fire through the code that exists today (`parse_clock` constrains the value before it ever reaches
the wire), which is why this is not a blocker — but it is one bad value away from silently killing
belief/perception/speech for the rest of a sortie with no visible symptom beyond a stderr
traceback, which is exactly the "quiet failure" class this review was asked to look for.

### Recommended Fixes (non-blocking)

1. `body-layer/src/belief/crew_console.py:486,1009` (and the sibling reads at `:474,477,762`, for
   consistency even though those are token-keyed, not wire-keyed) — change `_CLOCK_REPORT_LABELS[clock]`
   to `_CLOCK_REPORT_LABELS.get(clock, str(clock))` so an out-of-range value degrades to a plain
   number in the spoken/confirm text instead of raising.
2. `body-layer/src/logger.py:1038-1045` (`_poll_transcripts`'s slot validation) — add a membership
   check for `slots["clock"]` against the same forward-hour set `vocabulary.
   FORWARD_CLOCK_POSITIONS` names on the audio-adapter side (hand-mirrored, matching this branch's
   own established pattern for `_FOLLOW_DESCRIPTOR_OP_CLASSES`), so a wire violation is dropped at
   the boundary rather than reaching a dict index three calls later.
3. `body-layer/src/logger.py:1116-1120` (`_run_crew_text_poll_loop`) — wrap the
   `_poll_f10_commands`/`_poll_transcripts` dispatch calls (or just the `CrewConsole` calls inside
   them) in a `try`/`except Exception: logger.exception(...)` matching the log-and-continue posture
   already used for the HTTP calls one line above, so a future defect in any command handler costs
   one skipped command, not the rest of the sortie's perception.

None of these block DoD at this project's current scope — they are cheap, and worth doing in the
same branch if there is appetite, otherwise fine to carry to `todo/todo.md` as a follow-up.
