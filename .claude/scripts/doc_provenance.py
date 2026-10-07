#!/usr/bin/env python3
"""Shared logic for doc-provenance-refresh.sh and doc-provenance-gate.sh.

Stage A0 of plans/obsidian-links-and-tags/plan-document-graph.md: lift the document citations
that already exist in prose inside audio-adapter/ROADMAP/AA-*.md into a generated, delimited
block on the *cited* document (never on the entry) -- a research note, an acceptance card, or a
plan's plan.md. Cite what is there; infer nothing. No typed dependency edges, no git-history
inference -- those are later stages, out of scope here.

Stage A/B (plan-document-graph.md Sec.1/Sec.3) extends the same block with a **Topics:** line,
on every document unit including the roadmap entries themselves -- the one document kind that
never carries a citation line of its own ("Roadmap: no -- it IS one"). A tag is only ever emitted
if it has an approved section in docs/TAGS.md (read fresh on every run via
load_approved_topic_tags): the vocabulary is closed, and this generator is the enforcement of
that, not docs/TAGS.md's prose alone. With no approved tags, every Topics line is empty and the
entry-only half of this extension writes nothing -- this is Stage A's own stop point, by
construction rather than by a special case.

Deterministic and read-only on the entry files' own citations. The files this writes are: every
document a converted entry cites, and (once a topic tag is approved) the entries themselves.

Usage:
    doc_provenance.py plan                 -- print what would change, write nothing
    doc_provenance.py refresh              -- write the blocks in place
    doc_provenance.py gate                 -- verify-only; regenerate into a temp dir and diff
"""

from __future__ import annotations

import difflib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

START = "<!-- doc-provenance:start -->"
END = "<!-- doc-provenance:end -->"

ENTRY_ID_RE = re.compile(r"^[A-Z]+-[A-Za-z0-9.]+$")

# Citation shapes already present in audio-adapter/ROADMAP/AA-*.md prose (see
# plans/obsidian-links-and-tags/plan-document-graph.md Stage A0, and the implementer's own
# measurement over the 22 entries). Order of alternatives does not matter -- each is matched
# independently against the full entry text.
RESEARCH_RE = re.compile(r"(?:([A-Za-z0-9_-]+)/)?research/([A-Za-z0-9._-]+\.md)")
ACCEPTANCE_RE = re.compile(r"docs/acceptance/[A-Za-z0-9._-]+\.md")
PLAN_DIR_RE = re.compile(r"plans/([A-Za-z0-9_-]+)/")

LABELS = {
    "research": "Evidence for",
    "flight": "Flight for",
    "plan": "Decision for",
    # "entry" deliberately has no label: a roadmap entry's block carries Topics only, never a
    # Roadmap/Evidence/Flight/Decision line -- it IS the thing other documents cite, so it never
    # cites itself (plan-document-graph.md's per-kind table).
}

# Topic-tag vocabulary, read fresh from docs/TAGS.md on every run (Stage A/B). A tag's own
# `### \`#tag\`` section header and its `**Matches:**` line -- the same shape doc_tags.py's
# load_approved_tags reads, duplicated here rather than imported so this module stays runnable
# standalone, matching every other script in this family.
TAG_SECTION_RE = re.compile(r"^### `#([A-Za-z0-9/_-]+)`\s*$", re.MULTILINE)
MATCHES_LINE_RE = re.compile(r"^- \*\*Matches:\*\* `([^`]+)`\s*$", re.MULTILINE)


class MalformedBlock(Exception):
    pass


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(out.stdout.strip())


def id_sort_key(entry_id: str) -> list:
    """Sort key giving AA-1 < AA-1.1 < ... < AA-1.6 < AA-2 < ... < AA-B1 < AA-B2, independent
    of filesystem listing order -- entry ids are not purely numeric (AA-B1 mixes a letter in)."""
    prefix, _, rest = entry_id.partition("-")
    key: list = [prefix]
    for part in rest.split("."):
        m = re.match(r"^([A-Za-z]*)(\d*)$", part)
        assert m is not None
        letters = m.group(1) or ""
        digits = int(m.group(2)) if m.group(2) else 0
        key.append((letters, digits))
    return key


