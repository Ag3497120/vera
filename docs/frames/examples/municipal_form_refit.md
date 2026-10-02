# Example conduct frame: refit an online residence-change application form of a city office.

[goal]
project: ResidenceForm
statement: The online residence change form accepts a valid application and tells the applicant which document is missing

[philosophy_invariants]
I1: The form never stores an identification number outside the application record
I2: An incomplete application is returned with the missing document named
I3: The form text is reviewed by a clerk before release

[completion_criteria]
C1: The form validation tests pass | {"kind":"command_exit","command":["python","-m","pytest","tests/form","-q"],"expected_exit":0}
C2: The accessibility lint exits cleanly | {"kind":"command_exit","command":["node","tools/a11y-lint.js"],"expected_exit":0}
C3: A clerk approves the wording | human-judged

[phases]
P1: List the required documents per application type
P2: Implement the validation rules
P3: Run the lint and the tests

[phase_order]
P1 -> P2: Validation rules need the document list
P2 -> P3: Checks run on the implemented rules

[decisions]
D1: missing document message => The message names the document and the office window
D2: SCOPE | identification number storage | out of scope
D3: CONFIRM | test applications | permitted

[vocabulary_aliases]
転入届 => residence change application
添付書類 => required document

[escalation_conditions]
E1: legal wording question => A clerk must decide any statutory wording => human => ANY

[protected_actions]
publish => Human approval is required before the form goes live => human
send email to applicants => Human approval is required before any applicant is contacted => human

[write_allowlist]
W1: web/form
W2: tests/form
W3: tools/a11y-lint.js

[forbidden_actions]
store identification numbers => The privacy ordinance forbids storing them outside the application record
send test data to the live mail server => Test data must never reach real applicants

[conflict_precedence]
R1: forbidden_actions > protected_actions: Approval cannot unlock a forbidden operation
R2: forbidden_actions > completion_criteria: A passing check never justifies a forbidden operation
