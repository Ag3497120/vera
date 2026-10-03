# Choir rehearsal planner (English, branch and merge, no write allowlist)
[goal]
project: ChoirPlanner
statement: Singers confirm attendance and the director sees who comes to each rehearsal

[philosophy_invariants]
I1: A singer's phone number is shown only to the director

[completion_criteria]
C1: Every confirmed singer appears on the attendance sheet | {"kind":"command_exit","command":["make","check-sheet"],"expected_exit":0}
C2: A new singer can confirm without help | human-judged
C3: The confirmation form layout fits a phone screen | human-judged

[phases]
P1: Define the attendance fields
P2: Build the confirmation form
P3: Write the reminder sender
P4: Implement the attendance sheet
P5: Try the planner at a rehearsal

[phase_order]
P1 -> P2: The form collects the defined fields
P2 -> P3: Reminders go to confirmed singers
P2 -> P4: The sheet lists confirmed singers
P3 -> P5: The trial needs reminders to work
P4 -> P5: The trial needs the sheet

[decisions]
D1: reminder lead time => two days
D2: SCOPE | carpool matching | out of scope
D3: SCOPE | sheet music downloads | in scope
D4: CONFIRM | sending a test reminder | permitted
D5: CHOICE | confirmation channel | web form
D6: CHOICE | sheet layout | by voice part
D7: SCOPE | password reset screen | out of scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
share the attendance sheet externally => External sharing needs approval => human

[forbidden_actions]
show a singer's phone number to other singers => Numbers are for the director only
