---
name: doc-tags-stage-a
description: Stage A (topic-tag vocabulary/proposer/generator-extension) of obsidian-links-and-tags -- a self-referential-corpus trap and a two-layer quoting trap, both found by running against the real tree rather than inspecting code.
metadata:
  type: project
---

Stage A of `plans/obsidian-links-and-tags/plan-document-graph.md`: rewrote `docs/TAGS.md`'s
topic-tag admission rule, built `doc-tags-propose.sh`/`doc_tags.py` (harvest candidates, measure
repo-wide vs. in-scope reach, write `docs/TAGS.proposals.md`), and extended `doc_provenance.py` +
`roadmap-tag-vocabulary-gate.sh` to carry/gate a `**Topics:**` line in the same block. Zero tags
approved this round, by design -- the real committed tree stays byte-identical and the mechanism
was proven against a scratch copy outside the repo instead.

Three real bugs, all found by running the tool, not by reading the code:

1. **A naive single-word document-frequency harvester is both too slow and too noisy.** Every
   lowercase word with doc-frequency >=3 across ~240 units is thousands of candidates, and a
   second full-corpus regex scan per candidate (one version did this) costs minutes of 100% CPU
   with no completion. Worse, a project's own docs are dense with generic nouns ("panel",
   "delay", "press") that clear any frequency bar without naming a topic. Fix: harvest ID-shaped
   tokens, capitalised phrases, and graphify labels in ONE pass that doubles as the measurement
   (no per-candidate rescan); drop word-frequency as a source entirely -- it isn't one of the
   plan's three named sources anyway.

2. **`re.escape` then substitute corrupts the escape.** `re.escape("SPU-8")` produces `SPU\-8`
   (the hyphen escaped); substituting a literal `-` for a tolerant separator afterwards matches
   only the un-escaped half, leaving a dangling backslash (`\bSPU\[- ]?8\b`) that compiles and
   runs without error -- it just matches wrong text. Found by reading the generated proposals
   file's `Matches:` value next to `docs/TAGS.md`'s own documented example, not by inspecting the
   regex. Fix: split on the separator first, escape each part, rejoin with the tolerant
   separator.

3. **Two independent "is this a real block or just a quote" bugs, both from fence/code-span
   confusion, found one round apart.** (a) `docs/TAGS.md`'s own `### \`#SPU-8\`` format example
   lives inside a fenced block; `load_approved_topic_tags`/`load_approved_tags` both read it as a
   real approved tag before a fence-strip was added (caught by `doc_provenance.py plan` reporting
   `1 approved topic tag(s)` against prose that says "None approved yet"). (b) The
   vocabulary-gate's own group-(b) file discovery excluded a document that *quotes* the
   provenance delimiter inside a ``` fence, but not one that quotes it inside a single-backtick
   inline code span -- which this very implementation log did, describing its own fix, in the
   same round. A block-fence-only strip left that survive, pulling the file into tag-scanning and
   surfacing an unrelated decade-old-in-project-time false positive (`#fenced-code-tag`, a test
   string from an earlier review's fence-mutation transcript). Fix: strip inline code spans too,
   not just block fences -- the same two-step strip the tag-scanner itself already used.

**Self-referential corpus trap, general lesson:** when a plan directory is matched as one unit
(all its `.md` files concatenated) and the implementation log lives in that same directory, the
candidate measurement reported inside the log changes the corpus the next measurement sees.
Writing "`#NET-1`: 5 units" into `implementation.md` makes the next real run report 6, because
`implementation.md` is itself scanned. Resolution used here: take the measurement that will
actually match the *final* committed tree (after the log is fully written), not an intermediate
one, and say so explicitly rather than quietly report a number the committed tree can no longer
reproduce. Re-run and diff after any edit to a self-referencing log, not just once at the end.

Related: [[project_doc_provenance_stage_a0]] (the sibling generator this stage extends),
[[project_obsidian_gate_class_fixes]] (the fence/code-span stripping this file's bug (3b) is a
second instance of).
