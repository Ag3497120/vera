# Memory revalidation injection review

## Findings

The required acceptance run completed with **13 passed**. No defect was
reproduced, so there are no finding rows.

| id | severity (`wrong-ANSWER`, `ungrounded`, `crash`, `hang`, `robustness`) | minimal repro | expected | observed |
|---|---|---|---|---|

## What held

- Testimony remained answerable with `UNVERIFIABLE` status.
- A mismatched file hash or absent text witness marked the record `STALE`; even
  `require_fresh=False` did not restore it to an answer.
- Instruction text in document contents, witness metadata, record authors, and
  questions did not add answers or widen the returned evidence. Quoted, nested,
  and full-width Unicode instruction phrasing was included.
- A git witness was sent through the fixed `git cat-file -e` argument vector;
  metacharacters in its repo and commit fields were not interpreted as shell
  syntax.
- A confusable witness kind stayed `UNVERIFIABLE` rather than becoming a
  recognized witness type.

## What was not covered

- Escalation and agent-message handling are outside `RevalidatingMemory`'s API.
- File reads were stubbed in tests; filesystem permissions, symlinks, and actual
  path handling were not exercised.
- The git runner was a stub; no real repository or commit lookup was used.
- Cache expiry under concurrent reads and malformed on-disk memory logs were
  not covered.
