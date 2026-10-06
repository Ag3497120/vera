## 1. Strict grading (T0 grader, 7.2 rule; CHOICE/UNKNOWN = abstain)

| system | tier | questions | correct/wrong/abstain (answerable) | loose | unanswerable answered (fict+attr) | of which wrong |
|---|---|---|---|---|---|---|
| T0 legacy a1 | - | 90 | 45/7/8 | 48 | 3+8 | 11 |
| T0 legacy a2 | - | 90 | 44/9/7 | 48 | 0+10 | 10 |
| T6 read-out (adopted candidate / list=abstain) | RUN | 90 | 0/0/60 | 0 | 0+0 | 0 |
| (reference) T5 unit answer, same core | RUN | 90 | 0/48/12 | 0 | 3+5 | 8 |
| T6 read-out (adopted candidate / list=abstain) | WORD | 30 | 0/0/20 | 0 | 0+0 | 0 |
| (reference) T5 unit answer, same core | WORD | 30 | 0/20/0 | 0 | 7+3 | 10 |
| T6 read-out (adopted candidate / list=abstain) | CHAR | 10 | 0/0/7 | 0 | 0+0 | 0 |
| (reference) T5 unit answer, same core | CHAR | 10 | 0/7/0 | 0 | 2+1 | 3 |

Verdict counts (T5 unit verdict -> T6 read-out verdict):
- RUN: {'ANSWER->CHOICE': 56, 'CHOICE->CHOICE': 19, 'UNKNOWN_NO_EVIDENCE->None': 15}
- WORD: {'ANSWER->CHOICE': 30}
- CHAR: {'ANSWER->CHOICE': 10}

## 2. Diagnostic: is the gold string anywhere in the read-out? (answerable questions a01..a60 only)

| tier | answerable | with an adopted state | gold in some candidate sentence | gold in some single section path | gold in the union of path words | gold held in the subject's sentences (T0 gold_held) |
|---|---|---|---|---|---|---|
| RUN | 60 | 60 | 1 | 1 | 1 | 58 |
| WORD | 20 | 20 | 0 | 0 | 0 | 20 |
| CHAR | 7 | 7 | 0 | 0 | 0 | 7 |

## 3. Function-word paths

| tier | questions with a read-out | all adopted states' paths function-only (POS) | at least one adopted state function-only | all hiragana-only | function words / path words (distinct per state, summed) | questions whose paths hold at least one content word |
|---|---|---|---|---|---|---|
| RUN | 75 | 0 | 56 | 0 | 11424/14472 | 75 |
| WORD | 30 | 0 | 0 | 0 | 1932/3540 | 30 |
| CHAR | 10 | 0 | 0 | 0 | 618/1218 | 10 |

## 4. Candidates, lists, trace

| tier | questions with a read-out | adopted states per question (min/median/max) | listed sentences (min/median/max) | orderings (min/median/max) | too many (> 20) | trace: words checked | words traced | all questions 100% |
|---|---|---|---|---|---|---|---|---|
| RUN | 75 | 6/13/13 | 40/9360/9360 | 4320/9360/9360 | 75 | 9444000 | 9444000 | True |
| WORD | 30 | 1/2/3 | 720/1440/2160 | 720/1440/2160 | 30 | 2548800 | 2548800 | True |
| CHAR | 10 | 1/1/3 | 720/720/2160 | 720/720/2160 | 10 | 876960 | 876960 | True |

distinct content-word sets of the paths across the 75 RUN questions with a read-out: 2
distinct content-word sets of the paths across the 30 WORD questions with a read-out: 3
distinct content-word sets of the paths across the 10 CHAR questions with a read-out: 3

RUN section paths (first 3 adopted states per question): 1008 of 1350 consist only of function words
WORD section paths (first 3 adopted states per question): 4 of 354 consist only of function words
CHAR section paths (first 3 adopted states per question): 0 of 84 consist only of function words

k (working sections) per adopted state: {6: 915}
