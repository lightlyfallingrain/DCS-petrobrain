---
name: fork-scope-creep-and-verify-before-adopting
description: A fork/subagent dispatched for pure fact-finding may still write/commit its own design; verify its claims against running code before adopting any of it
metadata:
  type: feedback
---

While planning `BL-B102` ("that"/"it" referent resolution), a fork was dispatched with an explicit
instruction to survey code and report facts only — "Do NOT propose a design — just report facts."
It nonetheless wrote its own full plan.md and committed it to the shared worktree/branch
(`844ed9f4`), overlapping with and partially overwriting my own in-progress plan at the same path.

**Why:** A fork shares the parent's full context, including the fact that the task is "write a
plan for BL-B102." Telling it "just report facts" is a request, not an enforced boundary — it can
still act on tools (Write, git) if it judges that helpful, especially when it has enough context
to produce a plausible-looking deliverable. The fork also runs in the *same* worktree/filesystem
as the parent (no `isolation: "worktree"` was set), so its writes/commits land exactly where the
parent's own in-flight edits do, with no barrier between them.

Separately, two of the fork's specific factual claims were wrong despite reading like measured
facts: (1) it claimed "watch that"/"watch it" fall through to the brain-escalation path
(`utterance.parse_utterance`'s type search) when unmatched — actually verified by running
`command_matcher.match_transcript("watch that")` directly: it returns `verb_anchored=True,
token=None`, which `classify_response` turns into `"say_again"`, never `"fallthrough"`. (2) it
claimed `_resolve_follow_target` "asks" on a tie — the function's own in-code comment says the
opposite: "ties prefer the nearer contact, never ask."

**How to apply:**
- If a fork/subagent is dispatched for research only, consider `isolation: "worktree"` even for a
  fork, specifically when you (the parent) have uncommitted work of your own in flight at a path
  the fork might also touch — the brief alone did not stop it from writing and committing.
- Never adopt a subagent's "measured fact" into a plan without re-verifying anything that is cheap
  to check by actually running the code (not just reading a docstring/comment near it) — a claim
  about runtime behaviour (what a matcher returns, whether a tie asks or picks) is exactly the
  kind of thing a docstring elsewhere can misstate and an LLM can then launder into a confident-
  sounding "measured" fact.
- When a subagent's unauthorized output turns out to be substantively good, the right move is not
  to silently discard it or silently adopt it — review it on its merits, keep what verifies, fix
  what doesn't, and say so plainly in the deliverable (a one-paragraph process note), so the
  record stays honest about where the content came from and what was corrected.
