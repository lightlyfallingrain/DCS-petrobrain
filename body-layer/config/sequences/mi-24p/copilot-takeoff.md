<!-- Four-switch guidance-unit power-up (BL-B66), run on every real
     ground->air takeoff (D2/D4) -- an air start fires `mission-start`/
     `mission-start-in-air` instead and never reaches this file
     (`plans/effector-sequences/explore-notes.md`, "Two new triggers:
     mission start"). No row carries an explicit `condition` cell any
     more (R12, 2026-10-23 user correction) -- the engine's own
     implicit self-check (every switch row, every trigger) is what
     makes a re-run after the first a no-op and what lets a hot start
     finish the power-up on its own, by comparing each row's own
     effector against its already-observed readback before writing.
     "Guidance unit ready" is not spoken from this file: it stays
     hard-coded on the real 960 lamp's off->on edge (plan R3/D7). -->

| file-param | for |
| --- | --- |
| aircraft | Mi-24P |
| petrovich-role | copilot |
| run-on-trigger | takeoff |

| condition | effector | value | petrovich-says | comment |
| --- | --- | --- | --- | --- |
| | missile_power | on | | MISSILE POWER |
| | cplr_distr | on | | CPLR DISTR -- unverified, see registry |
| | sight_power | on | | Sight Power (GUID.UNIT POWER) |
| | scho_pwr_b1 | on | | SHCHO PWR B1 |
