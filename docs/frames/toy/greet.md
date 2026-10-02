# Toy frame for the W2-a live run: one file, two machine-checked criteria.
# Slot text cannot contain ! or ? (the typed writer refuses them), so the expected output is described in words.

[goal]
project: Greeter
statement: Create greet.py so that the command python greet.py Vera prints the line Hello, Vera followed by one exclamation mark

[philosophy_invariants]
I1: Keep the program in one small file named greet.py

[completion_criteria]
C1: The command python greet.py Vera exits with status zero | {"kind":"command_exit","command":["python","greet.py","Vera"],"expected_exit":0}
C2: The command python greet.py Vera prints exactly Hello, Vera followed by one exclamation mark | {"kind":"command_exit","command":["python","-c","import subprocess, sys; r = subprocess.run([sys.executable, 'greet.py', 'Vera'], capture_output=True, text=True); print(repr(r.stdout)); sys.exit(0 if r.stdout in ('Hello, Vera!\\n', 'Hello, Vera!') else 1)"],"expected_exit":0}

[phases]
P1: Write greet.py

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
W1: greet.py

[agent_settings]
codex_model: gpt-6-luna
codex_effort: low
agent_timeout_seconds: 600
# W2-b: the CLI requires a verifier by default; this W2-a toy frame opts out explicitly (recorded as VERIFICATION_SKIPPED).
verifier_adapter: none
