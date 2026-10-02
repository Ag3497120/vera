# Semantic coordination attacker: tense and time

Scope: `verantyx/semantic_coord.py` coordination and phrase-boundary helpers. The tests use hand-built token tuples to check the module's documented contract; they do not exercise a tagger or a downstream answer path.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| T1 | robustness | `year-number + 年 + の + 春 + は + predicate`; call `topic_phrase` with the first predicate | The span covers the full は-marked date phrase, including the genitive modifier | The span begins at 春, omitting the year and `の`. The xfail test reproduces this mismatch. |

The span defect is a phrase-boundary issue. This module does not itself produce or judge an answer, so this finding is not reported as a wrong ANSWER or fabrication.

## What held

- A te-connected chain with a renyō first predicate was accepted when its final clause had past marking, and the later clause's relative-time token remained inside its chunk.
- A corresponding chain with a nonpast final predicate was accepted.
- Bare renyō plus comma was accepted; bare renyō without the comma and a past-form nonfinal predicate were rejected.
- A later clause's own が-marked phrase was detected even when a time expression preceded it.
- A complete date phrase was bounded before は, while a span ending inside its date expression was rejected.
- A simple relative-time topic was returned with its whole time noun.

## Not covered

- Whether a downstream consumer preserves this span correctly or uses it to make a time-sensitive claim.
- End-to-end parsing, semantic routing, answer generation, or judging.
- Real tagger behavior and tokenization; the tests supply token tuples directly.
- Other date formats, aspect forms, relative-time expressions, quantity expressions, or corpus behavior.

## Acceptance run

Ran the required acceptance command with the unit environment (`VERA_CORPUS_ROOT=/tmp/vera-empty-materials`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=.`): **9 passed, 1 xfailed in 0.08s**. The xfail is the T1 reproducer.
