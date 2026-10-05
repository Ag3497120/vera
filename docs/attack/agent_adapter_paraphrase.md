# Agent adapter paraphrase attack

Scope: protocol parsing, event routing, Codex command construction, and frame brief compilation in `verantyx/agent_adapter.py`. The adapter transports typed events; it does not assign semantic verdicts.

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| P-01 | robustness | Compile an active record with `slots.summary = "See C:/private/notes.txt"`. | The absolute path is redacted as `[PATH_REDACTED]`, consistent with the brief sanitizer's path handling. | The brief retains `See C:/private/notes.txt`. The sanitizer recognizes `C:\\...` paths but misses this forward-slash surface variant. The regression test is marked xfail. |

No wrong `ANSWER` or fabricated answer was observed in the covered cases. P-01 is a brief sanitization defect, not an answer verdict.

## What held

- In a single newline-delimited JSON record, whitespace and key order changes preserve the normalized `QUESTION` event.
- Polite and plain text carried as structured `QUESTION` events retain the same event type and conductor question ID. Plain prose variants remain `OTHER` and route as `adapter-other`.
- Changed entity and count values remain distinct in `CLAIM` content; changing the event type from `QUESTION` to `CLAIM` changes routing eligibility.
- Surrounding whitespace is trimmed, duplicate JSON keys produce `ERROR`, and UTF-8 bytes parse like the equivalent text.
- Frame brief compilation redacts a sensitive-key value and excludes fields outside the active record shape.
- The Codex command keeps a Unicode brief intact as one argument after `--`.

Required acceptance run: **10 passed, 1 xfailed** in 0.15 seconds.

## Not covered

- Semantic truth checking or whether two natural-language paraphrases receive the same verdict; this module does not produce verdicts.
- Live Codex execution, external process behavior, timeout/hang behavior, or interaction with a real runner.
- Other path encodings, all secret formats, parser size-limit boundaries, and broad generated paraphrase sets.
- External corpora or held-out data.
