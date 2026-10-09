# Tag vocabulary

A closed vocabulary for the inline `#tag`s used in split roadmap/backlog entries (see
`docs/DOC_CONVENTIONS.md`). Closed on purpose: the find-the-set recipe

```sh
grep -rl '#needs-flight' --include='*.md' */ROADMAP/ todo/backlog/ todo/todo/ \
  | grep -vE -- '-(roadmap|backlog|tasks)\.md$'
```

is only a trustworthy *negative* — "nothing is tagged this" really means nothing is — if nothing
spells the same concept two ways. Every split directory has to be named, or the negative is worth
nothing: the copy of this recipe in `body-layer/ROADMAP/body-layer-roadmap.md` named two pointer
files and omitted a whole subproject, and reported four real items as absent while exiting 0
(review round 4, RF4-3). The `grep -v` drops index files, which match because they discuss the tag
rather than carrying it. If you change this recipe, change that copy in the same commit. The gate in `.claude/scripts/` (added alongside the first
conversion) checks every inline tag in a converted entry file against this list; an unlisted tag
fails the gate rather than silently expanding the vocabulary.

**Two rules, both load-bearing:**

1. **Tag only what the entry's path and ID do not already say.** The ID tells you which
   subproject and whether it is a milestone or a backlog item (`<prefix>-<n>` vs `<prefix>-B<n>`);
   the directory tells you which repo area. Do not add a tag that restates either.
2. **Status is tagged on the same line as its checkbox marker**, never in frontmatter and never
   elsewhere in the entry — so the two cannot drift apart unnoticed. `docs/DOC_CONVENTIONS.md`
   has the full entry-file shape this implies.

## Status tags

One of these per entry, matching its checkbox marker (root `CLAUDE.md`, "Backlog Management":
`[ ]` open, `[~]` in progress, `[x]` done, `[?]` decision needed, `[>]` deferred):

| Tag | Checkbox | Meaning |
|---|---|---|
| `#status/open` | `[ ]` | Not started. |
| `#status/in-progress` | `[~]` | Underway; some sub-items done, others not. |
| `#status/done` | `[x]` | Complete as specified. |

`#status/decision-needed` (`[?]`) and `#status/deferred` (`[>]`) are reserved for when an entry in
that state is first split — not pre-minted here, so a converter adds exactly the tag a real entry
needs rather than guessing the set in advance.

## Cross-cutting tags

| Tag | Meaning |
|---|---|
| `#needs-flight` | A shipped, merged change with no in-cockpit observable and no dedicated
sortie yet — the mechanical replacement for a hand-kept "live acceptance debt" list
(`plans/obsidian-links-and-tags/plan.md`, "Trustworthy grep negatives over tags"). Means the code
is correct and merged; it does not mean anything is wrong. |

## Topic tags

**Seven approved, 2026-10-08.** This section used to require a `#topic/*` tag to cross **at
least two subprojects** — the wrong axis. The user's own worked example (`AA-3` is about
`#SPU-8`, `#aircraft-manipulation`, and `#audio`) crosses two *document kinds* inside one
subproject (a roadmap entry and the research notes/acceptance cards that informed it), and no
path lookup relates those directories. `#topic/*` had zero members when this was rewritten, so
nothing needed renaming — the rule was replaced before its first real use. Full rationale and the
measurements behind the numbers below: `plans/obsidian-links-and-tags/plan-document-graph.md`,
§2–§3, §8.

**Deliberately excluded: every hardware/unit designator** (`#SPU-8`, `#NET-1`, `#NET-2`, and the
Soviet/DCS unit designators listed in `docs/TAGS.proposals.md` — `#BTR-70`, `#ZSU-23`, `#SA-3`,
`#BMP-2`, `#ZU-23`, `#ASP-17`, `#9K113`, and the rest). User direction, 2026-10-08: *"I don't think
Designators-only is even needed. The concepts are more important than parts, I can go and find the
parts from the concepts."* and *"even SPU-8 is about audio playback and volume. SPU-8 is just the
tool that controls them."* The part is reachable through the concept it serves; the reverse is not
useful. Say so here rather than leaving the omission to be rediscovered and re-proposed later.

**Four rules, all load-bearing:**

1. **Crosses at least two document kinds** — roadmap entry / research note / acceptance card /
   plan. A tag confined to one kind in one directory is something `ls`/`grep` over that directory
   already answers, so it would just be a second spelling for a plain path lookup. This is the old
   rule's sound half, re-aimed at the axis that actually matters.
2. **Lands in the navigable band: 3–25 document units**, measured repo-wide at admission by
   `.claude/scripts/doc-tags-propose.sh` and recorded in the tag's own section with the date.
   Below 3 it connects almost nothing and is not a hub worth having. Above 25 it is a hub that
   means nothing — `#audio` alone would connect 80 documents repo-wide, which is exactly the
   undifferentiated fan the closed vocabulary exists to prevent — and it must be split into
   narrower tags instead (`#audio` → `#audio-playback`, `#audio-volume`, `#audio-transport`).
   Two cheaper fixes were measured and both failed before this rule was settled: requiring more
   mentions per document kills a good tag faster than it tames a bad one, and anchoring the match
   to titles/headings only drops the sketch's own centre (`AA-3`'s H1 never says "SPU-8"). The
   band is the only lever that works, which is why it is the admission rule rather than a
   judgement call.

   **Stated exception: shorthand reach.** A candidate over 25 is still `TOO BROAD` *unless* the
   excess comes from an approved shorthand of a single coherent concept (rule 4 below), in which
   case it is admitted and the reason is recorded on its own `**Measured:**` line.
   `#push-to-talk` measures 29 units *because* its pattern also matches `PTT`, not because it is
   vague — it is one coherent topic with a widely-used abbreviation. The band was using raw count
   as a proxy for specificity, and the shorthand rule breaks that proxy: the fix is to write the
   exception down, not to narrow a pattern just to fit a number it was never measuring correctly
   in the first place.
