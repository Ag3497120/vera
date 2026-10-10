# line3 combined list, standard, fulllead (flat records: group_insert ordered; window evidence plain,window; merge none)

Questions combined: 94 (flat file 94, window files plain 94, window 94). Code: line3 combined.combine, the one `ask(structure="combined")` uses.

## intra2: is the gold in a candidate

| system | n | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max |
|---|---|---|---|---|---|---|---|---|
| flat (3 tiers) | 69 | 19 (28%) | 0 | 1 | 19 | 49 | 0 | 44.5 / 203 |
| flat + layers (ssp) | 69 | 27 (39%) | 0 | 0 | 27 | 42 | 0 | 61.0 / 234 |
| windows alone, plain | 69 | 8 (12%) | 1 | 7 | 7 | 27 | 27 | 4.0 / 16 |
| windows alone, window | 69 | 21 (30%) | 0 | 8 | 21 | 31 | 9 | 5.0 / 24 |
| COMBINED (flat + layers + windows plain/window) | 69 | 32 (46%) | 0 | 0 | 32 | 37 | 0 | 70.0 / 234 |

## unans: can a user reject what is shown

| system | n | no candidate (abstained) | list (rejectable) | single answer (confident wrong) |
|---|---|---|---|---|
| flat (3 tiers) | 25 | 0 | 25 | 0 |
| flat + layers (ssp) | 25 | 0 | 25 | 0 |
| windows alone, plain | 25 | 13 | 7 | 5 |
| windows alone, window | 25 | 3 | 16 | 6 |
| COMBINED (flat + layers + windows plain/window) | 25 | 0 | 25 | 0 |

