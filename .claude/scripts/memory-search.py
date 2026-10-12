#!/usr/bin/env python3
"""Search or list agent memory, building the index on the fly.

Replaces the hand-maintained `MEMORY.md` index in each
`.claude/agent-memory/<role>/`. Every memory file already carries a
`description:` in its frontmatter -- measured 2026-10-12, 556 of 556 files
across all eight roles -- so the index was a second copy of data the files
already held, kept in step by hand.

**Why a tool instead of a file.** The index was loaded on *every* agent
dispatch (all eight role files carry `memory: project`, which is a Claude Code
feature, not a repo convention) and no role file ever told an agent to read it.
So its ~6k tokens were an unconditional cost against a benefit that required an
agent to spontaneously decide to look. A search is the other way round: it costs
nothing until something asks a question, and it answers the question that was
actually asked instead of handing over 97 lines to scan.

It also removes a whole class of maintenance failure. The index drifted, grew
past its read limit, and a `PostToolUse` hook asked six separate agents in one
session to compact it -- each correctly refusing, because the ask was impossible
as phrased (fixed cost is ~86 bytes per entry, so a byte target is an
entry-count target, and no amount of prose trimming reaches it). A derived index
cannot drift and cannot be asked to shrink.

Usage:

    memory-search.py                      # every role, newest first
    memory-search.py fixture degenerate   # search all roles
    memory-search.py --role reviewer      # list one role
    memory-search.py -r implementer mypy  # search one role
    memory-search.py --body counterfactual  # also show matching body lines

Matching is case-insensitive over the filename, the description and the body.
Ranking puts a filename/description hit above a body-only hit, because the
filenames here are written as whole lessons and a body hit is often incidental.
Exit status is 1 when a query matched nothing, so a caller can tell "no memory
about this" from "memory says nothing useful" -- a distinction the index could
not express at all.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MEMORY_ROOT = Path(".claude/agent-memory")

#: Frontmatter key that stands in for the index's old hook text.
DESCRIPTION_RE = re.compile(r"^description:\s*(.*)$", re.IGNORECASE)

#: Weight on a filename/description hit relative to a body hit. A filename
#: here is a whole lesson (`feedback_guard_fixture_must_not_pick_a_degenerate_
#: case.md`), so a hit there is about the memory's subject; a body hit may be
#: the memory merely mentioning the term in passing.
NAME_WEIGHT = 5


def _description(text: str) -> str:
    """The `description:` frontmatter value, including indented continuation
    lines, or `""` when the file has none.

    Continuation handling matters: the value is free prose and several entries
    wrap. Taking only the first line would silently truncate the one field this
    tool presents as the summary.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    out: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if out and (line.startswith(("  ", "\t")) and ":" not in line.split("#")[0]):
            out.append(line.strip())
            continue
        match = DESCRIPTION_RE.match(line)
        if match:
            out = [match.group(1).strip()]
        elif out:
            break
    return " ".join(out).strip()


def _roles(requested: str | None) -> list[Path]:
    if not MEMORY_ROOT.is_dir():
        sys.exit(f"no {MEMORY_ROOT} here -- run from the repo root")
    if requested:
        path = MEMORY_ROOT / requested
        if not path.is_dir():
            available = ", ".join(sorted(p.name for p in MEMORY_ROOT.iterdir() if p.is_dir()))
            sys.exit(f"no such role {requested!r}; have: {available}")
        return [path]
    return sorted(p for p in MEMORY_ROOT.iterdir() if p.is_dir())


def _score(terms: list[str], name: str, description: str, body: str) -> tuple[int, list[str]]:
    """`(score, matching body lines)` for one file against `terms`.

    A file must match **every** term to score at all -- an AND, not an OR. With
    a two-word query an OR degrades to listing most of the directory, which is
    the failure the index already had.
    """
    haystack_name = f"{name} {description}".lower()
    haystack_body = body.lower()
    score = 0
    for term in terms:
        in_name = haystack_name.count(term)
        in_body = haystack_body.count(term)
        if not in_name and not in_body:
            return 0, []
        score += NAME_WEIGHT * in_name + in_body
    hits = [
        line.strip()
        for line in body.splitlines()
        if line.strip() and all(term in line.lower() for term in terms)
    ]
    return score, hits


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search or list agent memory, building the index on the fly.",
        epilog="With no query, lists every memory newest first -- the old MEMORY.md, derived.",
    )
    parser.add_argument("query", nargs="*", help="terms; a file must match all of them")
    parser.add_argument("-r", "--role", help="restrict to one role (default: all)")
    parser.add_argument(
        "--body", action="store_true", help="also print the matching body lines, not just the hit"
    )
    parser.add_argument(
        "-n", "--limit", type=int, default=0, help="stop after N hits (default: no limit)"
    )
    args = parser.parse_args()

    terms = [t.lower() for t in args.query]
    rows: list[tuple[int, float, str, str, str, list[str]]] = []

    for role in _roles(args.role):
        for path in role.glob("*.md"):
            if path.name == "MEMORY.md":
                continue  # a leftover index is data about data; never a hit
            text = path.read_text(encoding="utf-8", errors="replace")
            description = _description(text)
            if terms:
                score, hits = _score(terms, path.stem, description, text)
                if not score:
                    continue
            else:
                score, hits = 0, []
            rows.append(
                (score, path.stat().st_mtime, role.name, path.name, description, hits)
            )

    # Query: best match first. No query: newest first, which is what someone
    # listing a memory directory almost always wants -- the index was in
    # append order, so its tail was the newest and also the part a read limit
    # truncated first.
    rows.sort(key=lambda r: (-r[0], -r[1]) if terms else (-r[1],))
    if args.limit > 0:
        rows = rows[: args.limit]

    if not rows:
        print(
            f"no memory matching {' '.join(args.query)!r}"
            + (f" in {args.role}" if args.role else "")
            + " -- NOT INDEXED YET is not the same as DOES NOT EXIST; grep the repo too",
            file=sys.stderr,
        )
        return 1

    width = max(len(r[2]) for r in rows)
    for _score_, _mtime, role_name, filename, description, hits in rows:
        print(f"{role_name:<{width}}  {filename}")
        if description:
            print(f"{'':<{width}}  {description}")
        if args.body:
            for line in hits[:3]:
                print(f"{'':<{width}}  | {line[:160]}")
    # stdout, and last: on stderr it flushes ahead of the results and reads as
    # a header for a list that has not been printed yet.
    print(f"\n{len(rows)} memor{'y' if len(rows) == 1 else 'ies'}. Read a file before relying on it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
