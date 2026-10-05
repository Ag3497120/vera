# Semantic reader: long and multi-document attack

The acceptance run on this attack file reported **10 passed in 0.17s**. No defect was reproduced, so there are no xfail cases. The table records exercised robustness surfaces whose observed behavior matched the reader's typed, source-bound contract. `robustness` here classifies the surface checked; it does not report a defect.

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| L1 | robustness | One document contains `東京の人口は100人です。` twice. | Keep both occurrences as clauses with distinct spans and IDs. | Both clauses remained, with ordered spans and distinct IDs. |
| L2 | robustness | Repeat the same sentence twice, then use `101人` for the third value. | Preserve each clause's own typed quantity and shared entity. | Three clauses retained quantities 100, 100, and 101 人 for 東京. |
| L3 | robustness | Two documents state the population is 100 人, one affirmative and one negative. | Keep the claims separately source-bound with opposite polarity. | Both claims remained, with their original source keys and `+` / `-` polarity. |
| L4 | robustness | 48 source keys each contain the same population sentence. | Preserve every document boundary and repeated entity without merging clauses. | Returned 48 clauses, each with its own source key and ID. |
| L5 | robustness | Two duplicate documents receive different `sovereigns` metadata. | Keep each sovereign label attached to its own clause. | The two clauses retained `claimant` and `witness`, respectively. |
| L6 | robustness | A document contains `東京の人口は何人ですか？`. | A source question must not become an asserted fact. | Returned no clauses and retained the question as unread source text. |
| L7 | robustness | A `引用：` scope prefixes 350 comma-separated repetitions of the population sentence. | Leave the uninterpreted scoped sentence whole and unread. | Returned no clauses and one unread span covering the full input. |
| L8 | robustness | Ask about a nominal path containing 80 `人口` segments. | An over-budget request should return typed unread, not a partial plan or uncaught error. | Returned no plans and one unread span covering the question. |
| L9 | robustness | Ask `東京の人口は何人ですか`. | Represent the requested result as a typed quantity variable with unit 人, not as a document-derived value. | The Project output had quantity sort and unit 人. |
| L10 | robustness | One document repeats the population sentence 80 times. | Preserve each sentence boundary and source order. | Returned 80 clauses with the expected sentence text and increasing start offsets. |

## What held

- Exact duplicates and near-duplicates stayed as separate clauses with source spans; nearby values were not substituted across occurrences.
- Contradictory documents retained their own provenance and polarity rather than being pooled into one claim.
- Repeated entities across many sources kept distinct source identities. Per-document sovereign metadata also stayed attached.
- A question in a document remained unread, and a long colon-scoped sentence was not partially asserted.
- The request reader represented an answer slot as a typed variable and returned a typed unread request for the over-budget nominal path.

## Not covered

- This unit exercises `semantic_reader` only. It does not test downstream routing, verification, answer selection, or whether another component abstains when documents conflict.
- Inputs were constructed Japanese strings. No external corpus, sealed/heldout material, production-scale document set, concurrency, or resource-exhaustion campaign was used.
- The tested sizes were 48 documents, 80 repeated sentences, 350 comma-separated repetitions in one scoped sentence, and an 80-segment question path. Larger limits and other Japanese constructions remain untested.
