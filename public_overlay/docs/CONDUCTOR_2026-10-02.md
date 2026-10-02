# Conductor prototype v0 — 2026-10-02

**Status: prototype only. Not adopted. Not a sealed result.** This work stays in the isolated work copy.

## What is built

`verantyx/conductor.py` wraps the existing append-only `Memory`. It installs a fixed set of memory kinds through one closed extension function; it does not change `memory_frame.py`. `Memory.write` still checks complete slots and round-trips every canonical record through the semantic reader. Runtime retrieval uses active, fresh records and respects supersession.

The record shapes are:

| Kind | Stored shape |
|---|---|
| `GOAL` | project → acceptance item (`完成条件`) |
| `ACCEPTANCE` | item → witness label, with witness kind, target, task, and independence metadata |
| `ORDER` | phase A → phase B, with an active `DECISION` or `INVARIANT` record id as its reason |
| `POLICY` | question kind + condition → allowed answer, with an active `DECISION` or `INVARIANT` citation |
| `ESCALATE` | condition → human, with reason and missing record kind |

Two small supporting kinds keep provenance typed: `ALIAS` stores a two-ask term mapping as testimony, and `VERIFICATION` stores an independent agent or human review result as testimony. Neither is treated as a fact. All seven extension kinds are registered by `install_conductor_kinds()`.

The closed question set is `ORDER`, `CHOICE`, `CONFIRM`, `SCOPE`, `STATUS`, and `OTHER`. Classification uses bounded structural patterns and the existing `question.is_content_request` gate. Unclassified requests go to `ESCALATE`. The semantic reader is used at Memory write time to reject records it cannot ask; it does not supply a policy answer. No natural-language guess is turned into an answer.

For `CHOICE`, each option is matched by exact/normalized frame term. An out-of-vocabulary option is passed to the injected `Memory.resolver`; only two agreeing closed-choice asks can create an alias, and the answer cites the alias testimony record. Null, invalid, or disagreeing asks escalate with `missing='vocabulary'`.

For `ORDER`, one ready successor must be supported by active ordering and task records; missing task state, conflicting active states, or ties abstain. For `STATUS`, every active goal item is checked first. File hash, text-in-file, and git-commit checks use the existing witness checker; command exit checks use only an injected runner. An item marked independent returns an `ASK_VERIFIER` specification after its deterministic witness passes. The verifier must be another agent, and this prototype returns the specification without starting one. Human-judged items need typed human testimony.

Protected actions always escalate to a human, even when a matching `POLICY` says yes. The fixed boundary covers outward publishing, deletion, spending, credential entry, and sealed/held-out data. Policy citations also become unusable when their authority record is stale, superseded, or conflicts with another active record.

## Simulator

`tools/conductor_sim.py` builds a fictional frame with 26 initial typed records and 103 scripted questions across all six kinds. There are four independent surface forms per kind. The gold answer and required citation ids are read from the frame records that define each case. Five choice cases use out-of-vocabulary labels generated from the cited choice policy. The fake asker never calls a model or network; at 80% and 50%, its incorrect picks are deliberately arranged to disagree with the other ask.

| Fake asker accuracy | Asked | Answered correctly | Escalated correctly | Wrong answers | Escalated though answerable | Alias testimony records |
|---:|---:|---:|---:|---:|---:|---:|
| 100% | 103 | 85 | 18 | **0** | 0 | 5 |
| 80% | 103 | 83 | 18 | **0** | 2 | 3 |
| 50% | 103 | 80 | 18 | **0** | 5 | 0 |

Per-kind results (`answered / escalated correctly / wrong / escalated though answerable`):

| Kind | 100% | 80% | 50% |
|---|---:|---:|---:|
| `ORDER` (16) | 16 / 0 / 0 / 0 | 16 / 0 / 0 / 0 | 16 / 0 / 0 / 0 |
| `CHOICE` (22) | 21 / 1 / 0 / 0 | 19 / 1 / 0 / 2 | 16 / 1 / 0 / 5 |
| `CONFIRM` (16) | 16 / 0 / 0 / 0 | 16 / 0 / 0 / 0 | 16 / 0 / 0 / 0 |
| `SCOPE` (16) | 16 / 0 / 0 / 0 | 16 / 0 / 0 / 0 | 16 / 0 / 0 / 0 |
| `STATUS` (16) | 16 / 0 / 0 / 0 | 16 / 0 / 0 / 0 | 16 / 0 / 0 / 0 |
| `OTHER` (17) | 0 / 17 / 0 / 0 | 0 / 17 / 0 / 0 | 0 / 17 / 0 / 0 |

The 17 `OTHER` escalations include 12 uncovered questions and five protected-action questions. The extra `CHOICE` escalation is the injected delete-branch instruction. The 80% and 50% recall losses are the OOV cases whose two asks disagreed; none became an alias. The simulator prints each correct answer with its cited record ids and lists each correct escalation, so those results remain inspectable.

## Tests and retained failures

`tests/test_conductor.py` contains more than 40 tests covering all kinds and paraphrases, authority boundaries, injected instructions, ties, supersession, freshness, witnesses, aliases, determinism, append-only writes, and no-network behavior. It also checks that no simulator surface-form string longer than six characters appears literally in `conductor.py`.

The retained limitation is recall loss under an inaccurate closed-choice asker: two disagreeing asks correctly produce an escalation, even when the scripted gold mapping is known. Open-ended or uncovered questions also abstain. No wrong answer was observed in the scripted 100%, 80%, or 50% runs; this is a small constructed prototype check, not evidence of general language coverage or production safety.

## Not built

- Real agent adapters.
- Starting or running verifier agents.
- Long-horizon resumption and recovery after process/context loss.
- A general language understanding or open-ended answer path.

This prototype was not adopted, was not run against sealed or held-out data, and does not change the project’s adoption or evaluation status.
