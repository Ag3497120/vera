# Kiln firing log (English, branch and merge, no write allowlist)
[goal]
project: KilnLog
statement: The log records each firing from temperature readings and lets the studio compare batches

[philosophy_invariants]
I1: A firing record is never edited after the kiln has cooled
I2: The temperature reader log is never overwritten

[completion_criteria]
C1: The firing report totals match the raw readings | {"kind":"command_exit","command":["make","check-report"],"expected_exit":0}
C2: The firing report archive is readable by the studio manager | human-judged

[phases]
P1: Define the reading format
P2: Build the temperature reader
P3: Write the batch label printer
P4: Implement the firing report
P5: Pilot the log in the studio

[phase_order]
P1 -> P2: The reader decodes the reading format
P1 -> P3: The labels carry the reading format version
P2 -> P4: The report summarises the readings
P3 -> P4: The report lists the printed labels
P4 -> P5: The pilot needs a firing report to compare

[decisions]
D1: report interval => 10 minutes
D2: SCOPE | glaze recipe library | out of scope
D3: SCOPE | kiln door sensor | in scope
D4: CONFIRM | running a test firing | permitted
D5: CHOICE | log file layout | CSV
D6: CHOICE | label size | small
D7: SCOPE | purchase order export | out of scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
order replacement elements => Spending needs approval => human

[forbidden_actions]
edit a finished firing record => Records are final
