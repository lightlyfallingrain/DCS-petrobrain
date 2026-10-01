# Explore — what makes several units one group (user, 2026-10-01)

Held after the 2026-10-01 sortie, once `debug.md` had settled that the repetition was a dedup bug
(range drift re-triggering the whole roster) and had flagged two things it refused to decide alone:
whether a legitimate re-report says a delta or the whole roster, and how one distance constant can
serve both a two-infantry pair and an S-300 battery. The user answered both. His words are quoted
where the phrasing carries the reasoning; this file is controlling over any earlier assumption in
`debug.md` or the group-reporting plan.

## 1. Re-reports are deltas

**Settled: delta.** When something earns a second mention, Petrovich says what changed — not the
roster again. The reason was given earlier the same day, watching six identical eleven-unit lines
go past: *"I know it's there from the first report. And repeating the whole group composition every
time adds noise."*

## 2. Merging infantry too eagerly is acceptable

> *"Ok to merge infantry too eagerly. Infantry is the least detectable and also least important of
> unit types."*

This matters because it **releases a constraint the debugger was treating as hard**. A speculative
cohesion fix was reverted during the debug pass precisely because it merged two infantry 260 m apart
at 500 m range, which a pinned test forbade. That test encodes a strictness the pilot does not want.
Infantry is the one class where over-merging costs little: hardest to see, least consequential to
get wrong.

Do not read this as "infantry grouping is unimportant" — read it as *the error is asymmetric*.
Wrongly merging two infantry is cheap; wrongly splitting an air-defence site is not.

## 3. Cohesion is kind-coherence AND size-relative spacing

The architect's guess — that an S-300 site is one thing because its parts belong to one
installation — was confirmed, and then **extended with the part that was missing**:

> *"Your guess at kind-coherence is correct. It's also relative-to-unit-size coherence."*

Three worked cases, in the user's own words:

| case | spacing | verdict | why |
|---|---|---|---|
| trucks, *"roughly 2x6x2 m boxes"* | 1 km apart | **individual units**, even though same type | spacing is enormous relative to the things |
| SAM radar + launchers | *"typically spread out to not be single hit target"* | **one site** | they belong to one installation; the spread is the point of the design |
| naval ships, *"100+ metres"* long | *"hundreds of meters or even kilometers apart when moving in formation"* | **one formation** | *"relative to that the spacing is normal"* |

So a single distance constant cannot work, and no retune of one will: **the threshold is a multiple
of the characteristic size of the units being considered**, not an absolute distance. 1 km between
6 m trucks and 1 km between 150 m ships are not the same situation, and the current code cannot tell
them apart because it only sees metres.

Two independent axes fall out of this, both needed:

- **Size-relative spacing** — the cohesion distance scales with unit size. This is the general rule
  and it covers the trucks and the ships without any domain knowledge.
- **Kind coherence** — units that are functionally parts of one installation group even when their
  spacing would otherwise separate them. The SAM site is the motivating case, and the user notes the
  spread is deliberate: *"spread out to not be single hit target"*. A purely geometric rule, however
  well scaled, will keep splitting these, because being spread is what the design is for.

## What this does not settle

- The actual multiple (how many unit-lengths of spacing still reads as one group) is unknown and
  should be found by looking at real cases, the way the terrain thresholds were — not picked blind.
- Which kinds count as one installation, and where that knowledge lives (a table in body-layer, a
  property of the world model, something derived from DCS group membership — noting that DCS group
  membership is mission-author knowledge and may be exactly the kind of omniscience the project's
  own invariant forbids). This is an architecture question, not a tuning one.
- Whether naval formations matter at all for current scope. Raised by the user as an illustration of
  the size-relative principle; the Mi-24P over Syria is not currently a maritime problem.
