# Marathon drink stations (English, diamond dependency, scope contradiction, write allowlist)
[goal]
project: WaterPoints
statement: Race volunteers see which drink stations need refilling and the organisers can plan supplies

[philosophy_invariants]
I1: Runner names are never shown on a station screen

[completion_criteria]
C1: Every station screen refreshes within the agreed interval | {"kind":"command_exit","command":["make","check-refresh"],"expected_exit":0}
C2: A volunteer can report a low supply in one tap | human-judged

[phases]
P1: Draw the course map with the stations
P2: Build the station status screen
P3: Add the supply forecast
P4: Build the organiser dashboard
P5: Run a rehearsal at the park

[phase_order]
P1 -> P2: The status screen lists the mapped stations
P1 -> P3: The forecast works per mapped station
P2 -> P4: The dashboard shows the station statuses
P3 -> P4: The dashboard shows the forecast too
P4 -> P5: The rehearsal uses the finished dashboard

[decisions]
D1: refresh interval => 2 minutes
D2: SCOPE | medal engraving orders | out of scope
D3: SCOPE | volunteer shift lists | in scope
D4: SCOPE | spectator screens | in scope
D5: SCOPE | spectator screens | out of scope
D6: CONFIRM | texting volunteers outside their shifts | not permitted
D7: CHOICE | low-supply report | one-tap button

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
wipe the recorded supply counts => Clearing the counts needs the race director's approval => human

[write_allowlist]
W1: app
W2: tests

[forbidden_actions]
show runner names on a station screen => Names are not shown at stations
