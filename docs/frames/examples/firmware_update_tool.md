# Example conduct frame: firmware update tool of an embedded sensor.
# The explicit empty list `none: none` is used where the frame has nothing to say.

[goal]
project: SensorUpdater
statement: The update tool flashes a signed firmware image and restores the previous image when the new one fails its self test

[philosophy_invariants]
I1: An unsigned image is never flashed
I2: A failed self test always ends with the previous image restored

[completion_criteria]
C1: The rollback simulation passes | {"kind":"command_exit","command":["make","sim-rollback"],"expected_exit":0}
C2: The signature check rejects the tampered fixture | {"kind":"command_exit","command":["python","tool/verify_sig.py","fixtures/tampered.bin"],"expected_exit":1}

[phases]
P1: Add the signature check
P2: Add the rollback path

[phase_order]
P1 -> P2: Rollback is only meaningful for verified images

[decisions]
D1: flash order => The signature is verified before the first write
D2: SCOPE | production devices | out of scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
flash production device => Human approval is required before a real device is flashed => human

[write_allowlist]
W1: tool
W2: fixtures
W3: Makefile

[forbidden_actions]
disable signature check => Shipping without the check would break the first invariant

[conflict_precedence]
R1: forbidden_actions > completion_criteria: A passing check never justifies a forbidden operation
R2: philosophy_invariants > protected_actions: An approval does not suspend an invariant

[agent_settings]
codex_model: gpt-6-luna
codex_effort: medium
max_concurrency: 1
