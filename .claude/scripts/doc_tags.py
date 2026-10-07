#!/usr/bin/env python3
"""Shared logic for doc-tags-propose.sh (Stage A of
plans/obsidian-links-and-tags/plan-document-graph.md): harvest candidate topic tags, measure each
one's reach against the real document corpus, and report a ranked, human-sized proposal list.

This tool never writes a tag into docs/TAGS.md and never writes a block into any document --
"closed vocabulary" means a human approves every row before the generator (doc_provenance.py) may
emit it. The only file this writes is docs/TAGS.proposals.md, a disposable candidate list the user
edits down and then promotes by hand.

Two counts per candidate, and the distinction is load-bearing (task spec, and
plan-document-graph.md Sec.2/Sec.8):

  - repo-wide reach: measured over EVERY document unit of the four in-scope kinds (converted
    roadmap entries, research notes, acceptance cards, plan directories) across the whole repo.
    This is what decides the 3-25 admission band -- hub size is a property of the corpus, not of
    whichever slice is being tagged today.
  - in-scope reach: measured over Stage A's own 35 units (the 22 audio-adapter/ROADMAP/AA-*.md
    entries + the 13 documents that already carry a doc-provenance block). This decides whether a
    tag is worth emitting NOW, independent of whether it is admissible repo-wide.

Usage:
    doc_tags.py propose          -- print the ranked table, write docs/TAGS.proposals.md
    doc_tags.py measure <term>   -- one candidate's counts, for ad hoc checking
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROVENANCE_START = "<!-- doc-provenance:start -->"
ENTRY_ID_RE = re.compile(r"^[A-Z]+-[A-Za-z0-9.]+$")

# Band from docs/TAGS.md / plan-document-graph.md Sec.3 and Sec.8.
BAND_MIN = 3
BAND_MAX = 25

# How many in-band candidates to show expanded, ranked by in-scope reach -- the task's own
# "8-12 strong candidates" instruction, and the plan's "the user will not grind through 200
# proposals" reasoning for Sec.2(b).
BATCH_SIZE = 12

KIND_LABELS = {
    "entry": "roadmap",
    "research": "research",
    "acceptance": "acceptance",
    "plan": "plan",
}

# ID-like prefixes (root CLAUDE.md's "Backlog Management", plus PB -- body-layer's retired
# pre-rename milestone numbering, e.g. "PB-1.5", still mentioned in older prose) whose matches
# are roadmap/milestone references, not topic candidates (TAGS.md rule 1: "tag only what the
# entry's path and ID do not already say").
_KNOWN_ID_PREFIXES = {"AA", "BL", "WM", "AC", "MI", "BR", "M", "X", "PB"}

_STOPWORDS = frozenset(
    """
    this that these those with from into onto over under about above below between after
    before while when where which what whose whom whether while since until because although
    though than then there here their there's its his her your yours ours theirs them they
    the and for are was were been being have has had having does did doing will would
    should could might must shall can cannot could've should've would've isn't aren't
    wasn't weren't hasn't haven't hadn't doesn't don't didn't won't wouldn't shan't shouldn't
    couldn't mustn't let's that's who's what's here's there's when's where's why's how's
    not only own same each few more most other some such nor too very just also
    once again further once more most other some such only own same more most
    into onto over under again further then once here there when where why how all any
    each few more most other some such nor not only own same than too very s t can will
    just don should now also would could still even already always never ever
    that this what which who whom whose where when while because although though since until
    plan plans roadmap entry entries document documents docs file files stage stages note
    notes acceptance research line lines text block blocks link links tag tags kind kinds
    task tasks user users agent agents repo project subproject review reviewer implement
    implemented implementer implementation decision decisions section sections table rows
    row column columns step steps word words phrase candidate candidates measured measure
    yes no done open status needs flight evidence decision for the a an is it to of in on
    as by at or if so be do go up out no not but you we he she they them his her our your
    their was were been being have has had having
    """.split()
)

ATX_HEADING_RE = re.compile(r"^#{1,6}\s.*$", re.MULTILINE)

# Cross-cutting document-TEMPLATE vocabulary, not topics: dod-check.md/review.md/security-*.md's
# own repeated section names and cross-references to them ("see Optional Refinements below"),
# plus common protocol/API field names (Content-Length/Content-Type). Stripping ATX headings
# (see ATX_HEADING_RE) removes the heading itself; this removes the same phrase when it recurs
# as an inline cross-reference in prose, which the heading strip cannot catch. This is a
# precision filter on known structural vocabulary, not a hand-seeding of real topic candidates --
# nothing here is a domain term (SPU-8, BTR-70, aircraft-manipulation, ...) the harvest should
# find; it exists because every one of these recurs across >=3 of this project's own document
# *templates*, which a frequency-based harvester cannot otherwise tell apart from a real topic.
_PROCESS_VOCAB = frozenset(
    {
        "action-required",
        "optional-refinements",
        "optional-refinement",
        "required-fixes",
        "required-fix",
        "reproducible-test",
        "possible-approaches",
        "edge-cases",
        "pass-criteria",
        "see-decision",
        "see-finding",
        "see-risks",
        "see-stage",
        "test-cases",
        "tests-added",
        "milestone-completion",
        "escalation-rules",
        "code-quality",
        "second-order-effect",
        "second-order-effects",
        "debug-output",
        "covers-stage",
        "current-focus",
        "invariant-check",
        "non-obvious-behavior",
        "turning-point",
        "notable-discoveries",
        "affected-modules",
        "content-length",
        "content-type",
        "code-findings",
        "security-deep-analysis",
        "dependency-status",
        "checklist-results",
        "verification-results",
        "mechanical-checks",
        "cancel-task",
        "performance-reviewer",
    }
)
ID_TOKEN_RE = re.compile(r"\b[A-Z]{2,6}-\d{1,3}[A-Za-z]{0,2}\b")
DIGIT_ID_RE = re.compile(r"\b\d{1,2}[A-Z]\d{2,4}\b")
TITLE_PHRASE_RE = re.compile(
    r"\b[A-Z][a-z0-9]{2,}(?:-[A-Za-z0-9]+)?(?:[ -][A-Z][a-z0-9]{2,}(?:-[A-Za-z0-9]+)?){1,2}\b"
)

TAG_SECTION_RE = re.compile(r"^### `#([A-Za-z0-9/_-]+)`\s*$", re.MULTILINE)
MATCHES_LINE_RE = re.compile(r"^- \*\*Matches:\*\* `([^`]+)`\s*$", re.MULTILINE)


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(out.stdout.strip())


def graph_json_path(root: Path) -> Path | None:
    """Borrow the main checkout's graph when run from a worktree -- same pattern as gq.sh,
    since graphify-out/ is gitignored and exists only in the main checkout."""
    local = root / "graphify-out" / "graph.json"
    if local.is_file():
        return local
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if common.returncode == 0 and common.stdout.strip():
        main_root = (root / common.stdout.strip()).resolve().parent
        candidate = main_root / "graphify-out" / "graph.json"
        if candidate.is_file():
            return candidate
    return None


@dataclass
class DocUnit:
    kind: str  # "entry" | "research" | "acceptance" | "plan"
    rel_path: str  # representative file, repo-root-relative, posix form
    files: list[str]  # every file contributing matching text (plan: all siblings)
    raw_text: str  # concatenated original-case text, used for extraction
    lower_text: str  # same text, lowercased, used for matching


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _subproject_dirs(root: Path) -> list[str]:
    return sorted(p.parent.name for p in root.glob("*/pyproject.toml"))


def entry_units(root: Path) -> list[DocUnit]:
    units = []
    for sub in _subproject_dirs(root):
        roadmap_dir = root / sub / "ROADMAP"
        if not roadmap_dir.is_dir():
            continue
        for f in sorted(roadmap_dir.glob("*.md")):
            if not ENTRY_ID_RE.match(f.stem):
                continue  # the index file, e.g. audio-adapter-roadmap.md
            raw = _read(f)
            rel = f.relative_to(root).as_posix()
            units.append(DocUnit("entry", rel, [rel], raw, raw.lower()))
    return units


def research_units(root: Path) -> list[DocUnit]:
    units = []
    for f in sorted(root.rglob("research/*.md")):
        rel = f.relative_to(root).as_posix()
        if rel.startswith(".claude/") or rel.startswith("plans/archive/"):
            continue
        raw = _read(f)
        units.append(DocUnit("research", rel, [rel], raw, raw.lower()))
    return units


def acceptance_units(root: Path) -> list[DocUnit]:
    units = []
    d = root / "docs" / "acceptance"
    if d.is_dir():
        for f in sorted(d.glob("*.md")):
            rel = f.relative_to(root).as_posix()
            raw = _read(f)
            units.append(DocUnit("acceptance", rel, [rel], raw, raw.lower()))
    return units


def plan_units(root: Path) -> list[DocUnit]:
    """A plan directory is one unit, matched over all its .md files together
    (plan-document-graph.md Sec.1) -- but the block (were one ever written) always lands on
    plan.md, the directory's designated representative (docs/DOC_CONVENTIONS.md)."""
    units = []
    plans_dir = root / "plans"
    if not plans_dir.is_dir():
        return units
    for d in sorted(p for p in plans_dir.iterdir() if p.is_dir() and p.name != "archive"):
        md_files = sorted(d.glob("*.md"))
        if not md_files:
            continue
        rep = d / "plan.md"
        rep_path = rep if rep.is_file() else md_files[0]
        rep_rel = rep_path.relative_to(root).as_posix()
        files = [f.relative_to(root).as_posix() for f in md_files]
        raw = "\n".join(_read(f) for f in md_files)
        units.append(DocUnit("plan", rep_rel, files, raw, raw.lower()))
    return units


