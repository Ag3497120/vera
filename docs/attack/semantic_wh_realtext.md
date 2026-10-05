# `semantic_wh` real-text stress review

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| R1 | robustness | `富士山は日本の静岡県と山梨県にまたがる活火山である。` | Descriptive prose yields no role-list plan or builder side effects. | Returned `None` with no bind or output; no defect reproduced. |

## What held

- Particle-form questions preserve the requested surface labels and map `が`/`は` to `agent`, `を` to `patient`, `に`/`へ` to `recipient`, `で` to `location`, and `から` to `origin` in the wildcard `Pattern('*', ...)`.
- Role-noun lists preserve their labels and map to the role names represented by the module. A plan is omitted when fewer than two distinct semantic roles are requested.
- The recording builder saw one wildcard pattern and one projected output per requested role in the contract probes. Descriptive prose did not create a plan. These probes exercise plan construction only; they do not establish downstream answer behavior.
- Acceptance run: 12 passed, 0 failed, 0 xfailed.

## Real-text sample and rates

The specified loader was called as `load(100, 300)`, which selects every 300th eligible row with `split == 'train'` and a lead length of at least 40 characters. The loader raised `FileNotFoundError` before returning any rows because its configured Wikipedia lead file was absent. Therefore the sample size and module-call count were both 0, and crash, hang, plan, wrong-answer, and ungrounded-output rates on real leads are **N/A**, not zero. No real-text rate is inferred from the deterministic probes.

## Not covered

- Running `read_role_list_question` over real Wikipedia train leads, including empirical crash, latency, acceptance, wrong-answer, or ungrounded-output rates.
- End-to-end answer generation, evidence grounding, or semantic-reader integration. This module constructs a question plan and does not itself produce an `ANSWER`.
- Corpus splits other than `train`, any corpus beyond the designated loader, and any questions outside the role-only shapes.
