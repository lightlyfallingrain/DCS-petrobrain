---
name: project_voice_vocabulary_lives_in_audio_adapter
description: Spoken command vocabulary (phrase tables, verb anchoring, fuzzy matching) lives entirely in audio-adapter/src/vocabulary.py + command_matcher.py, not body-layer -- body-layer only dispatches a resolved token
metadata:
  type: project
---

When a task says "wire a command into voice," the vocabulary (phrase table, verb anchor
derivation, fuzzy matching) lives in `audio-adapter/src/vocabulary.py` and
`audio-adapter/src/command_matcher.py` -- never in `body-layer`. `body-layer`'s
`belief/crew_console.py` only ever receives an already-resolved `{token, match_ratio, confidence,
verb_anchored, ambiguous, slots}` tuple (`CrewConsole.handle_transcript`'s signature) and dispatches
it through `handle_command`. This split is deliberate module independence (root `CLAUDE.md`'s
rule) and is documented at the top of both `vocabulary.py` and `command_matcher.py`.

**Practical consequence for adding a new voice command whose handler already exists in
`crew_console.py`:** the only work is a `vocabulary.py` edit (new token in `TOKENS`/`VOICE_ONLY_
TOKENS`, phrasings in `PHRASES`). Nothing in `body-layer` needs touching if its dispatch/readback
already exists (check `DISPATCHED_COMMAND_TOKENS` first -- it is often already there from an
earlier stage that built the handler but not the voice surface).

**Readback reaching speech is automatic, not something to add.** `CrewConsole.handle_command`'s
tail call `self._print(lines, now_sim)` is the single funnel every dispatched token's return value
goes through to both the in-cockpit text overlay and the TTS `speech_client` push. A handler that
returns a one-line readback string needs no special wiring to be spoken -- confirm this by reading
`_print`'s docstring before assuming a gap exists.

**Collision-checking a new phrase pair:** `audio_adapter.command_matcher.VERB_ANCHOR_WORDS` is
derived automatically from every phrasing's first word (not hand-maintained), so check it directly
rather than guessing. For the fuzzy-match collision check itself, `difflib.SequenceMatcher` over the
normalised word lists (`vocabulary.normalize_for_match`) is a good enough proxy for
`_phrase_match_ratio` to catch a real collision before writing any test -- run it against every
existing `PHRASES` entry, not just a few you'd expect to be close.

See [[feedback_agent_memory_path]] for the worktree-root memory-path rule this file follows.