def all_units(root: Path) -> list[DocUnit]:
    """Repo-wide document units of the four in-scope kinds -- plan-document-graph.md Sec.8's
    243-unit count (23 converted roadmap + 96 research + 32 acceptance + 92 plan, measured
    2026-10-07; this function re-measures live rather than trusting that figure to still hold)."""
    return entry_units(root) + research_units(root) + acceptance_units(root) + plan_units(root)


def has_provenance_block(root: Path, unit: DocUnit) -> bool:
    """True only if the unit's own REPRESENTATIVE file carries a real doc-provenance block --
    not merely if some file inside it mentions the delimiter in quoted/prose form (both
    docs/DOC_CONVENTIONS.md and plans/obsidian-links-and-tags/implementation.md quote the
    delimiter as documentation; neither is a real block, and neither is a research/acceptance/plan
    *unit*'s representative file, so checking only the representative file's own text already
    excludes both without special-casing them)."""
    if unit.kind == "entry":
        return False
    text = _read(root / unit.rel_path)
    return PROVENANCE_START in text


def in_scope_units(root: Path, units: list[DocUnit]) -> list[DocUnit]:
    """Stage A's own 35: all 22 converted audio-adapter entries + the 13 documents that already
    carry a doc-provenance block (task scope, and implementation.md's Stage A0 "Files Changed")."""
    return [
        u
        for u in units
        if (u.kind == "entry" and u.rel_path.startswith("audio-adapter/ROADMAP/"))
        or has_provenance_block(root, u)
    ]


