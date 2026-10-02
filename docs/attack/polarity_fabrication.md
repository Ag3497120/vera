# Polarity fabrication and provenance attack

Scope: `verantyx/polarity.py` observed and inferred negation, source spans,
predicate keys, and the explicit negation detector. The two provenance findings
below are marked xfail in the attack tests so they remain visible without
making the acceptance suite fail.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| P-OVERRIDE | ungrounded | `o = observe_negation("水が流れない。").observed[0]; polarity_key(o, "死ぬ")` | Reject a lemma override that does not match the observed dictionary form, or keep the source-backed `¬流れる` key. | Returned `¬死ぬ` on both reproductions, although the source says that water does not flow. |
| P-CONSTRUCTED | ungrounded | `polarity_key(ObservedNegation("ending", "ない", "死ぬ", (0, 2)))` | A record without a source-bound observation must not become testimony or a storable key. | Returned `¬死ぬ` on both reproductions; the record was caller-created and had no source text. |

Both findings were reproduced twice before being reported. The tests assert the
expected provenance guard and are marked `xfail(strict=False)` because the
current implementation accepts these records.

## What held

- An observed `ない` maps to the expected dictionary form and its span selects
  exactly the written source substring.
- The lexicalized adjective `つまらない` and the unrecognized stem in
  `大人げない` produce no observed negation.
- An embedded negation remains in the observation list while the sentence
  verdict stays positive; the unfoldable modality pattern abstains.
- Both written halves of `行かなくない` retain their own spans and fold to an
  even, positive verdict.
- `問題はない` retains `問題` as context and uses `ある` as the negated lemma;
  copula negation spans the written `ではない`.
- Absence-inferred negation is refused by `polarity_key`, and `fold_polarity`
  marks the observed lemma while leaving a different predicate unchanged.
- Explicit Japanese and English negators retain the polarity of their aspect.

## Not covered

This run did not cover the supplied token stream path, lattice-backed prefix
negation, multi-record ingestion and supersession in `CrossStore`, or the
answer-gating integration. It did not use corpus material or test other
modules.

## Acceptance run

Command:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_polarity_fabrication.py
```

Result: 12 passed, 2 xfailed.
