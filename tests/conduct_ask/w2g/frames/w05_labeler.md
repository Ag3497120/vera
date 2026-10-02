# Warehouse pallet labeler (English, diamond dependency, scope contradiction)
[goal]
project: PalletLabeler
statement: The service prints a barcode label for every pallet and the handheld scanner checks the label against the order

[philosophy_invariants]
I1: A serial number is printed on one label only

[completion_criteria]
C1: The label layout test passes for every sample order | {"kind":"command_exit","command":["make","test-labels"],"expected_exit":0}
C2: The operator guide is clear to a new employee | human-judged

[phases]
P1: Define the label layout
P2: Build the printing service
P3: Build the scan check
P4: Write the operator guide

[phase_order]
P1 -> P2: The service prints the layout
P1 -> P3: The check reads the layout
P2 -> P4: The guide explains the printing steps
P3 -> P4: The guide explains the checking steps

[decisions]
D1: barcode type => Code 128
D2: SCOPE | returns handling | out of scope
D3: SCOPE | damaged pallet photos | in scope
D4: SCOPE | night shift support | in scope
D5: SCOPE | night shift support | out of scope
D6: CONFIRM | printing a test label on the production printer | not permitted
D7: CHOICE | printer driver | the vendor driver

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
ship a pallet to a customer => Shipping needs the shift manager's approval => human

[forbidden_actions]
reprint a label with an existing serial number => Serial numbers must stay unique