def find_entries(root: Path) -> list[tuple[str, Path]]:
    """Every real entry file under audio-adapter/ROADMAP/ (the index excluded), sorted by id."""
    roadmap_dir = root / "audio-adapter" / "ROADMAP"
    entries = []
    for f in roadmap_dir.glob("*.md"):
        entry_id = f.stem
        if ENTRY_ID_RE.match(entry_id):
            entries.append((entry_id, f))
    entries.sort(key=lambda pair: id_sort_key(pair[0]))
    return entries


def _strip_fenced_code(text: str) -> str:
    """Removes fenced code blocks (```...```) before scanning for `### #tag` sections --
    docs/TAGS.md's own "Format" section demonstrates the section shape inside a fence (its
    `#SPU-8` example), and a naive scan reads that illustration as a real approved tag: found
    live, by running this module's own `plan` mode against the committed tree and seeing
    `1 approved topic tag(s)` when docs/TAGS.md's prose says "None approved yet." Mirrors
    roadmap-tag-vocabulary-gate.sh's own fence handling, including treating an odd fence count
    as a hard failure rather than silently scanning past an unclosed fence."""
    lines = text.split("\n")
    fence_count = sum(1 for line in lines if re.match(r"^\s*```", line))
    if fence_count % 2 != 0:
        raise MalformedBlock(
            f"docs/TAGS.md has an unbalanced fenced code block ({fence_count} delimiter(s)) -- "
            "cannot safely scan for approved tag sections"
        )
    out = []
    fence = False
    for line in lines:
        if re.match(r"^\s*```", line):
            fence = not fence
            continue
        if not fence:
            out.append(line)
    return "\n".join(out)


def load_approved_topic_tags(root: Path) -> list[tuple[str, re.Pattern[str]]]:
    """Every approved `### \\`#tag\\`` section in docs/TAGS.md, in declaration order -- order
    matters here, since it is what makes a document's **Topics:** line byte-stable across runs
    rather than depending on dict/set iteration order. Empty today: Stage A ends at a candidate
    list (docs/TAGS.proposals.md), nothing is approved yet, so this always returns [] until the
    user promotes a row -- which is what makes "nothing is tagged this round" true by
    construction rather than by a special case in the generator."""
    tags_path = root / "docs" / "TAGS.md"
    try:
        text = _strip_fenced_code(tags_path.read_text(encoding="utf-8"))
    except OSError:
        return []
    approved: list[tuple[str, re.Pattern[str]]] = []
    for m in TAG_SECTION_RE.finditer(text):
        name = m.group(1)
        rest = text[m.end() :]
        next_section = rest.find("\n### ")
        section = rest[:next_section] if next_section != -1 else rest
        match_m = MATCHES_LINE_RE.search(section)
        if match_m:
            approved.append((name, re.compile(r"\b" + match_m.group(1) + r"\b", re.IGNORECASE)))
    return approved


def topics_for_text(text: str, approved: list[tuple[str, re.Pattern[str]]]) -> list[str]:
    """Every approved tag whose pattern matches anywhere in `text`, in docs/TAGS.md's own
    declaration order."""
    return [name for name, pattern in approved if pattern.search(text)]


def extract_citations(text: str) -> list[tuple[str, str]]:
    """Returns a de-duplicated, order-preserving list of (kind, target_rel_path) found in one
    entry's text. `target_rel_path` is always repo-root-relative."""
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for m in RESEARCH_RE.finditer(text):
        sub = m.group(1)
        filename = m.group(2)
        target = f"{sub}/research/{filename}" if sub else f"audio-adapter/research/{filename}"
        pair = ("research", target)
        if pair not in seen:
            seen.add(pair)
            found.append(pair)

    for m in ACCEPTANCE_RE.finditer(text):
        pair = ("flight", m.group(0))
        if pair not in seen:
            seen.add(pair)
            found.append(pair)

    for m in PLAN_DIR_RE.finditer(text):
        # A plan directory is one unit (plan-document-graph.md Sec.1): whichever specific
        # sibling file the prose names (or none at all, a bare directory mention), the block
        # always carries on plan.md -- the directory's designated representative.
        target = f"plans/{m.group(1)}/plan.md"
        pair = ("plan", target)
        if pair not in seen:
            seen.add(pair)
            found.append(pair)

    return found


