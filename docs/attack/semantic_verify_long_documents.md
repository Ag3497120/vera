# Long and multi-document semantic verifier attack

No verifier defect was reproduced. The table records the failure classes exercised and their observed outcomes; the severity column names the failure that each case was designed to catch.

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| LD1 | wrong-ANSWER | Repeat the same identity sentence in 12 source documents. | Duplicate evidence yields one distinct projected answer. | One answer; held. |
| LD2 | ungrounded | Repeat the same sentence 40 times in one source. | Every repeated source offset remains licensed. | One answer; held. |
| LD3 | wrong-ANSWER | Query 48 near-duplicate subjects in one source. | Each distinct subject remains distinguishable. | All expected subjects returned; held. |
| LD4 | ungrounded | Put the same positive and negative identity pair in separate documents. | Applicable opposite evidence raises `Conflict`. | `Conflict`; held. |
| LD5 | wrong-ANSWER | Put a positive identity for one entity and a negative identity for another in separate documents. | The unrelated negative must not suppress the positive answer. | Only the positive entity was returned; held. |
| LD6 | ungrounded | Use a sentence whose subject and value are each 1,200 characters long. | Both role spans are licensed exactly against the source. | The exact projected roles were returned; held. |
| LD7 | crash | End a two-sentence source with an unpunctuated final sentence. | The end-of-source sentence remains inside its original source range. | Both answers returned; held. |
| LD8 | wrong-ANSWER | Repeat one subject with two distinct values in one source. | Projection preserves both subject/value pairs. | Both pairs returned; held. |
| LD9 | wrong-ANSWER | Reverse the order of three independent source documents. | Document order does not change the answer set. | Same answer set; held. |
| LD10 | robustness | Query 257 candidate documents with the default candidate budget. | Reject cleanly at the candidate limit. | `Limit("candidates")`; held. |

## What held

The 10 attack tests passed in 0.10 seconds with the required acceptance command. Repeated clauses across or within documents did not multiply an identical answer. Near-duplicate subjects and repeated subjects with distinct values remained distinguishable. Candidate ordering did not change the answer set. Contradictions were scoped to matching entities, long role spans were licensed against their source text, and the final unpunctuated sentence was included.

## What was not covered

The tests hand-build typed `View` and `Clause` values with explicit source spans, then exercise `Checker.audit`. They do not cover reader-produced views, proof-node replay through `Checker.proof` or `Checker.gate`, conditions and exceptions, event-frame or measure clauses, or integration with routing and answer rendering.