def normalize_candidate(raw: str) -> str:
    """Hardware/ID-style tokens (all caps/digits/hyphens, e.g. SPU-8, 9K113) keep their casing --
    that is how the user drew and would type them. Everything else becomes flat lowercase-hyphen
    (TAGS.md rule 3)."""
    if re.fullmatch(r"[A-Z0-9-]+", raw):
        return raw
    return re.sub(r"[ _]+", "-", raw.strip()).lower()


def load_graphify_doc_labels(root: Path, units: list[DocUnit]) -> dict[str, list[str]]:
    """Node labels and community names graphify already attached to one of these document
    units' own files -- the "community labels, concept nodes" candidate source
    (plan-document-graph.md Sec.2(a)). Returns {} rather than raising when no graph is reachable
    (a worktree with no main checkout to borrow from, or no graph built yet): this is one of
    three candidate sources, not a dependency the whole tool needs to run."""
    graph_path = graph_json_path(root)
    if graph_path is None:
        return {}
    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    unit_files = {f for u in units for f in u.files}
    by_file: dict[str, list[str]] = {}
    for node in data.get("nodes", []):
        source_file = node.get("source_file")
        if source_file not in unit_files:
            continue
        label = node.get("label")
        if label:
            by_file.setdefault(source_file, []).append(str(label))
        community_name = node.get("community_name")
        if community_name and not re.fullmatch(r"Community \d+", str(community_name)):
            by_file.setdefault(source_file, []).append(str(community_name))

    # Fold per-file labels up to the unit's representative path, since harvesting operates on
    # units, not individual files (a plan unit's labels can live on any of its sibling files).
    file_to_rep = {f: u.rel_path for u in units for f in u.files}
    by_unit: dict[str, list[str]] = {}
    for f, labels in by_file.items():
        rep = file_to_rep.get(f)
        if rep:
            by_unit.setdefault(rep, []).extend(labels)
    return by_unit