def build_target_map(
    root: Path,
) -> tuple[dict[str, tuple[str, list[str]]], list[tuple[str, str, str]]]:
    """Returns (target -> (kind, [citing entry ids in ascending id order]), raw citation log).

    The raw log is (entry_id, kind, target) triples in the order discovered, for reporting.

    Every converted roadmap entry is ALSO added as its own unit, kind="entry", ids=[] -- the one
    document kind whose block never carries a citation line (Stage A/B's per-kind table: a
    roadmap entry gets Topics, never Roadmap, "it IS one"). No citation pattern in
    `extract_citations` can ever target a path under audio-adapter/ROADMAP/, so an entry can
    never collide with a cited target here.
    """
    target_map: dict[str, tuple[str, list[str]]] = {}
    log: list[tuple[str, str, str]] = []

    for entry_id, path in find_entries(root):
        text = path.read_text(encoding="utf-8")
        for kind, target in extract_citations(text):
            log.append((entry_id, kind, target))
            if target not in target_map:
                target_map[target] = (kind, [])
            existing_kind, ids = target_map[target]
            if existing_kind != kind:
                raise MalformedBlock(
                    f"{target} is cited as both '{existing_kind}' and '{kind}' -- "
                    "a document's kind must follow from its own path, not from who cites it"
                )
            if entry_id not in ids:
                ids.append(entry_id)

    for entry_id, path in find_entries(root):
        rel = path.relative_to(root).as_posix()
        target_map.setdefault(rel, ("entry", []))

    return target_map, log


def block_lines(kind: str, ids: list[str], topics: list[str]) -> list[str] | None:
    """Returns None -- no block at all, never an empty one -- when there is nothing to say:
    plan-document-graph.md Sec.1's "a line with no values is omitted entirely" rule, extended
    from citation lines to the whole block now that Topics can also be empty on its own."""
    body: list[str] = []
    if topics:
        body.append("**Topics:** " + " ".join(f"#{t}" for t in topics))
    if kind in LABELS:
        label = LABELS[kind]
        for entry_id in ids:
            body.append(f"**{label}:** [[{entry_id}]]")
    if not body:
        return None
    return [START, *body, END]


def find_h1_index(lines: list[str]) -> int | None:
    for i, line in enumerate(lines):
        if line.startswith("# "):
            return i
    return None


def strip_existing_block(lines: list[str]) -> list[str]:
    """Removes a well-formed existing doc-provenance block, plus exactly the one blank line
    `regenerate_content` inserts as a separator -- which side that blank is on depends on
    whether the block sits right after an H1 (blank *before* the block; the rest of the file
    already supplies its own blank after) or at the very top of a file with no H1 at all
    (no blank before possible; the inserted blank is the one *after* the block instead, see
    `regenerate_content`). Getting this wrong does not corrupt content, but it does break
    idempotency -- found live, by running the no-H1 (plan.md) path twice.

    Raises MalformedBlock on anything that is not exactly one clean block: an unmatched
    start/end, nesting, two blocks, or end-before-start. Never guesses."""
    start_count = lines.count(START)
    end_count = lines.count(END)

    if start_count == 0 and end_count == 0:
        return list(lines)
    if start_count != 1 or end_count != 1:
        raise MalformedBlock(
            f"found {start_count} start delimiter(s) and {end_count} end delimiter(s), "
            "expected exactly one of each (or neither)"
        )

    s = lines.index(START)
    e = lines.index(END)
    if e <= s:
        raise MalformedBlock(f"'{END}' at line {e + 1} appears before '{START}' at line {s + 1}")

    if s == 0:
        # No H1, no head: the block is the first thing in the file, so the inserted
        # separator blank is the one immediately AFTER the end delimiter. Strip every
        # consecutive blank there, not just one -- a file regenerated by an earlier, buggy
        # version of this function could have left more than one, and a strip that only
        # ever removes exactly one is not actually idempotent against that leftover state.
        remove_to = e + 1
        while remove_to < len(lines) and lines[remove_to] == "":
            remove_to += 1
        return lines[remove_to:]

    # A head (through the H1) precedes the block: the inserted separator blank is the one
    # immediately BEFORE the start delimiter. Same reasoning: strip every consecutive blank.
    remove_from = s
    while remove_from > 0 and lines[remove_from - 1] == "":
        remove_from -= 1
    return lines[:remove_from] + lines[e + 1 :]


