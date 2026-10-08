# Hive inspection log (English, branch and merge, write allowlist)
[goal]
project: HiveLog
statement: Beekeepers note what they see at each hive visit and are reminded when an inspection is due

[philosophy_invariants]
I1: A hive's location is shown only to its owner

[completion_criteria]
C1: A saved visit note shows the date it was made | {"kind":"command_exit","command":["make","check-notes"],"expected_exit":0}
C2: A beekeeper wearing gloves can use the entry screen | human-judged

[phases]
P1: Set up the hive register
P2: Build the visit note screen
P3: Add the due-date reminders
P4: Build the season summary
P5: Try it with the club's members

[phase_order]
P1 -> P2: Notes are attached to a registered hive
P2 -> P3: Reminders are worked out from the saved notes
P2 -> P4: The summary reads the saved notes
P3 -> P5: Members try the reminders
P4 -> P5: Members also try the summary

[decisions]
D1: reminder interval => 14 days
D2: SCOPE | honey sales records | out of scope
D3: SCOPE | weather notes | in scope
D4: CONFIRM | sharing notes with other clubs | not permitted
D5: CHOICE | note entry | voice input
D6: CHOICE | date format | day-month-year

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
delete a hive from the register => Removing a hive needs the club chair's approval => human

[write_allowlist]
W1: app
W2: docs

[forbidden_actions]
show a hive's location on the club page => Locations stay private
