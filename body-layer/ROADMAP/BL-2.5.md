# BL-2.5 — In-cockpit text mirror

- [x] **BL-2.5 — In-cockpit text mirror (interim, no PB- equivalent; done, merged 2026-09-09).** #status/done
  `feature/dcs-text-panel-output`. Mirrors belief lifecycle events into a DCS Hook-state overlay
  window (`Saved Games/DCS/Scripts/Hooks/`, `AutoScrollText` widget, SRS-pattern loopback UDP),
  fed via new `POST /text/push` on aircraft-layer, so live sortie testing is readable in-cockpit.
  Live-verified on a real sortie. Refinement pass: a restyle matching DCS's own `gameMessages.dlg`
  values was live-tested and **rejected by the user** — "reads worse in cockpit than the titled
  window despite being factually grounded" — reverted, keeping only the contact-id fix. Lesson:
  grounding a design in authoritative source values does not guarantee visual acceptance; keep
  cosmetic and correctness changes in separate commits so a rejected restyle doesn't collateral
  damage an unrelated fix. Full history: `plans/dcs-text-panel-output/`.

