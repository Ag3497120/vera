# Example conduct frame: refit the search of a library catalog.
# Grammar: see ../vera_project_frame.md. This frame uses every optional conduct section.
# Run: python -m verantyx.cli conduct --frame docs/frames/examples/library_catalog_search.md --repo <git worktree> --adapter fake

[goal]
project: LibraryCatalog
statement: The catalog search returns every holding that matches a title author or ISBN query and never lists a withdrawn item as available

[philosophy_invariants]
I1: Search results come from the holdings table only and never from a cache that can outlive a withdrawal
I2: A query with no match returns an empty result and not an error
I3: The search path never reads patron records

[completion_criteria]
C1: The search test suite passes | {"kind":"command_exit","command":["python","-m","pytest","tests/search","-q"],"expected_exit":0}
C2: The withdrawn item regression check exits cleanly | {"kind":"command_exit","command":["python","tools/check_withdrawn.py"],"expected_exit":0}
C3: Reading room staff confirm the result ordering | human-judged

[phases]
P1: Reproduce the stale withdrawn listing
P2: Rewrite the holdings query
P3: Verify against the regression set

[phase_order]
P1 -> P2: The failing reproduction defines what the rewrite must fix
P2 -> P3: Verification needs the rewritten query

[decisions]
D1: ranking rule => Exact ISBN matches rank above title matches
D2: SCOPE | patron records | out of scope
D3: CONFIRM | local index rebuild | permitted

[vocabulary_aliases]
holdings => holdings table
OPAC => catalog search

[escalation_conditions]
E1: ranking dispute => Staff must decide how ties between editions are ordered => human => ANY

[protected_actions]
publish => Human approval is required before the new search goes live => human
rebuild production index => Human approval is required before the production index is rebuilt => human

[write_allowlist]
W1: src/catalog
W2: tests/search
W3: tools/check_withdrawn.py

[forbidden_actions]
read patron records => Patron privacy law forbids the search service from reading them
drop holdings table => The table is the system of record and is never dropped by an agent

[conflict_precedence]
R1: forbidden_actions > protected_actions: A forbidden operation stays forbidden even when approval is offered
R2: philosophy_invariants > completion_criteria: Passing a check never justifies breaking a stated invariant

[agent_settings]
codex_model: gpt-6-luna
codex_effort: high
claude_model: claude-sonnet-5-5
claude_effort: high
max_concurrency: 2
