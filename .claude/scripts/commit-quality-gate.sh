#!/bin/bash
# Hook script: PreToolUse gate on `git commit`. Detects which subproject(s) the staged diff
# touches -- DISCOVERED from the filesystem, never a list written here; see the loop below -- and
# runs each touched subproject's own format/lint/type/test commands (per its own CLAUDE.md
# "Commands" section). Blocks the commit with combined output on any failure.
#
# This docstring named three subprojects out of six until 2026-09-27, forty lines above a comment
# recounting two prior audits of that exact defect. A reader trusts the docstring.
set -uo pipefail

# `cd "$CLAUDE_PROJECT_DIR" || exit 0` was the written form, and under `set -u` it never reached
# its own `|| exit 0`: an unset variable aborts the shell at expansion time, before the `||` is
# evaluated. The behaviour was still fail-open for a PreToolUse hook (a non-zero, non-2 exit is a
# non-blocking error), but by accident rather than by the stated mechanism. This is the pattern
# the sibling gates in this directory already use, and it also makes the script runnable by hand.
REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 0

STAGED=$(git diff --cached --name-only)
FAIL=0
OUT=""

run() {
    local label="$1"; shift
    local this_out
    this_out=$("$@" 2>&1)
    local status=$?
    if [ $status -ne 0 ]; then
        FAIL=1
        OUT="$OUT

## $label — FAIL
$this_out"
    fi
}

# Run a check from INSIDE the subproject directory. Two defects made this
# necessary, both found and reproduced on 2026-09-27, and together they meant
# this gate could not pass on any commit that touched a subproject's code:
#
#   1. Bare `ruff`/`mypy`/`pytest` are not on PATH at all here (verified in both
#      an interactive and a login shell). Each subproject keeps its own .venv
#      (root CLAUDE.md, "Module independence"), so every check exited 127
#      "command not found" -> FAIL=1 -> commit blocked with noise instead of a
#      real result. `check`/SKILL.md and `dod-check` already resolve the
#      venv-qualified binary; this script and posttooluse-mypy.sh never got it.
#      Nobody noticed because the recent commits that exercised the gate touched
#      only .claude/, docs/ and todo/ -- paths that skip the loop entirely.
#   2. mypy's config discovery is CWD-only. Run from the repo root (no root-level
#      pyproject.toml exists) it silently loses `strict` and the CWD-relative
#      `mypy_path`. Reproduced on body-layer: `mypy body-layer/src` from the root
#      reports 6 phantom import-not-found errors, while `cd body-layer && mypy src`
#      reports "Success: no issues found in 52 source files".
#
# All six subprojects share the same config shape, so all six get the same
# treatment rather than body-layer being special-cased -- the reviewer's open
# question about whether the others were silently weaker is resolved by running
# every one of them the way its own CLAUDE.md documents.
run_in() {
    local sub="$1" label="$2"; shift 2
    local this_out
    this_out=$(cd "$sub" && "$@" 2>&1)
    local status=$?
    if [ $status -ne 0 ]; then
        FAIL=1
        OUT="$OUT

## $label — FAIL
$this_out"
    fi
}

# Resolve a tool to the subproject's own venv, falling back to PATH. Mirrors
# dod-check's resolve_tool.
resolve_tool() {
    local sub="$1" tool="$2"
    if [ -x "$sub/.venv/bin/$tool" ]; then
        printf '%s' "$PWD/$sub/.venv/bin/$tool"
    elif command -v "$tool" >/dev/null 2>&1; then
        printf '%s' "$tool"
    fi
}




