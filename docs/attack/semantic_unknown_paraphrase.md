# Semantic unknown paraphrase attack

Attacker scope: surface variants and changed lexical material in small,
hand-built Views. Every unknown result was checked as a typed constructed
candidate; no candidate was treated as an answer or as evidence.

## Findings

No defect was reproduced in the cases below. The table records the observed
robustness checks and the expected behavior from the module's contract.

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| P-01 | robustness | Query `houseboat` over `house and boat` vs `boat and house` | Keep the same candidate kind, units, and families | Both produced the same `KIN_NEIGHBOURHOOD` route and family data |
| P-02 | robustness | Query `houseboat` with plain vs `please`-marked source wording | Keep the same route | Same `KIN_NEIGHBOURHOOD` route |
| P-03 | robustness | Query `houseboat` over `house and boat` vs plural `houses and boats` | Keep the same route where the semantic role terms stay `house` and `boat` | Same `KIN_NEIGHBOURHOOD` route |
| P-04 | robustness | Query `猫好き` over `太郎が猫をなでる。` vs `猫を太郎はなでます。` | Keep the same report verdict across particle/order/politeness changes | Same `CANDIDATES` / `NO_REACH` verdict |
| M-01 | robustness | Replace query `houseboat` with `housecar` in a View containing `house` and `boat` | Route should reflect available units/neighbours for the changed compound | `houseboat` yielded `KIN_NEIGHBOURHOOD`; `housecar` yielded `NO_REACH` |
| M-02 | robustness | Replace the `boat` role with `car`, keeping query `houseboat` | The unrelated entity should not retain the boat neighbourhood | `house and boat` yielded `KIN_NEIGHBOURHOOD`; `house and car` yielded `NO_REACH` |

## What held

- A role term and the clause predicate were reported as `KNOWN_TERM`.
- Zero, negative, non-integer, boolean, and insufficient budgets returned
  `BUDGET_REFUSAL`.
- A non-string query raised the documented `TypeError`.
- Unknown reports used only the documented candidate kinds, with
  `constructed=True` and `evidence=False`.
- Candidate provenance spans validated against and matched their source text.
- Tested word order, politeness, number, and Japanese particle/politeness
  variants preserved the route. Changed compounds and entity substitutions
  changed the route when the corresponding positional material disappeared.

## Not covered

This attacker used a small set of manually constructed English and Japanese
Views. It did not cover broad language or morphology coverage, malformed View
objects, concurrent calls, corpus-backed inputs, or long-running stress cases.
