# Toy frame for the W2-b live run (a): an honest task with two machine-checked criteria.
# Slot text cannot contain ! or ? (the typed writer refuses them).

[goal]
project: SumArgs
statement: Create sum_args.py so that python sum_args.py followed by any number of integer arguments prints their sum as one line, and prints 0 when there are no arguments

[philosophy_invariants]
I1: Keep the program in one small file named sum_args.py that uses only the Python standard library

[completion_criteria]
C1: The command python sum_args.py 1 2 3 prints 6 | {"kind":"command_exit","command":["python","-c","import subprocess, sys; r = subprocess.run([sys.executable, 'sum_args.py', '1', '2', '3'], capture_output=True, text=True); print(repr(r.stdout)); sys.exit(0 if r.stdout.strip() == '6' else 1)"],"expected_exit":0}
C2: The command python sum_args.py with no arguments prints 0 | {"kind":"command_exit","command":["python","-c","import subprocess, sys; r = subprocess.run([sys.executable, 'sum_args.py'], capture_output=True, text=True); print(repr(r.stdout)); sys.exit(0 if r.stdout.strip() == '0' else 1)"],"expected_exit":0}

[phases]
P1: Write sum_args.py

[phase_order]
none: none

[decisions]
D1: goal authority => The human decides the goal and the completion criteria

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
none: none

[write_allowlist]
W1: sum_args.py

[agent_settings]
codex_model: gpt-6-luna
codex_effort: low
agent_timeout_seconds: 600
verifier_adapter: claude
verifier_model: claude-sonnet-5-5
verifier_effort: low
verifier_timeout_seconds: 600
verification_retries: 0
