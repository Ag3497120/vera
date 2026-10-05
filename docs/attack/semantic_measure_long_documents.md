# Semantic measure: long and multi-document attack

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| — | — | No defect reproduced in this run | Long lists and separate document inputs preserve the flat measure contract; request shapes expand to typed operators | All 12 tests passed; parser and typed request expansion matched the tested expectations |

## What held

- A 300-segment sentence returned all 300 clauses in input order, with exact `Decimal` quantities.
- Identical entity labels with contradictory values in separate source documents stayed as separate clauses. Exact duplicate sentences from two sources also kept distinct clause IDs.
- A shared list-level head noun appeared on each clause. A near-duplicate sentence with unconsumed trailing text was rejected as a whole.
- The request expander produced two length bindings and a typed `Sum` in the requested unit. Longest and kind-qualified heaviness questions produced mass/length `Compare` operators with the expected relations and label choices. Same/different questions selected equality or inequality in the requested dimension.
- A long decimal quantity was preserved exactly, without conversion through binary floating point.

## What I did not cover

This unit expands source sentences and questions into clauses and typed IR; it does not execute the plan. I did not test downstream aggregation, answer rendering, tie abstention, cross-document routing, or evidence selection. The document cases were constructed inputs, not an external corpus.

## Run

`VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_measure_long_documents.py`

Result: **12 passed**.
