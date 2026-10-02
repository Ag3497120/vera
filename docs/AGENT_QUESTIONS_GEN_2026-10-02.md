# Agent question generator — 2026-10-02

## Output

`tools/agent_questions_gen.py --out DIR --n N` writes `train.jsonl`, `dev.jsonl`, and `metadata.json`.
`--n` counts question rows across both splits; it must be at least 55 so each split has a frame.
Every JSONL line uses schema `agent_question_gen_v1` and contains:

- `frame_id`: the independent synthetic frame that supplies the row's typed records.
- `question`, `options`, and `claimed_state`: inputs passed to `conductor.AgentQuestion`.
- `expected_question_kind`: one of `ORDER`, `CHOICE`, `CONFIRM`, `SCOPE`, `STATUS`, or `OTHER`.
- `gold`: a typed annotation tied to an active record in that frame.
- `provenance`: generator, structural template, and an explicit constructed-output marker.
- `split`: `train` or `dev`.

For a record-backed answer, `gold` is `{ "kind": "record_ref", "record_id": ..., "value": ... }`.
The reference points to the frame record that supplies the answer or selected option; the `value` is an evaluation label.
For an escalation, `gold` is `{ "kind": "ESCALATE", "record_id": ..., "reason": ..., "missing": ..., "question_kind": ... }`.
`REFUSE` is accepted as a reserved gold kind, but the current conductor reply type has no terminal `REFUSE` result,
so this generator represents protected actions as cited `ESCALATE` rows.
Gold annotations are not runtime answers and are never appended to memory.

## Frame construction and coverage

The canonical human-owned frame at `docs/frames/vera_project_frame.md` supplies the policy vocabulary, escalation
reason, and protected-action reason. The generator makes independent minimal cases from those typed shapes and writes
them into a fresh in-memory `Memory` using `kind: constructed` provenance. Values created for these cases are synthetic;
they do not claim new human decisions. The conductor sees only the records belonging to the row's own frame.

Each frame has 11 questions. Rows exercise all six conductor question kinds, including a current status answer,
a completion claim that needs human judgment, a choice with an alias, an injected instruction, an unmapped option,
extra out-of-frame words, and a protected publishing action. Option order varies by frame and is reversed for the
injected-instruction case. A fixed fake asker returns JSON `null`; no model or network is used.

The split is deterministic: frame indexes divisible by five go to dev, and all other frame indexes go to train.
All questions from a frame stay in the same split. The final frame may be partial when `N` is not a multiple of 11.
The script asserts disjoint frame ids, row count, gold record membership, question-kind classification, and the
conductor outcome against the constructed gold before it writes the output files.

## Surface structure source

When `VERA_CORPUS_ROOT` resolves inside this worktree, the generator looks only for `general_qa` JSONL paths and
uses rows whose `split` is exactly `train` and whose `q_variants` has three strings. It extracts only structural
features—language, interrogative shape, register, and ending—and uses those features to select its own templates.
It never copies a corpus sentence or a phrase from a variant into an output question. Paths or files marked
`round5-dev`, `sealed`, `heldout`, `Verantyx-Vera-alpha`, or `fixtures.jsonl` are excluded.

The build environment for the recorded runs pointed `VERA_CORPUS_ROOT` at `/tmp/vera-empty-materials`, outside the
worktree. That path was not read. No accessible in-worktree `general_qa` train variants were available, so the run
reported zero mined variant groups and used the built-in structural fallback. The miner is present for a permitted
in-worktree train corpus; this report does not claim corpus-derived patterns were observed in this run.

## Conductor run report

Run with `--n 10010` to obtain 2,002 dev rows, then score the first 2,000 with the deterministic fake asker:

- Generated rows: 10,010 total; 8,008 train and 2,002 dev across disjoint frame ids.
- Dev sample: 2,000 questions; conductor `ANSWER` replies: 1,273; `ESCALATE` replies: 727; `WRONG`: 0.
- `WRONG` means the reply kind, answer value, or cited primary record did not match the row's gold annotation.
- The protected-action gold keeps the human frame's approval reason; correctness checks the cited escalation record,
  since the current conductor reports its authority-boundary escalation reason in different wording.

The required 400-row run produced 323 train rows and 77 dev rows; the full dev split had 49 answers, 28 escalations,
and 0 wrong. Both reports ended with `DEMO OK` after the script's assertions passed.
