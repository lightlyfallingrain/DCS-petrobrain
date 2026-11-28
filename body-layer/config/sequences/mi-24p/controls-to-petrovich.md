| file-param | for |
| --- | --- |
| aircraft | Mi-24P |
| petrovich-role | copilot |
| run-on-trigger | controls-to-petrovich |
| step-delay-s | 0 |

| condition | effector | value | petrovich-says | comment |
| --- | --- | --- | --- | --- |
| | p_sau_h_channel_off | on | | H = heading channel, off while Petrovich flies mode 1 |
| | p_sau_k_channel_off | on | | K = bank channel, off while Petrovich flies mode 1 |
| | p_sau_t_channel_off | on | | T = pitch channel, off while Petrovich flies mode 1 |
| | p_sau_b_channel_off | on | | B = altitude channel, off while Petrovich flies mode 1 (user, 2026-11-28: "set off on take") |
| | p_spuu_power | off | | adjustable stops (SPUU-52) off while Petrovich flies: right-pedal cap -0.566 -> -0.678 (probe 2026-11-28; user chose option 2) |
