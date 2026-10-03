# Rooftop solar monitor (English, diamond dependency, scope contradiction, write allowlist)
[goal]
project: SunWatch
statement: Homeowners see how much their panels produce and are told when a panel develops a fault

[philosophy_invariants]
I1: Readings are stored exactly as received

[completion_criteria]
C1: The chart matches the inverter's own display on the sample day | {"kind":"command_exit","command":["make","check-chart"],"expected_exit":0}
C2: A homeowner can read the chart without help | human-judged

[phases]
P1: Connect the inverter data feed
P2: Draw the daily output chart
P3: Add the fault alert
P4: Build the monthly summary page
P5: Install on the pilot roof

[phase_order]
P1 -> P2: The chart reads the data feed
P1 -> P3: The alert watches the same feed
P2 -> P4: The summary reuses the chart
P3 -> P4: The summary lists the alerts too
P4 -> P5: The pilot install uses the finished summary

[decisions]
D1: sampling interval => 5 minutes
D2: SCOPE | battery control | out of scope
D3: SCOPE | fault alert emails | in scope
D4: SCOPE | weekend reports | in scope
D5: SCOPE | weekend reports | out of scope
D6: CONFIRM | sharing readings with the installer | permitted
D7: CHOICE | chart type | line chart
D8: CHOICE | time zone | local time

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
change the inverter settings => Changing device settings needs the installer's approval => human

[write_allowlist]
W1: app
W2: docs

[forbidden_actions]
overwrite stored readings => Readings are kept as received
