# Star-party sign-up (English, linear with a shortcut edge, write allowlist)
[goal]
project: StarNight
statement: Club members sign up for observing evenings and the host sees who is bringing which telescope

[philosophy_invariants]
I1: Attendees' home addresses are never printed on the sign-up sheet

[completion_criteria]
C1: The sheet total equals the number of confirmed sign-ups | {"kind":"command_exit","command":["make","check-count"],"expected_exit":0}
C2: A first-time visitor can sign up unaided | human-judged

[phases]
P1: List the observing sites
P2: Build the sign-up form
P3: Add the equipment list
P4: Build the host's evening sheet
P5: Hold a trial evening

[phase_order]
P1 -> P2: The form offers the listed sites
P2 -> P3: An equipment list belongs to a sign-up
P2 -> P4: The evening sheet reads the sign-ups
P3 -> P4: The sheet shows the equipment too
P4 -> P5: A trial evening needs the host's sheet

[decisions]
D1: sign-up cut-off => noon on the day
D2: SCOPE | telescope loans | out of scope
D3: SCOPE | car-pool matching | in scope
D4: CONFIRM | emailing guests who are not members | not permitted
D5: CHOICE | form layout | single page
D6: CHOICE | sheet format | printed list

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
erase the sign-up history => Erasing the history needs the club secretary's approval => human

[write_allowlist]
W1: app
W2: docs

[forbidden_actions]
print attendees' home addresses on the sheet => Home addresses stay off the sheet
