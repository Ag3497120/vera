# Example conduct frame with an agent table: the implementer is a codex agent, the verifier and the reviewer are claude agents.
# Grammar: see ../vera_project_frame.md and ../../AGENT_ROUTING.md. This frame uses [agents] [routing] and task_kind.
# Run: python -m verantyx.cli conduct --frame docs/frames/examples/routing_two_lineages.md --repo <git worktree> --dry-run
# There is no --adapter: the router chooses the agents from the records below and writes each decision to the ledger.
# What the human wrote about the agents (model, lineage, roles, kinds) is testimony. Nothing here is a measurement.

[goal]
project: NumberTally
statement: Create tally.py so that python tally.py followed by any number of integer arguments prints their sum as one line and prints 0 when there are no arguments

[philosophy_invariants]
I1: Keep the program in one small file named tally.py that uses only the Python standard library

[completion_criteria]
C1: The command python tally.py 1 2 3 prints 6 | {"kind":"command_exit","command":["python","-c","import subprocess, sys; r = subprocess.run([sys.executable, 'tally.py', '1', '2', '3'], capture_output=True, text=True); print(repr(r.stdout)); sys.exit(0 if r.stdout.strip() == '6' else 1)"],"expected_exit":0}
C2: The command python tally.py with no arguments prints 0 | {"kind":"command_exit","command":["python","-c","import subprocess, sys; r = subprocess.run([sys.executable, 'tally.py'], capture_output=True, text=True); print(repr(r.stdout)); sys.exit(0 if r.stdout.strip() == '0' else 1)"],"expected_exit":0}

[phases]
P1: Write tally.py

[phase_order]
none: none

[decisions]
D1: goal authority => The human decides the goal and the completion criteria

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
publish the tool => Human approval is required before the tool is published => human

[write_allowlist]
W1: tally.py

[forbidden_actions]
rewrite repository history => The repository history is a record and no agent may rewrite it

[conflict_precedence]
R1: forbidden_actions > protected_actions: A forbidden operation stays forbidden even when approval is offered
R2: philosophy_invariants > completion_criteria: Passing a check never justifies breaking a stated invariant

[agent_settings]
task_kind: feature
agent_timeout_seconds: 600
verifier_timeout_seconds: 600
verification_retries: 0

[agents]
CodexImpl: adapter=codex model=gpt-6-luna effort=low roles=implement kinds=small_fix,feature,large_refactor,test_authoring lineage=openai concurrency=1
ClaudeVerify: adapter=claude model=claude-sonnet-5-5 effort=low roles=verify kinds=verification lineage=anthropic concurrency=1
ClaudeReview: adapter=claude model=claude-opus-5-5 effort=low roles=review,answer kinds=review,closed_choice lineage=anthropic concurrency=1
CodexBulk: adapter=codex model=gpt-6-luna effort=low roles=generate kinds=bulk_generation lineage=openai concurrency=2

[routing]
IMPL_SMALL_FIX: role=implement & kind=small_fix => CodexImpl: small edits go to the codex implementer
IMPL_FEATURE: role=implement & kind=feature => CodexImpl: a feature is written by the codex implementer
IMPL_TESTS: role=implement & kind=test_authoring => CodexImpl: tests are written by the codex implementer
VERIFY_ANY: role=verify & kind=verification => ClaudeVerify: verification is done by a lineage other than the implementer's
REVIEW_ANY: role=review & kind=review => ClaudeReview: review is done by the claude reviewer
BULK_GENERATION: role=generate & kind=bulk_generation => CodexBulk: bulk generation goes to the cheap codex agent
ASK_CLOSED: role=answer & kind=closed_choice => ClaudeReview: closed choices are put to the claude reviewer
DEFAULT: role=implement => CodexImpl: the codex implementer is the default implementer
DEFAULT: role=verify => ClaudeVerify: the claude verifier is the default verifier
DEFAULT: role=review => ClaudeReview: the claude reviewer is the default reviewer
DEFAULT: role=generate => CodexBulk: the codex generator is the default generator
DEFAULT: role=answer => ClaudeReview: the claude reviewer is the default asker
