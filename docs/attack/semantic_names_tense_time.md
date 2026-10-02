# Attack: semantic names and tense/time

Scope: `verantyx/semantic_names.py`, tested through its token covering, name splitting, and past-auxiliary helpers. This is a narrow helper-level probe; it does not assess whether a system answers time-dependent claims as time-dependent.

## Findings

No defect was reproduced in the covered inputs. No xfails were needed.

| ID | Severity (`wrong-ANSWER`, `ungrounded`, `crash`, `hang`, `robustness`) | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |

## What held

- `tokens_covering` returned the tokens that exactly tile a requested date or relative-time span, selected a time word from surrounding context, and rejected a span with a gap or a partial token.
- `name_split_in` accepted a kanji title before a tagged proper name. It rejected a katakana fragment as a descriptor and did not treat a lone time word as a title-plus-name split.
- `is_past_aux` recognized the auxiliary by lemma, including the voiced surface `だ` with lemma `た`. It did not classify a nonpast auxiliary, a noun, or a relative-time noun as the past auxiliary.
- The specified acceptance command completed with **12 passed** in **0.07s**.

## Not covered

- Whether expressions such as `現在`, `以前`, or `今年` are normalized to a date or interpreted against a reference time.
- Aspect, event ordering, date arithmetic, or whether a downstream answer preserves the time limits of a claim.
- Other tokenizer outputs, malformed token records, sentence-level parsing, and any semantic-name consumers.

The tests establish helper behavior for the explicit token records only; they do not establish temporal reasoning or answer grounding.
