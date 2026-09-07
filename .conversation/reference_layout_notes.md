# Final reference layout notes

The reference image is 1532 x 700 pixels. The implementation uses it as the fixed background for `/outfit-image`.

| Element | Coordinates |
|---|---|
| Left outfit slot centers | (135,174), (80,280), (102,395), (145,508) |
| Right outfit slot centers | (858,176), (912,280), (888,396), (841,506) |
| Avatar box | x=1062..1158, y=106..208 |
| Player name box | x=1180..1368, y=108..142 |
| UID box | x=1180..1368, y=143..166 |
| Clan/guild name box | x=1180..1368, y=167..193 |
| Like count box | x=1368..1432, y=179..218 |
| Level box | x=1020..1115, y=214..250 |
| Statistic value x-coordinate | x=1322 |
| Statistic value y-coordinates | 321, 362, 403, 445, 486 |

The five displayed statistic rows are Matches Played, Kills, Headshots, Win Rate, and KD Ratio. The `mode` query parameter selects BR or CS statistics, and `matchmode` selects CAREER, NORMAL, or RANKED.

A synthetic preview was rendered successfully at 1532 x 700. The coordinate renderer is implemented in `reference_renderer.py`; the live endpoint is `/outfit-image?uid=...&region=IND&mode=br&matchmode=CAREER`.
