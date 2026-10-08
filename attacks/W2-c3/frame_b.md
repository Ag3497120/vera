# Sensor import
[goal]
project: Sensor import
statement: Import observations and mark how missing values are treated

[philosophy_invariants]
I1: Missing observations remain visible in the audit trail
I2: The report archive stays separate from the ordinary report

[completion_criteria]
C1: The import report is readable | human-judged

[phases]
P1: Parse observations
P2: Write the import report

[phase_order]
P1 -> P2: The report uses parsed observations

[decisions]
D1: SCOPE | 欠測の扱い | out of scope
D2: CHOICE | report | CSV

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
none: none

[forbidden_actions]
none: none
