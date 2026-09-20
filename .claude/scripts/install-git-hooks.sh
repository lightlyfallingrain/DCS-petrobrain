#!/bin/bash
# Install this project's git hooks. Run once per clone:
#
#     .claude/scripts/install-git-hooks.sh
#
# Git hooks live in .git/hooks, which is not version controlled, so they cannot
# simply be committed. This script points .git/hooks at the tracked scripts in
# .claude/scripts/ so the behaviour travels with the repository and a change to
# a hook is reviewable like any other change.
#
# Installs:
#   pre-commit   graphify-dirty-flag.sh   -- records that docs changed
#   post-commit  graphify-ast-refresh.sh  -- refreshes code structure in the graph
#
# Both fail open. Neither can block a commit.
#
# If a hook already exists and is not ours, this appends rather than replacing
# it -- silently discarding someone's existing hook would be worse than doing
# nothing.

set -uo pipefail

REPO=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "not a git repository" >&2; exit 1; }
cd "$REPO" || exit 1

HOOKS="$REPO/.git/hooks"
mkdir -p "$HOOKS"

install_hook() {
    # Separate statements on purpose: bash expands a `local` command's entire
    # word list before performing any of its assignments, so referencing
    # $script in the same `local` that sets it is unbound under `set -u`.
    local name="$1"
    local script="$2"
    local marker="# petrobrain: $script"
    local path="$HOOKS/$name"

    if [ -f "$path" ] && grep -qF "$marker" "$path" 2>/dev/null; then
        echo "  $name already installed"
        return
    fi

    if [ ! -f "$path" ]; then
        printf '#!/bin/bash\n' > "$path"
    fi

    {
        printf '\n%s\n' "$marker"
        printf 'if [ -x "$(git rev-parse --show-toplevel)/.claude/scripts/%s" ]; then\n' "$script"
        printf '    "$(git rev-parse --show-toplevel)/.claude/scripts/%s" || true\n' "$script"
        printf 'fi\n'
    } >> "$path"

    chmod +x "$path"
    echo "  $name installed"
}

echo "installing git hooks:"
install_hook pre-commit  graphify-dirty-flag.sh
install_hook post-commit graphify-ast-refresh.sh

echo
echo "To remove, edit .git/hooks/{pre,post}-commit and delete the petrobrain blocks."
