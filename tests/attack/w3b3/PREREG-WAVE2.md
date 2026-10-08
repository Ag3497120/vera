# W3-b3 supplementary attack preregistration

Registered: 2026-10-04 02:53:10 +0900, before writing or running the supplementary cases.

This second wave adds explicit coverage for the W1-a4 refusal shapes that were not all separately represented in the frozen 170-row corpus. It does not edit or replace that corpus or its expected values.

| ID | Input | Expected result |
|---|---|---|
| W2-01 | 兄がすぐ近くの店に行き、弟が帰った。 | Abstain: an adverbial phrase modifying a noun phrase must not be read as a clause arm. |
| W2-02 | 兄が全く来なかったので弟が帰った。 | Abstain: the negative adverb's scope is not to be inferred into an outer relation. |
| W2-03 | 兄がほとんど来なかったので弟が帰った。 | Abstain: same negative-adverb scope gate. |
| W2-04 | 兄が来ると母は思った。 | Abstain: `と` has a quotation reading; do not force the conditional relation. |
| W2-05 | 父が読んだので母が喜んだ。 | Abstain: an omitted transitive object is not supplied. |
| W2-06 | 兄が来て、しかし弟が駅へ帰った。 | Abstain: the conjunction outside the cut must not be ignored. |
| W2-07 | 兄が来て、弟が帰って、母が寝た。 | Abstain: three predicate clauses / multiple cuts. |
| W2-08 | 兄が駅へ行ったり、弟が家へ帰ったりした。 | Abstain: `たり` is outside the registered closed cut list. |

Run all eight through the public entry with `VERA_PLACEMENT` unset and with `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1`. The unset output must serialize byte-for-byte as the base entry at `c875ed3`; the configured output must remain unreadable and have no relation. A hit requires an actual readable output, relation, or placement-free byte mismatch. No expected value will be changed after execution.

Cases and per-row expectations frozen: 2026-10-04 02:53:56 +0900. SHA-256:

```text
f353dd1139094c7738493fc52efb30a14c45abd832f8481761b97b95bcc8c10c  attacks/W3-b3/cases_wave2.jsonl
```
