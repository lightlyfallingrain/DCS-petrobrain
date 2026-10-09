# Mission Interpreter — Roadmap

Decisions locked in for this phase (`plans/mission-interpreter/plan.md`):

- **`.miz`/Lua parsing**: vendored pydcs `dcs.lua` parse/serialize subpackage (Decision 1), not the
  full `pydcs` package.
- **`trigrules`**: parsed as a raw `predicate`-string tree directly, not through pydcs's wrapper
  classes (Decision 1a).
- **World-model transport**: HTTP, not in-process import (Decision 2) -- `mission-interpreter` <->
  `world-model` is a network call, mirroring `aircraft-layer` <-> `body-layer`'s existing seam, not
  `body-layer` <-> `world-model`'s deliberate single in-process exception.
- **Player-intent input**: text console for MVP (MI-5), a web form later (MI-5b) (Decision 4).
- **`mission["trig"]` vs. `trigrules` runtime authority**: open, not blocking (Decision 5) --
  `trig` is treated as an explicitly documented out-of-scope gap through MI-1.5.
- **MI-4's capable-model choice/hosting**: still open (Decision 3) -- gates only MI-4; MI-0 through
  MI-3 do not need it.

Milestones below are from `plans/mission-interpreter/plan.md`'s Implementation Plan.

This is the pointer's index — see `docs/DOC_CONVENTIONS.md` for the directory layout, ID scheme
and link form it follows. The index carries links and titles only; status lives on each entry.
Cross-subproject links resolve too, now that every subproject is split: the whole repo is one
Obsidian vault, so a wikilink here reaches `body-layer/ROADMAP/` and `todo/` entries as readily as
this directory's own.

**No ID was minted converting this file.** `MI-0`…`MI-6`, plus `MI-1.5`'s dotted sub-ID and
`MI-5b`'s letter suffix, were all already in use and all keep their own spelling — `MI-5b` stays
`MI-5b` rather than becoming `MI-5.1`, per `docs/DOC_CONVENTIONS.md`: the existing spelling is
what every historical prose mention greps for. There is no `MI-B<n>` backlog section in this
subproject, so the prefix stays reserved.

## Milestones

- [[MI-0]] — Get a real `.miz` and lock the schema shape
- [[MI-1]] — Structured `.miz` parser
- [[MI-1.5]] — Author-only-knowledge filter
- [[MI-2]] — World enrichment
- [[MI-3]] — First Mission Understanding schema
- [[MI-4]] — Capable-model synthesis
- [[MI-5]] — Player questions — text console MVP
- [[MI-5b]] — Player questions — web form
- [[MI-6]] — Runtime compilation

`MI-6` was the last planned Mission Interpreter stage per the parent plan's own stage list. The
two sections below are orientation narrative rather than entries, and are kept here verbatim: the
acceptance record is the only account in the repo of what happened when this subproject first met
real missions, and the finding under it is the only record that its output currently goes nowhere.
Neither is a property of any one milestone, so neither can live in an entry file
(`docs/DOC_CONVENTIONS.md`, "Narrative orientation prose stays in the index").

## First real acceptance — 2026-09-24

**MI ran end to end against three missions the pilot actually intends to fly**
(`MI24-outpost-M03/M04/M06.miz`, Syria), the first time it has faced anything other than the
committed synthetic fixture or the third-party Bagram sample. Card:
`docs/acceptance/2026-09-24-mission-interpreter-sortie.md`.

**Desk half: pass.** A1 (completes end to end), A3 (mission understanding — *"well enough for first
iteration implementation"*) and A4 (author-only-knowledge boundary — no hidden-group leak against
real content, not a fixture) all passed.

**Wall-clock, three runs:** 1:12 with `qwen3:14b` already resident, 3:19 cold (model load
dominates), 2:28 warm-ish. Worth knowing before anyone treats MI as interactive: the pre-mission
pass is minutes, not seconds, and the first run of a session pays roughly two extra minutes for the
model load alone.

**A2 — MI-5's question set is narrower than the stage claims.** In practice it asked only threat
confirmations (*"is this threat &lt;description&gt; real?"*), accepting yes/no. Pilot's verdict:
*"kinda pass ... will do for now, needs further work."* The ambiguity detector is doing its job for
threats and effectively nothing else — ownship, purpose and task ambiguities did not produce
questions on any of the three missions. Backlog, not a regression: MI-5 was never claimed to be
exhaustive, but the gap between "player questions" and "threat confirmations" is wide enough to
name. **Deferred to the brain** (user, 2026-09-24: *"yes, refine later, again we need brain"*) —
a richer ambiguity detector written now would be a second, hand-rolled judgement layer that the
brain would then replace.

**A5 — unicode in place names** surfaced in the compact artifact. Probably already fixed upstream
in the world-model builder and simply not rebuilt into the store the server is reading; unconfirmed
until a rebuild. Not blocking.

**B (sortie half) could not be run at all — see the finding below. Deferred to the brain layer by
user direction the same day; not a Mission Interpreter defect.**

**Verdict: MI is tested and passed, with notes** (user, 2026-09-24). The two open notes — MI-5's
narrow question set (A2) and the unreachable phase data (B) — are both explicitly gated on the
brain layer, not on further MI work. Nothing here reopens an MI milestone.

### MI-6's artifact reaches body-layer and then stops

`body-layer`'s `--mission-understanding` loads the compact artifact and `MissionPhaseTracker`
updates every poll, but **no code path a pilot can reach in flight reads it.** `mission_phase`
appears in exactly four body-layer files (`console.py`, `tools.py`, `mission_phase.py`,
`tool_api.py`) — *not* `attention.py`, not `callouts.py`, not `crew_console.py`. BL-7's
phase-proximity tie-break is real but lives inside `_highest_attention_contact`, whose only caller
is `get_situation`, whose only caller is the `--console` debug harness. The brain layer that would
otherwise call the tool API is still `NullBrainClient`.

So BL-7 is complete as designed and **currently unreachable in a sortie**: mission phase changes
nothing about what Petrovich attends to or says. Closing that is a body-layer question (a
crew-facing way to ask for the situation, or phase feeding attention directly), tracked in
`body-layer/ROADMAP.md`, not more Mission Interpreter work.

## Keeping this current

See root `ROADMAP.md`'s "Keeping this current" note -- this file is the source of truth for Mission
Interpreter's own milestone status; the root file only tracks the cross-subproject picture.
