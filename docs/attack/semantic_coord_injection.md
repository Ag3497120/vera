# Semantic coordination injection review

Scope: direct probes of `verantyx/semantic_coord.py` using synthetic tagged tokens. The module contract licenses only te/renyō coordination, limits topic sharing to later clauses without their own は/が phrase, and requires role phrases to respect token boundaries.

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| SC-01 | ungrounded | `読み(連用形) + て + しかし(接続詞) + 日記を + 書く`; predicate indexes `[2, 7]` | Reject: the chain contains an adversative connective beyond the te marker. | `coordination_ok` accepts it. The function checks the consumed te/comma tail but does not inspect tokens from that tail to the next predicate. Reproduced by the xfailed test. |
| SC-02 | ungrounded | One token `管理者` spans `[0, 4)`, followed by `は`; call `phrase_bounded(..., 1, 3)`. | Reject: the proposed phrase starts and ends inside a token. | `phrase_bounded` accepts it because no token starts or ends at either supplied boundary. Reproduced by the xfailed test. |
| SC-03 | robustness | `前置` + U+200B tagged `補助記号` + `名前` + `は`; check the `名前` span `[3, 5)`. | Reject: a zero-width format character is not punctuation and cannot establish a real phrase boundary. | `phrase_bounded` accepts it because `_punctuation` treats any non-alphanumeric `補助記号` token as punctuation. Reproduced by the xfailed test. |

## What held

The acceptance run reported 11 passed and 3 xfailed in 0.09 seconds. The passing probes confirmed that a te-linked chain exposes the first clause's は topic; a later clause with its own は/が is recognized as locally marked; a first clause without は provides no topic; bare renyō requires a comma; a non-renyō predicate and an unmarked causal link are refused; and split-name fragments are rejected while actual punctuation can bound a phrase. A quoted record containing an instruction-like string did not remove the later clause's local は marker.

## Not covered

- These tests supply synthetic tags directly; they do not exercise a tokenizer or normalization pipeline.
- The quoted record probe checks only structural subject sharing. Downstream agent-message authority, instruction execution, and escalation decisions are outside this module and were not exercised.
- No end-to-end answer generation, crash, or hang behavior was tested.
