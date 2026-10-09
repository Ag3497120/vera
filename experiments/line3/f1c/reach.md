# F1c reach (bank2 intra2, n = 69, fulllead, level mid)

A gold counts as reached in a tier when a cross that holds a question unit also holds a unit containing the gold.
`gold unit exists` = some unit of the tier contains the gold (tokenisation, independent of placement). One hop = a sentence holds a question unit and a gold unit (RUN or WORD): 41.

| tier | gold unit exists | whole (before) | ordered + stop | ordered + skip |
|---|---|---|---|---|
| RUN | 50 | 29 | 40 | 40 |
| WORD | 18 | 9 | 17 | 17 |
| CHAR | 1 | 1 | 1 | 1 |
| any tier | | 31 | 41 | 41 |
| RUN or WORD | | 31 | 41 | 41 |

Crosses (seeds) that hold a question unit AND a gold unit, summed over the 69 golds (how many different crosses reach, not whether one does):

| tier | whole | ordered + stop | ordered + skip |
|---|---|---|---|
| RUN | 90 | 250 | 262 |
| WORD | 24 | 113 | 124 |
| CHAR | 1 | 10 | 21 |

Gained / lost against ordered+stop (any tier): skip +0 / -0; against whole: stop +10 / -0, skip +10 / -0
Reached by skip though not one hop: none
One hop but still not reached (skip): none
Reached by skip, per tier, differing from stop: none
