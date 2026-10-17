# BL-8 — Memory layer interfaces

- [~] **BL-8 — Memory layer interfaces.** #status/in-progress Deliberately last (user decision, 2026-09-10:
  "the shape of what's worth remembering is only knowable after BL-2..BL-7 have run for real").
  Standing awareness note while BL-2..BL-7 touch in-mission memory shapes (`Contact`/`ContactStore`,
  BL-4's `AttentionArea` registry): keep BL-8's eventual mission-end export/persistence boundary in
  mind, not as a design constraint yet, just don't shape something in a way that obviously fights it.

  **A concrete consumer now waits on this, added 2026-09-29: the "safe from" callout.**
  `plans/dcs-driven-los/plan.md` defers it at user direction, and the reason names exactly what
  BL-8 would have to hold. *"Danger"* is a claim about something Petrovich can see; *"safe from"* is
  a claim about an **absence** — it asserts a unit is no longer able to shoot you, which needs to
  know where that unit is *now*, not where it was last observed. Once LOS comes from DCS for units
  the naked-eye channel is currently observing, a contact outside that coverage has no honest basis
  for a clearance without remembered believed positions. So BL-8 is no longer only "what is worth
  remembering after a sortie" — it now has one named in-mission consumer whose feature is switched
  off until it exists (`belief/speech.py`'s `engaged=False` branch).

  **Code-pointer correction, 2026-10-17** (`plans/bl8-mission-memory/plan.md` Decision 10): the
  sentence above names the wrong module. `belief/speech.py` renders *"Safe from …"* perfectly well;
  what holds it back is `belief/callouts.py`'s `_OBSERVABILITY_EXEMPT_KINDS`, which exempts only the
  `engaged is True` danger call — and its stated reason is about **priority, not memory** (*"nothing
  is evaded by hearing it… silence costs the pilot the chance to stop evading, which is a comfort,
  not a threat cue"*). **So BL-8 does not automatically unblock this callout.** BL-8 supplies what it
  needs (a believed position for a contact outside live coverage, via `recall_memory`); flipping the
  gate is a separate speech decision with its own acceptance sortie, and is an open question on that
  plan rather than a stage of it.

  **Landed, 2026-10-17 (`plans/bl8-mission-memory/plan.md`), Stages 1, 2, 3, 5 of the batch
  Decision 3 (and the 2026-10-17 `/explore` conversation) settled on.** The `mission_memory/`
  package (`entries.py`, `store.py`, `admission.py`, `marks.py`, `query.py`, `tools.py`, `log.py`)
  — the append-only JSONL store, the `group`/`air_defence`/`fired_on` admission rules, the
  commanded-mark path, and the query/tool surface (`TOOL_SET` 15 → 17) — is built, tested, and
  reviewed (`plans/bl8-mission-memory/review.md`).

  **Deferred by the user's own 2026-10-17 decision** (`plan.md`'s "Decisions Requiring User
  Input"), not left incomplete by oversight:
  - **Stage 4 (attack-run entries)** — the schema shipped in Stage 1 (`AttackRunPayload.weapon`
    is `str | None`; `.outcome` has an explicit `"unknown"` value in its `AttackOutcome` literal),
    but the trigger that would actually write one does not exist. Deferred until the two
    prerequisites land elsewhere (aircraft-layer's weapon-selector export and a
    `getLife()`-based outcome signal — see the plan's effort/value flag); without them an entry
    would read "aimed at CONTACT_9, weapon unknown, outcome unknown."
  - **Stage 6 ("safe from" re-enablement)** — its own batch, after Sortie A has shown the memory
    itself is trustworthy; the gate it needs to flip lives in `belief/callouts.py`
    (`_OBSERVABILITY_EXEMPT_KINDS`), a separate speech decision with its own acceptance sortie.

  **Outstanding: Sortie A.** The feature is write-only in flight — nothing in this batch reads
  `mission_memory`'s own JSONL back during a sortie — so acceptance is a post-flight file read:
  fly a mission with ground units, air defence, a mark, and something shooting, then check the
  notepad reads like a kneeboard page (entry count in the tens, not the thousands; a group's
  strike chain is a sensible history; nothing obviously missing or obviously noise). The three
  admission thresholds (`RESIGHT_MOVE_M`, `RESIGHT_MIN_INTERVAL_S`, `FIRED_ON_FOLD_WINDOW_S`) are
  guesses until this sortie runs.