def harvest_occurrences(
    units: list[DocUnit], graphify_labels: dict[str, list[str]]
) -> dict[str, set[str]]:
    """Candidate harvesting from exactly the three sources plan-document-graph.md Sec.2(a)
    names: graphify's own community labels/concept-node labels, hardware/ID-shaped jargon tokens,
    and capitalised multi-word phrases -- all found in the documents' own prose or in the labels
    graphify has already attached to them. This is recall over precision, deliberately -- the
    banding step below is what turns a noisy harvest into a short, navigable list; nothing here
    is hand-seeded with the plan's own worked example terms.

    Deliberately NOT a source: raw document-frequency over every lowercase word in the corpus.
    An earlier version of this function did that too, and it produced two failures at once: a
    performance one (thousands of harvested words, each needing measurement, cost minutes) and a
    quality one (a project's documentation is dense with generic nouns -- "panel", "delay",
    "press" -- that recur in >=3 documents purely because they are common English, not because
    they name a topic; nothing in that signal distinguishes the two). The three sources above are
    exactly the ones the plan names, and all three are either ID-shaped or capitalised, which is
    a real (if imperfect) proxy for "this is a name, not incidental prose."

    Returns {candidate: {rel_path, ...}} -- every unit each candidate was found in, gathered in
    ONE pass over the corpus. This doubles as the repo-wide measurement: a second full-corpus
    regex scan per candidate is exactly the performance trap described above, so it is never
    done for the harvested set. Precision lost by not re-scanning with the hyphen/space-tolerant
    `candidate_pattern` is accepted here -- this is a proposal tool, not the generator, and
    `measure_one` below still does a real regex scan for a single candidate a human wants to
    check closely."""
    occurrences: dict[str, set[str]] = {}

    for u in units:
        extra_text = " ".join(graphify_labels.get(u.rel_path, []))
        # Markdown ATX headings ("## Second-Order Effect", "### Content-Length") are structural
        # boilerplate repeated across many dod-check.md/review.md files -- Title Case by
        # convention, not by naming a topic -- so they are stripped before phrase/token
        # harvesting. Measurement later still matches against the unit's full text, headings
        # included, since a real topic mentioned only in a heading should still count.
        body_only = ATX_HEADING_RE.sub("", u.raw_text)
        prose_and_labels = body_only + "\n" + extra_text

        found_here: set[str] = set()
        for m in ID_TOKEN_RE.finditer(prose_and_labels):
            token = m.group(0)
            if token.split("-")[0] in _KNOWN_ID_PREFIXES:
                continue  # a roadmap/milestone ID, not a topic candidate
            found_here.add(normalize_candidate(token))
        for m in DIGIT_ID_RE.finditer(prose_and_labels):
            found_here.add(normalize_candidate(m.group(0)))
        for m in TITLE_PHRASE_RE.finditer(prose_and_labels):
            phrase = m.group(0)
            first_word = phrase.split()[0].split("-")[0].lower()
            if first_word in _STOPWORDS:
                continue  # a capitalised sentence-starter, not a name
            found_here.add(normalize_candidate(phrase))
        for cand in found_here:
            if cand.lower() in _PROCESS_VOCAB:
                continue  # document-template boilerplate, not a topic -- see _PROCESS_VOCAB
            occurrences.setdefault(cand, set()).add(u.rel_path)

    return occurrences


