# AC-4 — Text-overlay write channel

- [x] **Text-overlay write channel — done, merged as part of BL-2.5, 2026-09-09.** #status/done
  `POST /text/push` → collector → loopback UDP → a DCS Hook-state overlay
  (`Saved Games/DCS/Scripts/Hooks/`), modeled on SRS's overlay pattern. First write path in an
  otherwise read-only layer; reframed `CLAUDE.md` from "read-only" to "read-mostly with narrow
  write channels." See `body-layer/ROADMAP.md` BL-2.5 for the body-layer side.
