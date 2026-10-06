---
name: bl11-round3-deletion-review
description: BL-11 round 3 — the test that decides which stale references a deletion must sweep (present-tense claim vs dated record), and why a misclassified reference still needs checking.
metadata:
  type: project
---

**When a deletion leaves prose references behind, the sweep boundary is not "is this a research
note?" It is: does the text claim to describe the code as it is now, or does it record what was
observed or decided at a stated time?** Present-tense claims about current code must be swept;
dated records must not be.

**Why:** deleting `_resolvable` / `_cohesive` from `perception/group_salience.py` left ~35 prose
mentions across research notes, `ROADMAP.md`/`BACKLOG.md` measurements, four plan directories and
four agent-memory files. Rewriting a dated measurement to use today's names makes it read as though
the measurement were taken against today's code — laundering, not tidying — and the old identifier
is itself the evidence trail: `git log -S _cohesive` only works if the note still *says*
`_cohesive`. The project already runs on this line (`plans/<feature>/review.md` is append-only;
memory is read as "what was true then, verify current state"), so it is a line to apply, not to
invent per deletion.

**How to apply:** run `git grep` for the identifier with the surviving `*_terms`-style names
filtered out, then sort hits into present-tense-about-current-code (fix) and dated-record (leave).
The hits that actually matter are `src/`, the test suite, and present-tense module documentation
(`docs/STRUCTURE.md`, module maps, module docstrings) — on BL-11 all of those were clean and every
remaining hit was a dated record.

**And check the classification even when the disposition is right.** The implementer left
`plans/player-bubble/performance.md:64` alone on the grounds that it was "forward-looking prose for
an unbuilt feature" — it is in fact a performance review of an already-merged feature (its header
names tip `5c5bde6`; `filter_player_bubble` is in `src/perception/association.py`), with the
mention sitting inside a measured-savings block. Dated record, so leave it — right answer, wrong
reason, and had the reason been right the "out of scope" disposition would have been wrong by the
implementer's own rule. A stated rule and its stated application pointing opposite ways is the
signal to check rather than accept.

Also from this branch: **an inline precondition `assert` is the right mechanism for a test whose
teeth depend on a fixture value** (`assert path.read_text() == "", "row flushed before close();
test has no teeth"`). The toothless version survived two rounds and was caught only by mutation; a
comment would have allowed `flush_every_n_polls=1` to silently restore it.

Related: [[feedback_docstring_so_clause_delete_the_mechanism]],
[[project_pb2_review_log_append_only]], [[feedback_boundary_only_tested_via_fixture]],
[[project_player_bubble_approved]].