3. **Flat spelling for topics** (`#SPU-8`, `#aircraft-manipulation`), never prefixed. The
   machine-read tags above (`#status/*`, `#needs-flight`) keep their prefix — they are a different
   kind of thing, read by a gate rather than clicked for navigation.
4. **A tag's pattern must include the concept's common shorthand**, when the concept has one.
   User direction, 2026-10-08: *"PTT is shorthand for push-to-talk, so push-to-talk must match
   PTT. Similar for other shorthands like FOV = field-of-view."* `#speech-synthesis` matches
   `TTS`, `#speech-recognition` matches `STT`/`ASR`/`whisper`, `#push-to-talk` matches `PTT`,
   `#intercom` matches `ICS`. A future `#field-of-view` tag would need to match `FOV` for the same
   reason — named here as the illustrative example, not yet proposed.

**Why the closed vocabulary still matters — kept verbatim in substance from before this
rewrite.** `grep -rl '#SPU-8'` is only a trustworthy *negative* — "nothing is tagged this" really
means nothing is — if nothing spells the same concept two ways. That benefit does not depend on
which axis admits a tag; it depends on every tag that exists being listed here and nowhere else.

**Format: one short section per tag, not a table row.** A match pattern needs alternation, and
`|` inside a markdown table cell has to be escaped — precisely the two-spellings footgun this file
exists to prevent, in the file that documents it. A section looks like this once a tag is
approved (illustrative shape below, not an approved tag — see rule 4):

```markdown
### `#field-of-view`

- **Matches:** `field[- ]of[- ]view|FOV`
- **Measured:** 18 units, 2026-10-07 (9 research · 4 acceptance · 3 plan · 2 roadmap)
- The pilot's/gunner's visible cockpit volume and its limits.
```

### `#audio-playback`

- **Matches:** `playback|audio (transport|channel)|/audio/play|wav (file|payload)`
- **Measured:** 21 units, 7 roadmap entries, 2026-10-08.
- Moving a rendered audio payload from wherever it is produced (TTS output, a recorded wav) onto
  the aircraft's own audio path — the transport/channel mechanism, not any one box that uses it.

### `#audio-volume`

- **Matches:** `audio volume|playback volume|volume knob|volume scal`
- **Measured:** 5 units, 1 roadmap entry, 2026-10-08.
- Scaling or setting playback loudness — the volume knob/control concept, independent of which
  cockpit box exposes it.

### `#speech-synthesis`

- **Matches:** `\b(TTS|text-to-speech|speech synthesis)\b`
- **Measured:** 13 units, 2 roadmap entries, 2026-10-08.
- Turning Petrovich's text into spoken audio (TTS) before it reaches the audio-playback path.

### `#speech-recognition`

- **Matches:** `\b(STT|ASR|speech-to-text|whisper)\b`
- **Measured:** 21 units, 7 roadmap entries, 2026-10-08.
- Turning the player's captured speech into text (STT/ASR, including the Whisper model family)
  before it reaches command handling.

### `#push-to-talk`

- **Matches:** `\b(push[- ]to[- ]talk|PTT)\b`
- **Measured:** 29 units, 6 roadmap entries, 2026-10-08 — admitted over the 3–25 band under rule
  2's shorthand exception: the excess comes entirely from `PTT`, this tag's own approved shorthand
  (rule 4), for one coherent concept, not from vagueness.
- Gating player speech capture to only the window the player is holding a transmit key, and the
  key/gesture that opens that window.

### `#cockpit-manipulation`

- **Matches:** `cockpit argument|clickable|performClickableAction|set_command`
- **Measured:** 18 units, 1 roadmap entry, 2026-10-08.
- Driving a DCS cockpit argument/clickable as code would — `performClickableAction`/`set_command`
  and the argument IDs they move — independent of which cockpit box is on the other end.

### `#intercom`

- **Matches:** `(intercom|\bICS\b)`
- **Measured:** 18 units, 4 roadmap entries, 2026-10-08.
- The crew intercom system (ICS) as a concept: who can hear whom, and over what.

## Adding a tag

1. Check it is not already covered by an ID or a path (the first rule at the top of this file).
2. Run `.claude/scripts/doc-tags-propose.sh` and check the candidate's measured repo-wide reach
   lands in the 3–25 band. A tag outside the band is reported `TOO BROAD` (split it first) or
   `TOO NARROW` (it is not a hub).
3. The user approves the candidate — the vocabulary is closed, so nothing here is minted without
   that approval (`plans/obsidian-links-and-tags/plan-document-graph.md`, §2).
4. Add the section here, in the same commit as the first document whose generated block emits
   that tag — never retroactively, so the gate never has to pass against a vocabulary that does
   not yet exist on disk. The generator (`.claude/scripts/doc-provenance-refresh.sh`) refuses to
   emit a tag with no approved section, so a document can never carry a tag this file does not
   list.

**Drift**: `doc-tags-propose.sh` also re-measures every already-approved tag's band each time it
runs and reports one that has grown out of band (e.g. admitted at 20 units, now 40) — the same
tool that proposes a tag is the one that grooms it, which is the standing tiebreak for anything
automatable in this convention (*"more automation is better"*, the user's own words).
