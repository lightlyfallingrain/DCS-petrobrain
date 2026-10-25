## Security Deep Analysis: BL-B102 ("that"/"it" referent resolution)

Branch `feature/that-it-referent`, tip `58e66a8e3de8b0f2df04dfff7d6edd55b5552750` (fast-forwarded
into this worktree, clean). Diff reviewed: `dcfaa705..58e66a8e` (11 source/test files,
`body-layer/src/belief/referent.py` new, `crew_console.py`/`callouts.py`/`speech.py`/`body.py`
threading, `audio-adapter/src/vocabulary.py`/`command_matcher.py` additive slot parsing).

### Dependency Status

No dependency change. Confirmed independently of the plan review: `git diff` touches no
`pyproject.toml`/manifest in either subproject, and `referent.py`'s own imports are
`collections.abc`, `dataclasses`, `typing`, `tuning`, `belief.speech` — all already-present
first-party/stdlib. The plan's security-plan-review (APPROVED, no new dependency) still matches
what shipped.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/referent.py` (whole file) | New mutable in-memory state (`ReferentMemory`) | Pure in-memory list, pruned to `REFERENT_WINDOW_S` (15–180s tunable) on every `record`/`recent`/`last` call. Growth is bounded by the window, not by an external counter — but the only writer is `CrewConsole._print`, itself rate-limited by `SPEECH_RATE_WPS`/the poll loop, and the only trigger is the pilot's own voice in a single-user LAN threat model. No externally-reachable flood path. Matches the plan review's own advisory (not a blocker there either). | None |
| `body-layer/src/belief/referent.py:144-236` (`resolve_referent`) | Reads `ContactStore`/`Mention` only | Confirmed the no-omniscience boundary holds: no import of `belief.percept.Observation`, no DCS truth, no ground-truth field anywhere in this module. Only `store.contact(id)`/`store.groups`/`group_membership_state` (belief-layer) are touched. Satisfies the orchestrator's specific check. | None |
| `audio-adapter/src/vocabulary.py:1268-1289` (`parse_referent`/`REFERENT_WORDS`) | Transcript parsing | Bounded: a 2-tuple membership check over `normalize_for_match(text).split()`. No regex, no backtracking risk, no length amplification. | None |
| `audio-adapter/src/command_matcher.py` (`_parse_where_is_it_slots`/`_parse_mark_slots`/`_parse_watch_slots`, new `match_transcript` branches) | Transcript parsing | Same shape as the five pre-existing slotted parsers (`difflib.SequenceMatcher` on short fixed strings, dict-of-bounded-values output). No new parsing idiom, no unbounded loop over attacker-controlled length (transcript length is already bounded upstream by the audio-adapter's own capture/recognition pipeline, unchanged by this feature). | None |
| `body-layer/src/belief/crew_console.py` (full diff, 517 lines) | `_print`/`_speak_or_defer`/`_pending_mentions`/handler wiring | Grepped the diff for `eval`/`exec`/`subprocess`/`os.`/`open(`/`socket`/`pickle`/`yaml`/`__import__` — zero hits. All additions are dict/list bookkeeping and dispatch, no new I/O, no new file path, no new network call. | None |
| `body-layer/src/belief/callouts.py`, `speech.py`, `body.py` | `last_spoken_mention` field, `NO_REFERENT` template, `where_is_it_slots` clear | Same: pure in-memory field assignment and a new fixed-string template entry (`_UNABLE_TEMPLATES`). No new boundary. | None |
| `/security-grep` sweep over changed files | type-ignore / error-suppression / credentials / eval / subprocess / network / file-write / `assert`/`raise` categories | The only hits inside files this feature touches (`crew_console.py:1620`, `:4861`, `body.py:603`) are **pre-existing** lines unmodified by this diff (`git diff` confirms they are not in the `+` lines) — a `# type: ignore[misc]` on `__init__` reassignment and a pre-existing debug-sink `except Exception: # noqa`. Not introduced by BL-B102. | None |
| No-prompt-injection surface | Voice transcript → command token path | Confirmed independently of the plan review's claim: referent resolution runs entirely inside `command_matcher`'s slotted branches and `resolve_referent`'s pure belief query, both reached *before* `match_transcript`'s phrase-table fallthrough to brain escalation. No new text is carried into a place an LLM later reads as instructions — the brain-layer HTTP seam is untouched by this diff (`brain_client.py`/`brain_reply.py` do not appear in the changed-file list). | None |

### LAN-port-scanner surface

No new listening socket, no new HTTP endpoint, no change to any existing endpoint's input
handling. Not applicable to this feature.

### Verdict

APPROVED

### Required Fixes

None.

### Passed to Reviewer / already addressed

- The plan's own security-plan-review already passed through one non-security item (the "nearest
  wins, never ask" tie-break's player-experience consequence) — Reviewer's `review.md` already
  covers this as an accepted design decision (Decision 2/5), not a security question. Not
  re-verdicted here, consistent with this role's scope boundary.

### Findings requiring filing

None. No finding in this analysis produced a risk-matrix choice or an unresolved advisory —
every item above is a direct confirmation (either "no such pattern exists" or "pattern is
pre-existing and unmodified"). Nothing to mint an ID for.
