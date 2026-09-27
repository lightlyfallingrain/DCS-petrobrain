---
name: graph-refresh
description: Rebuild the knowledge graph after a merge, once the documents are current
type: user-invocable
---

Rebuild `graphify-out/` from the current documentation. Usage: `/graph-refresh`.

Run this **after a merge**, once the documents describe what was actually built. It is the step
that makes the merge-time doc pass worth doing — without it the graph keeps answering from the
previous state while the repository has moved on.

## The one ordering rule

**Documents current, then rebuild.** That dependency is real: a graph built from stale documents
does not merely lag, it *launders* the staleness — the next query returns the outdated claim with a
citation and a confidence score attached, which is considerably more convincing than the stale
paragraph was on its own.

Where the merge itself sits does not matter. The graph is gitignored and local, so merging changes
nothing the rebuild would index. An earlier version of this rule said "documents, graph, merge" as a
rigid sequence and the first person to apply it nearly held up a merge for a twenty-minute rebuild
to honour a step whose position was arbitrary. What must not happen is the rebuild being **skipped**.

## Before rebuilding: is the documentation actually current?

Do not assume the Definition of Done pass caught everything. Check, cheaply:

```sh
git diff --name-only HEAD~1 HEAD | grep -E '\.py$'    # what changed
cat graphify-out/.needs_update 2>/dev/null            # what the hooks flagged
```

For each changed source file, ask whether any document describes behaviour that just changed. The
mechanical half of that is greppable — search the corpus for the file's name and its changed
symbols — but the judgement is not. Three things to look for specifically:

- **A roadmap item still open that this work closed**, or closed that it reopened.
- **A decision now overturned.** Do not rewrite it: add the replacement as its own section and give
  the original a pointer forward (`docs/PROCESS.md`, "Superseding a decision"). A section that reads
  as current when it has been superseded is worse than one that is merely missing.
- **A plan nothing cites any more** — move it to `plans/archive/`, which the corpus excludes.

## Rebuild

```sh
.claude/scripts/graph-corpus-files.sh > graphify-out/.corpus.txt
.claude/scripts/graph-corpus-guard.sh graphify-out/.corpus.txt   # refuses a too-wide corpus
```

**The guard is not a formality — run it and let it stop you.** On 2026-09-26 a rebuild indexed
**1182 files / ~1.56M words** and announced it in its own `GRAPH_REPORT.md` ("Consider running on a
subfolder"), while the curated corpus is ~119 files / ~333k words. Nobody noticed for a day. That run
cost roughly **14x an incremental refresh**, and every one of those tokens was an extraction
subagent's.

The reason it went unnoticed is worth keeping: a too-wide corpus produces a *bigger* graph, which
reads as richer rather than wrong. There is no symptom to spot. So the count is the only defence, and
`graph-corpus-guard.sh` exits non-zero rather than printing a number somebody skims past.

The corpus is a **selection expressed as a file list, not a directory**. It was once a copied mirror
under `graphify-corpus/` and that broke two things at once: cache lookups keyed on mirror paths
never matched entries saved under repo-relative `source_file` values, so a re-run reported 65 of 85
files changed when ten had been touched; and files at the mirror root were keyed `graphify_corpus_*`,
leaking a staging directory into the graph's vocabulary. Do not reintroduce a mirror.

Check what actually needs work before spending anything:

```sh
PY=$(cat graphify-out/.graphify_python)
$PY -c "
from pathlib import Path
from graphify.cache import check_semantic_cache
files=[l.strip() for l in Path('graphify-out/.corpus.txt').read_text().splitlines() if l.strip()]
n,e,h,unc = check_semantic_cache(files)
print(f'{len(files)-len(unc)} cached, {len(unc)} need extraction')
Path('graphify-out/.uncached.txt').write_text('\n'.join(unc))
"
```

If nothing needs extraction, skip to **Finish**. Otherwise run `/graphify` — it reads the cache,
extracts only the uncached files, and rebuilds. Dispatch extraction subagents with
`subagent_type="general-purpose"`; `Explore` is read-only and silently drops results.

**Delete stale chunk files before dispatching, and count them after:**

```sh
rm -f graphify-out/.graphify_chunk_*.json      # BEFORE dispatching
ls graphify-out/.graphify_chunk_*.json | wc -l # AFTER — must equal the number dispatched
```

This is not housekeeping. Extraction writes `.graphify_chunk_NN.json`, and the merge step globs
**every** chunk file present — including any left by a previous run. On 2026-09-21 a rebuild
dispatched three chunks and the merge found four: the fourth was from the day before and held
world-model research notes in their *pre-triage* form. Merging it would have reintroduced the exact
claims that run existed to correct, with fresh citations attached — the laundering failure this
whole procedure is built to prevent, arriving through the cleanup step rather than the documents.

It was caught only because the merge printed a count that did not match. **So print the count and
check it**, rather than trusting the glob.

**One corpus-specific instruction belongs in every extraction prompt.** This project preserves
superseded decisions in place, with the replacement above and a `SUPERSEDED — see ...` pointer in
the original. Where a section carries that marker, the edge to its successor matters more than the
section's own content — surfacing a superseded decision without its replacement is the specific
failure the graph exists to prevent.

## Finish

```sh
rm -f graphify-out/.needs_update graphify-out/.corpus.txt graphify-out/.uncached.txt \
      graphify-out/.graphify_chunk_*.json graphify-out/.graphify_semantic_new.json
.claude/scripts/gq.sh "<something this merge changed>"
```

The chunk files are in that list deliberately — see the warning above. Leaving them is how the
*next* run silently merges *this* run's work into a corpus it no longer matches.

That last line is the check that matters: query for something the merge changed and confirm the
graph answers from the new state. A rebuild that produced a graph still describing the old one is
the failure this whole procedure exists to prevent, and it is invisible unless you look.

## `graphify-out/` is gitignored — there is no undo

Everything under `graphify-out/` — `graph.json`, the extraction cache, the chunk files — is
gitignored and therefore unrecoverable. A careless write truncated `graph.json` during the
2026-09-21 rebuild; it was recovered only because the *cache* happened to survive in the same
untracked directory, which is luck rather than a property.

So: **write `graph.json` through `paths.write_json_atomic`, never with an inline expression**, and
if you are about to overwrite it, remember the cache is the only thing standing between a slip and
a full re-extraction of every uncached file.

## What this does not fix

The graph says **where** to look, not what the text says — edge annotations quote fragments and a
fragment can lose its tense. `gq.sh` is the documented query path precisely because it ends every
answer with the sources to read; a `PreToolUse` hook blocks raw `graphify query` for that reason.

And the graph only carries supersession edges where a marker exists. Most of `plans/` has never been
checked for contradictions against what was actually built — not because those plans are clean, but
because nobody has looked. A rebuild does not touch that; it is separate work, and the count of
unchecked plans is whatever `plans/` currently holds rather than a number worth writing down here.
