# F1 reach (bank2 intra2, n = 69, fulllead, level mid)

A gold counts as reached in a tier when a cross that holds a question unit also holds a unit containing the gold.
`gold unit exists` = some unit of the tier contains the gold (tokenisation, independent of placement). One hop = a sentence holds a question unit and a gold unit (RUN or WORD): 41.

| tier | gold unit exists | whole (before) | ordered | reverse order |
|---|---|---|---|---|
| RUN | 50 | 29 | 40 | 36 |
| WORD | 18 | 9 | 17 | 14 |
| CHAR | 1 | 1 | 1 | 1 |
| any tier | | 31 | 41 | 37 |
| RUN or WORD | | 31 | 41 | 37 |

Gained / lost against whole (any tier): ordered +10 / -0; reverse +6 / -0. Ordered vs reverse differ on: I2-017, I2-023, R2-I006, R2-I010
Reached though not one hop (ordered): none
One hop but still not reached (ordered): none
