# Brain Layer — Roadmap

The model-backed decision process behind a free-text utterance: the low-latency crew cognition
layer that turns what the pilot said, plus what body-layer believes, into a decision and a line of
speech. Full design — D1 through D11, the prompt pair, the async wire, the D10 trust boundary:
`plans/brain-layer/plan.md`. Body-layer owns the belief state this layer reasons over and is
reached only through its published tool contract (`body-layer/src/belief/tool_api.py`'s
`TOOL_SET`), so read `body-layer/ROADMAP/body-layer-roadmap.md` alongside this file.

This is the pointer's index — see `docs/DOC_CONVENTIONS.md` for the directory layout, ID scheme
and link form it follows. The index carries links and titles only; **status lives on each entry.**
Update this index whenever a brain-layer branch merges — see `../../.claude/skills/merge/SKILL.md`.

**This directory was created 2026-10-17 at user direction** (*"Put brain milestone and backlog
items under brain layer in folder. Same logic as other layers."*). Until then brain-layer had no
roadmap of its own and all six entries lived in `body-layer/ROADMAP/`, which root `CLAUDE.md` and
root `ROADMAP.md`'s status table both documented as a deliberate arrangement. It is reversed
because the mint rule it forced was the fragile one: one directory holding `BL-`, `BL-B`, `BL-W`
**and** `BR-`/`BR-B` meant a prefix-agnostic `ls | grep -oE '^[A-Z]+-B[0-9]+'` would read a `BL-B`
maximum when minting a `BR-B`, and vice versa. Root `CLAUDE.md` called that collision
not-yet-fired *"only because no `BR-B` item exists"* — a claim already false when written, since
`BR-B1`–`BR-B3` were filed. Separate directories remove the hazard rather than documenting it.

## Live acceptance

A merged, correct change with no in-cockpit observable and no dedicated sortie yet carries
`#needs-flight` on its entry rather than a hand-kept prose list. Find the current set with:

```sh
grep -rl '#needs-flight' --include='*.md' */ROADMAP/ todo/backlog/ todo/todo/ \
  | grep -vE -- '-(roadmap|backlog|tasks)\.md$'
```

**Everything in this layer is unflown against a real model.** The sandbox every agent here runs in
has no route to `127.0.0.1:11434`, so all verification to date ran against a fake HTTP server or
the stub — see each entry.

## Milestones (BR-x)

- [[BR-1.1]] — Brain layer, Stage 1 — first working slice
- [[BR-1.2]] — Brain layer, Stage 2 — `OllamaDecider`
- [[BR-2]] — The brain cannot call a single tool: `TOOL_SET` has no dispatcher

## Backlog (BR-B\<n\>)

A new item takes the next unused number in **this** directory's `BR-B` sequence, which is now
independent of body-layer's. Numbers are never reused and never renumbered, including for done or
rejected items:

```sh
ls brain-layer/ROADMAP/ | grep -oE '^BR-B[0-9]+' | sort -V | tail -1
```

Spell the prefix out and keep `sort -V` — `docs/DOC_CONVENTIONS.md` carries why both halves of
that command are load-bearing.

- [[BR-B1]] — The wider `CLASSIFY_COMMAND_VOCABULARY` the duplicate Stage 2 branch built
- [[BR-B2]] — `brain-layer`'s HTTP server trusts the `Content-Length` header itself
- [[BR-B3]] — The Ollama response body is read without a byte cap

## Keeping this current

Status belongs on the entry file, never here and never in `brain-layer/ROADMAP.md` (a four-line
pointer — writing there puts content where nothing reads it). Root `ROADMAP.md`'s status table
summarises this layer for the cross-subproject view and links here; when a milestone completes,
update the entry and that row, and answer root `CLAUDE.md`'s "Milestone Completion" question —
does this change what the next milestone should be?