# Every subproject with src/ and tests/ gets its own checks. DISCOVERED, NOT
# ENUMERATED -- and that distinction is the point. This script hardcoded one
# subproject until the 2026-09-10 integrity audit, which fixed it by hardcoding
# three; the 2026-09-21 audit then found audio-adapter/ and mission-interpreter/
# running zero checks on a commit that touched only them, while root CLAUDE.md
# claimed the gate enforced per-subproject verification. Enumerating five would
# have set up the same finding a year out. A new subproject is now covered the
# moment it has src/ and tests/, with nothing to remember.
for sub in */; do
    sub=${sub%/}
    [ -d "$sub/src" ] && [ -d "$sub/tests" ] || continue
    printf '%s\n' "$STAGED" | grep -q "^$sub/" || continue

    RUFF=$(resolve_tool "$sub" ruff)
    MYPY=$(resolve_tool "$sub" mypy)
    PYTEST=$(resolve_tool "$sub" pytest)

    # A missing tool is reported as a missing tool, not as 127 noise attached to
    # whichever check happened to run first.
    MISSING=""
    [ -z "$RUFF" ] && MISSING="$MISSING ruff"
    [ -z "$MYPY" ] && MISSING="$MISSING mypy"
    [ -z "$PYTEST" ] && MISSING="$MISSING pytest"
    if [ -n "$MISSING" ]; then
        FAIL=1
        OUT="$OUT

## $sub toolchain — FAIL
Cannot run the quality gate for $sub: missing tool(s):$MISSING
Not found in $sub/.venv/bin/ and not on PATH. Provision the subproject venv
(cd $sub && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]') or
activate it before committing."
        continue
    fi

    # Every check runs with the subproject as CWD (see run_in's comment).
    run_in "$sub" "$sub ruff format" "$RUFF" format --check src tests
    run_in "$sub" "$sub ruff check"  "$RUFF" check src tests
    run_in "$sub" "$sub mypy"        "$MYPY" src
    run_in "$sub" "$sub pytest"      "$PYTEST" tests -q
done

# Lua syntax (parse-only, Lua 5.1 = the version DCS embeds) for staged aircraft-layer Lua files.
STAGED_LUA=$(printf '%s\n' "$STAGED" | grep -E '^aircraft-layer/.*\.lua$' || true)
if [ -n "$STAGED_LUA" ]; then
    if command -v luac5.1 >/dev/null 2>&1; then
        while IFS= read -r f; do
            [ -f "$f" ] && run "aircraft-layer luac5.1 $f" luac5.1 -p "$f"
        done <<< "$STAGED_LUA"
    else
        FAIL=1
        OUT="$OUT

## aircraft-layer Lua syntax — FAIL
luac5.1 not installed; needed to syntax-check staged DCS Lua before commit. Install Lua 5.1
(WSL/Debian: sudo apt install lua5.1). Files: $STAGED_LUA"
    fi
fi


# Split entry documents (docs/DOC_CONVENTIONS.md): run the three convention gates when the commit
# touches a split directory or the tag vocabulary. The convention doc said these "run before
# committing a converted file" from the day it was written, while none of the three was wired to
# anything -- so a dangling [[ID]], an orphaned entry, an unlisted tag or a stale provenance block
# committed clean across 253 entry files and surfaced only when somebody clicked or grepped
# (review round 4, RF4-2). A stated mechanical guarantee that does not exist is worse than no
# guarantee, because it is relied on.
#
# Each gate scans the whole tree rather than only the staged paths, which is deliberate: an
# orphaned entry and a dangling link are both relational defects, so a staged-paths-only check
# would miss the half of each pair that did not change. Measured cost is under two seconds for
# all three over 253 entries, so there is nothing to buy by narrowing it.
#
# The staged-path condition exists so a commit touching none of these paths is completely
# unaffected -- this is a PreToolUse hook on every `git commit`, and a gate that fires on
# unrelated commits is a gate that gets bypassed. A missing or non-executable gate script is
# skipped rather than reported: this hook must stay fail-open on its own internal errors.
if printf '%s\n' "$STAGED" | grep -qE '(^|/)ROADMAP/|^todo/(backlog|todo)/|^docs/TAGS\.md$'; then
    for gate in roadmap-entry-consistency-gate roadmap-tag-vocabulary-gate doc-provenance-gate; do
        gate_path=".claude/scripts/$gate.sh"
        [ -x "$gate_path" ] || continue
        run "$gate" "$gate_path"
    done
