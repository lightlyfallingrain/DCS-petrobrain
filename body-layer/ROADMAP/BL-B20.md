# BL-B20 — Sector coverage

- [ ] **BL-B20 — Sector coverage — Decision 2a of `plans/sortie-2026-09-26-fixes/decisions.md`, staged out
  as a follow-on, 2026-09-26.** #status/open The user's requirement: if a scanned/watched sector holds several
  contacts, all of them should eventually get the attention needed to say what they are — not just
  re-eligibility for whichever one `choose_look` happens to land on. This is a `choose_look`
  selection-fairness redesign (least-known-first or round-robin among worth-a-look candidates), a
  different mechanism from the per-contact eligibility fix `sortie-2026-09-26-fixes` shipped
  (Stages 2/3, time-based retry). **Needs its own `/explore` pass with the user before Architect**
  (per `AGENTS.md`'s "Explore Before Deciding") — the starvation bound (what stops a 30-unit sector
  from crowding out search/react-to-threat/other watched contacts) and the give-up condition (what
  happens to a contact that genuinely cannot be resolved) are both open and need the user's
  cockpit-feel judgment, not a derived answer. Proposed plan location:
  `plans/optic-sector-coverage/plan.md` (not created yet).
