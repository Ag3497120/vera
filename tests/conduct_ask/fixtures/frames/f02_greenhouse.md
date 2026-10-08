# Greenhouse watering controller (English, branch and merge, protected only)
[goal]
project: GreenhouseWatering
statement: The controller waters each bed from soil moisture readings and never floods a bed

[philosophy_invariants]
I1: A bed is never watered twice within the cooldown window
I2: Sensor faults must stop the pump instead of guessing a reading

[completion_criteria]
C1: The moisture simulation keeps every bed below the flood level | {"kind":"command_exit","command":["make","sim-moisture"],"expected_exit":0}
C2: The operator panel is readable on a phone | human-judged

[phases]
P1: Define the sensor message format
P2: Write the pump driver
P3: Build the moisture reader
P4: Implement the watering scheduler
P5: Add the operator panel

[phase_order]
P1 -> P2: The driver reports status in the message format
P1 -> P3: The reader decodes the message format
P2 -> P4: The scheduler commands the pump through the driver
P3 -> P4: The scheduler consumes the readings
P4 -> P5: The panel shows what the scheduler decided

[decisions]
D1: scheduler tick => 30 seconds
D2: SCOPE | rain forecast integration | out of scope
D3: SCOPE | manual override button | in scope
D4: CONFIRM | running the pump for a dry test | permitted
D5: CHOICE | message encoding | JSON
D6: CHOICE | moisture unit | percent

[vocabulary_aliases]
none: none

[escalation_conditions]
E1: change to the cooldown window => The cooldown protects the plants => human => ANY

[protected_actions]
order replacement hardware => Spending needs approval => human
