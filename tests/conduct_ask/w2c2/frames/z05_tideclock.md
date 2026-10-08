# Tide clock display (English, protected and forbidden actions, write allowlist)
[goal]
project: TideClock
statement: A harbour display shows the next high and low tide from a published table

[philosophy_invariants]
I1: The display never shows a time older than the table
I2: The table importer log is kept for a month

[completion_criteria]
C1: The shown times equal the table for the whole month | {"kind":"command_exit","command":["make","check-times"],"expected_exit":0}
C2: The release notes are readable by the harbour office | human-judged
C3: The display screen brightness follows the harbour lights | human-judged

[phases]
P1: Define the table format
P2: Write the table importer
P3: Build the display screen
P4: Write the alarm handler
P5: Install the display at the harbour

[phase_order]
P1 -> P2: The importer reads the table format
P2 -> P3: The screen shows the imported times
P2 -> P4: The alarm uses the imported times
P3 -> P5: The installation needs a working screen
P4 -> P5: The installation needs the alarm

[decisions]
D1: refresh period => 5 minutes
D2: SCOPE | tide height graph | out of scope
D3: SCOPE | moon phase icon | in scope
D4: CONFIRM | running the importer on a sample table | permitted
D5: CHOICE | time format | 24-hour
D6: CHOICE | screen theme | dark
D7: SCOPE | release notes page | out of scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
publish a release => Public release needs approval => human

[write_allowlist]
W1: src
W2: docs

[forbidden_actions]
change a published table => Tables are owned by the port authority
