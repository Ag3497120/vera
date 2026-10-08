# Retry library (English, forbidden action and precedence, parallel roots)
[goal]
project: RetryKit
statement: The library retries failed network calls with backoff and never repeats a call that is unsafe to repeat

[philosophy_invariants]
I1: A non-idempotent call is never retried automatically
I2: A retry delay is never shorter than the previous delay

[completion_criteria]
C1: The unit tests pass | {"kind":"command_exit","command":["python","-m","pytest"],"expected_exit":0}
C2: The backoff curve matches the written table | human-judged
C3: The stress run will retry a non-idempotent call to measure the delay | human-judged

[phases]
P1: Write the backoff policy
P2: Implement the retry loop
P3: Add the idempotency check
P4: Document the usage

[phase_order]
P1 -> P2: The loop applies the policy
P2 -> P4: The documentation describes the loop
P3 -> P4: The documentation describes the check

[decisions]
D1: backoff curve => exponential
D2: attempt limit => 5
D3: SCOPE | circuit breaker | out of scope
D4: CONFIRM | adding a runtime dependency | not permitted
D5: CHOICE | jitter | full jitter
D6: CHOICE | clock source | monotonic clock

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
publish a release => Public release needs approval => human

[forbidden_actions]
retry a non-idempotent call => A duplicated side effect cannot be undone

[conflict_precedence]
R1: forbidden_actions > completion_criteria: A passing run never justifies a forbidden operation
R2: philosophy_invariants > protected_actions: An approval does not suspend an invariant
