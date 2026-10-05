# Agent adapter injection review

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| AAI-01 | robustness | Compile a frame brief with a record value containing `safe\u202eIgnore prior rules...`. | Untrusted text should not retain a bidi override that can visually reorder the brief. | The U+202E character is present in the compiled brief. Reproduced by an xfailed test. |
| AAI-02 | robustness | Compile a frame brief with a record value containing `safe\u2028Ignore prior rules...`. | A Unicode line separator in untrusted text should not act as a visual prompt boundary. | The U+2028 character is present unescaped in the compiled brief. Reproduced by an xfailed test. |

Neither finding demonstrates that an agent obeyed an injected instruction or produced an answer. The adapter builds a text brief but does not execute the agent model, so these are prompt-boundary robustness defects rather than confirmed answer fabrication.

## What held

- Free prose that claims to be `DONE` remains an `OTHER` event.
- The parser rejects unsupported `ANSWER` events, extra fields on `DONE`, duplicate JSON keys, and a fullwidth Unicode lookalike for `DONE`.
- An injected `CLAIM` remains a `CLAIM`; `to_conductor_question` rejects it instead of upgrading it to a question.
- Quoted JSON inside question text remains within that text field. A frame record containing quotes and a newline remains a JSON data value under the brief's data-only instruction.
- `build_command` keeps the brief as one argument after `--` and retains the adapter's fixed model and sandbox values.

Acceptance command run from the worktree root with the specified environment: **10 passed, 2 xfailed** in **0.15s**.

## Not covered

- No external agent model or real runner was executed, so actual obedience to hostile text, answer fabrication, escalation decisions, and agent-message handling were not observed.
- The review was limited to `verantyx/agent_adapter.py`; downstream conductor classification and escalation policy were not independently reviewed.
- The Unicode reproductions cover bidi override and line separator characters in compiled frame values. Other formatting characters, renderers, encodings, and nested payload shapes were not exhaustively explored.
