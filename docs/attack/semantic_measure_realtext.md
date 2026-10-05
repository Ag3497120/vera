# Semantic measure real-text attack

## Findings

No wrong-answer, ungrounded-output, crash, or hang defect was established by these limited parser and plan probes. They do not evaluate final answers. The table records robustness properties that held; it does not claim a real-text pass.

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| SM-01 | robustness | `棒Aは1.20m。` | Preserve the exact decimal quantity and read the IR length unit as `measure.length`. | One clause with `Decimal("1.20")`, unit `m`, predicate `measure.length`, and source spans covering the quantity and particle. |
| SM-02 | robustness | `容器Aは1L、容器Bは2Lの水です` | Return both segments and attach the shared head noun to each. | Two volume clauses; both carry substance `水`. |
| SM-03 | robustness | `合計は何mですか` | Build two length bindings followed by a distinct-entity filter and a sum in `m`. | The plan recorder observed `Join`, `Filter`, and `Sum`, with two quantity terms and output unit `m`. |
| SM-04 | robustness | `重い箱は？` | Compare mass measures with the `>` relation and constrain both bindings to kind `箱`. | Both bindings use `measure.mass` and kind `箱`; the compare relation is `>`. |
| SM-05 | robustness | `棒Aは1mで、たぶん長い` | Decline the sentence because the measure parser must consume the whole input. | Returned `None`. |

No defect reproducer or `xfail` was needed for these probes.

## What held

The acceptance command completed with **11 passed** in **0.08 seconds**. The probes confirmed exact decimal parsing, multi-segment parsing, shared-noun propagation, unit dimensions from the IR, whole-input rejection, and the closed sum, compare, and same/different request shapes. Unsupported signed and scientific-notation values were declined. Unrecognized questions returned `None` without mutating the plan recorder.

The request tests use a small builder recorder to inspect the generated operators. They do not execute the plans against a measure store or verify final computed answers.

## Real-text sampling and limits

I attempted the specified train-only loader call `tools.round5a_route_tune.load(8, 1)`. It raised `FileNotFoundError` for its configured Wikipedia leads corpus, so it yielded no paragraphs. The number of real lead paragraphs processed is **0**; real-text wrong-answer, ungrounded-output, crash, and hang rates are **not available**. The contract probes above are not substitutes for those rates.

I could not cover actual Wikipedia lead text, measure-store execution, result grounding through the full semantic path, or broad fuzz and long-running-input behavior. The module itself was left unchanged.
