---
name: body-layer-bounded-growth-accepted-pattern
description: body-layer never removes Contact objects or per-contact optic-policy map entries — a documented, accepted design bound, not an exhaustion vulnerability to flag repeatedly
metadata:
  type: project
---

`body-layer`'s `ContactStore` never removes `Contact` objects (grep confirms no `del`/`.pop()` on
the contact dict anywhere in `contacts.py`), and `OpticState`'s per-contact maps
(`attempted_at_range_m`, and as of `sortie-2026-09-26-fixes`, its twin `attempted_at_time_sim`)
grow 1:1 with distinct contacts seen in one sortie, never shrink. The codebase's own comment on
`attempted_at_range_m` names this explicitly: "Contacts are never removed: the map is bounded by
how many distinct contacts one sortie produces."

**Why:** single-player, one-sortie-at-a-time project (root `CLAUDE.md` scope). A sortie's contact
count is naturally small and bounded by mission duration/detection range, not attacker-controlled —
there is no untrusted-input path that can inflate this count. This was re-verified during the
`sortie-2026-09-26-fixes` deep security analysis (2026-09-26), which added `attempted_at_time_sim`,
`pending_attempted_at_range_m` (transient, cleared every look-end — not even sortie-bounded),
`look_contact_id`/`last_command_target_contact_id` (scalars, no growth risk), and
`Contact.last_observable_sim` (per-Contact field, same lifecycle as the Contact itself).

**How to apply:** when a future feature adds another per-contact dict to `OpticState`, `Contact`,
or `CrewConsole`, don't re-flag "does this leak/grow unbounded" as a new finding unless it grows
*independently* of contact count (e.g. per-tick, per-utterance, or per-poll accumulation that
never resets) — that would be a genuinely new class of exhaustion this pattern doesn't cover. Per-
contact, sortie-lifetime growth is the accepted baseline here. If very long sorties ever become a
real concern, it's a pre-existing design point affecting `attempted_at_range_m` too, not something
a single new feature introduces — worth a `todo/todo.md` note, not a per-feature blocker.
