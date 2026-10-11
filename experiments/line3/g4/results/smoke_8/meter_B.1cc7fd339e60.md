# G4 meter -- arm B

Records: 30 (5 steps: 1,2,3,5,8), errors recorded: 0.  Format line3.g4.meter.v1.
Config: {"arrival_oracle": {"error": null, "loaded": true, "needed": true, "source": "cache/g4_stack_A"}, "config": {"code_sha256": "fcf0b10355ca125e430f3959119c855b23cd251a212d3bd357a9ebce9c5601da", "effort": "fast", "grammar": "off", "level": "mid", "site": "on"}, "foundation": "on", "kind": "stack", "tiers": ["CHAR"]}

## 2x2 per step (headline = the correct cells over the present row WITHOUT 未着, 未着 counted apart; gold in a candidate beside it)

| step | present (all) | 未着 (unarrived_3tier) | 未着 (the arm's own tiers) | denominator = present - 未着 | correct | correct / denominator | miss (abstain / list-no-gold / not-from-evidence) | confident wrong | gold in a candidate (present) | absent | correct (abstained) | false presence | confident wrong | single ANSWER | median listed | crosses read (median/tier) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | 1 | 0 | 0 | - | 0 / 0 / 0 | 0 | 0 | 5 | 2 | 2 | 1 | 1 | 3 | CHAR 2 |
| 2 | 2 | 1 | 2 | 1 | 0 | 0.0% | 0 / 0 / 0 | 1 | 0 | 4 | 2 | 1 | 1 | 2 | 1 | CHAR 1 |
| 3 | 2 | 1 | 2 | 1 | 0 | 0.0% | 0 / 0 / 0 | 1 | 0 | 4 | 0 | 2 | 2 | 3 | 3 | CHAR 2 |
| 5 | 2 | 1 | 2 | 1 | 0 | 0.0% | 0 / 0 / 0 | 1 | 0 | 4 | 0 | 2 | 2 | 3 | 3 | CHAR 2 |
| 8 | 3 | 1 | 3 | 2 | 0 | 0.0% | 0 / 0 / 0 | 2 | 0 | 3 | 0 | 3 | 0 | 2 | 2.5 | CHAR 3 |

## Events (現れる / 残る / 壊れる), 未着 flag `unarrived_3tier`

| quantity | value |
|---|---|
| intra2 questions with a record at or after their entry | 3 of 3 |
| 未着 at the last step, flag `unarrived_3tier` (3-tier flag: no RUN / WORD / CHAR unit holds the gold): left out of the denominator | 1 |
| 未着 at the last step, the arm's own flag `unarrived` (its own tiers only): beside, not used for the denominator | 3 |
| denominator of 現れる | 2 |
| 現れる (H at some measured step) | 0/2 (0.0%) |
| 　直入 (appeared at e(q), delay 0) / 後から (later, e(q) on the schedule) | 0 / 0 |
| 　appeared with e(q) NOT on the arm's schedule (直入 / 後から unknowable) | 0 |
| 　後から whose gold entry cites a sentence, or its cross a seat, from after the entry | 0 |
| never appeared, by tag (the site tags read the ARM's own tiers: for a CHAR-only arm 未着 here = no CHAR unit holds the gold) | 未着 2 |
| 残る: appeared questions with H at every later measured step | 0 of 0 that have a later step |
| 残る: share of later measured steps still holding the gold | 0/0 (-) |
| gold in a candidate at the last step (denominator questions) | 0/2 |
| losses of H (consecutive measured steps) | 0 |
| 　壊れる | 0 (-) |
| 　置き換え (growth: every gold cross R) | 0 (rearrangement kinds: -) |
| 　単独誤答化 | 0 |
| 　cause tags over the gold crosses of all losses | - |
| 　loss with an unlookable cross (?) | 0 |
| 戻る (H again after a loss) | 0 |

## Per question

| id | e | appear | delay | 残る | losses (j -> k: class, tags) | final |
|---|---|---|---|---|---|---|
| I2-001 | 1 | - | - | - | - | 未着 |
| I2-002 | 2 | - | - | - | - | 未着 |
| I2-003 | 8 | - | - | - | - | 未着 |

## Absent row (unans at every step; intra2 before entry)

| kind | cells over all (question, step) pairs on the absent row |
|---|---|
| intra2 | correct/None 2, miss/false_presence 1, wrong/None 2 |
| unans | correct/None 2, miss/false_presence 9, wrong/None 4 |

single ANSWER (単独誤答) first appears, per question: UF-002@1, I2-003@3

## Registered predictions (PREDICTIONS.md) judgeable from this arm alone

| id | prediction | value | status |
|---|---|---|---|
| P-5 | B: present-correct at 300 <= 3 of 69 | 0 | not judged: arm B has 66 of 66 scheduled steps incomplete (e.g. 1,2,3,5) |
| P-7 | stack: the closed share at 300 is higher with the foundation on than off | not computed by the meter | not judged: a structure fact (gate G-2 / stack ledgers), not a question |
