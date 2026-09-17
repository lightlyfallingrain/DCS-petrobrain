---
name: tts-voice-output-stages1-4-approved
description: srs-adapter subproject (BL-10 first slice) reviewed and approved; winsound mypy claim reproduced directly, agent-memory commit flagged as side-quest violation
metadata:
  type: project
---

Reviewed `feature/tts-voice-output` stages 1-4 (`ac9cce5`..`3994d0a`): new `srs-adapter/`
subproject + aircraft-layer `AudioPlaybackSender`/`POST /audio/play` + body-layer
`SrsAdapterClient`/`speech_client`. Verdict: APPROVED, no required fixes.

**The implementer's `winsound` mypy claim was reproduced directly, not taken on trust** — wrote a
throwaway `try/except ImportError` file and a throwaway static `sys.platform == "win32"` file,
ran `mypy --strict` on both. The `try/except` form genuinely fails (`Module has no attribute
"PlaySound"`); the static form genuinely passes. This is the kind of claim (item 2 in the review
brief) that's easy to just believe from a docstring — worth the ~2 minutes to check when a plan
explicitly asks "verify this reasoning holds, try breaking it."

**Module independence held up on direct grep, not just docstring claims**: grepped both
`body-layer/src/belief/srs_client.py` and `srs-adapter/src/aircraft_client.py` for cross-refs to
each other's subprojects — only docstring mentions, no actual `import` statements. `srs-adapter/pyproject.toml`
declares `dependencies = []`. See [[project_module_independence_rule]] (auto-memory) for the
standing rule this checks against.

**Process flag, not a required fix**: commit `3994d0a` on this feature branch touched
`.claude/agent-memory/implementer/` — a non-code, cross-cutting bookkeeping change that
AGENTS.md's side-quest rule says belongs in a disposable worktree on `main`, not the feature
branch. Content was accurate; only the commit's *location* was the issue. Flagged as optional,
left to the user's judgment call per the task brief's own framing.

**Verification-numbers check**: re-ran all three subprojects' format/lint/type/test suites
independently rather than trusting the implementation log's reported counts (21/126/600+1xfail).
All three matched exactly this time — a useful contrast to [[project_f10_crew_commands_minor_fix]]
where a reported count turned out wrong on rerun. Don't skip the rerun just because the numbers
"look right" or match plan expectations.
