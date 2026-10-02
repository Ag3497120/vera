# Attack: semantic names, negation, and modality

Scope: `verantyx.semantic_names` exposes token-span coverage, a structural title-plus-name split, and a check for the past auxiliary whose lemma is `た`. The checks below probe whether common negative, modal, and question tokens are mistaken for that auxiliary or for a name. They do not treat these morphology helpers as a clause-level semantic parser.

## Findings

No defect was reproduced, so no xfail was added.

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| N1 | robustness | `is_past_aux(word("ない", "助動詞", "ない"))` | `False`: the helper accepts only an auxiliary with lemma `た`. | `False` |
| N2 | robustness | `is_past_aux(word("べき", "助動詞", "べき"))` and the tested negative, adjective, permission, prohibition, and question tokens | `False`: none has the required past-auxiliary lemma and POS. | All tested tokens returned `False`. |
| N3 | robustness | `tokens_covering(tagged, 2, 4)` for the exact `ない` token in `行かないか` | Return the token exactly covering `[2, 4)`. | Returned that token; a span with a gap returned `None`. |
| N4 | robustness | `name_split_in(tagged, "研究員花子は来ない")` | `None`: the full negative clause is not a title-plus-proper-name token cover. | `None`; the exact `研究員花子` subspan returned `("研究員", "花子")`. |
| N5 | robustness | `name_split_in(tagged, "研究員花子は来るか")` | `None`: the full question clause is not a title-plus-proper-name token cover. | `None`. |

The expected results follow the module's documented contracts: token spans must tile exactly; the last name token must be proper; and the past-auxiliary check requires POS `助動詞` and lemma `た`. The acceptance run reported **16 passed**.

## What held

- `た` with auxiliary POS and lemma `た` was recognized, including voiced surface `だ` with that lemma.
- The past check used the lemma rather than the surface form. Tested `ない` auxiliary/adjective forms, `ぬ`, `べき`, `よい`, prohibitive `な`, and question particle `か` returned `False`.
- Exact coverage of a negative token succeeded, while a gapped span did not.
- The name helper split the exact title-plus-name span and did not split complete negative or question clauses.

These are morphology and span results only. `False` from `is_past_aux` is not a polarity judgment; `None` from `name_split_in` is not a semantic Unknown value. The module does not expose clause polarity, modality, or speech-act judgments.

## What I did not cover

- Actual tokenizer output: test tokens were constructed directly to isolate the helper contracts.
- Composition of single or double negation, including whether a clause means No or remains Unknown.
- Permission, obligation, prohibition, or hearsay as proposition-level modality.
- Whether a question, assertion, or past negative clause is true, false, or unknown.
- Any semantic IR or routing behavior outside `semantic_names.py`.