fi

# Reject agent-memory files written under a subproject-relative path instead of repo-root
# .claude/agent-memory/ (recurring mistake — see feedback_agent_memory_path_recurrence.md).
STRAY_MEMORY=$(printf '%s\n' "$STAGED" | grep -E '^[^/]+/\.claude/agent-memory/' || true)
if [ -n "$STRAY_MEMORY" ]; then
    FAIL=1
    OUT="$OUT

## Stray agent-memory path — FAIL
Agent memory must live at repo-root .claude/agent-memory/<role>/, not a subproject-relative
path. Move these before committing:
$STRAY_MEMORY"
fi

# Warn (never block) when a role wrote an artifact but not its memory index. Four of eight roles
# independently reported this in the 2026-09-18 retro: the artifact gets written, the index that
# makes it findable next session does not. Debugger wrote no entry for a diagnosis that overturned
# the roadmap; investigator's entry still said "blocked on a 403" hours after the user resolved it;
# architect's ellipse-to-angular lesson lived only in plan prose; dod noted a recurring pattern in
# a dod-check and never indexed it.
MEM_WARN=""
check_memory() {
    local pattern="$1" role="$2" label="$3"
    if printf '%s\n' "$STAGED" | grep -qE "$pattern"; then
        if ! printf '%s\n' "$STAGED" | grep -q "^\.claude/agent-memory/$role/"; then
            MEM_WARN="$MEM_WARN
  - $label staged, but nothing under .claude/agent-memory/$role/"
        fi
    fi
}
check_memory '^plans/[^/]+/plan\.md$'           architect    "a plan"
check_memory '^plans/[^/]+/implementation\.md$' implementer  "an implementation log"
check_memory '^plans/[^/]+/review\.md$'         reviewer     "a review"
check_memory '^plans/[^/]+/debug\.md$'          debugger     "a debug report"
check_memory '^plans/[^/]+/dod-check\.md$'      dod          "a DoD check"
check_memory '/research/[0-9]{4}-[0-9]{2}-[0-9]{2}-.*\.md$' investigator "a research finding"

# Warn (never block) when a commit adds/modifies a plans/*/dod-check.md without also touching a
# ROADMAP.md (root or any subproject's) in the same commit. This is the missing-roadmap-entry
# gap: it recurred three times, each time caught reactively by a reviewer noticing (cross-linked
# in reviewer memory as m10-junction-review and group-detectability-roadmap-lag) rather than
# mechanically. Warn rather than hard-block: DoD's own report commit legitimately lands *before*
# the merge commit that updates the roadmap in this project's normal sequencing (see root
# CLAUDE.md "Milestone Completion" and root ROADMAP.md "Keeping this current") -- a hard block
# here would misfire on that common, correct case and train people to bypass the gate, which is
# worse than the gap it's meant to close.
ROADMAP_WARN=""
DOD_CHECK_FILES=$(printf '%s\n' "$STAGED" | grep -E '^plans/[^/]+/dod-check\.md$' || true)
if [ -n "$DOD_CHECK_FILES" ]; then
    if ! printf '%s\n' "$STAGED" | grep -qE '(^|/)ROADMAP(\.md|/[^/]+\.md)$'; then
        ROADMAP_WARN="
  - dod-check.md staged, but no ROADMAP.md (root ROADMAP.md, or a subproject's, e.g.
    world-model/ROADMAP.md, aircraft-layer/ROADMAP.md, body-layer/ROADMAP.md) is touched in
    this commit:
$(printf '%s\n' "$DOD_CHECK_FILES" | sed 's/^/      /')"
    fi
fi

