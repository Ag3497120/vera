# Ledger service
[goal]
project: Ledger service
statement: Keep the books and answer audits

[philosophy_invariants]
I1: Audit data stays internal

[completion_criteria]
C1: The totals are readable | human-judged

[phases]
P1: Collect the entries
P2: Check the totals

[phase_order]
P1 -> P2: Check starts after collection

[decisions]
D1: CHOICE | invoice | PDF
D2: CHOICE | notice language | Japanese
D3: SCOPE | refund handling | in scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
none: none

[forbidden_actions]
none: none