def candidate_inner_pattern(candidate: str) -> str:
    """Hyphen/space-tolerant inner pattern, no word boundaries -- the same shape docs/TAGS.md's
    own example `Matches:` value uses (`SPU-?8`, not `\\bSPU-?8\\b`); `load_approved_tags` and
    doc_provenance.py's matching both add the `\\b...\\b` wrapping themselves, so this is what a
    promoted proposal row should carry. Each hyphen/space-separated part is escaped on its own
    and then rejoined with the tolerant separator -- escaping the whole string first and
    substituting afterwards (an earlier version of this function did that) corrupts the escape:
    re.escape("SPU-8") produces the literal two characters "\\-", and a substitution looking for
    a bare "-" afterwards matches only the second character, leaving a dangling backslash in the
    compiled pattern (found by reading the generated docs/TAGS.proposals.md output, not by
    inspection -- it compiled and ran without error, it just matched the wrong, broken text)."""
    parts = [p for p in re.split(r"[-\s]+", candidate.strip()) if p]
    return r"[- ]?".join(re.escape(p) for p in parts)


def candidate_pattern(candidate: str) -> re.Pattern[str]:
    """Word-bounded, case-insensitive compiled form of candidate_inner_pattern, for measurement."""
    return re.compile(r"\b" + candidate_inner_pattern(candidate) + r"\b", re.IGNORECASE)


@dataclass
class Measurement:
    candidate: str
    pattern: str
    repo_total: int
    repo_by_kind: dict[str, int]
    repo_files: list[str]
    in_scope_total: int
    in_scope_by_kind: dict[str, int]
    in_scope_files: list[str]


def measurement_from_occurrence(
    candidate: str, repo_files_found: set[str], units_by_path: dict[str, DocUnit], in_scope: set[str]
) -> Measurement:
    repo_files = sorted(repo_files_found)
    repo_by_kind: dict[str, int] = {}
    in_scope_by_kind: dict[str, int] = {}
    in_scope_files: list[str] = []

    for rel_path in repo_files:
        kind = units_by_path[rel_path].kind
        repo_by_kind[kind] = repo_by_kind.get(kind, 0) + 1
        if rel_path in in_scope:
            in_scope_by_kind[kind] = in_scope_by_kind.get(kind, 0) + 1
            in_scope_files.append(rel_path)

    return Measurement(
        candidate=candidate,
        pattern=candidate_inner_pattern(candidate),
        repo_total=len(repo_files),
        repo_by_kind=repo_by_kind,
        repo_files=repo_files,
        in_scope_total=len(in_scope_files),
        in_scope_by_kind=in_scope_by_kind,
        in_scope_files=in_scope_files,
    )


def measure(pattern: re.Pattern[str], units: list[DocUnit], in_scope: set[str]) -> Measurement:
    """Real regex scan over every unit for exactly one candidate -- used by the `measure`
    subcommand and the drift check, both of which look at a handful of candidates, never the
    full harvested set (see harvest_occurrences' docstring for why that distinction matters)."""
    repo_by_kind: dict[str, int] = {}
    repo_files: list[str] = []
    in_scope_by_kind: dict[str, int] = {}
    in_scope_files: list[str] = []

    for u in units:
        if not pattern.search(u.lower_text):
            continue
        repo_by_kind[u.kind] = repo_by_kind.get(u.kind, 0) + 1
        repo_files.append(u.rel_path)
        if u.rel_path in in_scope:
            in_scope_by_kind[u.kind] = in_scope_by_kind.get(u.kind, 0) + 1
            in_scope_files.append(u.rel_path)

    return Measurement(
        candidate="",
        pattern=pattern.pattern,
        repo_total=len(repo_files),
        repo_by_kind=repo_by_kind,
        repo_files=repo_files,
        in_scope_total=len(in_scope_files),
        in_scope_by_kind=in_scope_by_kind,
        in_scope_files=in_scope_files,
    )


def band(repo_total: int) -> str:
    if repo_total < BAND_MIN:
        return "TOO NARROW"
    if repo_total > BAND_MAX:
        return "TOO BROAD"
    return "CANDIDATE"


def already_said_by_path(candidate: str, subprojects: list[str]) -> bool:
    flat = candidate.lower().replace("-", "")
    for sub in subprojects:
        if flat == sub.replace("-", ""):
            return True
    return False


