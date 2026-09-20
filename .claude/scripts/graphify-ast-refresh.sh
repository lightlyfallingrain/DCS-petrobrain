#!/bin/bash
# Post-commit: refresh the knowledge graph's structural spine from changed code.
#
# Cheap enough to run every commit. Measured 2026-09-20: AST extraction over all
# 141 Python files in this repo took 1.56s on the slow path (the parallel pool
# fell back to sequential). A commit touches a handful of files, so this is
# well under a second in practice.
#
# **It captures docstrings, which is why it is worth running at all.** graphify's
# AST extractor emits nodes for module and function docstrings, not just symbols
# -- and this project puts its design reasoning in docstrings (the binocular
# premise in visibility.py, the measured angles in cockpit_mask.py, the 700:1
# association lesson). Those arrive here deterministically, with no LLM and no
# API key.
#
# What it does NOT do is cross-file conceptual linking. Connecting two ideas
# that share no import and no citation -- "these are the same mistake in
# different subsystems" -- needs semantic extraction, which needs an LLM. That
# happens at merge (see docs/PROCESS.md, "Keeping the knowledge graph honest").
#
# So the division is: structure per commit, meaning per merge.
#
# Fails open, always. A stale graph is an inconvenience; a hook that breaks
# `git commit` is a broken repository.

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 0

# Nothing to refresh if no graph exists yet, and nothing to refresh with if the
# interpreter graphify was installed into has gone away.
[ -f graphify-out/graph.json ] || exit 0
[ -f graphify-out/.graphify_python ] || exit 0
PY=$(cat graphify-out/.graphify_python 2>/dev/null) || exit 0
[ -x "$PY" ] || exit 0

changed=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null) || exit 0
code=$(printf '%s\n' "$changed" | grep -E '\.py$' | grep -vE '^(\.claude/worktrees/|graphify-corpus/)') || true
[ -z "$code" ] && exit 0

# Only files that still exist -- a commit that deletes a module must not make
# this fail, and the graph keeps the stale node until the next full rebuild.
existing=""
for f in $code; do [ -f "$f" ] && existing="$existing $f"; done
[ -z "$existing" ] && exit 0

"$PY" - "$existing" <<'PYEOF' >/dev/null 2>&1 || exit 0
import sys, json
from pathlib import Path
from graphify.extract import extract

files = [Path(p) for p in sys.argv[1].split() if p]
if not files:
    raise SystemExit(0)
# parallel=False: the pool needs a __main__ guard the stdin entrypoint cannot
# provide, and 141 files run in 1.56s sequentially anyway.
result = extract(files, cache_root=Path('.'), parallel=False)
Path('graphify-out/.graphify_ast_incremental.json').write_text(
    json.dumps(result, ensure_ascii=False), encoding='utf-8')
PYEOF

count=$(printf '%s\n' $existing | grep -c .)
printf '%s  refreshed AST for %s changed file(s)\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$count" >> graphify-out/.ast_refresh.log

exit 0
