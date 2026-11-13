#!/bin/bash
# Hook script: PreToolUse gate on Bash. Argv-aware detection of the destructive
# operations the permissions deny-list is meant to block.
#
# WHY A SCRIPT AND NOT MORE DENY PATTERNS. The deny list matches literal command
# prefixes (`Bash(rm -rf*)`, `Bash(git reset --hard*)`,
# `Bash(git worktree remove --force*)`). The 2026-09-27 security audit
# demonstrated three same-effect spellings that sail straight past all three:
#
#   rm -fr <path>              flags reordered
#   git worktree remove -f     short alias for --force
#   git -C <dir> reset --hard  global flag inserted before the subcommand
#
# The third one actually destroyed an uncommitted change in the audit's scratch
# repo -- i.e. it reproduced the exact 2026-09-20 incident the rule exists to
# prevent, with a one-flag rewrite and no prompt. The realistic actor here is not
# an attacker but an agent reaching for an ordinary alternate flag order; the
# 2026-09-20 incident was itself accidental. A glob list will always be one
# rewrite behind, so this walks the argv instead: flags are parsed as flags,
# `-rf` and `-fr` and `-r -f` are the same thing, and git's global options are
# skipped to find the real subcommand.
#
# The deny-list entries stay in place as cheap defense-in-depth; this is the
# layer that is actually expected to hold.
#
# Chaining is NOT handled here on purpose: the audit confirmed Claude Code's own
# matcher already parses compound/multi-line commands structurally. We still
# split on shell separators so a destructive command in the second half of a
# `&&` chain is seen.
set -uo pipefail

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0
# Where a bare `git` would run: the hook payload's cwd, else wherever this script runs.
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$cwd" ] || cwd=$(pwd)

deny() {
    printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$1" | jq -Rs .)"
    exit 0
}

RESET_MSG='git reset --hard is blocked: it reverts tracked files AND deletes staged new files. On 2026-09-20 it destroyed a pre-commit script, a .gitignore edit and a whole docs/PROCESS.md section during hook test cleanup. Use instead: git revert <sha> to undo a commit, git restore <path> for one file, git reset --soft HEAD~1 to keep the work, or git stash. If you genuinely need --hard, ask the user.

(Detected by argv-aware parsing, so alternate spellings such as `git -C <dir> reset --hard` are caught too.)'

WORKTREE_MSG='git worktree remove --force is blocked (AGENTS.md, "Where work happens"). --force is not needed: a plain `git worktree remove` succeeds on a clean worktree and when the only leftovers are gitignored build artifacts. It refuses ONLY when genuinely untracked files are present -- and that refusal is the safety check, firing in exactly the case where unharvested agent work would be destroyed. Read what it names and fix that instead: it is telling you about work you have not cherry-picked, or an artifact that needs a .gitignore entry. A worktree whose directory was deleted externally needs `git worktree prune`, not force.

(Detected by argv-aware parsing, so `-f` is caught as well as `--force`.)'

DISCARD_MSG='git checkout -- <path> / git checkout <path> / git restore <path> is blocked here because that path has uncommitted changes in the working tree, and the command would discard them with no undo. Retro 2026-11-13: this exact command wiped in-progress work twice in one window, each time by someone meaning to "reset one file" while the check that the file was clean lived only in their head. Bind the check to the action: first `git commit -m "WIP: <what>"` (preferred -- reachable by sha forever) or `git stash push -u -m "<unique-tag>"` (AGENTS.md: the stash stack is shared across worktrees, so tag it and re-find by tag), THEN discard. If the change really is garbage, say so in one line and ask the user. A clean path is not blocked; `git restore --staged` (unstage only) is not blocked; `git checkout <branch>` is not blocked.

(Detected by argv-aware parsing plus `git status --porcelain` on the named paths, so `git -C <dir> checkout -- f` and `git checkout HEAD -- f` are caught too.)'

RM_MSG='A recursive+force rm is blocked, in any flag spelling (-rf, -fr, -Rf, -r -f, --recursive --force). Delete a specific path without -f so the shell can refuse when something unexpected is there, or use `git clean -n` first to see what would go. If you genuinely need a recursive force delete, ask the user.'

# Split into segments on shell separators so a destructive command after && or |
# is still examined. Newlines count as separators too.
segments=$(printf '%s' "$cmd" | tr '\n;|&' '\n\n\n\n')

