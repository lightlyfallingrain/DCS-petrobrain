<!-- Four-switch guidance-unit power-up (BL-B66), run on every takeoff
     (D2/D4) -- the row conditions below are what makes a re-run after
     the first a no-op, and what lets a hot/air start finish the
     power-up on its own. "Guidance unit ready" is not spoken from this
     file: it stays hard-coded on the real 960 lamp's off->on edge
     (plan R3/D7). -->

| file-param | for |
| --- | --- |
| aircraft | Mi-24P |
| petrovich-role | copilot |
| run-on-trigger | takeoff |

| condition | effector | value | petrovich-says | comment |
| --- | --- | --- | --- | --- |
| missile_power != on | missile_power | on | | MISSILE POWER |
| cplr_distr != on | cplr_distr | on | | CPLR DISTR -- unverified, see registry |
| sight_power != on | sight_power | on | | Sight Power (GUID.UNIT POWER) |
| scho_pwr_b1 != on | scho_pwr_b1 | on | | SHCHO PWR B1 |
