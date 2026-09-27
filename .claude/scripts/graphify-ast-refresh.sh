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
# .py and .lua. Lua added 2026-09-27.
#
# Why it was missing and what that cost: the full rebuild's AST pass already
# covers .lua (and .sh and .toml), so nothing was ever lost from graph.json --
# this hook's job is only to keep the spine current *between* rebuilds. With
# .py alone, editing Export.lua or a mission hook left the graph describing the
# previous structure until the next full rebuild, which on this project can be
# a week apart. That is the whole defect: a lag, not a loss.
#
# It is worth closing because Lua is where the DCS-side behaviour lives --
# Export.lua, nine probe variants, five mission hooks, the world-model mission
# probes, 22 files and 233 nodes -- and it is the code least reconstructable
# from memory, which is exactly what the investigator role goes to the graph
# for.
#
# .sh and .toml stay out of *this* hook but remain in the full rebuild's spine,
# because graphify's code discovery has no extension-exclude knob and
# post-filtering would have to be redone after every rebuild. They are 99 nodes
# of glue out of 8405 (1.2%) -- .claude/scripts/ gates, run-scripts/ launchers,
# WSL probe wrappers, pyproject manifests. Not worth a fragile filter to remove
# (user direction, 2026-09-27: "those need not be indexed" -- they need not, and
# they also do no harm at this share).
code=$(printf '%s\n' "$changed" | grep -E '\.(py|lua)$' | grep -vE '^(\.claude/worktrees/|graphify-corpus/)') || true
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
