# Semantic reader attack: negation and modality

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| N1 | ungrounded | `箱は大きくない。` | Preserve negative-adjective meaning in a typed property or leave the clause unread; do not emit a supported positive identity literal. | Emits a copula `identity` clause with polarity `+`, literal value `大きくない`, and no unsupported marker. Reproduced twice in the xfailed test. |
| N2 | ungrounded | `ユンは箱を開けないわけではない。` | Do not emit a negative candidate for double negation; if unresolved, keep it unread. | Emits an `開ける` candidate with polarity `-` and unsupported markers (`unrepresented source content`, `ambiguous frame role`). Reproduced by two reads in the xfailed test. |
| N3 | ungrounded | `ユンは箱を開けたそうだ。` | Hearsay must not be labelled as an asserted fact; preserve the modality or leave the clause unread. | Emits an `開ける` candidate with modality `assert` and unsupported markers (`unrepresented source content`, `ambiguous frame role`). Reproduced by two reads in the xfailed test. |

## What held

- The affirmative `ユンは箱を開けた。` reads as `+ / assert` without unsupported content; `ユンは箱を開けなかった。` reads as `- / assert` without unsupported content.
- Explicit copular negation (`箱は安全ではない。`) retains negative polarity.
- A document question ending in `か` is unread rather than an asserted fact. In a request, affirmative and negative yes/no forms both keep pattern polarity `*`; the negative form is separately marked with relation `whether-negative`.
- The tested prohibition and permission forms are labelled `prohibition` and `permission`, respectively. `らしい` is labelled `hedge`.

## Not covered

This attack did not cover other negative adjective inflections, other hearsay forms, nested quoted speech, longer clause chains, or the behavior of downstream consumers when a clause carries `unsupported` markers. Findings concern only the reader output; no consumer integration was exercised.

## Test run

Acceptance command: `/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_reader_negation_modality.py`

The command was run from the worktree root with the unit's configured corpus and Python environment. Result: 9 passed, 3 xfailed in 0.16s.
