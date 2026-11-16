#!/usr/bin/env python3
"""Print the directory a Bash hook payload's git command actually runs in.

Reads a PreToolUse hook payload (JSON) on stdin and prints one directory path.

Why this exists (2026-11-16): the repo-inspecting git hooks (commit-quality-gate.sh,
push-roadmap-gate.sh, accepted-items-ledger.sh, branch-delete-guard.sh) resolved the repository
from the payload's ``cwd`` alone. That is the *session's* directory. A command such as
``cd ../<worktree> && git commit ...`` -- the main loop's normal way of committing on a feature
branch -- runs git somewhere else, so the commit gate inspected the root's (empty) index and
passed every such commit unchecked. A lint error reached ``main`` that way and was found by a
later Reviewer.

Resolution, in order, against the first ``git ... commit|push|branch|merge|tag`` in the command:
  1. start from the payload's ``cwd`` (else the process cwd);
  2. apply every ``cd <dir>`` that appears before that git command, in order, each relative to the
     directory reached so far;
  3. apply that git command's own ``-C <dir>``, if any.
Any step whose directory does not exist is ignored. With no git command found, the payload's cwd
is printed unchanged, so the hooks behave exactly as before for everything else. Never raises:
any parse failure falls back to the payload's cwd (hooks must stay fail-open on internal errors).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

_GIT_CMD = re.compile(r"\bgit\b(?P<args>[^;&|]*?)\b(?:commit|push|branch|merge|tag)\b")
_CD = re.compile(r"(?:^|[;&|(]\s*|\s)cd\s+(?P<path>\"[^\"]*\"|'[^']*'|[^\s;&|)]+)")
_DASH_C = re.compile(r"-C\s+(?P<path>\"[^\"]*\"|'[^']*'|[^\s;&|)]+)")


def _unquote(token: str) -> str:
    try:
        parts = shlex.split(token)
    except ValueError:
        return token
    return parts[0] if parts else token


def _step(base: str, token: str) -> str:
    target = os.path.expanduser(_unquote(token))
    candidate = os.path.normpath(target if os.path.isabs(target) else os.path.join(base, target))
    return candidate if os.path.isdir(candidate) else base


def resolve(payload: dict[str, object]) -> str:
    cwd = payload.get("cwd")
    base = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return base
    match = _GIT_CMD.search(command)
    if match is None:
        return base
    directory = base
    for cd in _CD.finditer(command[: match.start()]):
        directory = _step(directory, cd.group("path"))
    dash_c = _DASH_C.search(match.group("args"))
    if dash_c is not None:
        directory = _step(directory, dash_c.group("path"))
    return directory


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            payload = {}
        print(resolve(payload))
    except Exception:  # noqa: BLE001 -- hooks must stay fail-open
        print(os.getcwd())


if __name__ == "__main__":
    main()
