## T6ab oracle (S300 RUN; T6z default lists; rule B on an entry's words = a gold string occurs in a word)

| id | kind | entries | gold entries | first gold position (1-based) | positions of gold entries |
|---|---|---|---|---|---|
| a05 | which | 19 | 2 | 12 | 12,13 |
| a06 | who | 45 | 36 | 1 | 1,4,5,7,8,10,11,12,14,15,16,17... |
| a11 | where | 89 | 0 | - |  |
| a16 | where | 34 | 34 | 1 | 1,2,3,4,5,6,7,8,9,10,11,12... |
| a19 | where | 22 | 0 | - |  |
| a24 | what | 65 | 51 | 1 | 1,2,3,4,5,9,10,11,15,16,17,18... |
| a27 | what | 42 | 41 | 1 | 1,2,3,4,5,6,7,8,9,10,11,13... |
| a32 | who | 26 | 0 | - |  |
| a33 | what | 11 | 10 | 1 | 1,2,3,4,5,6,8,9,10,11 |
| a37 | which | 18 | 0 | - |  |
| a43 | what | 18 | 17 | 2 | 2,3,4,5,6,7,8,9,10,11,12,13... |
| a47 | where | 7 | 7 | 1 | 1,2,3,4,5,6,7 |
| a48 | where | 25 | 21 | 1 | 1,2,3,4,5,8,9,10,11,12,13,15... |
| a55 | where | 30 | 16 | 3 | 3,6,7,10,12,13,15,16,19,21,22,24... |
| a59 | what | 6 | 3 | 4 | 4,5,6 |
| u03 | fict | 85 | - (unanswerable) | - | - |
| u04 | fict | 2 | - (unanswerable) | - | - |
| u19 | fict | 88 | - (unanswerable) | - | - |
| u26 | attr | 6 | - (unanswerable) | - | - |
| u30 | attr | 42 | - (unanswerable) | - | - |

- lists on answerable questions: 15; with at least one gold entry: 11; without: 4; unanswerable lists (rejected): 5
- first gold position over lists with gold: [1, 1, 1, 1, 1, 1, 1, 2, 3, 4, 12] (median 1); gold entries share of list: ['2/19', '36/45', '34/34', '51/65', '41/42', '10/11', '17/18', '7/7', '21/25', '16/30', '3/6']

| system | correct/wrong/abstain (60 answerable) | unanswerable answered (fict+attr) |
|---|---|---|
| T0 legacy a1 | 45/7/8 | 11 |
| T6z (list = abstention) | 18/3/39 | 4 |
| **oracle (gold-knowing user picks a gold entry)** | 29/3/28 | 4 (a knowing user rejects unanswerable lists) |

(non-list abstentions of the 60 answerable stay abstentions: 24 have no list at all (UNKNOWN / AMBIGUOUS / no state); oracle recovers 11 of the 15 list abstentions)