def by_kind_str(by_kind: dict[str, int]) -> str:
    parts = [f"{by_kind.get(k, 0)} {label}" for k, label in KIND_LABELS.items() if by_kind.get(k)]
    return ", ".join(parts) if parts else "0"


def _strip_fenced_code(text: str) -> str:
    """Removes fenced code blocks before scanning for `### #tag` sections -- docs/TAGS.md's own
    "Format" section demonstrates the section shape inside a fence (its `#SPU-8` example), which
    a naive scan reads as a real approved tag (found live, running doc_provenance.py's own
    `plan` mode against the committed tree -- see that module's identical helper for the full
    story). Mirrors roadmap-tag-vocabulary-gate.sh's fence handling, odd-count included."""
    lines = text.split("\n")
    if sum(1 for line in lines if re.match(r"^\s*```", line)) % 2 != 0:
        return text  # malformed; load_approved_tags' caller treats an empty result as "none yet"
    out = []
    fence = False
    for line in lines:
        if re.match(r"^\s*```", line):
            fence = not fence
            continue
        if not fence:
            out.append(line)
    return "\n".join(out)


def load_approved_tags(root: Path) -> dict[str, re.Pattern[str]]:
    """Every approved `### \\`#tag\\`` section in docs/TAGS.md with its own `**Matches:**` line.
    Empty today -- Stage A ends at a candidate list, nothing is approved yet."""
    tags_path = root / "docs" / "TAGS.md"
    text = _strip_fenced_code(_read(tags_path))
    approved: dict[str, re.Pattern[str]] = {}
    for m in TAG_SECTION_RE.finditer(text):
        name = m.group(1)
        rest = text[m.end() :]
        next_section = rest.find("\n### ")
        section = rest[:next_section] if next_section != -1 else rest
        match_m = MATCHES_LINE_RE.search(section)
        if match_m:
            approved[name] = re.compile(r"\b" + match_m.group(1) + r"\b", re.IGNORECASE)
    return approved


def propose(root: Path) -> int:
    units = all_units(root)
    units_by_path = {u.rel_path: u for u in units}
    in_scope_paths = {u.rel_path for u in in_scope_units(root, units)}
    subprojects = _subproject_dirs(root)

    graphify_labels = load_graphify_doc_labels(root, units)
    if not graphify_labels:
        print("doc-tags-propose: note: no graph reachable -- candidates drawn from document "
              "prose only, not graphify community labels (see load_graphify_doc_labels)\n",
              file=sys.stderr)
    occurrences = harvest_occurrences(units, graphify_labels)

    already_said = sorted(c for c in occurrences if already_said_by_path(c, subprojects))
    measurements = [
        measurement_from_occurrence(cand, files, units_by_path, in_scope_paths)
        for cand, files in occurrences.items()
        if not already_said_by_path(cand, subprojects)
    ]

    in_band = [m for m in measurements if band(m.repo_total) == "CANDIDATE"]
    too_broad = [m for m in measurements if band(m.repo_total) == "TOO BROAD"]
    too_narrow = [m for m in measurements if band(m.repo_total) == "TOO NARROW"]

    in_band.sort(key=lambda m: (-m.in_scope_total, -m.repo_total, m.candidate))
    batch = in_band[:BATCH_SIZE]
    overflow = in_band[BATCH_SIZE:]

    print(
        f"doc-tags-propose: {len(units)} document units measured repo-wide "
        f"({len(in_scope_paths)} in Stage A's scope)"
    )
    print(f"doc-tags-propose: {len(occurrences)} candidate(s) harvested, {len(in_band)} in band\n")

    for m in batch:
        tag = f"#{m.candidate}"
        print(
            f"CANDIDATE   {tag:22s} {m.repo_total:3d} units  ({by_kind_str(m.repo_by_kind)})"
            f"  [in-scope: {m.in_scope_total}]"
        )
        for f in m.repo_files[:4]:
            print(f"            {f}")
        if len(m.repo_files) > 4:
            print(f"            ... and {len(m.repo_files) - 4} more")

    if overflow:
        print(f"\n{len(overflow)} more in-band candidate(s), not shown (batch size {BATCH_SIZE}):")
        for m in overflow:
            print(f"  #{m.candidate} -- {m.repo_total} units [in-scope: {m.in_scope_total}]")

    COMPACT_LIMIT = 30

    if too_broad:
        print(f"\n{len(too_broad)} TOO BROAD (over {BAND_MAX} units -- split before proposing):")
        for m in sorted(too_broad, key=lambda m: -m.repo_total)[:COMPACT_LIMIT]:
            print(f"  TOO BROAD   #{m.candidate:20s} {m.repo_total} units -- split before proposing")
        if len(too_broad) > COMPACT_LIMIT:
            print(f"  ... and {len(too_broad) - COMPACT_LIMIT} more")

    if too_narrow:
        print(f"\n{len(too_narrow)} TOO NARROW (under {BAND_MIN} units) -- compact, not expanded:")
        for m in sorted(too_narrow, key=lambda m: (m.repo_total, m.candidate))[:COMPACT_LIMIT]:
            print(f"  TOO NARROW  #{m.candidate:20s} {m.repo_total} units")
        if len(too_narrow) > COMPACT_LIMIT:
            print(f"  ... and {len(too_narrow) - COMPACT_LIMIT} more")

    if already_said:
        print(f"\n{len(already_said)} ALREADY-SAID (restates a subproject path), rejected before measuring:")
        for c in already_said[:COMPACT_LIMIT]:
            print(f"  ALREADY-SAID #{c}")
        if len(already_said) > COMPACT_LIMIT:
            print(f"  ... and {len(already_said) - COMPACT_LIMIT} more")

    approved = load_approved_tags(root)
    if approved:
        print("\nDrift check on already-approved tags:")
        for name, pattern in sorted(approved.items()):
            m = measure(pattern, units, in_scope_paths)
            flag = "" if band(m.repo_total) == "CANDIDATE" else f"  <-- now {band(m.repo_total)}"
            print(f"  #{name}: {m.repo_total} units{flag}")
    else:
        print("\nNo approved tags yet -- nothing to drift-check.")

    write_proposals_file(root, batch)
    print(f"\ndoc-tags-propose: wrote docs/TAGS.proposals.md ({len(batch)} candidate(s))")
    return 0


