# BL-B119 effector readbacks: acceptance sortie (2026-11-16)

**Artifact (cockpit-readable card):** https://claude.ai/artifact/CGyeRj5f8tHwt8NMrQEZyZ
**Card source:** `docs/acceptance/2026-11-16-effector-says-card.html`
**Branch to fly:** `main`, after this DoD pass's auto-merge.

What is under test, verbatim from the DoD dispatch: say "observ on", "observ off", "weapons
armed", "weapons safe" — each line heard once, after the switch moves (or at once if it was
already there); start an attack run — "Weapons armed." heard once, not twice, even though both
the attack-run start and the weapons-arm sequence set the same switch; no line ever heard twice;
"Unable, guidance unit not ready." still answers "observ on" before power-up, unchanged and never
reaching the sequence engine.

No Export.lua change, no collector restart. Restart `body.py` to pick up the merged code.

Results go to `body-layer/ROADMAP/BL-B119.md`, not into the card.