def _stripped_lines(original_text: str) -> list[str]:
    """The file's lines with any existing, well-formed doc-provenance block (and its separator
    blank) removed -- shared by topic-matching (which must match the document's own content, not
    a block left over from a previous run) and regenerate_content (which rebuilds onto the same
    stripped base). Raises MalformedBlock on anything that is not exactly one clean block."""
    had_trailing_newline = original_text.endswith("\n")
    lines = original_text.split("\n")
    if had_trailing_newline:
        lines = lines[:-1]
    return strip_existing_block(lines)


def regenerate_content(original_text: str, kind: str, ids: list[str], topics: list[str]) -> str:
    stripped = _stripped_lines(original_text)
    new_block = block_lines(kind, ids, topics)

    if new_block is None:
        # Nothing to say -- no citations and no matching topic tag. The file reverts to its
        # stripped form rather than keeping a now-empty block (block_lines' own "never an empty
        # one" rule, applied here to the whole-block case).
        return "\n".join(stripped) + "\n"

    h1_idx = find_h1_index(stripped)
    if h1_idx is not None:
        new_lines = stripped[: h1_idx + 1] + [""] + new_block + stripped[h1_idx + 1 :]
    else:
        # No H1 at all -- true of every plans/*/plan.md in this corpus (they open with
        # "### Goal", never a top-level heading). The block goes at the very top of the file.
        new_lines = new_block + [""] + stripped

    return "\n".join(new_lines) + "\n"


def collect_ids_in_blocks(text: str) -> list[str]:
    """Every [[ID]] appearing on a line between a well-formed block's delimiters."""
    lines = text.split("\n")
    if START not in lines:
        return []
    s = lines.index(START)
    e = lines.index(END) if END in lines else len(lines)
    ids = []
    for line in lines[s + 1 : e]:
        ids.extend(re.findall(r"\[\[([A-Za-z0-9._-]+)\]\]", line))
    return ids


def plan(root: Path) -> int:
    target_map, log = build_target_map(root)
    approved_tags = load_approved_topic_tags(root)
    print(f"doc-provenance: {len(log)} citation(s) found across audio-adapter/ROADMAP/*.md")
    print(f"doc-provenance: {len(target_map)} distinct document unit(s) (cited documents + entries)")
    print(f"doc-provenance: {len(approved_tags)} approved topic tag(s)")
    known_ids = {entry_id for entry_id, _ in find_entries(root)}
    for target in sorted(target_map):
        kind, ids = target_map[target]
        full_path = root / target
        if not full_path.is_file():
            print(f"doc-provenance: ERROR: {target} (cited by {ids}) does not exist", file=sys.stderr)
            return 1
        for entry_id in ids:
            if entry_id not in known_ids:
                print(
                    f"doc-provenance: ERROR: {target} cites unknown entry id {entry_id}",
                    file=sys.stderr,
                )
                return 1
        try:
            body_text = "\n".join(_stripped_lines(full_path.read_text(encoding="utf-8")))
        except MalformedBlock as exc:
            print(f"doc-provenance: ERROR: {target}: {exc}", file=sys.stderr)
            return 1
        topics = topics_for_text(body_text, approved_tags)
        topics_str = f" topics={topics}" if topics else ""
        print(f"  [{kind:8s}] {target}  <-  {' '.join(ids)}{topics_str}")
    return 0


