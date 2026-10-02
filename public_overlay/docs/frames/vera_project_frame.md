# Vera human-owned project frame
# Each field occupies one line. List sections are closed; use `none: none` only for an explicitly empty list.
# Goal has exactly `project` and `statement`; other sections use the entry grammar named below.
# Invariants and phases use `ID: text`; phase order uses `BEFORE -> AFTER: reason` and must be acyclic.
# Criteria use `ID: text | human-judged` or a JSON witness object with an exact supported schema.
# Decisions use `ID: subject => choice` or `ID: KIND | condition | answer` with KIND CHOICE, CONFIRM, or SCOPE.
# Vocabulary uses `alias => canonical`; escalation uses `ID: condition => reason => missing => scope`.
# Escalation scope is `ANY` or a conductor question kind; protected actions use `action => reason => missing`.

[goal]
project: Vera
statement: Vera is a general chatbot that understands requests and answers or generates from structure while retaining the human-decided goal and completion frame

[philosophy_invariants]
I1: Runtime uses no LLM or learned model to produce an answer sentence fact or decision
I2: Base on stereo cross and fall back to case-frame predicate-argument structure
I3: Stack stages without pooling votes and abstain on ties
I4: Refusals are typed and cite evidence and unknown is not negation
I5: Constructed outputs are typed with provenance and never become answers testimony or evidence
I6: Preserve source clauses semantic roles scope conditions exceptions quantities and negation
I7: Do not narrow the human-decided goal to pass an intermediate gate

[completion_criteria]
C1: Runtime does not use an LLM or learned model to produce an answer sentence fact or decision | human-judged
C2: General QA and dialogue handle unseen wording and relations instead of relying only on prior question matches | human-judged
C3: Code generation preserves requested inputs outputs conditions side effects and boundary cases | human-judged
C4: Complex document QA preserves facts conditions exceptions comparisons counts negation and citation scope | human-judged
C5: Text generation composes from structure and distinguishes supported facts from introduced creative content | human-judged

[phases]
P1: Write and review the human-owned design and completion frame
P2: Compile the frame into typed records with source witnesses
P3: Answer questions from cited records through the deterministic conductor
P4: Review observed answers and revise the frame only by a human decision

[phase_order]
P1 -> P2: Compilation must preserve the human-decided design and completion shape
P2 -> P3: The conductor needs typed records with witnesses before it can answer from the frame
P3 -> P4: Review follows observable answers and their citations

[decisions]
D1: goal authority => The human decides the design philosophy completion shape and revisions
D2: runtime answer path => Deterministic structure produces answers and generated content
D3: SCOPE | general QA and dialogue | in scope
D4: SCOPE | code generation | in scope
D5: SCOPE | complex document QA | in scope
D6: CONFIRM | local demo | permitted
D7: CHOICE | 基本構造 | stereo cross

[vocabulary_aliases]
立体十字 => stereo cross
述語項構造への後退 => case-frame fallback
case-frame predicate argument structure => case-frame fallback

[escalation_conditions]
E1: unsupported request => No supported structure is present to ground an answer => typed evidence => OTHER
E2: conflicting evidence => Conflicting support must be reviewed without pooling votes => human => ANY
E3: completion claim => Completion criteria require human judgment => human => STATUS

[protected_actions]
publish => Human approval is required before public release => human
delete => Human approval is required before removing records or files => human
spend money => Human approval is required before spending => human
enter credentials => Credentials must remain under direct human control => human
access evaluation-only material => Human approval is required before accessing restricted evaluation material => human
