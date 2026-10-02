# Community compost tracker (English, chain, forbidden action and write allowlist)
[goal]
project: CompostLog
statement: Volunteers log each compost drop-off and the neighbourhood sees weekly totals

[philosophy_invariants]
I1: Household names are never shown on the public totals page

[completion_criteria]
C1: The weekly report matches the sum of the logged entries | {"kind":"command_exit","command":["make","check-totals"],"expected_exit":0}
C2: A volunteer can log a drop-off in under a minute | human-judged

[phases]
P1: Define the bin categories
P2: Build the drop-off log form
P3: Add the weekly weight report
P4: Write the volunteer handbook page
P5: Run a trial week with volunteers

[phase_order]
P1 -> P2: The form lists the bin categories
P2 -> P3: The report totals what the form records
P3 -> P4: The handbook shows how to read the report
P4 -> P5: The trial starts once the handbook page exists

[decisions]
D1: report day => Sunday
D2: SCOPE | worm bin sales | out of scope
D3: SCOPE | neighbourhood leaderboard | in scope
D4: CONFIRM | emailing households a reminder | permitted
D5: CHOICE | weight unit | kilograms
D6: CHOICE | log entry style | tap-to-select form

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
send the totals to the city council => Official submissions need the coordinator's approval => human

[write_allowlist]
W1: app
W2: tests

[forbidden_actions]
edit logged entries => Entries stay as logged
