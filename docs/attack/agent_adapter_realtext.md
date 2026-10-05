# Agent adapter text stress

## Scope and result

This attack probes the agent protocol parser, command builder, chunk handling, timeout path, and frame-compiled brief. The acceptance run was:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_agent_adapter_realtext.py
12 passed in 0.14s
```

I also tried the designated loader with `load(40, 1)`. It failed before loading any documents because its configured `build/round4/jawiki_leads.full.jsonl` file is absent in this environment. The actual Wikipedia train-lead sample size was therefore **0**, and no corpus crash, hang, wrong-answer, or ungrounded-output rates can be estimated.

The deterministic fallback probes use **8 hand-authored lead-like prose strings**, not Wikipedia or corpus text. All 8 parsed as `OTHER`; 0 parsed as `ERROR` or `ANSWER`. The full test run took 0.14 seconds. This does not measure real-agent latency or hang rates.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| AAR-1 | robustness | `test_lead_like_prose_is_preserved_as_other_not_answer` | Plain non-JSON prose is returned as `OTHER`, not promoted to an answer. | 8/8 hand-authored paragraphs were preserved as `OTHER`; 0/8 were `ERROR` or `ANSWER`. |
| AAR-2 | robustness | `test_answer_alias_extra_fields_and_duplicate_keys_are_rejected` | Unsupported `ANSWER` events, extra fields, and duplicate JSON keys must not enter the typed event protocol. | All 3 inputs returned `ERROR`. |
| AAR-3 | robustness | `test_parser_limits_return_bounded_events_and_an_overflow_marker` | Parser limits stop processing and expose overflow through an error event. | With `max_events=3`, the result held 3 text events and one overflow error; total-output truncation also returned an error marker. |
| AAR-4 | robustness | `test_frame_brief_keeps_prose_as_context_and_sanitizes_secrets_and_paths` | Brief content stays framed as context, sensitive values are redacted, and project-relative paths remain project-relative. | Prose remained in the JSON record; the API-key value and outside path were redacted; `docs/lead.txt` remained relative. |
| AAR-5 | robustness | `test_codex_adapter_reassembles_a_structured_event_across_chunks`; `test_codex_adapter_timeout_closes_and_stops_runner_once` | Partial lines are buffered until complete, and timeout closes the handle and stops its runner once. | Split JSON became one `QUESTION`; the injected-clock timeout emitted the documented error and called `stop` once. |

No adapter defect was reproduced, so there are no `xfail` tests. In particular, no severity-1 wrong answer or fabrication was observed. The parser probe also confirms that the literal `ANSWER` event type is outside its accepted event vocabulary; this does not establish that a downstream live agent cannot produce an incorrect claim.

## What held

- Non-JSON text stayed typed as `OTHER`; embedded JSON-looking text inside a prose line was not parsed as an event.
- A valid closed `QUESTION` event was normalized, while the `ANSWER` alias and malformed structured events were rejected.
- Byte decoding, control-character rejection, duplicate keys, invalid JSON constants, and configured parser limits completed without a crash in these cases.
- The brief preserved ordinary prose as record data and redacted the tested secret and outside path.
- The command builder selected the configured project directory and sandbox while retaining its fixed `gpt-6-luna` model.
- Chunk reassembly and timeout cleanup worked with an in-memory runner.

## Not covered

- No real Wikipedia paragraphs were available from the loader, so the requested `split == train` real-text stress and its rates remain unmeasured.
- The injected runner did not start Codex or any external process. Process hangs, real command execution, and live model output were not tested.
- No end-to-end conductor judgment was exercised. These tests do not establish whether a downstream agent claim is grounded or whether an actual model could produce a wrong answer.