def refresh(root: Path, write: bool) -> int:
    target_map, _ = build_target_map(root)
    known_ids = {entry_id for entry_id, _ in find_entries(root)}
    approved_tags = load_approved_topic_tags(root)

    # Validate everything first -- no partial writes on a late failure.
    planned: dict[Path, str] = {}
    for target, (kind, ids) in target_map.items():
        full_path = root / target
        if not full_path.is_file():
            print(f"doc-provenance-refresh: ERROR: cited document missing: {target}", file=sys.stderr)
            return 1
        for entry_id in ids:
            if entry_id not in known_ids:
                print(
                    f"doc-provenance-refresh: ERROR: {target} cites unknown entry id {entry_id}",
                    file=sys.stderr,
                )
                return 1
        original = full_path.read_text(encoding="utf-8")
        try:
            body_text = "\n".join(_stripped_lines(original))
            topics = topics_for_text(body_text, approved_tags)
            new_text = regenerate_content(original, kind, ids, topics)
        except MalformedBlock as exc:
            print(f"doc-provenance-refresh: ERROR: {target}: {exc}", file=sys.stderr)
            return 1
        for new_id in collect_ids_in_blocks(new_text):
            if new_id not in known_ids:
                print(
                    f"doc-provenance-refresh: ERROR: {target}: generated block cites "
                    f"unknown entry id {new_id}",
                    file=sys.stderr,
                )
                return 1
        if new_text != original:
            planned[full_path] = new_text

    if not planned:
        print("doc-provenance-refresh: OK -- nothing to change")
        return 0

    for full_path, new_text in planned.items():
        if write:
            full_path.write_text(new_text, encoding="utf-8")
        rel = full_path.relative_to(root)
        print(f"doc-provenance-refresh: {'wrote' if write else 'would write'} {rel}")

    return 0


def gate(root: Path) -> int:
    target_map, _ = build_target_map(root)
    known_ids = {entry_id for entry_id, _ in find_entries(root)}
    approved_tags = load_approved_topic_tags(root)
    fail = False

    with tempfile.TemporaryDirectory(prefix="doc-provenance-gate-") as tmp:
        tmp_root = Path(tmp)
        for target, (kind, ids) in target_map.items():
            full_path = root / target
            if not full_path.is_file():
                print(
                    f"doc-provenance-gate: FAIL: cited document missing: {target}", file=sys.stderr
                )
                fail = True
                continue

            for entry_id in ids:
                if entry_id not in known_ids:
                    print(
                        f"doc-provenance-gate: FAIL: {target} cites unknown entry id {entry_id}",
                        file=sys.stderr,
                    )
                    fail = True

            original = full_path.read_text(encoding="utf-8")
            try:
                body_text = "\n".join(_stripped_lines(original))
                topics = topics_for_text(body_text, approved_tags)
                new_text = regenerate_content(original, kind, ids, topics)
            except MalformedBlock as exc:
                print(f"doc-provenance-gate: FAIL: {target}: {exc}", file=sys.stderr)
                fail = True
                continue

            for new_id in collect_ids_in_blocks(new_text):
                if new_id not in known_ids:
                    print(
                        f"doc-provenance-gate: FAIL: {target}: generated block cites "
                        f"unknown entry id {new_id}",
                        file=sys.stderr,
                    )
                    fail = True

            tmp_path = tmp_root / target
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(new_text, encoding="utf-8")

            if new_text != original:
                fail = True
                print(f"doc-provenance-gate: FAIL: {target} is stale or hand-edited", file=sys.stderr)
                diff = difflib.unified_diff(
                    original.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=f"a/{target}",
                    tofile=f"b/{target} (regenerated)",
                )
                sys.stderr.writelines(diff)
                print(
                    f"doc-provenance-gate: run .claude/scripts/doc-provenance-refresh.sh "
                    f"to regenerate {target}",
                    file=sys.stderr,
                )

    if fail:
        return 1
    print("doc-provenance-gate: OK")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("plan", "refresh", "check", "gate"):
        print(f"usage: {argv[0]} {{plan|refresh|check|gate}}", file=sys.stderr)
        return 2

    root = repo_root()
    mode = argv[1]
    if mode == "plan":
        return plan(root)
    if mode == "check":
        return refresh(root, write=False)
    if mode == "refresh":
        return refresh(root, write=True)
    if mode == "gate":
        return gate(root)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except MalformedBlock as exc:
        print(f"doc-provenance: ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # pragma: no cover -- loud failure, never a silent skip
        print(f"doc-provenance: ERROR: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