while IFS= read -r seg; do
    [ -z "${seg// /}" ] && continue

    # shellcheck disable=SC2086 # deliberate word-splitting: we want argv tokens.
    set -- $seg
    [ $# -eq 0 ] && continue

    # Skip leading VAR=value assignments and common wrappers so `env FOO=1 rm -fr x`
    # or `sudo rm -fr x` is still seen as an rm.
    while [ $# -gt 0 ]; do
        case "$1" in
            *=*)                          shift ;;
            sudo|env|command|nohup|time)  shift ;;
            *)                            break ;;
        esac
    done
    [ $# -eq 0 ] && continue

    prog=$(basename "$1")
    shift

    case "$prog" in
        rm)
            recursive=0; force=0
            for tok in "$@"; do
                case "$tok" in
                    --) break ;;
                    --recursive) recursive=1 ;;
                    --force) force=1 ;;
                    --*) ;;
                    -*)
                        # A bundle of short flags: -rf, -fr, -Rf, -r, -f ...
                        letters=${tok#-}
                        case "$letters" in *[rR]*) recursive=1 ;; esac
                        case "$letters" in *f*)   force=1 ;; esac
                        ;;
                esac
            done
            [ "$recursive" -eq 1 ] && [ "$force" -eq 1 ] && deny "$RM_MSG"
            ;;
        git)
            # Skip git's global options to reach the real subcommand. Those that
            # take a separate argument must consume it, or the argument gets
            # mistaken for the subcommand.
            gitdir="$cwd"
            while [ $# -gt 0 ]; do
                case "$1" in
                    -C) gitdir="$2"; shift 2 || break ;;
                    -c|--git-dir|--work-tree|--namespace|--exec-path|--config-env)
                        shift 2 || break ;;
                    --git-dir=*|--work-tree=*|--namespace=*|--exec-path=*|-c=*)
                        shift ;;
                    -*) shift ;;
                    *)  break ;;
                esac
            done
            [ $# -eq 0 ] && continue
            sub="$1"; shift

            case "$sub" in
                reset)
                    for tok in "$@"; do
                        case "$tok" in
                            --hard) deny "$RESET_MSG" ;;
                        esac
                    done
                    ;;
                checkout|restore)
                    # Discarding worktree changes. For `restore`, --staged without --worktree
                    # only unstages and is safe. For `checkout`, -b/-B creates a branch (handled
                    # by the branch-rule hook, not here). Everything else: collect the non-flag
                    # tokens and ask git whether any of them is a modified path. A branch name
                    # is not a modified path, so `git checkout main` passes; a path with
                    # uncommitted changes is what gets refused.
                    staged_only=0; worktree_flag=0; paths=()
                    for tok in "$@"; do
                        case "$tok" in
                            -b|-B|--orphan) staged_only=1; break ;;
                            --staged|-S) staged_only=1 ;;
                            --worktree|-W) worktree_flag=1 ;;
                            --) ;;
                            --source=*|--pathspec-from-file=*) ;;
                            -*) ;;
                            *) paths+=("$tok") ;;
                        esac
                    done
                    [ "$sub" = restore ] && [ "$staged_only" -eq 1 ] && [ "$worktree_flag" -eq 0 ] && continue
                    [ "$sub" = checkout ] && [ "$staged_only" -eq 1 ] && continue
                    [ ${#paths[@]} -eq 0 ] && continue
                    # Drop a leading ref (`git checkout HEAD -- f`): a token that is not a path in
                    # the tree is left to git; status ignores it. Any path with a porcelain line
                    # is dirty.
                    dirty=$(git -C "$gitdir" status --porcelain --untracked-files=all -- "${paths[@]}" 2>/dev/null | head -5)
                    [ -n "$dirty" ] && deny "$DISCARD_MSG

Dirty under this command's paths:
$dirty"
                    ;;
                worktree)
                    [ $# -eq 0 ] && continue
                    wsub="$1"; shift
                    [ "$wsub" = "remove" ] || continue
                    for tok in "$@"; do
                        case "$tok" in
                            --force) deny "$WORKTREE_MSG" ;;
                            --*) ;;
                            -*)
                                case "${tok#-}" in *f*) deny "$WORKTREE_MSG" ;; esac
                                ;;
                        esac
                    done
                    ;;
            esac
            ;;
    esac
done <<< "$segments"

exit 0
