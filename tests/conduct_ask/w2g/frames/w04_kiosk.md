# Museum visitor kiosk (English, chain, forbidden action and write allowlist)
[goal]
project: GalleryKiosk
statement: A touch kiosk lets visitors browse the exhibits and listen to a short audio note for each one

[philosophy_invariants]
I1: The kiosk never stores anything that identifies a visitor

[completion_criteria]
C1: Every exhibit page loads without an error | {"kind":"command_exit","command":["make","check-pages"],"expected_exit":0}
C2: The captions are easy to read from a standing position | human-judged

[phases]
P1: Choose the exhibit list
P2: Build the touch screen
P3: Add the audio playback
P4: Run the soft opening

[phase_order]
P1 -> P2: The screen shows the exhibits from the list
P2 -> P3: Audio plays from a button on the screen
P3 -> P4: The soft opening needs the audio to work

[decisions]
D1: input method => touch screen
D2: SCOPE | gift shop sales | out of scope
D3: SCOPE | accessibility captions | in scope
D4: CONFIRM | testing with real visitors | permitted
D5: CHOICE | audio format | MP3
D6: CHOICE | idle screen | slideshow

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
delete the visitor survey data => Deleting survey data needs the curator's approval => human

[write_allowlist]
W1: kiosk
W2: docs/gallery

[forbidden_actions]
record visitors' faces with the camera => Faces are never recorded
