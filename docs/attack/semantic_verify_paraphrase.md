# Semantic verifier paraphrase attack

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| PAR-WORD-ORDER | robustness | License the `行く` frame `agent=太郎, recipient=図書館` against `図書館に太郎が行った。`; ask `太郎は図書館に行った？`. | Accept the equivalent event and retain the supported positive verdict. | The checker rejects with `event predicate licensing`; independent frame reading identifies the predicate as `行う` for the reordered source. The xfailed test repeats the audit to show the rejection is stable. |

## What held

The acceptance run reported **13 passed, 1 xfailed**. Polite and plain forms, the tested topic-particle and destination-particle variants, and coherent entity substitutions retained support. Changing the queried entity or destination produced no matching answer. Explicit negation produced `False`, while a past-versus-nonpast mismatch remained unanswered. For measure clauses, `は` and `が` preserved the same `3個` projection, changing the amount changed the projected quantity, and changing the entity removed the match.

## What was not covered

The attacks exercise `Checker.audit` and source licensing, not complete proof construction, proof replay, or the proposal gate. The measure checks use a small explicit plan so they isolate verifier behavior; they do not establish that natural-language measure questions are wired to that path. The cases cover a narrow set of Japanese surface forms, not broad grammar, condition/exception scope, multiple-clause coordination, or resource-limit behavior.
