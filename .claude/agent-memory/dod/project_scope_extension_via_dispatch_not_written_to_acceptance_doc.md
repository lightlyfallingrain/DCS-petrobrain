---
name: project_scope_extension_via_dispatch_not_written_to_acceptance_doc
description: taking-fire-visible-shooter's second half ("firing at others") traces to a dispatch instruction quoting the user, not to text in docs/acceptance/2026-10-20-sortie-feedback.md — functionally correct and reviewed, but the written record doesn't carry the direction that authorized it. First occurrence; watch for a second.
metadata:
  type: project
---

`fix/taking-fire-visible-shooter`'s second commit (`9cbd2ace`, "a visible unit firing at others")
cites "F6 follow-up ('visible unit firing at others')" and `debug.md`/`implementation.md` both quote
*"someone shooting is important, especially if they are close -> report"* as the user's own words
authorizing the extension. **That sentence does not appear anywhere in
`docs/acceptance/2026-10-20-sortie-feedback.md`** — the F6 section and its one follow-up only ever
say *"Petrovich should definetely see the unit firing at me"* (targets-ownship only). `debug.md`
itself says the firing-at-others half was investigated "per dispatch instruction," i.e. the
orchestrating session relayed it rather than it being captured first.

**Outcome here was fine**: Reviewer, Security and Performance all independently verified the
extension is a correct, already-provisioned-for reading of `BL-B73`'s own design (the schema's
`targets_ownship: bool` field exists specifically so a visible-firing-at-others case can be
represented), not invented scope. DoD did not block on it.

**Why it's worth a memory anyway**: root `CLAUDE.md`'s "Flight feedback is captured, then explored,
then planned" exists precisely so a user direction that shapes a fix is traceable later — "write it
down first, verbatim where the wording carries the reasoning" — and here the only verbatim copy of
the authorizing sentence lives in two plan files describing *themselves*, not in the acceptance doc
the protocol designates. A future reader auditing "where did this scope come from" against the
sortie-feedback doc alone would not find it.

**How to apply at DoD**: when a plan/debug/implementation file quotes the user to justify scope and
that quote does not also appear in the cited `docs/acceptance/*.md` file, say so in the DoD report —
not as a blocker if the extension is otherwise well-reviewed and in-scope of an existing design, but
as a process gap worth surfacing, so the user can decide whether to backfill the quote into the
acceptance doc for the record. Do not fabricate or backfill the quote yourself.

**Occurrence count: 1.** Filed so a second instance (different feature) can be matched against this
one rather than treated as a fresh discovery.
