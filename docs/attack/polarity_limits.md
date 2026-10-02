# Polarity limits attack

The suite ran with the unit acceptance command: **10 passed, 2 xfailed in 0.11s**. Both xfails are reproduced robustness defects; neither changes `verantyx/polarity.py`.

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| PL-01 | robustness | `once = fold_polarity(["できる"], "できない。", tokens=[]); fold_polarity(once, "できない。", tokens=[])` | Folding an already marked predicate again is idempotent and does not add another copy of the same marked key. | The second fold differs from the first by appending a duplicate `¬できる`. The reproducer is an xfail. |
| PL-02 | robustness | Feed 160 distinct four-kana stems, each followed by `ない。`, to `observe_negation(..., tokens=[])`. | Rejected unique lemma candidates should not be retained without a memory bound. | The global lemma cache grew past the test's 32-entry bound. The reproducer is an xfail. |

## What held

- Empty input returned a positive reading with no observations.
- Written `ではない` produced a typed copula observation with the expected lemma and span; the mixed modality `来ないとは言えない` abstained with no observations.
- `polarity_key` refused both inferred absence and an untyped object.
- Two adjacent written negations folded to positive by parity.
- Repeating the same reading and the same fold on the original predicates returned equal results. A 100,000-character irrelevant input returned no observations.
- A reading containing 512 adjacent copula negations completed with the expected count and even-parity verdict.
- Reversing the two clauses preserved the observed multiset. Two concurrent readers returned the same readings as sequential calls.

## What was not covered

- Tokenizer, lattice-prefix, and Japanese grammar overlay paths were not exercised; the tests pass `tokens=[]` to pin the raw-text reader.
- Concurrent initialization or use of Fugashi was not exercised.
- CrossStore ingest, contradiction lookup, and the answer gate were not exercised.
- Inputs larger than the bounded cases above and long-running cache behavior beyond the unique-lemma probe were not measured.
