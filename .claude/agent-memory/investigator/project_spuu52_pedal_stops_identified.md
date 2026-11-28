---
name: project-spuu52-pedal-stops-identified
description: the Mi-24P's adjustable pedal stops are device 19 (SPUU_52) in body-layer's effectors-raw dump, not SAU channel B -- what each of its four elements is believed to do
metadata:
  type: project
---

Resolved 2026-11-28 (`aircraft-layer/research/2026-11-28-mi24p-pedal-stops.md`), after an earlier
reading in this project's own docs (`body-layer/ROADMAP/BL-16.md`, `plans/flight-lift-vector/
explore-notes.md`) wrongly called SAU channel B "adjustable stops channel". The user corrected
this live: **channel B is the ALTITUDE channel** (Cyrillic В = высота). The real adjustable-stops
system is **СПУУ-52** ("ПОДВИЖНЫЕ УПОРЫ", control unit БУ-32) — confirmed from the real DCS
Mi-24P QuickStart RU manual (pp.11-12, 37) and from `body-layer/config/effectors-raw/mi-24p.toml`,
device 19, `device_name = "SPUU_52"`:

- `SPUU-ON-OFF-PTR` cmd 3010 arg 270 — power ON/OFF, persistent switch. Already curated as
  `p_spuu_power` and pressed ON by `config/sequences/mi-24p/seat-pilot.md` (commit `ffa419f9`).
  Best candidate for the mechanism behind the measured right-pedal cap difference (≈−0.569 with
  stops on, ≈−0.676 off, both at hover/low speed) — not yet flown against this specific arg.
- `SPUU-OFF-PTR` cmd 3001 arg 275 — a button that "acts like a switch" per the raw-dump curator's
  own note. Possibly the manual's red-lit annunciator-pushbutton rather than an independent
  disable; ambiguous, unflown.
- `SPUU-KNOB-PTR` cmd 3003 arg 276 — continuous 0..1 adjustment knob (the black rotary knob the
  user saw on the real stops panel).
- `SPUU-CONTROL-PTR` cmds 3007(`switchDown`)/3006(`switchUp`) arg 277 — springloaded 3-position
  "P/NONE/T" switch. Working hypothesis (moderate-to-good confidence, corroborated independently
  by the user's own account of the real aircraft's density-dependent pedal authority): P/T select
  pressure/temperature inputs for the knob, used to set or test the stop against ambient air
  density — NOT yet distinguished from "ground self-test only, real scheduling is automatic".

**Key open question for whoever builds against this**: does DCS model automatic density sensing
for this unit at all, or only the manual knob/switch? The sibling ДИСС+СПУУ-52 *technical-check*
panel is explicitly flagged "not used in the game" in the manual — if the stops unit's own
automatic sensing is similarly unmodelled, the knob may be the *only* way the stop gets set
correctly per mission (dial from field elevation/OAT), not a side experiment.

**Do not hard-code a single cap number** (e.g. into `pedal_limit_positive`) — the cap is believed
condition-dependent (altitude/temperature), confirmed by the user's own account and by one hand-
flown data point (field ≈925 m ASL, temperature unlogged). A near-limit guard should detect the
live cap, not assume a fixed figure.

Probe (unflown as of this writing): `aircraft-layer/dcs-export/Export.probe-pedal-stops.lua`,
card `docs/acceptance/2026-11-28-pedal-stops-probe-card.md`.

See also [[reference_grep_device_name_not_label_for_russian_initialisms]].
