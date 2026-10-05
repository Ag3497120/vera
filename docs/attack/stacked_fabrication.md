# Stacked fabrication attack

Scope: provenance and fabrication paths in `verantyx/stacked.py`. The acceptance run used the unit's empty-materials environment and the required pytest command.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| SF-01 | ungrounded | `yes_no_en` on `Can Alpha swim?` with only `alpha -> water` is a held-gap case; the attack suite also checks `Does Alpha use art?` twice against `house` and `cart`. | A condition absent as a complete term should remain `NOT_ATTESTED`, with empty text. | `yes_no_en` matches substrings in both directions. The repeated `Does Alpha use art?` case is marked xfail because `use` occurs inside `house` and `art` inside `cart`, and the function returns `ATTESTED`. |
| SF-02 | ungrounded | `in_words` with arbitrary path `CENTER LEFT RIGHT` and only `edge_pairs=[("LEFT", "RIGHT")]`, exercised twice. | Keep the path visible but do not send facets to composition unless an edge licenses their relation to the speaking center. | The filter treats every endpoint of any edge pair as licensed, then passes `CENTER` with both `LEFT` and `RIGHT` to the composer. The test is xfail; its composer stub confirms the ungrounded content handoff twice. |

Both findings are severity-1 provenance defects under the unit rule for fabricated output. Expected behavior is derived from the function contracts: an attestation requires condition support in the subject's record, and arbitrary-order speech requires a corpus-written relation for the sentence being formed.

## What held

The passing checks confirm that a held question subject can replace a mismatched seed, absent subjects are refused by name, a subject found on the seed's own cross is accepted, and yes/no gaps remain empty rather than becoming denials. Comparisons require both records and report their shared and side-specific facets from those records. Aspect reads select from the answered core's own cross. An arbitrary path with no edge stays unspoken, an edge containing the center licenses only its connected facet, and quote composition does not run for an ordinary `ANSWER` verdict.

## What I did not cover

I did not inspect or test the upstream candidate generator, puzzle solver, stage splitter, corpus freshness or supersession rules, surface-center lookup, Japanese content-run extraction, or the real sentence composer and writer. The edge tests isolate the data handed from `in_words` into composition; they do not validate template grammar. All fixtures are synthetic and do not establish behavior on a real corpus.

## Acceptance run

`/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_stacked_fabrication.py`

Result: **14 passed, 2 xfailed** (16 tests total); the command exited successfully. The xfails are the two severity-1 provenance reproducers.
