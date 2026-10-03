# Toy lending library (English, branch and merge, no write allowlist; W2-c2 round 2 supplement)
[goal]
project: ToyShelf
statement: The shelf tracks which toys the neighbourhood lending library owns and who has borrowed them

[philosophy_invariants]
I1: A toy that is out on loan is never listed as available

[completion_criteria]
C1: Every borrowed toy appears on exactly one loan card | {"kind":"command_exit","command":["make","check-cards"],"expected_exit":0}
C2: A volunteer can find a toy in under a minute | human-judged

[phases]
P1: Define the toy fields
P2: Build the loan card printer
P3: Write the reminder mailer
P4: Implement the shelf overview
P5: Try the shelf at an open afternoon

[phase_order]
P1 -> P2: The printer prints the toy fields
P1 -> P3: The mailer quotes the toy fields
P2 -> P4: The overview counts printed cards
P3 -> P4: The overview shows sent reminders
P4 -> P5: The open afternoon needs the overview

[decisions]
D1: loan period => two weeks
D2: SCOPE | repair workshop booking | out of scope
D3: SCOPE | borrower sign-up desk | in scope
D4: CONFIRM | lending a toy to a guest | permitted
D5: CHOICE | card colour | yellow
D6: CHOICE | overview language | English
D7: SCOPE | parent newsletter | out of scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
buy replacement toys => Spending needs the treasurer's approval => human

[forbidden_actions]
list a child's home address on a loan card => Addresses stay with the coordinator