# Agent-memory index: APPEND, never rewrite. On 2026-09-20 one commit replaced
# the reviewer index's 27 entries with 1, leaving 73 memory files on disk and
# unreachable by the role that wrote them -- undetected for a day, and found
# only by an integrity audit. The files were never lost; only the index was.
# A memory nothing can reach is the most expensive loss in this system, since
# its whole purpose is to stop a later agent repeating a mistake.
SHRUNK_INDEX=""
for idx in $(printf '%s\n' "$STAGED" | grep -E '^\.claude/agent-memory/[^/]+/MEMORY\.md$' || true); do
    added=$(git diff --cached --numstat -- "$idx" | cut -f1)
    removed=$(git diff --cached --numstat -- "$idx" | cut -f2)
    [ -z "$added" ] && continue
    # A rewrite removes far more than it adds. Editing a hook removes ~1 line.
    if [ "$removed" -gt 3 ] && [ "$removed" -gt "$added" ]; then
        SHRUNK_INDEX="$SHRUNK_INDEX
  $idx (removed $removed lines, added $added)"
    fi
done
if [ -n "$SHRUNK_INDEX" ]; then
    FAIL=1
    OUT="$OUT

## agent-memory index shrank -- FAIL
$SHRUNK_INDEX

An agent-memory MEMORY.md is append-only. Removing more lines than it adds
means entries were dropped, and the memory files they point to become
unreachable while still sitting on disk.

If you meant to edit one hook, that removes one line and this will not fire.
If an entry is genuinely obsolete, delete its file in the same commit so the
index and the directory stay in step."
fi

# Skill layout: a skill must be .claude/skills/<name>/SKILL.md, never a flat
# .claude/skills/<name>.md, or Claude Code cannot discover it (invisible to
# /skills, not invokable, not loadable via the Skill tool). The PreToolUse
# hook catches Write/Edit; this catches everything else -- a heredoc, a mv, a
# script. 24 of this project's skills were flat and undiscoverable until
# 2026-09-21, and nobody noticed because the main loop read them as documents.
FLAT_SKILLS=$(printf '%s\n' "$STAGED" \
    | grep -E '^\.claude/skills/[^/]+\.md$' || true)
if [ -n "$FLAT_SKILLS" ]; then
    FAIL=1
    OUT="$OUT

## skill layout — FAIL
These are staged as flat files and would not be discoverable:
$(printf '%s\n' "$FLAT_SKILLS" | sed 's/^/  /')

Move each to .claude/skills/<name>/SKILL.md:
$(printf '%s\n' "$FLAT_SKILLS" | while IFS= read -r f; do
    n=$(basename "$f" .md)
    printf '  mkdir -p .claude/skills/%s && git mv %s .claude/skills/%s/SKILL.md\n' "$n" "$f" "$n"
done)"
fi

if [ $FAIL -ne 0 ]; then
    printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$OUT" | jq -Rs .)"
elif [ -n "$MEM_WARN" ] || [ -n "$ROADMAP_WARN" ]; then
    WARN_MSG=""
    if [ -n "$MEM_WARN" ]; then
        WARN_MSG="${WARN_MSG}Agent-memory index not updated:${MEM_WARN}

The artifact is committed either way -- this is a reminder, not a gate. Write the note only if the work taught something a future session would want retrieved; skip it for a typo fix."
    fi
    if [ -n "$ROADMAP_WARN" ]; then
        [ -n "$WARN_MSG" ] && WARN_MSG="${WARN_MSG}

"
        WARN_MSG="${WARN_MSG}Roadmap not updated alongside dod-check:${ROADMAP_WARN}

The commit proceeds either way -- this is a reminder, not a gate. If this dod-check is not yet
merged/complete, updating the roadmap in a later commit (e.g. at merge time) is expected and
fine; if the milestone this dod-check covers is actually done, update the relevant ROADMAP.md
now so it doesn't silently drift stale."
    fi
    printf '{"continue":true,"systemMessage":%s}' "$(printf '%s' "$WARN_MSG" | jq -Rs .)"
fi
# All touched subprojects clean (or nothing relevant staged): exit 0 silently, commit proceeds.
