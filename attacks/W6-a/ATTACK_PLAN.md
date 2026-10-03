# W6-a attack plan (frozen before attack tests)

Registered: 2026-10-03 18:47 +0900

Scope: `docs/BASIS_POLICY.md` §§2–6 and 11; `classify_sources`, `apply_to_ask`, `AskPolicy.from_args`, and the `vera ask` route. Synthetic result dicts only; no live model, network, hidden bank, or product edits.

## Frozen expectations

1. For a factual `ask`, a source read from a synthetic `local` P4 index but whose `origin` is omitted or SQL `NULL` must not produce an ANSWER: its provenance is unknown, so the result must abstain or ask for confirmation. Test result uses `kind: answer`, `verdict: ANSWER`, and the indexed citation text `窓が光った。`; query `窓は？`. Exercise all three `apply_to_ask` modes and all four human/reference flag combinations, checking the universal generated-only safety promise against the classifier's missing-origin boundary.
2. The same query with `origin: ""` or `origin: "GENERATED"` must remain non-answering; these are controls for the missing/None cases.
3. `AskPolicy.from_args` with `request_kind: "FACTUAL"` must return a typed error; it must not normalize to a valid table row or allow an answer.
4. A confirmation id computed for one sovereign must not authorize appending a human-confirmed record to a different sovereign. This is a probe of whether the confirmation is bound to its displayed destination; if the documented contract does not require destination binding, classify it as an uncounted robustness result.
5. C borrowing must not emit a borrowed form when a candidate changes polarity or introduces a new numeric/content item absent from the human source. Frozen source is `花子は太郎に資料を渡した。`; generated rows are `次郎が花子に資料を渡さなかった。` and `次郎が花子に資料を5冊渡した。`. These are negative probes against the preregistered center/content gates; a conservative refusal is a miss for the attack.
6. A changed/fabricated confirmation id and an otherwise valid id replayed for a different query must return `UNKNOWN_CONFIRM_ID` and append nothing. This checks the explicit id-mismatch behavior separately from destination replay.

No implementation code will be changed. The report will count only observed violations as hits; successful controls are misses.