def write_proposals_file(root: Path, batch: list[Measurement]) -> None:
    lines = [
        "# Tag proposals (disposable)",
        "",
        "Generated by `.claude/scripts/doc-tags-propose.sh`. Delete the rows you do not want;",
        "promote what remains into `docs/TAGS.md` by hand, in the `### \\`#tag\\`` section format",
        "docs/TAGS.md documents. Never read by a gate -- this file is a work surface, not part of",
        "the convention.",
        "",
    ]
    for m in batch:
        lines.append(f"### `#{m.candidate}`")
        lines.append("")
        lines.append(f"- **Matches:** `{m.pattern}`")
        lines.append(
            f"- **Measured:** {m.repo_total} units, repo-wide ({by_kind_str(m.repo_by_kind)}); "
            f"{m.in_scope_total} in Stage A's scope"
        )
        lines.append("- (one-line description of what this topic covers -- fill in by hand)")
        lines.append("")
    (root / "docs" / "TAGS.proposals.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def measure_one(root: Path, term: str) -> int:
    units = all_units(root)
    in_scope_paths = {u.rel_path for u in in_scope_units(root, units)}
    pattern = candidate_pattern(normalize_candidate(term))
    m = measure(pattern, units, in_scope_paths)
    print(f"#{term}: {m.repo_total} units repo-wide ({by_kind_str(m.repo_by_kind)})  "
          f"-- {band(m.repo_total)}")
    print(f"  in-scope: {m.in_scope_total} ({by_kind_str(m.in_scope_by_kind)})")
    for f in m.repo_files:
        print(f"  {f}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("propose", "measure"):
        print(f"usage: {argv[0]} propose | measure <term>", file=sys.stderr)
        return 2
    root = repo_root()
    if argv[1] == "propose":
        return propose(root)
    if argv[1] == "measure":
        if len(argv) != 3:
            print(f"usage: {argv[0]} measure <term>", file=sys.stderr)
            return 2
        return measure_one(root, argv[2])
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:  # pragma: no cover -- loud failure, never a silent skip
        print(f"doc-tags-propose: ERROR: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
