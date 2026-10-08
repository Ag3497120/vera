# T8 descent (coarse -> fine) vs the flat read, S300 90 questions

Descent = the question is read on the packed upper crosses (one cross per question unit), then ONLY the lower crosses under the elements of the selected path are read (capped by the preset's node budget). Flat = the T7b read of the same preset (fast 4 / standard 10 crosses per tier, full = every cross holding a question unit). Candidates are pooled over the three tiers as in T7b.

| search | answerable: gold in a candidate | no candidate | unanswerable: no candidate / list / single | crosses read per question (sum of 3 tiers) median / mean | wall s per question median / p90 |
|---|---|---|---|---|---|
| flat fast | 28 | 5 | 4 / 22 / 4 | 9.0 / 9.2 | 3.2 / 14.8 |
| descent (bounds of fast) | 2 | 19 | 11 / 9 / 10 | 14.5 / 13.8 | 12.4 / 20.1 |
| flat standard | 29 | 3 | 3 / 25 / 2 | 21.0 / 19.6 | 16.6 / 50.3 |
| descent (bounds of standard) | 19 | 7 | 4 / 22 / 4 | 25.5 / 25.1 | 34.6 / 62.3 |
| flat full | 30 | 2 | 1 / 26 / 3 | 79.0 / 155.2 | 108.6 / 404.0 |
| descent (bounds of full) | 21 | 10 | 13 / 13 / 4 | 29.5 / 26.1 | 75.5 / 172.8 |

Whole-flat crosses (every cross holding a question unit) vs crosses the descent read, sum over the 90 questions: 
- descent fast: upper 629 + lower 612 = 1241 crosses vs 13971 for the whole flat read
- descent standard: upper 802 + lower 1455 = 2257 crosses vs 13971 for the whole flat read
- descent full: upper 816 + lower 1529 = 2345 crosses vs 13971 for the whole flat read
