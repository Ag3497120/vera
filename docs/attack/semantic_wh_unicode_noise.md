# Semantic WH Unicode and noise attack

Target: `verantyx/semantic_wh.py`, specifically `read_role_list_question`, which accepts role-only wh questions or role-noun lists and returns a wildcard `Bind` plan.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| U-01 | robustness | `誰が何を？` | Read the labels as `誰が` → agent and `何を` → patient in one ordered wildcard plan. | The plan contains the expected roles in order and retains both labels. |
| U-02 | robustness | `起点、終点は？` | Read the role nouns as origin and recipient in one wildcard plan. | The plan contains origin then recipient and retains the source labels. |
| U-03 | robustness | `だれがどこで?` | Read the hiragana wh forms as agent and location. | The plan contains agent then location with the source labels. |
| U-04 | robustness | `誰が何をですか。` | Accept the optional polite ending and supported terminal punctuation. | The expected wildcard plan is returned. |
| U-05 | robustness | `ﾀﾞﾚが何を?` | Refuse half-width katakana that is outside the reader's accepted forms. | Returns `None`; no variables, outputs, or binding are produced. |
| U-06 | robustness | `誰が何を?` (decomposed dakuten) | Refuse a canonically equivalent but unnormalized particle rather than silently changing it. | Returns `None`; no binding or outputs are produced. |
| U-07 | robustness | `誰​が何を?` (zero-width space inserted) | Refuse the altered token. | Returns `None`; no plan is produced. |
| U-08 | robustness | `誰が何ヲ?` | Refuse the katakana lookalike in place of the supported hiragana particle. | Returns `None`; no plan is produced. |
| U-09 | robustness | `<b>誰が何を?</b>` | Refuse markup residue around an otherwise valid question. | Returns `None`; no plan is produced. |
| U-10 | robustness | `誰が何を? :-) `; `誰が何を? 😀`; `誰が何を?0` | Refuse ASCII art, emoji, and OCR-like trailing noise. | Each returns `None` without a partial plan. |
| U-11 | robustness | `物､起点は?` | Refuse a half-width separator rather than treating it as the supported list delimiter. | Returns `None`; no plan is produced. |
| U-12 | robustness | `物、起点ロは?` | Refuse mixed-script residue in a role-noun list. | Returns `None`; no plan is produced. |
| U-13 | robustness | `誰がだれは?` | Refuse duplicate semantic roles even when their labels differ. | Returns `None`; no plan is produced. |

No wrong-answer, ungrounded-plan, crash, or hang defect was reproduced in the covered cases, so there are no xfails. The reader uses full-string matches for these shapes; the tested noise was rejected without a partial wildcard plan.

## What held

- Supported full-width Japanese forms and listed terminal punctuation produced ordered wildcard role plans with their source labels.
- Half-width, decomposed, zero-width, mixed-script, markup, symbol, emoji, and OCR-like residue in the tested examples was refused.
- Invalid cases left the recording builder without bindings or output entries.
- Repeated semantic roles were refused.

## What was not covered

- I did not exercise image-based OCR, arbitrary Unicode confusables, or every Unicode normalization form.
- I tested this reader with a recording builder and captured the wildcard pattern arguments; I did not test downstream routing or the full application path.
- I did not run corpus-based or performance testing.

## Acceptance run

Command: `VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_wh_unicode_noise.py`

Result: **16 passed** in 0.07 seconds.
