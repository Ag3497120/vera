# Semantic coordinator attack: lead-text stress

## Scope and sample

The target was `verantyx.semantic_coord`, using its declared token tuple contract and clause/span rules. I invoked `load(60, 1)` from `tools/round5a_route_tune.py`; it raised `FileNotFoundError` for the loader's configured `jawiki_leads.full.jsonl` path (`/Users/motonisihikoudai/Projects/vera-corpus/build/round4/jawiki_leads.full.jsonl`). No Wikipedia lead paragraph was available to this worktree, so the real-text sample size was zero and real-text rates cannot be estimated. I did not substitute dev, heldout, or other corpus data.

The unit tests use short manually tagged Japanese clause fragments to exercise the module contract. Their outcomes are not presented as Wikipedia measurements.

The acceptance run completed in 0.09 seconds: 8 passed and 3 xfailed. All probes returned within the test run; no crash or hang occurred in these small synthetic cases.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| SC-1 | ungrounded | `連用形 + て + 、 + 接続詞(しかし) + predicate` | `coordination_ok` returns false because an intervening connective is outside the licensed chain. | Returns true: the connective is after `_tail_end`, outside the inspected range. This can license unsupported interclause sharing. |
| SC-2 | ungrounded | `日本(名詞) + の(助詞) + 首都(名詞) + は(係助詞)` | `topic_phrase` spans `日本の首都` (`0:5`). | Returns only `首都` (`3:5`), omitting the genitive modifier from the borrowed topic span. |
| SC-3 | ungrounded | A single token `日本` with requested span `0:1` | `phrase_bounded` returns false because the span cuts through a token. | Returns true: neither boundary coincides with a token edge, so both adjacency checks are skipped. |

Each defect has a minimal regression probe marked `xfail(strict=False)` so it remains visible without making the acceptance suite fail.

## What held

- A 連用 predicate followed by `て、` and another predicate was accepted.
- A 連用 predicate followed by `、` and another predicate was accepted.
- A single predicate, a non-連用 first predicate, and a causal `ので` separator were rejected.
- The later clause chunk began after the optional `て、` tail, and a local `が` phrase was detected as that clause's own subject phrase.
- A simple `は` topic span was returned, a clause without a `は` topic returned `None`, and phrase boundaries adjacent to a particle/predicate were accepted.
- Phrase boundaries next to stray noun tokens were rejected.

## What I did not cover

The configured Wikipedia leads file was unavailable, so this run provides no crash, hang, or wrong-output rate on real leads. The probes do not exercise a morphological analyzer, end-to-end semantic coordination, downstream subject borrowing, or answer generation. I also did not test performance on long paragraphs; all unit probes are small and bounded.
