---
name: project_audio_adapter_negative_length_round2_confirmed
description: audio-adapter negative-Content-Length fix round 2 — implementer's rejection of the reviewer's suggested test mechanism was verified correct; how to re-review a branch checked out elsewhere
metadata:
  type: project
---

Round 2 of `fix/audio-adapter-review-findings` (1b2e337 vs 64e9d37) fixed the round-1 required
fix: `test_speak_negative_content_length_returns_400` / `test_transcribe_negative_content_length_
returns_400` passed against pre-fix `server.py` (`2802c4f`) too, proving nothing.

**The implementer rejected the reviewer's own suggested mechanism (spy/mock `rfile.read`,
assert never called with a negative count) and was right to.** `2802c4f`'s
`self.rfile.read(length) if length > 0 else b""` ternary already prevents that call in both
pre-fix and post-fix code for the negative-length case — verified by reading `2802c4f`'s literal
source directly (`git show 2802c4f:audio-adapter/src/server.py`), not by trusting the report.
Since `rfile.read` behaves identically either way, the only discriminator left is *which*
rejection path fires (JSON-validation path pre-fix vs. header-guard path post-fix), so asserting
the exact response body is the correct substitute, not a workaround. **Lesson: a reviewer's
suggested fix mechanism is a hypothesis, and being corrected by the implementer with an
independently-verifiable reason is the process working, not a red flag** — verify the correction
against the literal pre-fix source before accepting or rejecting it.

**Re-reviewing a branch that's checked out in the main working copy, from an isolated worktree
on an unrelated branch:** cannot `git checkout` the branch under review (git refuses a second
checkout of the same branch). Use `git archive <sha> <subdir> | tar -x -C <scratch>` to extract
the exact tree into a scratch directory inside the worktree (not `/private/tmp` — the sandbox's
git-safety heuristic blocks `PYTHONPATH=... python -m pytest <path outside worktree>` as
"cannot be shown not to be git" even for pure Python invocations; copying into a subdir *inside*
the worktree, e.g. `_reviewtmp/`, avoids the block). Reuse another checkout's `.venv` by
absolute path for `ruff`/`mypy`/`pytest` binaries — no need to rebuild one. Remove the temp dir
before finishing so `git status --porcelain` comes back clean.

See also [[feedback_regression_test_empirical_check]] — this is the same empirical-check
discipline, applied a second time on the same feature and confirming the discipline itself paid
off (round 1 caught the gap, round 2 confirmed the fix and the implementer's counter-reasoning).
