# Memory frame paraphrase attack

Acceptance run: 8 passed, 2 xfailed.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| P1 | wrong-ANSWER | Write `FACT(subject="きのこ", attribute="未読上限", value="3件", witness=testimony)`, then call `ask_about("きこ", "未読上限")`. Reproduced in two independent memory instances. | `UNKNOWN_NO_EVIDENCE`: the queried entity differs from the entity in the fact. | `ANSWER`, value `3件`. The writer removes the lexical `の` in `きのこ`, so the stored sentence names `きこ`. Regression test: `test_lexical_no_is_not_a_genitive_particle`. |
| P2 | robustness | Write the same fact, then call `ask("ルーターの未読上限はいくつですか？")`. | `ANSWER`, value `3件`; the same numeric property is answerable with `ルーターの未読上限は何ですか？`. | `UNKNOWN_UNREAD`. Regression test: `test_numeric_paraphrase_preserves_supported_answer`. |

## What held

- The canonical property question returns the recorded value.
- `ask_about` keeps the answer when the attribute includes the documented genitive `の` form or the subject has a trailing case particle.
- Plain `は？` and polite `は何ですか？` questions return the same value for a FACT; a DECISION frame also answers through both `ask_about` and a polite question.
- Replacing the entity with `スイッチ` or the attribute with `接続数` abstains with `UNKNOWN_NO_EVIDENCE`.
- Separate facts with `3件` and `4件` return their respective recorded values.

## Not covered

I did not cover every Japanese question construction or every memory kind. I did not exercise resolver aliases, witness freshness, supersession, malformed event logs, or concurrent writes. The tests use a testimony witness for FACT records and focus on FACT and DECISION query surfaces.
