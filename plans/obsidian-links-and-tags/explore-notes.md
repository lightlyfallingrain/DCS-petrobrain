# Explore: tying research, plans and acceptance docs into the roadmap graph

**2026-10-06/07, with the user, after their first Obsidian glance at the converted
`audio-adapter/ROADMAP/`.** Captured before any Architect pass, per root `CLAUDE.md` "Direction
before speed". The user's own words are kept verbatim where the wording carries the reasoning.

**Their sketch is the specification: `sketch-document-graph.jpg` in this directory.** It is a
hand-drawn graph and it decides more than any paragraph here — read it first.

## What prompted it

The split worked, and the user said so:

> *"I see the roadmap split to files and the links between the master roadmap and the individual
> files work. That's good."*

Then the actual finding:

> *"However, research/\* and review/\* have no links, no tags, nothing to tie them with the roadmap
> items."*

> *"Using AA-3 as example: AA-3 is about #SPU-8 and #audio and #aircraft-manipulation. There's bound
> to be documents that describe findings or research of how to #aircraft-manipulation and what are
> the #SPU-8 button ids and how to handle the #audio volume. I think Graphify answers a lot of these
> for you, but that is a difficult interface for me. I'd need a visual representation and a way to
> jump between documents."*

> *"It does not have to be Obsidian, that's simply the best option that I know of."*

**The asymmetry is the point.** The knowledge graph already holds most of these relationships and
is queryable — by an agent. The user cannot use it. What they can use is a graph they can see and
click, and Obsidian renders exactly that **from links and tags that exist in the files**. Nothing
new has to be built to display it; the edges simply are not written down yet.

## What the sketch shows

`AA-3` at the centre, with:

- **Tags as hubs** — `#audio`, `#SPU-8`, `#aircraft-manipulation` drawn as their own nodes with
  edges to the entry. Obsidian renders tags as graph nodes (Graph view → Filters → Tags), so this
  is literal, not metaphorical.
- **Documents hanging off the tags** — "SPU-8 investigation notes" off `#SPU-8`, "research doc about
  how to command cockpit switches in DCS" off `#aircraft-manipulation`.
- **Topic refinement off a tag** — "volume" and "playback" off `#audio`, with "playback" marked
  *DONE*.
- **A directional dependency edge** — an arrow from `AA-3` down to *"something that depends on
  AA-3"*. This is a **typed** edge, unlike the others, and nothing in the convention expresses it
  yet.

## The four questions, and the user's answers

| question | answer |
|---|---|
| Who writes the links — the user, the agent, or graphify? | **"graphify can write links"** |
| Closed vocabulary or open? | **"closed vocabulary, but so that more can be added when need arises"** |
| Which document kinds get tagged? | **"only ones worth navigating. No agent memories, audits, agent notes. Roadmaps, plans, reseach, acceptance test docs - yes."** |
| What is the entry point you navigate from? | **"likely starting point is roadmap item or tags. A tag is actually a very likely starting point and a usefull way to navigate the graph at high level in any case."** |

### Topic notes: offered and rejected

A file per topic was proposed — a real note carrying a paragraph of definition, the SPU-8 arg
numbers, and curated links, so that clicking a tag lands somewhere that says what the topic *is*
rather than on an undifferentiated fan of edges. Recommended at the time; **the user rejected it**:

> *"bare tags. a topic note is one more thing to maintain and update, I'd rather not have them. More
> automation is better."*

**So: bare tags only.** No `docs/topics/*.md`. The standing preference behind it — *more automation
is better* — is the tiebreak for anything else this design turns up: when a choice is between
something a human keeps current and something a generator keeps current, take the generator.

### Decided without a round trip

- **Flat topic tags** — `#SPU-8`, `#audio`, `#aircraft-manipulation`, as drawn, not the current
  `#topic/ptt` prefixed form. Flat is what the user drew and would type. `#status/*` and
  `#needs-flight` stay prefixed: they are machine-read by gates, a different kind of thing.
- **Generated blocks carry delimiters** (`<!-- links:start -->` … `<!-- links:end -->`), so
  regeneration never touches hand-written prose, and the existing link gate extends to check every
  generated link resolves. Generated links that rot silently are worse than no links, because they
  still look authoritative.

## What this collides with in the current design

1. **`docs/TAGS.md` forbids exactly these tags.** Its rule: a `#topic/*` must cross **at least two
   subprojects** to earn a place, because a tag inside one directory is something `ls`/`grep`
   already answers. The user's case breaks it — `#SPU-8` ties `audio-adapter/ROADMAP/`,
   `aircraft-layer/research/` and `plans/spu8-intercom/`, often within one subproject, always
   across document trees that **no path lookup relates**. The rule picked the wrong axis:
   it should be *crosses two document kinds*, not *two subprojects*. `#topic/*` currently has zero
   members, so nothing has to be renamed — the rule is rewritten before it is first used.
2. **The `**Roadmap:**` header line was never written anywhere.** `plan.md` calls for it on every
   research note and plan ("one line, no other change"); the Stage 1 dispatch scoped the implementer
   to the roadmap only. Zero exist repo-wide. This is the cheap half of the work and it is an
   omission in the dispatch, not in the plan.
3. **Typed edges have no convention.** The sketch's dependency arrow needs something like
   `**Depends on:**` / `**Blocks:**`. Obsidian draws the line but carries neither direction nor
   meaning; backlinks supply the reverse direction for free, so only one end should state it.
4. **The corpus ceiling already blocks the next subproject.** 198 files against
   `graph-corpus-guard.sh`'s 200. This feature adds no files (bare tags, no topic notes) but is
   downstream of the same decision — see `performance.md`.

## Open, for the Architect

- **How graphify proposes a tag and who accepts it.** The vocabulary is closed but extensible, and
  graphify discovers topics; the loop has to end with a human-approved row in `docs/TAGS.md` before
  the generator may emit that tag, or "closed" means nothing.
- **How a generated link is kept honest when a document is renamed or deleted**, given
  bare-ID/basename links and 441 historical path mentions that must keep resolving.
- **Whether the generator runs per-commit, per-merge, or on demand** — automation is the user's
  stated preference, but `/graph-refresh` is already a manual, order-sensitive step
  (documents first, graph second).
