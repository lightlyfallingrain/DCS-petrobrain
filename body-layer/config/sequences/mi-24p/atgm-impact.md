
| file-param | for |
| --- | --- |
| aircraft | Mi-24P |
| petrovich-role | copilot |
| run-on-trigger | atgm-impact |

| condition | effector | value | petrovich-says | comment |
| --- | --- | --- | --- | --- |
| wait_s(1) | | | | wait 1s after impact before resetting the transmitter (`[[BL-B67]]`) |
| | radiation_reset | pressed | | Radiation Reset, press |
| | radiation_reset | released | | Radiation Reset, release |


