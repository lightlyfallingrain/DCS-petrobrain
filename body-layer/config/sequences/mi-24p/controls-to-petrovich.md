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
| | p_sau_b_channel_on | on | | B = adjustable-stops channel, kept on; never assume what the player left it |
