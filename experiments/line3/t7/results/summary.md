# T7 — three tiers combined, S300, 90 questions (placements: level mid, function-word filter; all defaults of T6z/T6ab)

## 1. Candidate quality (what a user can pick from)

Gold in a candidate = a gold string occurs in a word of the entry (the oracle rule of T6ab, no core condition). 'shown' = what the combination hands the user (the most stable tier, or the tied tiers' lists); 'pool' = the union of every tier's entries (reference: what the user would see if all tiers were listed).

### Answerable questions (60)

| | RUN only | WORD only | CHAR only | **combined: shown** | pool of all tiers |
|---|---|---|---|---|---|
| a candidate holds the gold (single answer or list entry) | 29 | 5 | 0 | **21** | 30 |
| ... as the single ANSWER (gold in it) | 18 | 1 | 0 | **15** | - |
| ... inside a list of >= 2 entries | 11 | 4 | 0 | **6** | - |
| no candidate at all (no state / no path) | 24 | 17 | 5 | **2** | 2 |
| candidates but none holds the gold | 7 | 38 | 55 | **37** | 28 |

### List sizes (entries) on answerable questions that have a list

| | RUN | WORD | CHAR | shown (combined) | pool |
|---|---|---|---|---|---|
| lists of >= 2 | n=15 median 25 max 89 | n=41 median 5 max 74 | n=49 median 8 max 193 | n=37 median 18 max 193 | n=57 median 22 max 201 |

shown lists with gold: 6; first gold position (1-based, list order is a label): [1, 1, 1, 1, 3, 12] (median 1.0)

### Unanswerable questions (30: fict + attr) — can a user reject what is shown?

| | RUN only | WORD only | CHAR only | **combined: shown** |
|---|---|---|---|---|
| no candidate (nothing to reject) | 21 | 11 | 1 | **1** |
| only a list (a user can reject it) | 5 | 19 | 24 | **24** |
| a single answer (looks like a confident answer: wrong) | 4 | 0 | 5 | **5** |

### Questions with no state (no candidate): does the combination help?

| | RUN | WORD | CHAR | combined (no tier has any) |
|---|---|---|---|---|
| answerable (60) | 24 | 17 | 5 | 2 |
| all 90 | 45 | 28 | 6 | 3 |

answerable questions with no RUN candidate but some candidate in another tier: 22 (a03,a04,a08,a09,a10,a14,a21,a23,a25,a26,a29,a30,a31,a34,a35,a38,a40,a42,a44,a50,a56,a57); of these the gold is in the pool for 0
answerable questions where RUN has no gold but another tier does: 1 (a41)

### What the combination returned (90 questions)

| verdict | tiers shown | tie between tiers | questions |
|---|---|---|---|
| ANSWER | 1 | False | 26 |
| CHOICE | 1 | False | 61 |
| UNKNOWN_NO_STATE | 0 | False | 3 |

tier appears among the shown tiers (times): {'CHAR': 47, 'RUN': 29, 'WORD': 11}; stability values seen: {'19/22': 20, '23/50': 17, '38/43': 13, '37/41': 10, '21/50': 6, '33/94': 4, '10/19': 4, '76/101': 3}
questions where at least two tiers share a literal word (reported, never used): 48; where the gold-holding tiers are more than one: 4

## 2. Rule-B scores (reference only; not the goal)

Rule B: the answer = the word set of the single entry; a list / UNKNOWN = abstention; correct iff a gold string is in it and the core is in the subject; unanswerable answered = wrong.

| system | correct/wrong/abstain (60 answerable) |
|---|---|
| T6z RUN only (recorded) | 18/3/39 (answered unanswerable 4) |
| T6ab blind user on T6z lists (recorded) | 29/4/27 |
| RUN only (this run) | 18/3/39 (answered unanswerable 4) |
| WORD only (this run) | 1/1/58 (answered unanswerable 0) |
| CHAR only (this run) | 0/6/54 (answered unanswerable 5) |
| **combined (this run)** | **15/6/39 (answered unanswerable 5)** |

RUN tier vs the stored T6z read-out objects (sha256 of the answer object): 45 / 45 equal

## 3. Time (per question, wall, 9 worker processes on one machine: contention included)

| | median s | p90 s | max s | total CPU-s |
|---|---|---|---|---|
| RUN search + read-out | 0.01 | 46.49 | 241.95 | 1505 |
| WORD search + read-out | 26.94 | 100.81 | 301.33 | 3756 |
| CHAR search + read-out | 40.84 | 306.10 | 382.31 | 9985 |
| all three tiers (one question) | 108.58 | 390.55 | 617.17 | 15250 |

budget raised on demand (question x tier): {'RUN': 9, 'WORD': 14, 'CHAR': 6}

slowest questions (all tiers): u03 617.2s, u19 543.5s, a11 540.5s, a32 471.5s, a37 465.7s, a38 449.6s

## 4. Per question

| id | kind | RUN n/gold | WORD n/gold | CHAR n/gold | combined | shown | gold in shown | gold in pool |
|---|---|---|---|---|---|---|---|---|
| a01 | what | 0/- | 0/- | 0/- | UNKNOWN_NO_STATE | - | - | - |
| a02 | where | 1/Y | 5/- | 14/- | ANSWER | RUN | Y | Y |
| a03 | where | 0/- | 2/- | 16/- | CHOICE | CHAR | - | - |
| a04 | what | 0/- | 0/- | 3/- | CHOICE | CHAR | - | - |
| a05 | which | 19/Y | 74/- | 3/- | CHOICE | RUN | Y | Y |
| a06 | who | 45/Y | 5/- | 3/- | CHOICE | RUN | Y | Y |
| a07 | where | 1/Y | 5/- | 4/- | ANSWER | RUN | Y | Y |
| a08 | what | 0/- | 1/- | 3/- | ANSWER | WORD | - | - |
| a09 | what | 0/- | 0/- | 17/- | CHOICE | CHAR | - | - |
| a10 | what | 0/- | 0/- | 22/- | CHOICE | CHAR | - | - |
| a11 | where | 89/- | 4/- | 4/- | CHOICE | RUN | - | - |
| a12 | what | 1/- | 0/- | 10/- | ANSWER | RUN | - | - |
| a13 | where | 1/Y | 4/- | 24/- | CHOICE | CHAR | - | Y |
| a14 | where | 0/- | 5/- | 2/- | CHOICE | CHAR | - | - |
| a15 | where | 1/Y | 9/- | 8/- | ANSWER | RUN | Y | Y |
| a16 | where | 34/Y | 5/- | 21/- | CHOICE | CHAR | - | Y |
| a17 | who | 1/Y | 27/- | 13/- | ANSWER | RUN | Y | Y |
| a18 | where | 1/Y | 5/- | 1/- | ANSWER | RUN | Y | Y |
| a19 | where | 22/- | 7/- | 59/- | CHOICE | CHAR | - | - |
| a20 | where | 1/Y | 5/- | 55/- | CHOICE | CHAR | - | Y |
| a21 | where | 0/- | 6/- | 1/- | CHOICE | WORD | - | - |
| a22 | what | 1/Y | 35/- | 30/- | ANSWER | RUN | Y | Y |
| a23 | where | 0/- | 8/- | 193/- | CHOICE | CHAR | - | - |
| a24 | what | 65/Y | 0/- | 1/- | CHOICE | RUN | Y | Y |
| a25 | where | 0/- | 3/- | 50/- | CHOICE | CHAR | - | - |
| a26 | where | 0/- | 6/- | 2/- | CHOICE | CHAR | - | - |
| a27 | what | 42/Y | 0/- | 2/- | CHOICE | RUN | Y | Y |
| a28 | what | 1/Y | 4/- | 3/- | ANSWER | RUN | Y | Y |
| a29 | what | 0/- | 9/- | 3/- | CHOICE | CHAR | - | - |
| a30 | where | 0/- | 2/- | 70/- | CHOICE | CHAR | - | - |
| a31 | where | 0/- | 6/- | 8/- | CHOICE | CHAR | - | - |
| a32 | who | 26/- | 0/- | 7/- | CHOICE | CHAR | - | - |
| a33 | what | 11/Y | 0/- | 2/- | CHOICE | CHAR | - | Y |
| a34 | what | 0/- | 0/- | 1/- | ANSWER | CHAR | - | - |
| a35 | where | 0/- | 6/- | 9/- | CHOICE | CHAR | - | - |
| a36 | what | 0/- | 0/- | 0/- | UNKNOWN_NO_STATE | - | - | - |
| a37 | which | 18/- | 17/- | 3/- | CHOICE | RUN | - | - |
| a38 | where | 0/- | 4/- | 27/- | CHOICE | CHAR | - | - |
| a39 | what | 1/Y | 0/- | 44/- | ANSWER | RUN | Y | Y |
| a40 | where | 0/- | 5/- | 4/- | CHOICE | CHAR | - | - |
| a41 | who | 1/- | 27/Y | 11/- | ANSWER | RUN | - | Y |
| a42 | what | 0/- | 0/- | 2/- | CHOICE | CHAR | - | - |
| a43 | what | 18/Y | 7/- | 3/- | CHOICE | WORD | - | Y |
| a44 | what | 0/- | 0/- | 4/- | CHOICE | CHAR | - | - |
| a45 | where | 1/Y | 4/- | 0/- | ANSWER | RUN | Y | Y |
| a46 | what | 1/Y | 32/Y | 7/- | ANSWER | RUN | Y | Y |
| a47 | where | 7/Y | 5/- | 1/- | ANSWER | CHAR | - | Y |
| a48 | where | 25/Y | 2/- | 4/- | CHOICE | CHAR | - | Y |
| a49 | who | 1/- | 27/- | 27/- | ANSWER | RUN | - | - |
| a50 | where | 0/- | 5/- | 15/- | CHOICE | CHAR | - | - |
| a51 | what | 1/Y | 0/- | 1/- | ANSWER | RUN | Y | Y |
| a52 | where | 1/Y | 5/- | 3/- | CHOICE | CHAR | - | Y |
| a53 | what | 1/Y | 1/Y | 3/- | ANSWER | RUN | Y | Y |
| a54 | who | 1/Y | 49/- | 3/- | ANSWER | RUN | Y | Y |
| a55 | where | 30/Y | 8/- | 3/- | CHOICE | RUN | Y | Y |
| a56 | where | 0/- | 5/- | 66/- | CHOICE | CHAR | - | - |
| a57 | what | 0/- | 0/- | 37/- | CHOICE | CHAR | - | - |
| a58 | what | 1/Y | 0/- | 8/- | ANSWER | RUN | Y | Y |
| a59 | what | 6/Y | 35/Y | 0/- | CHOICE | WORD | Y | Y |
| a60 | what | 1/Y | 5/Y | 0/- | ANSWER | RUN | Y | Y |
| u01 | fict | 0/. | 0/. | 0/. | UNKNOWN_NO_STATE | - | . | . |
| u02 | fict | 0/. | 6/. | 26/. | CHOICE | CHAR | . | . |
| u03 | fict | 85/. | 2/. | 100/. | CHOICE | CHAR | . | . |
| u04 | fict | 2/. | 63/. | 3/. | CHOICE | RUN | . | . |
| u05 | fict | 0/. | 0/. | 2/. | CHOICE | CHAR | . | . |
| u06 | fict | 0/. | 0/. | 58/. | CHOICE | CHAR | . | . |
| u07 | fict | 0/. | 6/. | 2/. | CHOICE | CHAR | . | . |
| u08 | fict | 0/. | 5/. | 16/. | CHOICE | CHAR | . | . |
| u09 | fict | 1/. | 65/. | 53/. | CHOICE | WORD | . | . |
| u10 | fict | 0/. | 0/. | 14/. | CHOICE | CHAR | . | . |
| u11 | fict | 0/. | 5/. | 67/. | CHOICE | CHAR | . | . |
| u12 | fict | 0/. | 0/. | 144/. | CHOICE | CHAR | . | . |
| u13 | fict | 0/. | 2/. | 30/. | CHOICE | CHAR | . | . |
| u14 | fict | 0/. | 0/. | 1/. | ANSWER | CHAR | . | . |
| u15 | fict | 1/. | 27/. | 34/. | ANSWER | RUN | . | . |
| u16 | fict | 0/. | 5/. | 32/. | CHOICE | CHAR | . | . |
| u17 | fict | 0/. | 0/. | 1/. | ANSWER | CHAR | . | . |
| u18 | fict | 0/. | 66/. | 9/. | CHOICE | WORD | . | . |
| u19 | fict | 88/. | 4/. | 78/. | CHOICE | CHAR | . | . |
| u20 | fict | 0/. | 0/. | 2/. | CHOICE | CHAR | . | . |
| u21 | attr | 0/. | 32/. | 3/. | CHOICE | WORD | . | . |
| u22 | attr | 1/. | 0/. | 2/. | ANSWER | RUN | . | . |
| u23 | attr | 0/. | 9/. | 3/. | CHOICE | WORD | . | . |
| u24 | attr | 0/. | 21/. | 4/. | CHOICE | WORD | . | . |
| u25 | attr | 0/. | 0/. | 1/. | ANSWER | CHAR | . | . |
| u26 | attr | 6/. | 11/. | 8/. | CHOICE | WORD | . | . |
| u27 | attr | 1/. | 3/. | 1/. | CHOICE | WORD | . | . |
| u28 | attr | 0/. | 27/. | 9/. | CHOICE | CHAR | . | . |
| u29 | attr | 0/. | 0/. | 4/. | CHOICE | CHAR | . | . |
| u30 | attr | 42/. | 2/. | 1/. | CHOICE | RUN | . | . |
