---
name: command-map
description: Redraw and republish the Petrovich voice-command map when the spoken vocabulary changes
type: user-invocable
---

Bring `docs/status/petrovich-commands.html` current with `audio-adapter/src/vocabulary.py` and
republish it. Usage: `/command-map`. The merge skill runs it whenever the check below says the map is
stale, so in practice it fires on every merge that touches the vocabulary.

Published artifact: **https://claude.ai/artifact/SwxZFbng1xd7fss7dnGbUo**

**Why it exists** — the user, 2026-10-21: *"There's enough commands now that I can't remember them
all and need a visual representation of the deterministic paths."* Then: *"keep the command map
updated automatically."* A map that lags the vocabulary is worse than none: the pilot says a command
the map shows, and it no longer exists.

## The check — mechanical, run first

```sh
python3 .claude/scripts/command-map-check.py
```

Exit 0 current — stop, nothing to do. Exit 1 stale, with the reason: tokens not on the map, tokens
on the map that no longer exist, or `vocabulary.py` changed since the last stamp (a phrase or slot
word moved; look, and redraw only if the pilot would say something different). Exit 2 means the check
itself broke — say so, do not treat it as current.

## Redrawing

**The page is a view; `vocabulary.py` is the truth.** If they disagree, the page is wrong.

1. Read the diff to `vocabulary.py` since the stamp, and what changed in behaviour — gating, refusals,
   automatic actions (card 7's "after takeoff" is one). `body-layer/src/belief/crew_console.py` is
   where tokens acquire behaviour.
2. Edit the Mermaid cards. One card per pilot job, read left to right as words said in order; slots
   are hexagons on card 2; dashed arrows optional. Keep the design as it is — do not restyle.
3. Mark new commands with the `new` badge / `⟵ new`, and **clear the previous update's markers** —
   the legend says "added since the previous update", so stale badges lie.
4. Update the header date. Main only: the map shows what is on `main`, never a feature branch.
5. Update the manifest's `cards` (token → card number) so every token in `TOKENS` has exactly one
   card, then stamp:

   ```sh
   python3 .claude/scripts/command-map-check.py --stamp
   ```

   It refuses while the token lists disagree, so a stamp means every token was placed.
6. Commit the page, then republish **with `url` set** to the artifact above — artifact identity
   follows the file path, and this page was first published from a scratchpad, so omitting `url`
   makes a second artifact and leaves the user's link stale (the `/status-page` skill has the
   incident). Keep the icon; pass a short `label`.

**Regenerating never blocks a merge.** If the redraw cannot be done now, say the map is stale in the
merge report and move on.
