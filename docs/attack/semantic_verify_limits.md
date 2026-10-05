# Semantic verifier limits and determinism

Independent attacker review of `verantyx/semantic_verify.py`. The checks use
typed requests from `read_request` and views built from local synthetic text.
Expected outcomes come from the request IR, source clauses, and the verifier's
typed `Limit` / `Rejected` refusal contract.

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| SVL-A | robustness | Audit the `何が走った？` request against `View({}, ())`. | No source clause can bind the request, so the answer set is empty. | Empty answer set. |
| SVL-B | robustness | Call `gate` with `Budget(steps=0)` and an empty view. | Stop with typed `Limit` when the step budget is spent. | Typed `Limit`; no crash. |
| SVL-C | robustness | Audit two matching clauses with `Budget(candidates=1)`. | Stop with typed `Limit` after the candidate bound is exceeded. | Typed `Limit`; no crash. |
| SVL-D | robustness | Audit 257 matching clauses with the default candidate budget of 256. | Stop with typed `Limit` rather than continuing through an over-budget candidate pool. | Typed `Limit`; no hang. |
| SVL-E | robustness | Audit a matching clause in a source with 20,000 leading spaces and `Budget(steps=1,000)`. | Stop with typed `Limit` when source scanning exhausts the budget. | Typed `Limit`; no crash or hang. |
| SVL-F | robustness | Audit the same single-clause view twice with one checker. | The answer set remains the IR-derived `{(('agent', '太郎'),)}` on both calls. | Same singleton answer set on both calls; meter steps increased. |
| SVL-G | robustness | Reverse insertion order for two source documents containing `太郎が走った。` and `猫が走った。`. | Answer set remains the two source-supported agent bindings, independent of source order. | Both orders produced the same two-answer set. |
| SVL-H | robustness | Run two independent checkers concurrently over the same one-clause view. | Both audits return the same source-supported answer set. | Both returned `{(('agent', '太郎'),)}`. |
| SVL-I | robustness | Call `gate` with `Budget(depth=0)` and the multi-node request plan. | Stop with typed `Limit` when the plan exceeds the depth budget. | Typed `Limit`; no crash. |
| SVL-J | robustness | Replay an empty proof whose root names no proof node. | Refuse the malformed proof with typed `Rejected`. | Typed `Rejected`; no uncaught error. |

## What held

The acceptance command completed with **10 passed in 0.17s**. No xfails or
defects were observed. Repeated audits, reversed source ordering, and two
concurrent independent checkers agreed on their IR-derived answer sets. The
tested budget overruns produced typed refusals.

## What I did not cover

- Valid nonempty proof proposals through `gate`; these checks audited outputs
  directly and exercised only a malformed proof root.
- Opposing evidence, applicable conditions and exceptions, or conflict paths.
- Memory use over long-running repeated calls; this unit did not measure RSS or
  heap growth.
- Concurrent construction or mutation of views, or simultaneous use of one
  shared `Checker` instance.
- Every source grammar and malformed span shape handled by clause licensing.
