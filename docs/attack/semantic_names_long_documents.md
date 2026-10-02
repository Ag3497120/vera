# Semantic names: long and multi-document attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| H1 | robustness | A sentence with a long prefix, `主任` + `研究員` + `ユン`, and a suffix; request only the name span. | Return only the tokens tiling the requested span, then split the kanji title from the final proper-name token. | Held: the selected tokens and split matched the sentence-local span. |
| H2 | robustness | Request a span over a gap, overlapping tokens, or a token that crosses a requested boundary. | Return no covering token sequence unless contained tokens tile the full span contiguously. | Held: each malformed span returned `None`. |
| H3 | robustness | Try `コカ` + proper-noun `カル`; try a non-kanji descriptor; try a non-proper final token or mismatched value. | Reject these as name splits under the module's descriptor and final-token rules. | Held: each candidate returned `None`. |
| H4 | robustness | Repeat `ユン` in many independent long sentence contexts, alternating `技師` and `研究員` as the title. | Split each sentence from its own token sequence; preserve its local title and name. | Held: all generated contexts produced their own expected split. |
| H5 | robustness | Check an auxiliary with lemma `た`, one with lemma `だ`, and a non-auxiliary with lemma `た`. | Treat only auxiliary lemma `た` as past, including the voiced surface form case described in the module contract. | Held: the result followed POS and lemma. |

No defect was reproduced, so the attack suite contains no xfailed cases. The acceptance run collected 13 cases: 13 passed in 0.07 seconds.

## What held

- Token covering selected the exact requested span from a long sentence and rejected gaps, overlaps, and partial boundary tokens.
- Name splitting accepted multiple kanji title tokens before a proper-name token and rejected the tested fragment, descriptor, final-token, and value mismatches.
- Repeated names with alternating titles stayed local to each independently supplied sentence token list.
- Past auxiliary detection followed the module's documented POS-and-lemma rule.

## What was not covered

- This module receives one sentence's tagged tokens at a time. These checks do not exercise corpus loading, document routing, answer generation, or contradiction handling in downstream modules.
- The generated contexts are synthetic; no external or project corpus was used.
- Malformed tagger objects, runtime failures in callers, and performance beyond the exercised sentence sizes were not assessed.
