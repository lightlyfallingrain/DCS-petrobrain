---
name: binocular-optic-review-fix
description: How the D4 command-interrupt wiring gap was closed without touching optic_policy.py, and why the fix point was _handle_utterance not handle_line.
metadata:
  type: project
---

`plans/binocular-optic/review.md`'s required fix 1: `CrewConsole._note_player_command()` (which
the poll loop diffs to decide whether to `lower_binoculars`) was called only from
`handle_f10_command`, so a typed free-form request or a voice utterance that fell through to
`handle_line` never lowered the binoculars, while the same intent as an F10 token did.

**The fix point that generalizes across surfaces without double-counting is `_handle_utterance`,
not `handle_line`.** `handle_line` is called both directly (typed REPL input) and recursively (from
`_act_on_voice_decision`'s `"fallthrough"` disposition) — but it only ever calls `_handle_utterance`
once per invocation, and `_handle_utterance` has exactly one caller (`handle_line`). So putting the
counter increment at the top of `_handle_utterance` covers both the typed and voice-fallthrough
paths with one call site, structurally incapable of double-firing. `handle_f10_command`'s own call
stays separate and correct, since token dispatch never routes through `_handle_utterance` — the two
surfaces (free text vs. token) are genuinely distinct call trees with no shared ancestor closer than
"the player did something", so one call site per surface (not one global call site) is the right
shape, not a shortcut.

**Confirming a test actually catches a regression**: stash (or scratch-copy) just the source fix,
re-run the specific test, confirm red, restore. Don't trust "the test passes with the fix" alone —
the old `test_a_player_command_lowers_the_binoculars` also "passed" while checking two unrelated
facts, which is exactly how the gap went uncaught.

See also [[feedback_agent_memory_path]], [[project_watch_as_standing_mode]] for other cases of "the
handler that looks like the shared ancestor isn't, the internal-only method is."
