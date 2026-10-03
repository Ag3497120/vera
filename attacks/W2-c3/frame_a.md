# Incident review
[goal]
project: Incident review
statement: Prepare a report and keep the decision trace

[philosophy_invariants]
I1: The incident data stays internal

[completion_criteria]
C1: The summary is readable | human-judged

[phases]
P1: Prepare the report
P2: Review the report

[phase_order]
P1 -> P2: Review starts after preparation

[decisions]
D1: CHOICE | report | CSV
D2: CONFIRM | publishing incident summaries | permitted

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
none: none

[forbidden_actions]
none: none
