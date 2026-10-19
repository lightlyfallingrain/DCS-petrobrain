### Performance Review

Batch: `feature/radio-check` (BL-B82 no-scan-on-ground, BL-B81 radio-check/greeting). Diff base
`main` @ `d1126570`, reviewed tip `2f1c8d8c` (body-layer `01a69ec7`, audio-adapter `49c24eb1` +
the two review-fix commits folded in). Scope calibration: this is Petrobrain Runtime-adjacent
voice/perception code running live during a sortie, but **no hard real-time budget applies yet**
(root `CLAUDE.md`: that constraint starts once Petrobrain Runtime work begins) — the applicable
bar is "bounded, event- or poll-driven work, no per-request allocation on a hot path," not a frame
budget. `.claude/scripts/gq.sh` and `memory-search.py` queried before concluding anything below;
results folded into the relevant sections.

### Findings

#### BL-B82 on-ground perception gate (`logger.py`, both poll loops)

- **Location:** `PerceptionLogger.run_once` (line ~324) and `ConsolePerceptionRunner.run_once`
  (line ~691) — the observation-gathering comprehension is now wrapped in
  `... if ownship.alt_agl_m > ON_GROUND_AGL_THRESHOLD_M else []`.
- **Risk:** none. Confirmed by reading the diff directly: the gate adds exactly one float
  comparison per poll and, when it fires, **replaces** a full per-source `poll()` call (the
  expensive branch — naked-eye visibility gates, hybrid association, clustering) with an empty
  list literal. This is a net reduction in per-poll cost while on the ground, not an addition.
  `ContactStore.tick`/`ingest([], ...)` still run unconditionally, so the existing decay/lifecycle
  machinery is untouched by this change — no new full-dataset iteration, no new allocation, no
  change to frequency (still one poll, same cadence as before).
- **Action:** NONE.

#### `CrewConsole.on_ground` field refresh (`crew_console.py`, `logger.py`'s poll loops)

- **Location:** `crew_console.on_ground = runner.last_ownship_state.alt_agl_m <=
  ON_GROUND_AGL_THRESHOLD_M`, refreshed every poll alongside `enrichment`; read by
  `handle_command`'s new look-command branch (`token in _LOOK_COMMAND_TOKENS`, a frozenset
  membership test, O(1)).
- **Risk:** none — one bool assignment and one frozenset lookup per poll/command, same order of
  cost as the pre-existing `enrichment` refresh this mirrors.
- **Action:** NONE.

#### `audio-adapter` `command_matcher.match_transcript` — the greeting branch and "good" anchoring

This is the one the implementer flagged (`implementation.md`'s "near-miss checks") and the task
asked to be quantified rather than taken on the report's word. Measured directly against the
actual `command_matcher.VERB_ANCHOR_WORDS`/`VERB_FLOOR`/`_PHRASE_WORDS` in this worktree (Python
3.11, `timeit`, 5,000–20,000 calls per figure, median-stable across repeats) — not estimated.

**The flagged premise does not hold at the magnitude claimed, and the reason is measurable, not
just reasoned:** `difflib.SequenceMatcher(None, "good", "look").ratio() == 0.5`, which is **already
`>= VERB_FLOOR` (0.5)** against the *pre-existing* anchor-word set — i.e. `"good ..."` already
anchored before this feature, via a coincidental tie with `"look"`, and therefore already paid the
full non-trivial branch chain + phrase-table scan cost on every sentence starting with "good". This
is confirmed by reconstructing the pre-change `VERB_ANCHOR_WORDS` (every `PHRASES` entry except
`greeting`/`radio_check`) and recomputing `_verb_anchor_ratio("good")` against it: `0.5`, not
rejected. Root `CLAUDE.md`'s "measure n before scaling anything by n" / "a reasoned count is the
figure most likely to be wrong by 2x" applies here directly — the implementer's own report reasoned
from "`'good'` is a new anchor word" without checking whether the *old* set already admitted it by
coincidence; it did.

Measured delta, OLD (anchor set + phrase table reconstructed without `greeting`/`radio_check`,
greeting branch disabled) vs NEW (actual current code), same transcripts, same machine:

| transcript | OLD µs/call | NEW µs/call | delta |
|---|---|---|---|
| `"good job keeping that altitude"` (ordinary chatter, false anchor either way) | 661 | 678 | **+17 µs (+2.6%)** |
| `"the weather is fine today"` (no anchor, control) | 629 | 665 | +36 µs (+5.7%, phrase-table size grew by 5 entries out of ~116) |
| `"good morning petrovich"` (real greeting) | 789 | 148 | **−641 µs** (new slot branch short-circuits before the phrase table — a win, consistent with the existing `slot-branch-beats-phrase-table` finding in this role's own memory) |
| `"radio check"` (real new command, previously unrecognised) | 136 (rejected, false reject) | 960 | +824 µs, but this is *intended* new work — a real command must now resolve, where before it silently fell through as free speech |
| `"scan left"` (pre-existing, unrelated token) | 865 | 881 | +16 µs (phrase-table size growth only) |

- **Risk:** negligible at this call frequency. `match_transcript` runs once per spoken utterance
  (PTT release → one `/transcribe` call → one `match_transcript` call), not per poll and not per
  frame — bounded by human speech cadence (seconds) and dominated by whisper transcription itself
  (hundreds of ms–seconds, per `audio-adapter/CLAUDE.md`). A sub-millisecond matcher cost, moving by
  tens of microseconds, is not observable against that. The one two-digit-percent apparent jump
  (`"radio check"`, +824 µs) is the cost of correctly recognising a command that previously fell
  through unrecognised — not a regression to guard against, the point of the feature.
- **Action:** NONE. Already covered by the module's own documented `VERB_FLOOR`/`MATCH_FLOOR`
  asymmetry (a false anchor costs one extra scoring pass that almost always rejects anyway; a false
  *reject* is irreversible) and by `test_good_job_degrades_rather_than_falsely_resolving_a_greeting`
  / `test_radio_check_does_not_falsely_fire_on_report_or_check_style_speech`, which pin the
  correctness outcome this review is not re-litigating.
- **Correction worth recording, not a required fix:** the implementer's own framing ("'good' became
  a new verb-anchor word, so ordinary sentences starting with 'good' now cost an extra
  phrase-scoring pass") overstates what changed — those sentences already paid that cost pre-change.
  What's actually new is ~17–36 µs of phrase-table growth (5 more entries scanned, out of ~116) for
  every transcript that reaches the final scan, which is immaterial at this frequency. Saved to
  agent memory below so the next review of this file does not re-derive it from scratch or repeat
  the overstated framing.

#### `handle_line`'s two new literal/regex checks (`crew_console.py`)

- **Location:** `_RADIO_CHECK_PATTERN`/`_GREETING_PATTERN`, two compiled-regex `.match()` calls
  ahead of `_handle_utterance`, mirroring the existing `!inject-urgent`/`!voice` special cases.
- **Risk:** none — typed crew-text is human-initiated (REPL input), not a poll-loop or per-frame
  path; two pre-compiled regex matches against a short line is immaterial at any realistic typing
  cadence.
- **Action:** NONE.

### Verdict

APPROVED

No required or deferred mitigations. BL-B82's gate is a net performance improvement on the ground
(less work, not more). BL-B81's new dispatch paths (typed-line regex, command-token branches,
voice-side slot branch) are all bounded, human/event-cadence work; the one place a cost increase is
measurable (`command_matcher`'s phrase-table growth) is sub-millisecond and the implementer's own
flagged concern was found, by direct measurement, to be smaller than reasoned — recorded as a
correction, not escalated.
