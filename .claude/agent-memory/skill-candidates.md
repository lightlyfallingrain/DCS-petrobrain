# Skill Candidates

Candidate patterns observed repeatedly in sessions that might warrant a dedicated skill.
Populated automatically by the SubagentStop skill-gap detector hook (see `settings.json`) after
each `dod` agent run. Reviewed and cleared during `merge-skill-review.sh`'s post-merge check —
entries are removed once created or rejected by the user.

## 2026-09-03 python-code-quality-gate
- **Pattern**: Run ruff format --check, ruff check, and mypy --strict in sequence on Python source trees to validate code quality before staging
- **Count**: 12+ ruff checks, 11 mypy runs, 10 ruff format checks in this session
- **Benefit**: DoD/review agents repeatedly discover and activate venv, then run the same three-command validation suite. A dedicated skill could normalize the toolchain discovery, report results clearly, and exit early on first failure. Saves ~10-20 tool calls per DoD gate.

## 2026-09-03 pytest-acceptance-gate
- **Pattern**: Activate venv and run pytest on test suite with quiet output (-q), verifying test pass/fail before staging
- **Count**: 10 pytest invocations in this session
- **Benefit**: Every DoD gate runs pytest at least once to catch regressions. A skill could handle venv discovery, run with consistent flags, and parse/report summary stats (passed/failed/skipped) in structured format for gate decisions.

## 2026-09-03 git-stage-and-commit-workflow
- **Pattern**: Stage groups of files with `git add`, check status with `git status`, then commit with structured message (multi-line, Co-Authored-By footer)
- **Count**: 3 git add operations in this session (but pattern is repetitive across agents)
- **Benefit**: DoD/reviewer agents manually stage files, verify, and commit. A skill could accept file list and commit template, handle the sequencing, and ensure Co-Authored-By/session link are always included consistently.
